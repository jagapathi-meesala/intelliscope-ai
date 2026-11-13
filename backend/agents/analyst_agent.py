"""
Insight Analyst Agent for IntelliScope AI.

Consumes structured research data and its verification report to produce
deterministic, explainable intelligence syntheses. Excludes invalid and
duplicate sources, grounds observations directly in verified evidence,
and identifies themes, keywords, information gaps, and recommendations.

Note:
    This agent uses explainable lexical analysis, frequency heuristics,
    and rule-based theme clustering. It does not use generative LLM APIs
    or fabricate unsupported claims.
"""

from collections import Counter
from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.models.analyst import (
    AnalysisRequest,
    AnalysisResponse,
    EvidenceObservation,
    KeyTheme,
)

logger = logging.getLogger(__name__)

# Agent metadata
AGENT_NAME = "Insight Analyst Agent"
AGENT_VERSION = "1.0.0"
AGENT_STATUS = "operational"
AGENT_CAPABILITIES = [
    "deterministic_text_analysis",
    "keyword_extraction",
    "theme_clustering",
    "evidence_grounding",
    "gap_identification",
    "verification_consistency_check",
]

# Convenience aliases
ANALYST_AGENT_NAME = AGENT_NAME
ANALYST_AGENT_VERSION = AGENT_VERSION
ANALYST_AGENT_STATUS = AGENT_STATUS
ANALYST_AGENT_CAPABILITIES = AGENT_CAPABILITIES

ANALYSIS_METHODOLOGY_DISCLOSURE = (
    "Deterministic keyword extraction, frequency analysis, and rule-based theme clustering. "
    "No generative LLM extrapolation."
)

# Standard English stop words for lexical normalization
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "also", "am", "an",
    "and", "any", "are", "aren't", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "cannot", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "itself", "just", "me", "more", "most", "my", "myself", "no",
    "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "with", "would",
    "you", "your", "yours", "yourself", "yourselves", "span", "class", "searchmatch",
}

# Thematic semantic clusters for rule-based grouping
THEME_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "Foundations & Theoretical Concepts": {
        "keywords": {
            "study", "science", "theory", "concept", "principle", "discipline",
            "intelligence", "understanding", "origin", "definition", "philosophy",
            "fundamental", "basis", "logic", "cognitive",
        },
        "description": "Fundamental principles, formal definitions, and theoretical underpinnings.",
    },
    "Systems, Architectures & Methods": {
        "keywords": {
            "system", "technology", "software", "machine", "algorithm", "model",
            "network", "device", "method", "computing", "learning", "computational",
            "structure", "process", "program", "neural", "hardware", "engineering",
        },
        "description": "Algorithmic architectures, computational methods, and engineering systems.",
    },
    "Applications & Operational Domains": {
        "keywords": {
            "application", "industry", "automation", "robotics", "health", "analysis",
            "data", "vision", "language", "speech", "processing", "business",
            "practical", "tool", "deployment", "use",
        },
        "description": "Real-world operational implementations and specialized domain deployments.",
    },
    "Ethics, Governance & Future Horizons": {
        "keywords": {
            "ethics", "governance", "future", "policy", "impact", "risk",
            "society", "safety", "human", "general", "social", "regulation",
            "challenge", "implication", "existential",
        },
        "description": "Societal implications, governance frameworks, and future trajectory analysis.",
    },
}


class AnalysisError(Exception):
    """Base exception for Insight Analyst Agent operations."""
    pass


class AnalysisValidationError(AnalysisError):
    """Raised when research and verification payloads are mismatched or inconsistent."""
    pass


