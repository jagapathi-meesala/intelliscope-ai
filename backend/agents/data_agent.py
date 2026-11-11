"""
Data Collector Agent for IntelliScope AI.

Responsible for retrieving, sanitizing, and structuring external research
data using asynchronous requests to the MediaWiki API (Wikipedia).
Supports introductory page extracts, markup cleaning, navigation filtering,
and transparent source relevance checks.
"""

from datetime import datetime, timezone
import html
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

# Agent metadata
AGENT_NAME = "Data Collector Agent"
AGENT_VERSION = "1.0.0"
AGENT_STATUS = "operational"
AGENT_CAPABILITIES = [
    "wikipedia_search",
    "asynchronous_data_retrieval",
    "html_snippet_sanitization",
    "structured_metadata",
    "introductory_extract_retrieval",
    "markup_sanitization",
    "navigation_extract_filtering",
    "source_relevance_classification",
    "snippet_length_management",
]

# Patterns for navigation-only or disambiguation boilerplate
NAVIGATION_PATTERNS = [
    r"may\s+(?:also\s+)?refer\s+to\s*:",
    r"can\s+(?:also\s+)?refer\s+to\s*:",
    r"often\s+refers\s+to\s*:",
    r"jump\s+to\s+navigation",
    r"jump\s+to\s+search",
    r"navigation\s+menu",
    r"disambiguation\s+page",
    r"redirected\s+from",
    r"for\s+other\s+uses[,\s]+see",
    r"main\s+article[,\s]+see",
]

# Common English stop words for query term extraction
RELEVANCE_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "also", "am", "an",
    "and", "any", "are", "aren't", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "cannot", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "just",
    "me", "more", "most", "my", "no", "nor", "not", "now", "of", "off", "on",
    "once", "only", "or", "other", "our", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "with", "would", "you", "your",
}

# Prefixes for index, list, or catalog articles
RELEVANCE_LIST_PREFIXES = (
    "list of",
    "index of",
    "outline of",
    "glossary of",
    "timeline of",
    "comparison of",
    "bibliography of",
)


class DataCollectorError(Exception):
    """Base exception for Data Collector Agent operations."""
    pass


class DataCollectorTimeoutError(DataCollectorError):
    """Raised when the external upstream request times out."""
    pass


class DataCollectorUpstreamError(DataCollectorError):
    """Raised when the upstream service returns an error or is unreachable."""
    pass


class DataCollectorResponseError(DataCollectorError):
    """Raised when the upstream service returns an invalid or malformed response."""
    pass


