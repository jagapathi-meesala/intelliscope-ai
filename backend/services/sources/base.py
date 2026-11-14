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

# Common research intent modifiers and meta-query words that describe research activity
# rather than domain subject matter (e.g. "healthcare AI research" -> core: healthcare, AI)
INTENT_MODIFIER_WORDS = {
    "research", "overview", "study", "studies", "application", "applications",
    "applied", "survey", "review", "reviews", "analysis", "system", "systems",
    "approach", "approaches", "methods", "method", "techniques", "technique",
    "trends", "challenges", "future", "recent", "using", "use", "based", "role",
    "impact", "advances", "development", "developments", "state", "art", "field",
}

# Domain concept clusters linking abbreviations, full phrases, and closely associated domain terms
# for transparent, topic-aware matching across multi-disciplinary academic literature.
# Supports directional matching: broad primary category query terms (e.g. 'healthcare', 'ai')
# match specialized subtopics (e.g. 'radiology', 'cardiovascular', 'transformer'), while narrow
# subtopic query terms (e.g. 'pneumonia') require their specific concept family.
CONCEPT_CLUSTERS: List[Dict[str, Any]] = [
    {
        "id": "ai",
        "primary": [
            "ai", "artificial intelligence", "intelligent system", "intelligent systems",
            "machine learning", "deep learning",
        ],
        "subtopics": [
            "neural network", "neural networks", "deep neural",
            "nlp", "natural language processing", "large language model", "large language models",
            "llm", "llms", "language model", "language models",
            "computer vision", "image recognition", "image segmentation", "medical imaging",
            "convolutional", "cnn", "transformer", "transformers", "vision transformer",
            "foundation model", "foundation models", "generative ai", "genai",
            "reinforcement learning", "federated learning", "supervised learning", "unsupervised learning",
            "predictive model", "predictive models", "predictive modeling", "data mining",
            "graph neural network", "graph neural networks",
        ],
        "terms": ["ai", "artificial intelligence", "intelligent system", "intelligent systems"],
        "broad": ["machine learning", "deep learning", "neural network", "neural networks"],
    },
    {
        "id": "ml",
        "primary": ["ml", "machine learning"],
        "subtopics": [
            "deep learning", "neural network", "neural networks", "deep neural",
            "supervised learning", "unsupervised learning", "reinforcement learning",
            "federated learning", "predictive model", "predictive modeling",
            "random forest", "gradient boosting", "xgboost", "support vector",
        ],
        "terms": ["ml", "machine learning"],
        "broad": ["deep learning", "neural network", "neural networks", "artificial intelligence", "ai"],
    },
    {
        "id": "deep_learning",
        "primary": ["dl", "deep learning"],
        "subtopics": [
            "neural network", "neural networks", "deep neural",
            "convolutional", "cnn", "transformer", "transformers",
            "foundation model", "foundation models",
        ],
        "terms": ["dl", "deep learning", "neural network", "neural networks", "deep neural", "convolutional", "cnn", "transformer", "transformers"],
        "broad": ["machine learning", "artificial intelligence", "ai"],
    },
    {
        "id": "nlp",
        "primary": ["nlp", "natural language processing"],
        "subtopics": [
            "large language model", "large language models", "llm", "llms",
            "language model", "language models", "text mining",
        ],
        "terms": ["nlp", "natural language processing", "llm", "llms", "language model", "language models"],
        "broad": ["artificial intelligence", "ai", "machine learning"],
    },
    {
        "id": "cv",
        "primary": ["cv", "computer vision"],
        "subtopics": [
            "image recognition", "image segmentation", "medical imaging",
            "image analysis", "object detection",
        ],
        "terms": ["cv", "computer vision", "image recognition", "image segmentation", "medical imaging", "image analysis"],
        "broad": ["artificial intelligence", "ai", "machine learning", "deep learning"],
    },
    {
        "id": "quantum",
        "primary": [
            "quantum computing", "quantum computation", "quantum computer", "quantum computers",
            "quantum algorithm", "quantum algorithms", "qubit", "qubits", "quantum",
        ],
        "subtopics": [
            "superconducting qubit", "ion trap", "quantum error correction", "quantum supremacy",
        ],
        "terms": ["quantum computing", "quantum computation", "quantum computer", "quantum computers", "quantum algorithm", "quantum algorithms", "qubit", "qubits", "quantum"],
        "broad": [],
    },
    {
        "id": "healthcare",
        "primary": [
            "healthcare", "health care", "health", "medical", "medicine", "clinical", "biomedical",
        ],
        "subtopics": [
            "hospital", "hospitals", "clinic", "clinics", "clinician", "clinicians",
            "physician", "physicians", "doctor", "doctors", "nurse", "nurses",
            "patient", "patients", "in-hospital", "inpatient", "outpatient", "intensive care", "icu",
            "ehr", "emr", "electronic health", "electronic medical", "health record", "health records",
            "diagnosis", "diagnostics", "diagnostic", "prognosis", "prognostic", "screening", "triage",
            "disease", "diseases", "disorder", "disorders", "syndrome", "syndromes",
            "mortality", "readmission", "therapy", "therapies", "therapeutic", "treatment", "treatments",
            "clinical decision support", "cdss",
            "radiology", "radiologist", "radiologists", "radiograph", "radiographs", "radiography", "radiographic",
            "x-ray", "x-rays", "xray", "xrays", "ct scan", "ct scans", "computed tomography", "mri", "ultrasound",
            "pathology", "pathologist", "pathologists", "pathological", "histopathology", "biopsy",
            "cardiology", "cardiovascular", "cardiac", "heart failure", "myocardial",
            "oncology", "cancer", "cancers", "tumor", "tumors", "neoplasm",
            "neurology", "neurological", "dermatology", "ophthalmology", "retinopathy",
            "pulmonary", "pneumonia", "covid-19", "covid", "coronavirus",
            "diabetes", "diabetic",
            "surgical", "surgery", "surgeries", "surgeon", "surgeons",
        ],
        "terms": [
            "healthcare", "health care", "health", "medical", "medicine", "clinical",
            "hospital", "hospitals", "biomedical", "patient", "patients", "physician",
            "physicians", "radiology", "radiologist", "radiologists", "pathology",
            "diagnosis", "diagnostics", "diagnostic", "prognosis", "ehr", "pneumonia",
            "disease", "clinical decision support",
        ],
        "broad": [],
    },
    {
        "id": "genomics",
        "primary": [
            "crispr", "gene editing", "genome editing", "genetic engineering", "cas9", "genomics", "dna", "rna",
        ],
        "subtopics": [
            "base editing", "prime editing", "guide rna", "genomic",
        ],
        "terms": ["crispr", "gene editing", "genome editing", "genetic engineering", "cas9", "genomics", "dna", "rna"],
        "broad": [],
    },
]


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