def validate_report_consistency(research: Dict[str, Any], verification: Dict[str, Any]) -> None:
    """
    Validate the relational integrity and consistency between research and verification reports.

    Args:
        research: Raw or structured research dictionary.
        verification: Raw or structured verification report dictionary.

    Raises:
        AnalysisValidationError: If queries mismatch, counts differ, items diverge,
            or verification flags contradict reported statuses.
    """
    if not isinstance(research, dict):
        raise AnalysisValidationError("Research data must be a dictionary object")
    if not isinstance(verification, dict):
        raise AnalysisValidationError("Verification data must be a dictionary object")

    r_query = str(research.get("query", "")).strip().lower()
    v_query = str(verification.get("query", "")).strip().lower()

    if r_query != v_query:
        raise AnalysisValidationError(
            f"Research query '{r_query}' does not match verification report query '{v_query}'"
        )

    r_results = research.get("results")
    v_results = verification.get("results")

    if not isinstance(r_results, list):
        raise AnalysisValidationError("Research 'results' must be a list")
    if not isinstance(v_results, list):
        raise AnalysisValidationError("Verification 'results' must be a list")

    v_total = verification.get("total_results", len(v_results))
    if len(r_results) != len(v_results) or len(r_results) != v_total:
        raise AnalysisValidationError(
            f"Count mismatch: research contains {len(r_results)} results, "
            f"but verification reports {len(v_results)} results (total_results: {v_total})"
        )

    # Validate item correspondence and inspect flags for tampering
    for idx, (r_item, v_item) in enumerate(zip(r_results, v_results)):
        if not isinstance(r_item, dict) or not isinstance(v_item, dict):
            continue

        r_url = (r_item.get("source_url") or r_item.get("source") or "").strip().rstrip("/")
        v_url = (v_item.get("source_url") or "").strip().rstrip("/")

        if r_url and v_url and r_url != v_url:
            raise AnalysisValidationError(
                f"Source URL mismatch at item index {idx}: research URL '{r_url}' "
                f"does not match verification report URL '{v_url}'"
            )

        # Integrity verification: do not trust reported status if checks failed
        checks = v_item.get("checks", {})
        errors = v_item.get("errors", [])
        status = v_item.get("status", "")

        essential_failed = (
            checks.get("https_valid") is False
            or checks.get("domain_allowed") is False
            or checks.get("title_valid") is False
            or checks.get("snippet_valid") is False
            or checks.get("doi_valid") is False
        )

        if status == "valid" and (essential_failed or len(errors) > 0):
            raise AnalysisValidationError(
                f"Inconsistent verification report: item at index {idx} claims 'valid' "
                f"status but failed essential checks or reported errors"
            )

        if checks.get("is_duplicate_url") and status == "valid":
            raise AnalysisValidationError(
                f"Inconsistent verification report: duplicate item at index {idx} "
                f"is erroneously flagged as 'valid'"
            )


def extract_keywords(texts: List[str], top_n: int = 8) -> List[str]:
    """
    Extract key terms deterministically based on frequency filtering and tokenization.

    Args:
        texts: List of text strings to analyze.
        top_n: Maximum number of keywords to return.

    Returns:
        List of prominent keywords in descending order of frequency.
    """
    counter: Counter = Counter()

    for text in texts:
        if not text or not isinstance(text, str):
            continue
        # Extract word tokens (letters only, min length 3)
        tokens = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        for token in tokens:
            if token not in STOP_WORDS:
                counter[token] += 1

    return [word for word, _ in counter.most_common(top_n)]


def filter_eligible_evidence(
    research_results: List[Dict[str, Any]],
    verification_results: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, List[str]]:
    """
    Filter research items based on individual verification check diagnostics.

    Returns:
        Tuple of (eligible_items, excluded_count, exclusion_reasons)
    """
    eligible: List[Dict[str, Any]] = []
    excluded_count = 0
    exclusion_reasons: List[str] = []

    for idx, (r_item, v_item) in enumerate(zip(research_results, verification_results)):
        if not isinstance(r_item, dict) or not isinstance(v_item, dict):
            excluded_count += 1
            exclusion_reasons.append(f"Item {idx}: Malformed item object")
            continue

        checks = v_item.get("checks", {})
        status = v_item.get("status", "")
        errors = v_item.get("errors", [])

        # Check all eligibility criteria
        title_ok = checks.get("title_valid", False)
        snippet_ok = checks.get("snippet_valid", False)
        https_ok = checks.get("https_valid", False)
        domain_ok = checks.get("domain_allowed", False)
        ts_ok = checks.get("timestamp_valid", True)
        dup_url = checks.get("is_duplicate_url", False)
        dup_title = checks.get("is_duplicate_title", False)
        doi_ok = checks.get("doi_valid") is not False
        dup_doi = checks.get("is_duplicate_doi", False)

        is_eligible = (
            title_ok
            and snippet_ok
            and https_ok
            and domain_ok
            and ts_ok
            and doi_ok
            and not dup_url
            and not dup_title
            and not dup_doi
            and status != "invalid"
            and len(errors) == 0
        )

        if is_eligible:
            eligible.append(r_item)
        else:
            excluded_count += 1
            reasons = []
            if not https_ok:
                reasons.append("insecure protocol")
            if not domain_ok:
                reasons.append("disallowed domain")
            if not doi_ok:
                reasons.append("invalid DOI")
            if dup_url or dup_title or dup_doi:
                reasons.append("duplicate record")
            if not title_ok or not snippet_ok:
                reasons.append("missing title/snippet")
            if not ts_ok:
                reasons.append("invalid timestamp")
            exclusion_reasons.append(f"Item {idx}: {', '.join(reasons) or 'verification failure'}")

    return eligible, excluded_count, exclusion_reasons


