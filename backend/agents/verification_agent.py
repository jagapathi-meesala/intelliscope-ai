"""
Research Verification Agent for IntelliScope AI.

Responsible for validating structural integrity, URL protocol compliance,
domain whitelist adherence, deduplication, and retrieval timestamps of
research data gathered by the Data Collector Agent.

Note:
    This agent explicitly validates structural and source integrity.
    It does NOT assert or guarantee the factual truthfulness of claims
    within text snippets.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from backend.config import settings
from backend.models.verification import VerificationRequest

logger = logging.getLogger(__name__)

# Agent metadata
AGENT_NAME = "Research Verification Agent"
AGENT_VERSION = "1.0.0"
AGENT_STATUS = "operational"
AGENT_CAPABILITIES = [
    "structural_schema_validation",
    "https_protocol_verification",
    "domain_whitelist_enforcement",
    "deduplication_analysis",
    "iso_timestamp_validation",
    "quality_score_calculation",
]

FACTUAL_ACCURACY_DISCLAIMER = (
    "This verification evaluates structural integrity, URL protocol compliance, "
    "domain whitelist adherence, timestamp validity, and deduplication. "
    "It does NOT assert that the factual claims within snippets are verified facts."
)


def _validate_title(raw_title: Any) -> Tuple[bool, Optional[str]]:
    """Validate that title is a non-empty string."""
    if raw_title is None:
        return False, "Missing required field: 'title'"
    if not isinstance(raw_title, str):
        return False, f"Field 'title' must be a string, got {type(raw_title).__name__}"
    if not raw_title.strip():
        return False, "Field 'title' cannot be empty or whitespace"
    return True, None


def _validate_snippet(raw_snippet: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate snippet presence, type, and length."""
    if raw_snippet is None:
        return False, "Missing required field: 'snippet'", None
    if not isinstance(raw_snippet, str):
        return False, f"Field 'snippet' must be a string, got {type(raw_snippet).__name__}", None
    stripped = raw_snippet.strip()
    if not stripped:
        return False, "Field 'snippet' cannot be empty or whitespace", None
    warning = None
    if len(stripped) < 15:
        warning = f"Snippet is unusually short ({len(stripped)} characters)"
    return True, None, warning


def _validate_url(raw_url: Any, allowed_domains: List[str]) -> Tuple[bool, bool, Optional[str], Optional[str]]:
    """
    Validate URL structure, protocol, and domain allowance.

    Returns:
        (https_valid, domain_allowed, error_msg, canonical_url)
    """
    if raw_url is None:
        return False, False, "Missing source URL ('source_url' or 'source')", None
    if not isinstance(raw_url, str):
        return False, False, f"Source URL must be a string, got {type(raw_url).__name__}", None
    url_str = raw_url.strip()
    if not url_str:
        return False, False, "Source URL cannot be empty", None

    try:
        parsed = urlparse(url_str)
    except Exception as exc:
        return False, False, f"Malformed source URL: {exc}", None

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if not netloc:
        return False, False, "Source URL lacks a valid network host", None

    # Strip port if present
    host = netloc.split(":")[0]

    # Check HTTPS scheme
    https_valid = (scheme == "https")
    protocol_error = None
    if not https_valid:
        if scheme == "http":
            protocol_error = "Insecure protocol: source URL must use HTTPS (found 'http')"
        else:
            protocol_error = f"Invalid protocol: source URL must use HTTPS (found '{scheme or 'none'}')"

    # Check allowed domain
    domain_allowed = False
    for allowed in allowed_domains:
        allowed = allowed.lower()
        if host == allowed or host.endswith("." + allowed):
            domain_allowed = True
            break

    domain_error = None
    if not domain_allowed:
        domain_error = (
            f"Source domain '{host}' is not in allowed domains list "
            f"(allowed: {', '.join(allowed_domains)})"
        )

    # Combine errors if any
    error = protocol_error or domain_error
    if protocol_error and domain_error:
        error = f"{protocol_error}; {domain_error}"

    canonical_url = f"{scheme}://{netloc}{parsed.path}".rstrip("/")
    return https_valid, domain_allowed, error, canonical_url