def _stem_term(w: str) -> str:
    """Strip common English inflectional suffixes cleanly."""
    w = w.lower()
    for s in ("ing", "ies", "es", "s", "ed", "al", "tion", "tive"):
        if w.endswith(s) and len(w) > len(s) + 2:
            return w[:-len(s)]
    return w


def _term_matches_text(term: str, target: str, allow_concept: bool = True) -> bool:
    """
    Check if a query term or its concept synonyms match the target text (title or snippet).
    Respects word boundaries for short acronyms (e.g. AI, ML, CV, EHR).
    Enforces directional concept matching: broad category query terms accept specialized
    subtopics, while narrow subtopic query terms require their specific concept family.
    """
    t_lower = target.lower()
    term_l = term.lower()

    # 1. Exact match or word boundary check for short terms
    if len(term_l) <= 3:
        if re.search(r"\b" + re.escape(term_l) + r"\b", t_lower):
            return True
    else:
        if term_l in t_lower:
            return True
        st = _stem_term(term_l)
        if len(st) >= 4 and st in t_lower:
            return True

    # 2. Concept cluster / taxonomy matching
    if allow_concept:
        for c in CONCEPT_CLUSTERS:
            primary = c.get("primary") or c.get("terms", [])
            subtopics = c.get("subtopics") or c.get("broad", [])

            # Case A: Query term is a primary category term (e.g. 'healthcare', 'ai', 'quantum')
            # It matches if target contains ANY primary term OR ANY specialized subtopic
            if any(term_l == p or term_l in p.split() for p in primary):
                for cand in primary + subtopics:
                    if len(cand) <= 3:
                        if re.search(r"\b" + re.escape(cand) + r"\b", t_lower):
                            return True
                    else:
                        if cand in t_lower:
                            return True
                        st_c = _stem_term(cand)
                        if len(st_c) >= 4 and st_c in t_lower:
                            return True

            # Case B: Query term is a specific subtopic (e.g. 'pneumonia', 'transformer', 'radiology')
            # It ONLY matches its specific subtopic family, preventing cross-contamination
            # (e.g. query 'pneumonia' will NOT match sibling subtopics like 'hospital' or 'cardiology')
            elif any(term_l == s or term_l in s.split() for s in subtopics):
                matched_subs = [s for s in subtopics if term_l == s or term_l in s.split()]
                for cand in matched_subs:
                    if len(cand) <= 3:
                        if re.search(r"\b" + re.escape(cand) + r"\b", t_lower):
                            return True
                    else:
                        if cand in t_lower:
                            return True
                        st_c = _stem_term(cand)
                        if len(st_c) >= 4 and st_c in t_lower:
                            return True

    return False