def cluster_themes(items: List[Dict[str, Any]]) -> List[KeyTheme]:
    """
    Cluster eligible items into categorical themes using deterministic keyword matching.

    Args:
        items: List of eligible research items.

    Returns:
        List of KeyTheme objects with frequency and supporting source URLs.
    """
    if not items:
        return []

    theme_matches: Dict[str, Dict[str, Any]] = {}

    for item in items:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        url = item.get("source_url") or item.get("source", "")
        text_corpus = f"{title} {snippet}".lower()
        matched_any = False

        for theme_name, meta in THEME_TAXONOMY.items():
            keywords = meta["keywords"]
            if any(kw in text_corpus for kw in keywords):
                matched_any = True
                if theme_name not in theme_matches:
                    theme_matches[theme_name] = {
                        "theme": theme_name,
                        "description": meta["description"],
                        "frequency": 0,
                        "sources": [],
                    }
                theme_matches[theme_name]["frequency"] += 1
                if url and url not in theme_matches[theme_name]["sources"]:
                    theme_matches[theme_name]["sources"].append(url)

        # Fallback if no taxonomy category matched: cluster under general topic
        if not matched_any:
            fallback_theme = f"Core Overview: {title}"
            if fallback_theme not in theme_matches:
                theme_matches[fallback_theme] = {
                    "theme": fallback_theme,
                    "description": f"Domain context and references anchored around '{title}'.",
                    "frequency": 0,
                    "sources": [],
                }
            theme_matches[fallback_theme]["frequency"] += 1
            if url and url not in theme_matches[fallback_theme]["sources"]:
                theme_matches[fallback_theme]["sources"].append(url)

    # Sort themes by frequency descending
    sorted_themes = sorted(theme_matches.values(), key=lambda t: t["frequency"], reverse=True)
    return [KeyTheme(**t) for t in sorted_themes]