def _validate_timestamp(raw_timestamp: Any) -> Tuple[bool, Optional[str]]:
    """Validate ISO 8601 timestamp string."""
    if raw_timestamp is None:
        return False, "Missing required field: 'retrieved_at'"
    if not isinstance(raw_timestamp, str):
        return False, f"Field 'retrieved_at' must be a string, got {type(raw_timestamp).__name__}"
    ts_str = raw_timestamp.strip()
    if not ts_str:
        return False, "Field 'retrieved_at' cannot be empty"

    try:
        normalized = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.year < 2000 or dt.year > 2100:
            return False, f"Timestamp year ({dt.year}) outside realistic range (2000-2100)"
        return True, None
    except Exception:
        return False, f"Invalid ISO 8601 timestamp format: '{ts_str}'"


def _calculate_item_score(
    title_valid: bool,
    snippet_valid: bool,
    has_snippet_warning: bool,
    https_valid: bool,
    domain_allowed: bool,
    timestamp_valid: bool,
    is_duplicate_url: bool,
    is_duplicate_title: bool,
) -> float:
    """
    Calculate transparent quality score (0 to 100) for a single item.

    Rubric:
    - Title: 20 pts (valid), 10 pts (if duplicate title), 0 pts (missing/invalid)
    - Snippet: 20 pts (valid >=15 chars), 10 pts (short), 0 pts (missing/invalid)
    - Source URL & HTTPS: 25 pts (valid HTTPS), 5 pts (HTTP), 0 pts (missing/malformed)
    - Domain compliance: 20 pts (allowed Wikipedia source), 0 pts (disallowed)
    - Timestamp: 15 pts (valid ISO 8601), 0 pts (missing/invalid)
    - Deduplication penalty: -15 pts if duplicate URL in batch.
    """
    score = 0.0

    # Title component (20 pts max)
    if title_valid:
        score += 10.0 if is_duplicate_title else 20.0

    # Snippet component (20 pts max)
    if snippet_valid:
        score += 10.0 if has_snippet_warning else 20.0

    # HTTPS URL component (25 pts max)
    if https_valid:
        score += 25.0
    elif not https_valid and domain_allowed:
        score += 5.0  # HTTP with valid domain

    # Domain compliance (20 pts max)
    if domain_allowed:
        score += 20.0

    # Timestamp validity (15 pts max)
    if timestamp_valid:
        score += 15.0

    # Penalty for duplicate URL
    if is_duplicate_url:
        score -= 15.0

    return max(0.0, min(100.0, round(score, 2)))


