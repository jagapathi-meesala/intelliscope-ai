"""
Crossref REST API client service for IntelliScope AI Data Collector Agent.

Queries the official public Crossref API (https://api.crossref.org/works),
extracts publication metadata (title, abstract, DOI, authors, publication date),
and normalizes records into the unified IntelliScope research-source schema.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional

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


def _extract_publication_date(item: Dict[str, Any]) -> Optional[str]:
    """Extract formatted publication date string (YYYY-MM-DD / YYYY-MM / YYYY) from Crossref date-parts."""
    for key in ("published", "published-online", "published-print", "issued", "created"):
        date_obj = item.get(key)
        if not isinstance(date_obj, dict):
            continue
        date_parts = date_obj.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list):
            parts = [p for p in date_parts[0] if isinstance(p, int)]
            if len(parts) >= 3:
                return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
            if len(parts) == 2:
                return f"{parts[0]:04d}-{parts[1]:02d}"
            if len(parts) == 1:
                return f"{parts[0]:04d}"
    return None


def _extract_authors(item: Dict[str, Any]) -> List[str]:
    """Extract clean author display names from Crossref author list."""
    raw_authors = item.get("author")
    if not isinstance(raw_authors, list):
        return []
    authors: List[str] = []
    for author in raw_authors:
        if not isinstance(author, dict):
            continue
        given = str(author.get("given") or "").strip()
        family = str(author.get("family") or "").strip()
        org_name = str(author.get("name") or "").strip()
        full_name = " ".join(p for p in (given, family) if p).strip() or org_name
        if full_name:
            authors.append(full_name)
    return authors


def _resolve_crossref_url(item: Dict[str, Any], doi: Optional[str]) -> str:
    """
    Construct canonical HTTPS DOI URL when DOI exists, or normalize Crossref URL field.
    """
    raw_url = str(item.get("URL") or "").strip()
    if doi:
        if raw_url and re.match(r"^https?://(?:dx\.)?doi\.org/", raw_url, flags=re.IGNORECASE):
            return "https://doi.org/" + raw_url.split("doi.org/", 1)[1]
        return f"https://doi.org/{doi}"
    if raw_url and re.match(r"^http://(?:dx\.)?doi\.org/", raw_url, flags=re.IGNORECASE):
        return "https://doi.org/" + raw_url.split("doi.org/", 1)[1]
    return raw_url


async def search_crossref(
    query: str,
    limit: int = settings.DEFAULT_RESULTS_LIMIT,
    client: Optional[httpx.AsyncClient] = None,
    max_snippet_length: int = settings.DEFAULT_SNIPPET_LENGTH,
    retrieved_at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Asynchronously search Crossref works metadata and return normalized items.
    """
    params = {
        "query": query,
        "rows": limit,
        "select": "DOI,title,abstract,author,published,published-print,published-online,created,URL,container-title,type",
    }
    headers = {
        "User-Agent": settings.DEFAULT_USER_AGENT,
        "Accept": "application/json",
    }

    async def _fetch(active_client: httpx.AsyncClient) -> httpx.Response:
        return await active_client.get(
            settings.CROSSREF_API_URL,
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
        logger.error("Crossref API request timed out for query '%s': %s", query, exc)
        raise DataCollectorTimeoutError("Crossref research service timed out") from exc
    except httpx.RequestError as exc:
        logger.error("Network error connecting to Crossref API for query '%s': %s", query, exc)
        raise DataCollectorUpstreamError(
            f"Network error connecting to Crossref service: {exc}"
        ) from exc

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        msg = "Crossref API rate limit exceeded (HTTP 429)."
        if retry_after:
            msg += f" Retry after {retry_after}s."
        logger.warning(msg)
        raise DataCollectorRateLimitError(msg)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Crossref API returned HTTP error status %s", exc.response.status_code)
        raise DataCollectorUpstreamError(
            f"Crossref service returned HTTP status {exc.response.status_code}"
        ) from exc

    try:
        data = response.json()
    except Exception as exc:
        logger.error("Failed to parse JSON from Crossref API: %s", exc)
        raise DataCollectorResponseError("Crossref service returned invalid JSON") from exc

    if not isinstance(data, dict) or not isinstance(data.get("message"), dict):
        raise DataCollectorResponseError("Crossref service returned unexpected response structure")

    items = data["message"].get("items")
    if items is None:
        return []
    if not isinstance(items, list):
        raise DataCollectorResponseError("Crossref message.items structure is not a list")

    retrieval_ts = retrieved_at or datetime.now(timezone.utc).isoformat()
    results: List[Dict[str, Any]] = []

    for item in items[:limit]:
        if not isinstance(item, dict):
            continue

        raw_titles = item.get("title")
        if isinstance(raw_titles, list) and raw_titles:
            title = clean_wiki_markup_and_html(str(raw_titles[0]))
        elif isinstance(raw_titles, str):
            title = clean_wiki_markup_and_html(raw_titles)
        else:
            title = ""

        if not title:
            continue

        doi = normalize_doi(item.get("DOI"))
        source_url = _resolve_crossref_url(item, doi)
        if not source_url:
            continue

        authors = _extract_authors(item)
        pub_date = _extract_publication_date(item)

        raw_abstract = item.get("abstract")
        cleaned_abstract = clean_wiki_markup_and_html(raw_abstract) if isinstance(raw_abstract, str) else ""

        if cleaned_abstract and len(cleaned_abstract) >= 15:
            snippet_text = truncate_snippet(cleaned_abstract, max_length=max_snippet_length)
            source_type = "crossref_abstract"
        else:
            containers = item.get("container-title")
            journal = (
                clean_wiki_markup_and_html(str(containers[0]))
                if isinstance(containers, list) and containers
                else "Crossref-indexed publication"
            )
            work_type = str(item.get("type") or "scholarly work").replace("-", " ")
            doi_str = f", DOI: {doi}" if doi else ""
            snippet_text = truncate_snippet(
                f"Scholarly {work_type} published in '{journal}'{doi_str}. "
                f"Full abstract is not available in Crossref open metadata.",
                max_length=max_snippet_length,
            )
            source_type = "crossref_work"

        rel_label, is_weak, rel_reason = check_source_relevance(
            query=query,
            title=title,
            snippet=snippet_text,
        )

        results.append(
            normalize_research_item(
                title=title,
                snippet=snippet_text,
                source_name="crossref",
                source_url=source_url,
                publication_date=pub_date,
                doi=doi,
                authors=authors,
                retrieved_at=retrieval_ts,
                source_type=source_type,
                relevance=rel_label,
                is_weakly_relevant=is_weak,
                relevance_reason=rel_reason,
            )
        )

    return results