def clean_wiki_markup_and_html(raw_text: str) -> str:
    """
    Remove HTML tags, wiki templates, internal/external links, citations,
    section headers, and decode HTML entities from text.

    Args:
        raw_text: Raw string containing HTML or wiki markup.

    Returns:
        Sanitized plain-text string.
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""

    text = raw_text

    # 1. Strip HTML tags (e.g. <span class="searchmatch">...</span>, <p>, <b>)
    text = re.sub(r"<[^>]+>", "", text)

    # 2. Decode HTML entities (&quot;, &amp;, &#160;, &minus;, etc.)
    text = html.unescape(text)

    # 3. Strip citations / references: [1], [12], [citation needed], [note 1]
    text = re.sub(r"\[(?:\d+|citation needed|note\s*\d+)\]", "", text, flags=re.IGNORECASE)

    # 4. Handle wiki piped links [[Target|Anchor]] -> Anchor
    text = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", text)

    # 5. Handle external wiki links [http://example.com Anchor] -> Anchor
    text = re.sub(r"\[https?://[^\s\]]+\s+([^\]]+)\]", r"\1", text)

    # 6. Remove wiki templates {{template_name}} or {{...}}
    text = re.sub(r"\{\{[^}]+\}\}", "", text)

    # 7. Remove wiki section headers like == Section ==
    text = re.sub(r"={2,}[^=]+={2,}", "", text)

    # 8. Clean spaces before punctuation and normalize excessive whitespace
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = " ".join(text.split())

    return text.strip()


def clean_html_snippet(raw_snippet: str) -> str:
    """
    Remove HTML tags and decode HTML entities from search snippets.
    Maintained as a backward-compatible alias.

    Args:
        raw_snippet: Raw snippet string containing HTML markup.

    Returns:
        Sanitized plain-text snippet string.
    """
    return clean_wiki_markup_and_html(raw_snippet)


def is_navigation_or_empty(text: Optional[str]) -> bool:
    """
    Detect whether a text snippet/extract is empty, whitespace, disambiguation
    boilerplate, or a navigation-only stub.

    Args:
        text: Candidate extract or snippet string.

    Returns:
        True if the text is empty or non-substantive navigation boilerplate.
    """
    if not text or not isinstance(text, str):
        return True

    cleaned = text.strip()
    if len(cleaned) < 15:
        return True

    lower = cleaned.lower()
    for pat in NAVIGATION_PATTERNS:
        if re.search(pat, lower):
            return True

    return False


def truncate_snippet(text: str, max_length: int = settings.DEFAULT_SNIPPET_LENGTH) -> str:
    """
    Apply configurable snippet length limits cleanly without breaking words when possible.

    Args:
        text: Source extract or snippet string.
        max_length: Maximum permitted character length.

    Returns:
        Truncated text string within limits.
    """
    if not text or len(text) <= max_length:
        return text

    truncated = text[:max_length]
    # Attempt to split at the last sentence end
    last_period = truncated.rfind(". ")
    if last_period > max_length // 2:
        return truncated[:last_period + 1]

    # Otherwise split at the last word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        return truncated[:last_space].rstrip(".,;:-") + "..."

    return truncated.rstrip() + "..."


def check_source_relevance(
    query: str,
    title: str,
    snippet: str
) -> Tuple[str, bool, str]:
    """
    Transparently assess topical relevance of a source to the search query.

    Evaluates lexical alignment between query terms and source title/snippet.
    Distinguishes directly relevant sources from weakly relevant or incidental sources.
    Incidental entities, people, companies, and peripheral list articles lacking the
    query topic in their title are classified as weakly relevant.
    Does NOT invent arbitrary numerical scores or factual claims.

    Args:
        query: Research query string.
        title: Article title.
        snippet: Source extract or snippet.

    Returns:
        Tuple of (relevance_label, is_weakly_relevant, relevance_reason)
        where relevance_label is 'relevant' or 'weakly_relevant'.
    """
    raw_words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", query.lower())
    query_words = [w for w in raw_words if w not in RELEVANCE_STOP_WORDS]

    if not query_words:
        query_words = raw_words

    if not query_words:
        return "relevant", False, "General research query matched."

    title_lower = (title or "").lower().strip()
    snippet_lower = (snippet or "").lower().strip()

    # Match terms by exact match or stem prefix (min 4 chars)
    def _term_matches(term: str, target: str) -> bool:
        if term in target:
            return True
        if len(term) >= 5:
            stem = term[:4]
            return stem in target
        return False

    title_matches = [w for w in query_words if _term_matches(w, title_lower)]
    snippet_matches = [w for w in query_words if _term_matches(w, snippet_lower)]
    all_matched_terms = set(title_matches).union(snippet_matches)

    # 1. Incidental Entity / Biography / Vendor Check:
    # If the title contains none of the query terms, the article is fundamentally about another
    # entity, person, company, vendor, or peripheral subject that merely mentions the query in its extract.
    if len(title_matches) == 0:
        return (
            "weakly_relevant",
            True,
            (
                f"Weakly related: Article title '{title}' contains none of the query terms "
                f"({', '.join(query_words)}). The source appears to be an entity, person, vendor, "
                f"or peripheral topic with incidental mention in the extract."
            ),
        )

    # 2. List / Catalog / Index Article Check:
    # If the article is a list or index and its title lacks full query coverage, it is peripheral.
    is_list_title = any(title_lower.startswith(prefix) for prefix in RELEVANCE_LIST_PREFIXES)
    if is_list_title and len(title_matches) < len(query_words):
        missing_title_terms = [w for w in query_words if w not in title_matches]
        return (
            "weakly_relevant",
            True,
            (
                f"Weakly related: Article is an index or list ('{title}') that lacks core query "
                f"term(s) '{', '.join(missing_title_terms)}' in its title."
            ),
        )

    # 3. Direct Full Match: Article title directly matches all query terms
    if len(title_matches) == len(query_words):
        return (
            "relevant",
            False,
            f"Article title directly matches all query terms: {', '.join(query_words)}."
        )

    # 4. Exact Query String in Title
    if query.lower() in title_lower:
        return (
            "relevant",
            False,
            f"Article title contains exact search phrase '{query}'."
        )

    # 5. Core Term in Title and Combined Extract Covers All Query Terms
    if len(all_matched_terms) == len(query_words):
        return (
            "relevant",
            False,
            f"Source title and extract cover all key query terms ({', '.join(query_words)})."
        )

    # 6. Extract Contains Exact Query Phrase (with Title containing at least one core term)
    if query.lower() in snippet_lower:
        return (
            "relevant",
            False,
            f"Extract contains exact search phrase '{query}' and article title aligns with core terms."
        )

    # 7. Single-term query matches title
    if len(query_words) == 1 and query_words[0] in title_lower:
        return (
            "relevant",
            False,
            f"Source title contains primary query term '{query_words[0]}'."
        )

    # 8. Partial match (some terms present, but key concepts missing)
    if len(all_matched_terms) > 0:
        matched_str = ", ".join(sorted(all_matched_terms))
        missing = [w for w in query_words if w not in all_matched_terms]
        missing_str = ", ".join(missing)
        return (
            "weakly_relevant",
            True,
            f"Weakly related: Source mentions '{matched_str}' but lacks core query terms '{missing_str}'."
        )

    # 9. Incidental / zero direct term matches
    return (
        "weakly_relevant",
        True,
        f"Weakly related: Neither title nor extract contains query key terms ({', '.join(query_words)})."
    )


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

        # Store with lowercased and exact title keys for flexible lookup
        extract_map[page_title.lower()] = cleaned_extract
        extract_map[page_title] = cleaned_extract

    # Also resolve redirects if provided in response
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


async def collect_research(
    query: str,
    limit: int = settings.DEFAULT_RESULTS_LIMIT,
    client: Optional[httpx.AsyncClient] = None,
    fetch_extracts: bool = True,
    max_snippet_length: int = settings.DEFAULT_SNIPPET_LENGTH,
) -> Dict[str, Any]:
    """
    Asynchronously collect research information from Wikipedia via the MediaWiki API.

    Uses search to discover candidate pages, fetches introductory page extracts,
    sanitizes markup, filters navigation-only extracts, enforces length limits,
    and applies transparent relevance checks.

    Args:
        query: Search query string (must not be empty, max 300 characters).
        limit: Number of search results to return (between 1 and 10).
        client: Optional existing httpx.AsyncClient instance for connection reuse or testing.
        fetch_extracts: Whether to fetch full introductory extracts (defaults to True).
        max_snippet_length: Maximum character length for snippets/extracts (default 500).

    Returns:
        Structured dictionary containing query, agent name, result count,
        and list of result items with titles, snippets, source URLs, timestamps,
        relevance classifications, and source provenance.

    Raises:
        ValueError: If query or limit fail basic validation.
        DataCollectorTimeoutError: If the external API request times out.
        DataCollectorUpstreamError: If the external API returns an HTTP error or is unreachable.
        DataCollectorResponseError: If the response is malformed or contains an API error.
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

    # Internal helper to execute HTTP GET for search
    async def _fetch(active_client: httpx.AsyncClient) -> httpx.Response:
        return await active_client.get(
            settings.WIKIPEDIA_API_URL,
            params=params,
            headers=headers
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

    # Validate HTTP status
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Wikipedia API returned HTTP status error: %s", exc)
        raise DataCollectorUpstreamError(
            f"Upstream search service returned HTTP status {exc.response.status_code}"
        ) from exc

    # Parse JSON response
    try:
        data = response.json()
    except Exception as exc:
        logger.error("Failed to parse JSON response from Wikipedia API: %s", exc)
        raise DataCollectorResponseError("Upstream service returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise DataCollectorResponseError("Upstream service returned unexpected response format")

    # Check for MediaWiki API error payload
    if "error" in data:
        error_info = data["error"].get("info", "Unknown MediaWiki error")
        logger.error("Wikipedia API returned error payload: %s", error_info)
        raise DataCollectorUpstreamError(f"Upstream API error: {error_info}")

    retrieval_timestamp = datetime.now(timezone.utc).isoformat()
    raw_search_items = data.get("query", {}).get("search", [])

    if not isinstance(raw_search_items, list):
        raise DataCollectorResponseError("Upstream query.search structure is not a list")

    # If zero search results, return empty result batch
    if not raw_search_items:
        return {
            "agent": AGENT_NAME,
            "agent_name": AGENT_NAME,
            "query": query,
            "result_count": 0,
            "total_results": 0,
            "retrieved_at": retrieval_timestamp,
            "results": [],
        }

    # Fetch page extracts if enabled
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

        # Check for introductory extract
        candidate_extract = extracts_map.get(title.lower()) or extracts_map.get(title)

        # Use extract if substantive and not navigation-only; otherwise fallback to search snippet
        if candidate_extract and not is_navigation_or_empty(candidate_extract):
            content_text = candidate_extract
            source_type = "wikipedia_extract"
        else:
            content_text = clean_fallback_snippet
            source_type = "wikipedia_search_snippet"

        # Apply configurable snippet length limit
        bounded_snippet = truncate_snippet(content_text, max_length=max_snippet_length)

        # Perform transparent relevance check
        relevance_label, is_weak, relevance_reason = check_source_relevance(
            query=query,
            title=title,
            snippet=bounded_snippet,
        )

        source_url = build_wikipedia_url(title)

        results.append({
            "title": title,
            "snippet": bounded_snippet,
            "source_url": source_url,
            "source": source_url,
            "retrieved_at": retrieval_timestamp,
            "relevance": relevance_label,
            "is_weakly_relevant": is_weak,
            "relevance_reason": relevance_reason,
            "source_type": source_type,
        })

    return {
        "agent": AGENT_NAME,
        "agent_name": AGENT_NAME,
        "query": query,
        "result_count": len(results),
        "total_results": len(results),
        "retrieved_at": retrieval_timestamp,
        "results": results,
    }