def check_source_relevance(
    query: str,
    title: str,
    snippet: str,
) -> Tuple[str, bool, str]:
    """
    Transparently assess topical relevance of a source to the search query.
    Distinguishes directly relevant works from weakly relevant / peripheral items.
    Uses meaningful term weighting, topic-aware matching, and concept evidence across
    title and abstract without demanding every query word in long academic queries.
    """
    raw_words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", query.lower())
    query_words = [w for w in raw_words if w not in RELEVANCE_STOP_WORDS]

    if not query_words:
        query_words = raw_words

    if not query_words:
        return "relevant", False, "General research query matched."

    title_lower = (title or "").lower().strip()
    snippet_lower = (snippet or "").lower().strip()

    # 1. Exact phrase in title (highest confidence direct match)
    if query.lower() in title_lower:
        return (
            "relevant",
            False,
            f"Article title directly matches all query terms: {', '.join(query_words)}.",
        )

    # 2. Direct literal word matches in title (all terms present literally)
    literal_title_matches = [w for w in query_words if _term_matches_text(w, title_lower, allow_concept=False)]
    if len(literal_title_matches) == len(query_words):
        return (
            "relevant",
            False,
            f"Article title directly matches all query terms: {', '.join(query_words)}.",
        )

    # 3. Check list prefix rule (Phase 3.3 regression: index/list lacking core query topic)
    is_list_title = any(title_lower.startswith(prefix) for prefix in RELEVANCE_LIST_PREFIXES)
    if is_list_title:
        missing_title = [w for w in query_words if not _term_matches_text(w, title_lower, allow_concept=True)]
        if missing_title:
            missing_str = ", ".join(missing_title)
            return (
                "weakly_relevant",
                True,
                (
                    f"Weakly related: Article is an index or list ('{title}') that lacks core query "
                    f"term(s) '{missing_str}' in its title."
                ),
            )

    # 4. Check for completely unrelated sources (neither title nor extract contains any query terms/concepts)
    concept_title_matches = [w for w in query_words if _term_matches_text(w, title_lower, allow_concept=True)]
    concept_snippet_matches = [w for w in query_words if _term_matches_text(w, snippet_lower, allow_concept=True)]

    if len(concept_title_matches) == 0 and len(concept_snippet_matches) == 0:
        query_str = ", ".join(query_words)
        return (
            "weakly_relevant",
            True,
            f"Weakly related: Neither title nor extract contains query key terms ({query_str}).",
        )

    # Check for incidental entities (person, company, vendor with ZERO query terms or concepts in title)
    if len(concept_title_matches) == 0:
        query_str = ", ".join(query_words)
        return (
            "weakly_relevant",
            True,
            (
                f"Weakly related: Article title '{title}' contains none of the query terms "
                f"({query_str}). The source appears to be an entity, person, vendor, "
                f"or peripheral topic with incidental mention in the extract."
            ),
        )

    # 5. Partition terms into core domain terms vs intent modifier terms
    core_terms = [w for w in query_words if w not in INTENT_MODIFIER_WORDS]
    if not core_terms:
        core_terms = query_words

    # 6. Concept-aware matching across title and snippet
    title_core = [w for w in core_terms if _term_matches_text(w, title_lower, allow_concept=True)]
    snippet_core = [w for w in core_terms if _term_matches_text(w, snippet_lower, allow_concept=True)]
    all_matched_core = set(title_core).union(snippet_core)
    query_str = ", ".join(query_words)

    # Concept group consolidation: Group core terms that belong to the same concept cluster
    # (e.g. 'artificial' and 'intelligence' are parts of the 'ai' cluster)
    concept_groups: List[Dict[str, Any]] = []
    clustered_terms: set = set()

    for c in CONCEPT_CLUSTERS:
        primary = c.get("primary") or c.get("terms", [])
        subtopics = c.get("subtopics") or c.get("broad", [])
        c_words = set()
        for phrase in primary + subtopics:
            for w in phrase.lower().split():
                c_words.add(w)

        c_core = [t for t in core_terms if t in c_words]
        if c_core:
            sat_title = any(t in title_core for t in c_core)
            sat_snippet = any(t in snippet_core for t in c_core)
            concept_groups.append({
                "id": c["id"],
                "terms": c_core,
                "in_title": sat_title,
                "in_snippet": sat_snippet,
                "satisfied": sat_title or sat_snippet,
            })
            clustered_terms.update(c_core)

    for t in core_terms:
        if t not in clustered_terms:
            sat_title = t in title_core
            sat_snippet = t in snippet_core
            concept_groups.append({
                "id": t,
                "terms": [t],
                "in_title": sat_title,
                "in_snippet": sat_snippet,
                "satisfied": sat_title or sat_snippet,
            })

    num_groups = len(concept_groups)
    sat_groups = [g for g in concept_groups if g["satisfied"]]
    sat_ratio = len(sat_groups) / max(1, num_groups)

    # If full query phrase is in snippet and title has at least one core match
    if query.lower() in snippet_lower and len(concept_title_matches) > 0:
        return (
            "relevant",
            False,
            f"Extract contains exact search phrase '{query}' and article title aligns with core terms.",
        )

    # 1. All core terms or concept groups satisfied
    if len(all_matched_core) == len(core_terms) or (num_groups > 0 and len(sat_groups) == num_groups):
        if len(snippet_core) == 0:
            return (
                "relevant",
                False,
                f"Source title directly covers all key query terms ({query_str}).",
            )
        return (
            "relevant",
            False,
            f"Source title and extract cover all key query terms ({query_str}).",
        )

    # 2. Single core term query and that core term is in title
    if len(core_terms) == 1 and core_terms[0] in title_core:
        return (
            "relevant",
            False,
            f"Source title contains primary query term '{core_terms[0]}'.",
        )

    # 3. When snippet/abstract is unavailable (e.g. Crossref records without abstract):
    # Title alone must satisfy >= 66% of distinct concept groups with >= 2 distinct groups satisfied
    title_sat_groups = [g for g in concept_groups if g["in_title"]]
    if len(snippet_core) == 0:
        if num_groups >= 3 and (len(title_sat_groups) / num_groups) >= 0.66 and len(title_sat_groups) >= 2:
            matched_str = ", ".join(sorted(title_core))
            return (
                "relevant",
                False,
                f"Source title substantiates core query concepts ({matched_str}).",
            )

    # 4. Multi-term queries: high proportion (>= 66%) of distinct concept groups satisfied across title AND snippet
    if num_groups >= 2 and sat_ratio >= 0.66 and len(title_core) >= 1 and len(snippet_core) >= 1:
        matched_str = ", ".join(sorted(all_matched_core))
        return (
            "relevant",
            False,
            f"Source title and extract substantiate core query concepts ({matched_str}).",
        )

    # Otherwise weakly relevant
    if len(all_matched_core) > 0:
        matched_str = ", ".join(sorted(all_matched_core))
        missing_groups = [g for g in concept_groups if not g["satisfied"]]
        missing = []
        for g in missing_groups:
            missing.extend(g["terms"])
        missing_str = ", ".join(missing) if missing else ", ".join([w for w in core_terms if w not in all_matched_core])
        return (
            "weakly_relevant",
            True,
            f"Weakly related: Source mentions '{matched_str}' but lacks core query terms '{missing_str}'.",
        )

    return (
        "weakly_relevant",
        True,
        f"Weakly related: Neither title nor extract contains query key terms ({query_str}).",
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