def assess_observation_confidence(
    item: Dict[str, Any],
    verification_item: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Assess confidence rating ('high', 'medium', 'low') transparently.

    Criteria:
    - Low confidence: Item is weakly relevant to the query topic.
    - Medium confidence: Item has advisory verification warnings, or extract is short (< 60 chars).
    - High confidence: Directly relevant source with substantive extract and no verification warnings.

    Returns:
        Tuple of (confidence_level, confidence_reason)
    """
    is_weak = bool(
        item.get("is_weakly_relevant", False)
        or item.get("relevance") == "weakly_relevant"
        or (verification_item and verification_item.get("is_weakly_relevant"))
    )
    if is_weak:
        reason = item.get("relevance_reason") or "Source is weakly relevant to research topic."
        return "low", f"Weak topical relevance: {reason}"

    v_warnings = verification_item.get("warnings", []) if verification_item else []
    snippet_len = len(item.get("snippet", "").strip())

    if len(v_warnings) > 0:
        return "medium", f"Verification advisory warnings present: {'; '.join(v_warnings)}."

    if snippet_len < 60:
        return "medium", f"Brief evidence extract ({snippet_len} chars) provides limited contextual depth."

    return "high", "Direct topical relevance with substantive verified extract and no verification defects."


def build_observations(
    items: List[Dict[str, Any]],
    verification_results: Optional[List[Dict[str, Any]]] = None,
) -> List[EvidenceObservation]:
    """
    Construct evidence-backed observations anchored directly in verified snippets and URLs.
    Assigns confidence dynamically based on topical relevance, extract length, and verification warnings.

    Args:
        items: List of eligible research items.
        verification_results: Optional list of corresponding verification item reports.

    Returns:
        List of EvidenceObservation models.
    """
    observations: List[EvidenceObservation] = []

    # Map verification reports by source_url or index for fast lookup
    v_map: Dict[str, Dict[str, Any]] = {}
    if verification_results:
        for v in verification_results:
            if isinstance(v, dict):
                v_url = (v.get("source_url") or "").strip().rstrip("/")
                if v_url:
                    v_map[v_url] = v

    for idx, item in enumerate(items):
        title = item.get("title", "Untitled Source")
        snippet = item.get("snippet", "").strip()
        url = item.get("source_url") or item.get("source", "")
        norm_url = url.strip().rstrip("/")

        if not snippet:
            continue

        clean_statement = snippet.rstrip(".")
        statement = f"According to '{title}': {clean_statement}."

        v_item = v_map.get(norm_url) if norm_url else None
        if not v_item and verification_results and idx < len(verification_results):
            v_item = verification_results[idx]

        confidence, confidence_reason = assess_observation_confidence(item, v_item)
        is_weak = (confidence == "low")
        source_name = str(item.get("source_name") or "wikipedia").strip().lower()
        source_type = str(item.get("source_type") or "wikipedia_extract").strip()
        pub_date = item.get("publication_date")
        doi = item.get("doi")
        raw_authors = item.get("authors")
        authors = [str(a).strip() for a in raw_authors if str(a).strip()] if isinstance(raw_authors, list) else []

        observations.append(
            EvidenceObservation(
                statement=statement,
                source_title=title,
                source_url=url,
                confidence=confidence,
                confidence_reason=confidence_reason,
                is_weakly_relevant=is_weak,
                source_name=source_name,
                source_type=source_type,
                publication_date=pub_date if isinstance(pub_date, str) else None,
                doi=doi if isinstance(doi, str) else None,
                authors=authors,
            )
        )

    return observations


def generate_executive_summary(
    topic: str,
    eligible_items: List[Dict[str, Any]],
    themes: List[KeyTheme],
    keywords: List[str],
) -> str:
    """Generate a concise narrative summary grounded strictly in evidence."""
    if not eligible_items:
        return (
            f"No eligible verified evidence was available to synthesize an analysis for topic '{topic}'. "
            "All provided records either failed verification checks, were duplicates, or contained malformed data."
        )

    theme_names = [t.theme for t in themes[:3]]
    theme_str = ", ".join(f"'{name}'" for name in theme_names) if theme_names else "general subject areas"
    kw_str = ", ".join(keywords[:5]) if keywords else "key technical terms"

    lead_item = eligible_items[0]
    lead_snippet = lead_item.get("snippet", "").rstrip(".")

    summary = (
        f"Synthesized research on '{topic}' across {len(eligible_items)} verified source(s). "
        f"Primary thematic focus centers on {theme_str}, with recurring terminology including {kw_str}. "
        f"Initial evidence from '{lead_item.get('title')}' establishes that {lead_snippet}."
    )

    weak_count = sum(
        1 for item in eligible_items
        if item.get("is_weakly_relevant") or item.get("relevance") == "weakly_relevant"
    )
    if weak_count == len(eligible_items):
        summary += " Caution: All available eligible sources provide only peripheral or weakly relevant coverage of this topic."
    elif len(eligible_items) == 1:
        summary += " Evidence base is constrained to a single verified source."

    return summary


def identify_information_gaps(
    topic: str,
    eligible_items: List[Dict[str, Any]],
    excluded_count: int,
    source_errors: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Identify empirical and structural gaps in the research base."""
    gaps: List[str] = []

    if source_errors:
        for src, err in source_errors.items():
            gaps.append(f"Partial retrieval failure from provider '{src}': {err}")

    if not eligible_items:
        gaps.append(f"Zero eligible sources available for topic '{topic}'.")
        gaps.append("All provided source candidates were excluded due to validation failures or duplication.")
        return gaps

    if len(eligible_items) < 3:
        gaps.append(
            f"Limited source diversity: Only {len(eligible_items)} eligible source(s) met verification standards."
        )

    if excluded_count > 0:
        gaps.append(
            f"Source attrition: {excluded_count} candidate record(s) were excluded due to verification failures."
        )

    weakly_relevant_count = sum(
        1 for item in eligible_items
        if item.get("is_weakly_relevant") or item.get("relevance") == "weakly_relevant"
    )
    if weakly_relevant_count > 0:
        gaps.append(
            f"Topical relevance constraint: {weakly_relevant_count} source(s) provide only peripheral or incidental context."
        )

    if len(eligible_items) <= 1:
        gaps.append(
            "Sparse evidence base: Cross-source corroboration is constrained by having fewer than two verified sources."
        )

    source_names = {str(item.get("source_name") or "wikipedia").lower() for item in eligible_items}
    if source_names == {"wikipedia"}:
        gaps.append("Evidence is derived from encyclopedia summary snippets rather than full primary papers.")
    else:
        gaps.append(
            "Evidence relies on abstracts, encyclopedia extracts, and publication metadata rather than full-text PDF bodies."
        )
    gaps.append("Real-time chronological updates and empirical benchmark tables are unrepresented in summary extracts.")

    return gaps


def generate_recommendations(
    topic: str,
    themes: List[KeyTheme],
    keywords: List[str],
    has_evidence: bool,
) -> List[str]:
    """Generate deterministic, actionable recommendations based on findings."""
    if not has_evidence:
        return [
            f"Broaden research parameters and query variations for '{topic}'.",
            "Validate source URLs, HTTPS protocol, and payload formatting prior to re-submission.",
            "Incorporate authoritative primary repositories to obtain valid evidence records.",
        ]

    recs: List[str] = []
    if themes:
        top_theme = themes[0].theme
        recs.append(f"Deepen primary literature review specifically targeting '{top_theme}'.")

    if keywords:
        sub_kws = ", ".join(keywords[:4])
        recs.append(f"Expand query retrieval using specific extracted keywords: {sub_kws}.")

    recs.append("Conduct multi-source fact cross-referencing against peer-reviewed journals.")
    return recs


async def analyze_research(
    payload: Union[AnalysisRequest, Dict[str, Any]],
    verification_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Asynchronously analyze research results using verified evidence.

    Accepts structured research and verification data, checks relational
    consistency, excludes ineligible/duplicate records, and generates
    structured intelligence observations.

    Args:
        payload: AnalysisRequest instance or dictionary containing research & verification.
        verification_payload: Optional separate verification dictionary if not packaged in payload.

    Returns:
        Structured analysis report dictionary.

    Raises:
        AnalysisValidationError: If reports are mismatched, tampered, or inconsistent.
    """
    if isinstance(payload, AnalysisRequest):
        data = payload.model_dump()
        research_data = data.get("research", {})
        verification_data = data.get("verification", {})
    elif isinstance(payload, dict):
        if "research" in payload and "verification" in payload:
            research_data = payload.get("research", {})
            verification_data = payload.get("verification", {})
        else:
            research_data = payload
            verification_data = verification_payload or {}
    else:
        raise AnalysisValidationError("Payload must be an AnalysisRequest or dictionary object")

    # Validate relational consistency between research and verification reports
    validate_report_consistency(research_data, verification_data)

    topic = str(research_data.get("query", "")).strip()
    r_results = research_data.get("results", [])
    v_results = verification_data.get("results", [])
    total_sources = len(r_results)

    # Filter eligible evidence based on verification diagnostics
    eligible_items, excluded_count, _ = filter_eligible_evidence(r_results, v_results)
    eligible_count = len(eligible_items)

    analysis_timestamp = datetime.now(timezone.utc).isoformat()

    # Extract text corpus for keyword analysis
    text_corpus = [
        f"{item.get('title', '')} {item.get('snippet', '')}"
        for item in eligible_items
    ]
    keywords = extract_keywords(text_corpus, top_n=8)
    themes = cluster_themes(eligible_items)
    observations = build_observations(eligible_items, v_results)
    summary = generate_executive_summary(topic, eligible_items, themes, keywords)
    source_errors = research_data.get("source_errors") if isinstance(research_data.get("source_errors"), dict) else None
    gaps = identify_information_gaps(topic, eligible_items, excluded_count, source_errors=source_errors)
    recs = generate_recommendations(topic, themes, keywords, has_evidence=(eligible_count > 0))

    source_distribution = dict(
        Counter(str(item.get("source_name") or "wikipedia").strip().lower() for item in eligible_items)
    )

    limitations = [
        "Analysis relies on deterministic lexical extraction, keyword frequency weighting, and rule-based clustering without generative LLM extrapolation.",
        "Findings are constrained strictly to text extracts and abstracts verified by the Research Verification Agent.",
        "Structural validity confirms protocol and domain compliance, not infallible factual truth.",
        "Confidence ratings reflect evidence depth and topical relevance, not absolute empirical certainty.",
    ]
    if eligible_count == 0:
        limitations.append("Analysis concluded with zero eligible evidence records due to validation failures.")

    return {
        "agent": AGENT_NAME,
        "agent_name": AGENT_NAME,
        "topic": topic,
        "analyzed_at": analysis_timestamp,
        "total_sources_evaluated": total_sources,
        "eligible_sources_count": eligible_count,
        "excluded_sources_count": excluded_count,
        "source_distribution": source_distribution,
        "executive_summary": summary,
        "key_themes": [t.model_dump() for t in themes],
        "important_keywords": keywords,
        "evidence_backed_observations": [obs.model_dump() for obs in observations],
        "information_gaps": gaps,
        "recommendations": recs,
        "limitations": limitations,
        "methodology": ANALYSIS_METHODOLOGY_DISCLOSURE,
    }
