"""
Shared exceptions, text sanitization, relevance assessment, and record normalization
for IntelliScope AI research source clients (Wikipedia, arXiv, Crossref).
"""

import html
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.config import settings

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


class DataCollectorRateLimitError(DataCollectorUpstreamError):
    """Raised when an external research API enforces HTTP 429 rate limiting."""
    pass


class DataCollectorResponseError(DataCollectorError):
    """Raised when the upstream service returns an invalid or malformed response."""
    pass


def clean_wiki_markup_and_html(raw_text: str) -> str:
    """
    Remove HTML/XML tags (including JATS tags), wiki templates, links, citations,
    section headers, and decode HTML entities from text.
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""

    text = raw_text

    # 1. Strip HTML/XML tags (e.g. <span class="searchmatch">...</span>, <jats:p>, <b>)
    text = re.sub(r"<[^>]+>", " ", text)

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
    """Remove HTML tags and decode HTML entities from snippets."""
    return clean_wiki_markup_and_html(raw_snippet)


def is_navigation_or_empty(text: Optional[str]) -> bool:
    """
    Detect whether a text snippet/extract is empty, whitespace, disambiguation
    boilerplate, or a navigation-only stub.
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
    """Apply configurable snippet length limits cleanly at sentence or word boundaries."""
    if not text or len(text) <= max_length:
        return text

    truncated = text[:max_length]
    last_period = truncated.rfind(". ")
    if last_period > max_length // 2:
        return truncated[: last_period + 1]

    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        return truncated[:last_space].rstrip(".,;:-") + "..."

    return truncated.rstrip() + "..."


def check_source_relevance(
    query: str,
    title: str,
    snippet: str,
) -> Tuple[str, bool, str]:
    """
    Transparently assess topical relevance of a source to the search query.
    Distinguishes directly relevant works from weakly relevant / peripheral items.
    """
    raw_words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", query.lower())
    query_words = [w for w in raw_words if w not in RELEVANCE_STOP_WORDS]

    if not query_words:
        query_words = raw_words

    if not query_words:
        return "relevant", False, "General research query matched."

    title_lower = (title or "").lower().strip()
    snippet_lower = (snippet or "").lower().strip()

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

    if len(title_matches) == len(query_words):
        return (
            "relevant",
            False,
            f"Article title directly matches all query terms: {', '.join(query_words)}.",
        )

    if query.lower() in title_lower:
        return (
            "relevant",
            False,
            f"Article title contains exact search phrase '{query}'.",
        )

    if len(all_matched_terms) == len(query_words):
        return (
            "relevant",
            False,
            f"Source title and extract cover all key query terms ({', '.join(query_words)}).",
        )

    if query.lower() in snippet_lower:
        return (
            "relevant",
            False,
            f"Extract contains exact search phrase '{query}' and article title aligns with core terms.",
        )

    if len(query_words) == 1 and query_words[0] in title_lower:
        return (
            "relevant",
            False,
            f"Source title contains primary query term '{query_words[0]}'.",
        )

    if len(all_matched_terms) > 0:
        matched_str = ", ".join(sorted(all_matched_terms))
        missing = [w for w in query_words if w not in all_matched_terms]
        missing_str = ", ".join(missing)
        return (
            "weakly_relevant",
            True,
            f"Weakly related: Source mentions '{matched_str}' but lacks core query terms '{missing_str}'.",
        )

    return (
        "weakly_relevant",
        True,
        f"Weakly related: Neither title nor extract contains query key terms ({', '.join(query_words)}).",
    )


def normalize_doi(raw_doi: Optional[str]) -> Optional[str]:
    """Normalize DOI identifier (stripping url/doi: prefixes if provided) cleanly."""
    if not raw_doi or not isinstance(raw_doi, str):
        return None
    cleaned = raw_doi.strip()
    if not cleaned:
        return None
    cleaned = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^doi:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or None


def normalize_research_item(
    *,
    title: str,
    snippet: str,
    source_name: str,
    source_url: str,
    retrieved_at: str,
    source_type: str,
    relevance: str,
    is_weakly_relevant: bool,
    relevance_reason: str,
    publication_date: Optional[str] = None,
    doi: Optional[str] = None,
    authors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Normalize a source record into the canonical IntelliScope multi-source item schema.
    """
    clean_authors = [str(a).strip() for a in (authors or []) if str(a).strip()]
    return {
        "title": title,
        "snippet": snippet,
        "abstract": snippet,
        "source_name": source_name,
        "source_url": source_url,
        "source": source_url,
        "publication_date": publication_date,
        "doi": doi,
        "authors": clean_authors,
        "retrieved_at": retrieved_at,
        "relevance": relevance,
        "is_weakly_relevant": is_weakly_relevant,
        "relevance_reason": relevance_reason,
        "source_type": source_type,
    }