async def verify_research(
    data: Union[VerificationRequest, Dict[str, Any]],
    allowed_domains: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Asynchronously verify research results collected by the Data Collector Agent.

    Evaluates structural compliance, URL protocol, allowed domain whitelist,
    deduplication, and timestamp validity. Produces a transparent quality score
    and per-item verification diagnostics.

    Args:
        data: VerificationRequest instance or dictionary containing research results.
        allowed_domains: Optional list of allowed domain names (defaults to settings).

    Returns:
        Structured verification report dictionary.
    """
    if isinstance(data, VerificationRequest):
        payload = data.model_dump()
    elif isinstance(data, dict):
        payload = data
    else:
        payload = {}

    domains_to_check = allowed_domains or settings.ALLOWED_SOURCE_DOMAINS
    query = str(payload.get("query", "") or "")
    raw_results = payload.get("results")

    # Handle non-list results safely
    if not isinstance(raw_results, list):
        raw_results = []

    verification_timestamp = datetime.now(timezone.utc).isoformat()
    total_results = len(raw_results)

    # Empty input handling
    if total_results == 0:
        return {
            "agent": AGENT_NAME,
            "agent_name": AGENT_NAME,
            "query": query,
            "verified_at": verification_timestamp,
            "total_results": 0,
            "valid_results_count": 0,
            "invalid_results_count": 0,
            "structurally_valid_count": 0,
            "directly_relevant_count": 0,
            "weakly_relevant_count": 0,
            "excluded_count": 0,
            "quality_score": 0.0,
            "status": "failed",
            "verification_type": "structural_and_source_integrity",
            "is_factually_verified": False,
            "factual_accuracy_disclaimer": FACTUAL_ACCURACY_DISCLAIMER,
            "summary": {
                "total_checks": 0,
                "passed_checks": 0,
                "failed_checks": 0,
                "warning_count": 1,
                "error_count": 1,
                "duplicate_urls_count": 0,
                "duplicate_titles_count": 0,
                "structurally_valid_count": 0,
                "directly_relevant_count": 0,
                "weakly_relevant_count": 0,
                "excluded_count": 0,
            },
            "results": [],
        }

    seen_urls: Dict[str, int] = {}
    seen_titles: Dict[str, int] = {}
    reports: List[Dict[str, Any]] = []

    total_checks_count = 0
    passed_checks_count = 0
    failed_checks_count = 0
    total_warnings_count = 0
    total_errors_count = 0
    duplicate_urls_count = 0
    duplicate_titles_count = 0
    valid_results_count = 0
    invalid_results_count = 0

    for idx, item in enumerate(raw_results):
        item_errors: List[str] = []
        item_warnings: List[str] = []

        if not isinstance(item, dict):
            item_errors.append(f"Result item at index {idx} is not a valid dictionary object")
            total_checks_count += 7
            failed_checks_count += 7
            total_errors_count += 1
            invalid_results_count += 1
            reports.append({
                "index": idx,
                "title": None,
                "source_url": None,
                "status": "invalid",
                "item_score": 0.0,
                "is_weakly_relevant": False,
                "relevance_reason": None,
                "checks": {
                    "title_valid": False,
                    "snippet_valid": False,
                    "https_valid": False,
                    "domain_allowed": False,
                    "timestamp_valid": False,
                    "is_duplicate_url": False,
                    "is_duplicate_title": False,
                },
                "errors": item_errors,
                "warnings": item_warnings,
            })
            continue

        raw_title = item.get("title")
        raw_snippet = item.get("snippet")
        raw_url = item.get("source_url") or item.get("source")
        raw_ts = item.get("retrieved_at")

        # 1. Title check
        title_ok, title_err = _validate_title(raw_title)
        total_checks_count += 1
        if title_ok:
            passed_checks_count += 1
        else:
            failed_checks_count += 1
            item_errors.append(title_err)

        # 2. Snippet check
        snippet_ok, snippet_err, snippet_warn = _validate_snippet(raw_snippet)
        total_checks_count += 1
        if snippet_ok:
            passed_checks_count += 1
        else:
            failed_checks_count += 1
            item_errors.append(snippet_err)
        if snippet_warn:
            item_warnings.append(snippet_warn)
            total_warnings_count += 1

        # 3. URL, HTTPS protocol, and domain check
        https_ok, domain_ok, url_err, canonical_url = _validate_url(raw_url, domains_to_check)
        total_checks_count += 2
        if https_ok:
            passed_checks_count += 1
        else:
            failed_checks_count += 1

        if domain_ok:
            passed_checks_count += 1
        else:
            failed_checks_count += 1

        if url_err:
            item_errors.append(url_err)

        # 4. Timestamp check
        ts_ok, ts_err = _validate_timestamp(raw_ts)
        total_checks_count += 1
        if ts_ok:
            passed_checks_count += 1
        else:
            failed_checks_count += 1
            item_errors.append(ts_err)

        # 5. Duplicate checks
        is_dup_url = False
        is_dup_title = False
        total_checks_count += 2

        # Check URL duplication
        if canonical_url:
            if canonical_url in seen_urls:
                is_dup_url = True
                failed_checks_count += 1
                duplicate_urls_count += 1
                first_seen_idx = seen_urls[canonical_url]
                item_warnings.append(
                    f"Duplicate source URL: already seen at result index {first_seen_idx}"
                )
                total_warnings_count += 1
            else:
                passed_checks_count += 1
                seen_urls[canonical_url] = idx
        else:
            failed_checks_count += 1

        # Check title duplication
        if title_ok and isinstance(raw_title, str):
            norm_title = raw_title.strip().lower()
            if norm_title in seen_titles:
                is_dup_title = True
                failed_checks_count += 1
                duplicate_titles_count += 1
                first_seen_idx = seen_titles[norm_title]
                item_warnings.append(
                    f"Duplicate article title: already seen at result index {first_seen_idx}"
                )
                total_warnings_count += 1
            else:
                passed_checks_count += 1
                seen_titles[norm_title] = idx
        else:
            failed_checks_count += 1

        # 6. Check transparent relevance status
        is_weak = bool(item.get("is_weakly_relevant", False) or item.get("relevance") == "weakly_relevant")
        relevance_reason = item.get("relevance_reason")
        if is_weak:
            item_warnings.append(
                f"Weakly related source: {relevance_reason or 'Source has only peripheral or incidental relevance to the query.'}"
            )
            total_warnings_count += 1

        # Compute item quality score
        item_score = _calculate_item_score(
            title_valid=title_ok,
            snippet_valid=snippet_ok,
            has_snippet_warning=(snippet_warn is not None),
            https_valid=https_ok,
            domain_allowed=domain_ok,
            timestamp_valid=ts_ok,
            is_duplicate_url=is_dup_url,
            is_duplicate_title=is_dup_title,
        )

        total_errors_count += len(item_errors)

        if len(item_errors) > 0:
            item_status = "invalid"
            invalid_results_count += 1
        elif len(item_warnings) > 0:
            item_status = "warning"
            valid_results_count += 1
        else:
            item_status = "valid"
            valid_results_count += 1

        reports.append({
            "index": idx,
            "title": raw_title if isinstance(raw_title, str) else None,
            "source_url": raw_url if isinstance(raw_url, str) else None,
            "status": item_status,
            "item_score": item_score,
            "is_weakly_relevant": is_weak,
            "relevance_reason": relevance_reason,
            "checks": {
                "title_valid": title_ok,
                "snippet_valid": snippet_ok,
                "https_valid": https_ok,
                "domain_allowed": domain_ok,
                "timestamp_valid": ts_ok,
                "is_duplicate_url": is_dup_url,
                "is_duplicate_title": is_dup_title,
            },
            "errors": item_errors,
            "warnings": item_warnings,
        })

    # Overall batch score
    overall_score = round(sum(r["item_score"] for r in reports) / total_results, 2)

    # Determine batch status
    if invalid_results_count == 0 and total_warnings_count == 0 and overall_score >= 80.0:
        batch_status = "passed"
    elif invalid_results_count == 0 and overall_score >= 50.0:
        batch_status = "passed_with_warnings"
    else:
        batch_status = "failed"

    structurally_valid_count = valid_results_count
    excluded_count = invalid_results_count
    directly_relevant_count = sum(
        1 for r in reports if r["status"] in ("valid", "warning") and not r.get("is_weakly_relevant", False)
    )
    weakly_relevant_count = sum(1 for r in reports if r.get("is_weakly_relevant", False))

    return {
        "agent": AGENT_NAME,
        "agent_name": AGENT_NAME,
        "query": query,
        "verified_at": verification_timestamp,
        "total_results": total_results,
        "valid_results_count": valid_results_count,
        "invalid_results_count": invalid_results_count,
        "structurally_valid_count": structurally_valid_count,
        "directly_relevant_count": directly_relevant_count,
        "weakly_relevant_count": weakly_relevant_count,
        "excluded_count": excluded_count,
        "quality_score": overall_score,
        "status": batch_status,
        "verification_type": "structural_and_source_integrity",
        "is_factually_verified": False,
        "factual_accuracy_disclaimer": FACTUAL_ACCURACY_DISCLAIMER,
        "summary": {
            "total_checks": total_checks_count,
            "passed_checks": passed_checks_count,
            "failed_checks": failed_checks_count,
            "warning_count": total_warnings_count,
            "error_count": total_errors_count,
            "duplicate_urls_count": duplicate_urls_count,
            "duplicate_titles_count": duplicate_titles_count,
            "structurally_valid_count": structurally_valid_count,
            "directly_relevant_count": directly_relevant_count,
            "weakly_relevant_count": weakly_relevant_count,
            "excluded_count": excluded_count,
        },
        "results": reports,
    }

