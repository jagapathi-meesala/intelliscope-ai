"""
Multi-source research client package for IntelliScope AI.
Provides normalized retrieval services for Wikipedia, arXiv, and Crossref.
"""

from backend.services.sources.arxiv_client import search_arxiv
from backend.services.sources.base import (
    DataCollectorError,
    DataCollectorRateLimitError,
    DataCollectorResponseError,
    DataCollectorTimeoutError,
    DataCollectorUpstreamError,
    check_source_relevance,
    clean_html_snippet,
    clean_wiki_markup_and_html,
    is_navigation_or_empty,
    normalize_doi,
    normalize_research_item,
    truncate_snippet,
)
from backend.services.sources.crossref_client import search_crossref

__all__ = [
    "search_arxiv",
    "search_crossref",
    "DataCollectorError",
    "DataCollectorTimeoutError",
    "DataCollectorUpstreamError",
    "DataCollectorRateLimitError",
    "DataCollectorResponseError",
    "clean_html_snippet",
    "clean_wiki_markup_and_html",
    "is_navigation_or_empty",
    "truncate_snippet",
    "check_source_relevance",
    "normalize_doi",
    "normalize_research_item",
]

