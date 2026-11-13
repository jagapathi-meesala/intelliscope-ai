"""
Data Collector Agent for IntelliScope AI.

Responsible for retrieving, sanitizing, normalizing, and orchestrating
external research data across multiple providers:
1. Wikipedia (MediaWiki search & introductory page extracts)
2. arXiv (Atom academic paper API)
3. Crossref (Scholarly publication metadata & DOI REST API)
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from backend.config import settings
from backend.models.research import validate_and_normalize_sources
from backend.services.sources import (
    DataCollectorError,
    DataCollectorRateLimitError,
    DataCollectorResponseError,
    DataCollectorTimeoutError,
    DataCollectorUpstreamError,
    check_source_relevance,
    clean_html_snippet,
    clean_wiki_markup_and_html,
    is_navigation_or_empty,
    normalize_research_item,
    search_arxiv,
    search_crossref,
    truncate_snippet,
)
from backend.services.sources.base import (
    NAVIGATION_PATTERNS,
    RELEVANCE_LIST_PREFIXES,
    RELEVANCE_STOP_WORDS,
)

logger = logging.getLogger(__name__)

# Agent metadata
AGENT_NAME = "Data Collector Agent"
AGENT_VERSION = "1.0.0"
AGENT_STATUS = "operational"
AGENT_CAPABILITIES = [
    "wikipedia_search",
    "arxiv_search",
    "crossref_search",
    "multi_source_collection",
    "asynchronous_data_retrieval",
    "html_snippet_sanitization",
    "structured_metadata",
    "introductory_extract_retrieval",
    "markup_sanitization",
    "navigation_extract_filtering",
    "source_relevance_classification",
    "snippet_length_management",
]

__all__ = [
    "AGENT_NAME",
    "AGENT_VERSION",
    "AGENT_STATUS",
    "AGENT_CAPABILITIES",
    "NAVIGATION_PATTERNS",
    "RELEVANCE_STOP_WORDS",
    "RELEVANCE_LIST_PREFIXES",
    "DataCollectorError",
    "DataCollectorTimeoutError",
    "DataCollectorUpstreamError",
    "DataCollectorRateLimitError",
    "DataCollectorResponseError",
    "clean_wiki_markup_and_html",
    "clean_html_snippet",
    "is_navigation_or_empty",
    "truncate_snippet",
    "check_source_relevance",
    "build_wikipedia_url",
    "fetch_page_extracts",
    "collect_research",
]


def build_wikipedia_url(title: str) -> str:
    """
    Construct a canonical Wikipedia article URL from an article title.

    Args:
        title: Article title string.

    Returns:
        Canonical HTTPS Wikipedia URL.
    """
    formatted_title = title.replace(" ", "_")
    return f"https://en.wikipedia.org/wiki/{quote(formatted_title, safe='/:@')}"


async def fetch_page_extracts(
    titles: List[str],
    client: httpx.AsyncClient,
) -> Dict[str, str]:
    """
    Fetch introductory plain-text page extracts from Wikipedia via MediaWiki API.

    Args:
        titles: List of Wikipedia article titles.
        client: Active httpx.AsyncClient instance.

    Returns:
        Dictionary mapping lowercased article titles to cleaned extract text.
    """
    if not titles:
        return {}

    params = {
        "action": "query",
        "prop": "extracts",
        "exintro": 1,
        "explaintext": 1,
        "titles": "|".join(titles),
        "format": "json",
        "utf8": 1,
        "redirects": 1,
    }

    headers = {
        "User-Agent": settings.DEFAULT_USER_AGENT,
        "Accept": "application/json",
    }

    try:
        response = await client.get(
            settings.WIKIPEDIA_API_URL,
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning(
            "Failed to fetch introductory extracts for titles %s: %s; falling back to snippets",
            titles,
            exc,
        )
        return {}

    if not isinstance(data, dict):
        return {}

    pages = data.get("query", {}).get("pages", {})
    if not isinstance(pages, dict):
        return {}

    extract_map: Dict[str, str] = {}

    for _, page in pages.items():
        if not isinstance(page, dict):
            continue
        page_title = page.get("title")
        if not page_title:
            continue

        raw_extract = page.get("extract", "")
        cleaned_extract = clean_wiki_markup_and_html(raw_extract)

        extract_map[page_title.lower()] = cleaned_extract
        extract_map[page_title] = cleaned_extract

    redirects = data.get("query", {}).get("redirects", [])
    if isinstance(redirects, list):
        for redir in redirects:
            if isinstance(redir, dict):
                from_title = redir.get("from", "")
                to_title = redir.get("to", "")
                if to_title.lower() in extract_map:
                    extract_map[from_title.lower()] = extract_map[to_title.lower()]
                    extract_map[from_title] = extract_map[to_title.lower()]

    return extract_map


async def _collect_wikipedia(
    query: str,
    limit: int,
    client: Optional[httpx.AsyncClient] = None,
    fetch_extracts: bool = True,
    max_snippet_length: int = settings.DEFAULT_SNIPPET_LENGTH,
    retrieved_at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve and normalize Wikipedia search articles & page extracts."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
        "utf8": 1,
    }
    headers = {
        "User-Agent": settings.DEFAULT_USER_AGENT,
        "Accept": "application/json",
    }

    async def _fetch(active_client: httpx.AsyncClient) -> httpx.Response:
        return await active_client.get(
            settings.WIKIPEDIA_API_URL,
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
        logger.error("Wikipedia API request timed out for query: %s: %s", query, exc)
        raise DataCollectorTimeoutError("Upstream search service timed out") from exc
    except httpx.RequestError as exc:
        logger.error("Network error while contacting Wikipedia API for query: %s: %s", query, exc)
        raise DataCollectorUpstreamError(
            f"Network error while connecting to upstream search service: {str(exc)}"
        ) from exc

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        msg = "Wikipedia API rate limit exceeded (HTTP 429)."
        if retry_after:
            msg += f" Retry after {retry_after}s."
        raise DataCollectorRateLimitError(msg)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Wikipedia API returned HTTP status error: %s", exc)
        raise DataCollectorUpstreamError(
            f"Upstream search service returned HTTP status {exc.response.status_code}"
        ) from exc

    try:
        data = response.json()
    except Exception as exc:
        logger.error("Failed to parse JSON response from Wikipedia API: %s", exc)
        raise DataCollectorResponseError("Upstream service returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise DataCollectorResponseError("Upstream service returned unexpected response format")

    if "error" in data:
        error_info = data["error"].get("info", "Unknown MediaWiki error")
        logger.error("Wikipedia API returned error payload: %s", error_info)
        raise DataCollectorUpstreamError(f"Upstream API error: {error_info}")

    retrieval_timestamp = retrieved_at or datetime.now(timezone.utc).isoformat()
    raw_search_items = data.get("query", {}).get("search", [])

    if not isinstance(raw_search_items, list):
        raise DataCollectorResponseError("Upstream query.search structure is not a list")

    if not raw_search_items:
        return []

    extracts_map: Dict[str, str] = {}
    should_fetch_extracts = fetch_extracts and getattr(settings, "ENABLE_PAGE_EXTRACTS", True)

    if should_fetch_extracts:
        candidate_titles = [
            item.get("title", "") for item in raw_search_items
            if isinstance(item, dict) and item.get("title")
        ]
        if candidate_titles:
            try:
                if client is not None:
                    extracts_map = await fetch_page_extracts(candidate_titles, client)
                else:
                    async with httpx.AsyncClient(timeout=settings.DEFAULT_REQUEST_TIMEOUT) as local_client:
                        extracts_map = await fetch_page_extracts(candidate_titles, local_client)
            except Exception as exc:
                logger.warning("Error fetching page extracts: %s; falling back to snippets", exc)
                extracts_map = {}

    results: List[Dict[str, Any]] = []
    for item in raw_search_items:
        if not isinstance(item, dict):
            continue

        title = item.get("title", "")
        raw_snippet = item.get("snippet", "")
        clean_fallback_snippet = clean_html_snippet(raw_snippet)

        candidate_extract = extracts_map.get(title.lower()) or extracts_map.get(title)

        if candidate_extract and not is_navigation_or_empty(candidate_extract):
            content_text = candidate_extract
            source_type = "wikipedia_extract"
        else:
            content_text = clean_fallback_snippet
            source_type = "wikipedia_search_snippet"

        bounded_snippet = truncate_snippet(content_text, max_length=max_snippet_length)

        relevance_label, is_weak, relevance_reason = check_source_relevance(
            query=query,
            title=title,
            snippet=bounded_snippet,
        )

        source_url = build_wikipedia_url(title)
        raw_ts = item.get("timestamp")
        pub_date = raw_ts[:10] if isinstance(raw_ts, str) and len(raw_ts) >= 10 else None

        results.append(
            normalize_research_item(
                title=title,
                snippet=bounded_snippet,
                source_name="wikipedia",
                source_url=source_url,
                publication_date=pub_date,
                doi=None,
                authors=[],
                retrieved_at=retrieval_timestamp,
                source_type=source_type,
                relevance=relevance_label,
                is_weakly_relevant=is_weak,
                relevance_reason=relevance_reason,
            )
        )

    return results


async def collect_research(
    query: str,
    limit: int = settings.DEFAULT_RESULTS_LIMIT,
    client: Optional[httpx.AsyncClient] = None,
    fetch_extracts: bool = True,
    max_snippet_length: int = settings.DEFAULT_SNIPPET_LENGTH,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Asynchronously collect normalized research information from one or more sources
    ('wikipedia', 'arxiv', 'crossref').

    Defaults to ['wikipedia'] when `sources` is omitted for backward compatibility.
    """
    if not query or not query.strip():
        raise ValueError("Research query cannot be empty or contain only whitespace")

    query = query.strip()
    if len(query) > settings.MAX_QUERY_LENGTH:
        raise ValueError(
            f"Research query exceeds maximum length of {settings.MAX_QUERY_LENGTH} characters"
        )

    if limit < settings.MIN_RESULTS_LIMIT or limit > settings.MAX_RESULTS_LIMIT:
        raise ValueError(
            f"Limit must be between {settings.MIN_RESULTS_LIMIT} and {settings.MAX_RESULTS_LIMIT}"
        )

    selected_sources = validate_and_normalize_sources(sources)
    retrieval_timestamp = datetime.now(timezone.utc).isoformat()

    async def _fetch_single(src_name: str) -> List[Dict[str, Any]]:
        if src_name == "wikipedia":
            return await _collect_wikipedia(
                query=query,
                limit=limit,
                client=client,
                fetch_extracts=fetch_extracts,
                max_snippet_length=max_snippet_length,
                retrieved_at=retrieval_timestamp,
            )
        if src_name == "arxiv":
            return await search_arxiv(
                query=query,
                limit=limit,
                client=client,
                max_snippet_length=max_snippet_length,
                retrieved_at=retrieval_timestamp,
            )
        if src_name == "crossref":
            return await search_crossref(
                query=query,
                limit=limit,
                client=client,
                max_snippet_length=max_snippet_length,
                retrieved_at=retrieval_timestamp,
            )
        raise ValueError(f"Unsupported research source '{src_name}'")

    raw_outcomes = await asyncio.gather(
        *[_fetch_single(src) for src in selected_sources],
        return_exceptions=True,
    )

    per_source_results: Dict[str, List[Dict[str, Any]]] = {}
    source_errors: Dict[str, str] = {}
    first_exception: Optional[BaseException] = None

    for src_name, outcome in zip(selected_sources, raw_outcomes):
        if isinstance(outcome, BaseException):
            if first_exception is None:
                first_exception = outcome
            source_errors[src_name] = str(outcome)
            logger.warning("Source '%s' failed for query '%s': %s", src_name, query, outcome)
        else:
            per_source_results[src_name] = outcome

    # If every selected source failed, re-raise the primary failure exception cleanly
    if len(per_source_results) == 0 and first_exception is not None:
        raise first_exception

    # Interleave results across selected sources round-robin for balanced representation
    combined_results: List[Dict[str, Any]] = []
    source_breakdown: Dict[str, int] = {src: len(per_source_results.get(src, [])) for src in selected_sources}

    max_len = max((len(items) for items in per_source_results.values()), default=0)
    for idx in range(max_len):
        for src_name in selected_sources:
            items = per_source_results.get(src_name, [])
            if idx < len(items):
                combined_results.append(items[idx])

    return {
        "agent": AGENT_NAME,
        "agent_name": AGENT_NAME,
        "query": query,
        "sources_requested": selected_sources,
        "source_breakdown": source_breakdown,
        "source_errors": source_errors,
        "result_count": len(combined_results),
        "total_results": len(combined_results),
        "retrieved_at": retrieval_timestamp,
        "results": combined_results,
    }
