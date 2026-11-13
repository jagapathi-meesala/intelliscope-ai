"""
arXiv API client service for IntelliScope AI Data Collector Agent.

Queries the official public arXiv Atom API (https://export.arxiv.org/api/query),
safely parses Atom XML entries, and normalizes records into the unified
IntelliScope research-source schema.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

import httpx

from backend.config import settings
from backend.services.sources.base import (
    DataCollectorRateLimitError,
    DataCollectorResponseError,
    DataCollectorTimeoutError,
    DataCollectorUpstreamError,
    check_source_relevance,
    clean_wiki_markup_and_html,
    normalize_doi,
    normalize_research_item,
    truncate_snippet,
)

logger = logging.getLogger(__name__)

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def _clean_whitespace(text: Optional[str]) -> str:
    """Collapse newlines and repeated whitespace cleanly."""
    if not text:
        return ""
    return " ".join(text.split()).strip()


def _canonicalize_arxiv_url(raw_url: str) -> str:
    """
    Upgrade official arXiv API HTTP IDs/links (`http://arxiv.org/...`)
    to canonical HTTPS while leaving unexpected URLs untouched for verification.
    """
    cleaned = raw_url.strip()
    if re.match(r"^http://(?:export\.)?arxiv\.org/", cleaned, flags=re.IGNORECASE):
        return "https://" + cleaned[len("http://") :]
    return cleaned


async def search_arxiv(
    query: str,
    limit: int = settings.DEFAULT_RESULTS_LIMIT,
    client: Optional[httpx.AsyncClient] = None,
    max_snippet_length: int = settings.DEFAULT_SNIPPET_LENGTH,
    retrieved_at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Asynchronously search arXiv preprints via the Atom API and return normalized items.
    """
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    headers = {
        "User-Agent": settings.DEFAULT_USER_AGENT,
        "Accept": "application/atom+xml, application/xml, text/xml",
    }

    async def _fetch(active_client: httpx.AsyncClient) -> httpx.Response:
        return await active_client.get(
            settings.ARXIV_API_URL,
            params=params,
            headers=headers,
        )

    try:
        if client is not None:
            response = await _fetch(client)
        else:
            async with httpx.AsyncClient(timeout=settings.DEFAULT_REQUEST_TIMEOUT) as local_client:
                response = await _fetch(local_client)
    except httpx.TimeoutException as exc:
        logger.error("arXiv API request timed out for query '%s': %s", query, exc)
        raise DataCollectorTimeoutError("arXiv research service timed out") from exc
    except httpx.RequestError as exc:
        logger.error("Network error connecting to arXiv API for query '%s': %s", query, exc)
        raise DataCollectorUpstreamError(
            f"Network error connecting to arXiv service: {exc}"
        ) from exc

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        msg = "arXiv API rate limit exceeded (HTTP 429)."
        if retry_after:
            msg += f" Retry after {retry_after}s."
        logger.warning(msg)
        raise DataCollectorRateLimitError(msg)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("arXiv API returned HTTP error status %s", exc.response.status_code)
        raise DataCollectorUpstreamError(
            f"arXiv service returned HTTP status {exc.response.status_code}"
        ) from exc

    raw_xml = response.text or ""
    if not raw_xml.strip():
        raise DataCollectorResponseError("arXiv service returned empty XML response")

    # Guard against XML entity expansion / DTD injection before parsing
    if re.search(r"<!(?:DOCTYPE|ENTITY)\b", raw_xml, flags=re.IGNORECASE):
        raise DataCollectorResponseError("Rejected unsafe XML DTD/ENTITY declaration from arXiv response")

    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        logger.error("Failed to parse XML from arXiv API: %s", exc)
        raise DataCollectorResponseError("arXiv service returned malformed XML") from exc

    if not root.tag.endswith("feed"):
        raise DataCollectorResponseError("Unexpected XML root element from arXiv API (expected Atom <feed>)")

    retrieval_ts = retrieved_at or datetime.now(timezone.utc).isoformat()
    entries = root.findall(f"{ATOM_NS}entry")
    if not entries and root.tag == "feed":
        # Support un-namespaced feed fixtures cleanly if encountered
        entries = root.findall("entry")

    def _find_text(el: ET.Element, tag: str) -> str:
        child = el.find(f"{ATOM_NS}{tag}")
        if child is None:
            child = el.find(tag)
        return _clean_whitespace(child.text if child is not None else "")

    results: List[Dict[str, Any]] = []
    for entry in entries[:limit]:
        entry_id = _find_text(entry, "id")
        title = clean_wiki_markup_and_html(_find_text(entry, "title"))
        summary = clean_wiki_markup_and_html(_find_text(entry, "summary"))

        # Check arXiv API inline error sentinel
        if "arxiv.org/api/errors" in entry_id.lower() or title.lower() == "error":
            raise DataCollectorResponseError(
                f"arXiv API returned error entry: {summary or 'Unknown arXiv query error'}"
            )

        if not title:
            continue

        # Find canonical HTML landing link or fall back to Atom <id>
        alt_url = ""
        links = entry.findall(f"{ATOM_NS}link") or entry.findall("link")
        for link in links:
            rel = (link.attrib.get("rel") or "").lower()
            link_type = (link.attrib.get("type") or "").lower()
            href = (link.attrib.get("href") or "").strip()
            if rel == "alternate" and ("html" in link_type or not alt_url) and href:
                alt_url = href
                break

        source_url = _canonicalize_arxiv_url(alt_url or entry_id)
        if not source_url:
            continue

        published_raw = _find_text(entry, "published") or _find_text(entry, "updated")
        pub_date = published_raw[:10] if len(published_raw) >= 10 else (published_raw or None)

        authors: List[str] = []
        author_els = entry.findall(f"{ATOM_NS}author") or entry.findall("author")
        for author_el in author_els:
            name_el = author_el.find(f"{ATOM_NS}name")
            if name_el is None:
                name_el = author_el.find("name")
            name_txt = _clean_whitespace(name_el.text if name_el is not None else "")
            if name_txt:
                authors.append(name_txt)

        doi_el = entry.find(f"{ARXIV_NS}doi")
        raw_doi = _clean_whitespace(doi_el.text if doi_el is not None else "")
        doi = normalize_doi(raw_doi)

        bounded_abstract = truncate_snippet(summary, max_length=max_snippet_length)
        if not bounded_abstract:
            bounded_abstract = f"arXiv academic paper: {title}."

        rel_label, is_weak, rel_reason = check_source_relevance(
            query=query,
            title=title,
            snippet=bounded_abstract,
        )

        results.append(
            normalize_research_item(
                title=title,
                snippet=bounded_abstract,
                source_name="arxiv",
                source_url=source_url,
                publication_date=pub_date,
                doi=doi,
                authors=authors,
                retrieved_at=retrieval_ts,
                source_type="arxiv_paper",
                relevance=rel_label,
                is_weakly_relevant=is_weak,
                relevance_reason=rel_reason,
            )
        )

    return results

