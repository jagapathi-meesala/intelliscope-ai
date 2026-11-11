"""
Dashboard Builder Agent for IntelliScope AI.

Transforms the Insight Analyst Agent's structured output into a safe, validated
dashboard specification JSON. The resulting specification contains titles, KPIs,
evidence citations, thematic structures, and chart specifications suitable for
rendering by the React frontend.

Note:
    This agent produces a declarative, static JSON specification. It never
    executes arbitrary code or generates unsafe HTML/JavaScript.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Union
from urllib.parse import urlparse
import uuid

from backend.models.analyst import AnalysisResponse
from backend.models.dashboard import (
    ChartDataPoint,
    ChartSpec,
    DashboardObservation,
    DashboardResponse,
    KPICard,
)

logger = logging.getLogger(__name__)

# Agent metadata
AGENT_NAME = "Dashboard Builder Agent"
AGENT_VERSION = "1.0.0"
AGENT_STATUS = "operational"
AGENT_CAPABILITIES = [
    "dashboard_specification_generation",
    "kpi_metric_synthesis",
    "chart_specification_derivation",
    "url_safety_enforcement",
    "schema_validation",
]

# Convenience aliases
BUILDER_AGENT_NAME = AGENT_NAME
BUILDER_AGENT_VERSION = AGENT_VERSION
BUILDER_AGENT_STATUS = AGENT_STATUS
BUILDER_AGENT_CAPABILITIES = AGENT_CAPABILITIES


class DashboardBuilderError(Exception):
    """Base exception for Dashboard Builder Agent operations."""
    pass


class DashboardValidationError(DashboardBuilderError):
    """Raised when analyst input is malformed, inconsistent, or contains unsafe URLs."""
    pass


def _validate_analysis_payload(payload: Dict[str, Any]) -> None:
    """
    Validate that the incoming analysis payload contains all required fields,
    safe URLs, and valid numeric boundaries.

    Raises:
        DashboardValidationError: If the payload violates validation rules.
    """
    if not isinstance(payload, dict):
        raise DashboardValidationError("Analysis payload must be a dictionary object")

    topic = payload.get("topic")
    if not topic or not isinstance(topic, str) or not topic.strip():
        raise DashboardValidationError("Analysis payload missing valid non-empty 'topic'")

    exec_summary = payload.get("executive_summary")
    if not exec_summary or not isinstance(exec_summary, str) or not exec_summary.strip():
        raise DashboardValidationError("Analysis payload missing valid non-empty 'executive_summary'")

    total_sources = payload.get("total_sources_evaluated", 0)
    eligible_sources = payload.get("eligible_sources_count", 0)
    excluded_sources = payload.get("excluded_sources_count", 0)

    if not isinstance(total_sources, int) or total_sources < 0:
        raise DashboardValidationError("Field 'total_sources_evaluated' must be a non-negative integer")
    if not isinstance(eligible_sources, int) or eligible_sources < 0:
        raise DashboardValidationError("Field 'eligible_sources_count' must be a non-negative integer")
    if not isinstance(excluded_sources, int) or excluded_sources < 0:
        raise DashboardValidationError("Field 'excluded_sources_count' must be a non-negative integer")

    observations = payload.get("evidence_backed_observations", [])
    if not isinstance(observations, list):
        raise DashboardValidationError("Field 'evidence_backed_observations' must be a list")

    # Safety check: audit every source URL
    for idx, obs in enumerate(observations):
        if not isinstance(obs, dict):
            raise DashboardValidationError(f"Observation at index {idx} is not a dictionary object")

        url = obs.get("source_url")
        if not url or not isinstance(url, str) or not url.strip():
            raise DashboardValidationError(f"Observation at index {idx} has missing or empty 'source_url'")

        url_str = url.strip()
        parsed = urlparse(url_str)
        scheme = parsed.scheme.lower()

        if scheme != "https":
            raise DashboardValidationError(
                f"Unsafe source URL detected at observation index {idx}: '{url_str}'. "
                f"Dashboard citations must use secure HTTPS protocol."
            )
        if not parsed.netloc:
            raise DashboardValidationError(
                f"Malformed source URL at observation index {idx}: '{url_str}'. Missing network host."
            )


def _normalize_themes(raw_themes: Any) -> List[Dict[str, Any]]:
    """
    Normalize analyst theme objects so downstream consumers (BAND, React frontend,
    charts, KPIs) receive consistent theme names, descriptions, evidence counts, and sources.
    Empty themes remain empty without fabricating entries.
    """
    if raw_themes is None:
        return []
    if not isinstance(raw_themes, list):
        raise DashboardValidationError("Field 'key_themes' must be a list")

    normalized: List[Dict[str, Any]] = []
    for item in raw_themes:
        if not isinstance(item, dict):
            continue

        theme_name = str(item.get("theme") or item.get("name") or "").strip()
        if not theme_name:
            continue

        raw_sources = item.get("sources") or []
        valid_sources: List[str] = []
        if isinstance(raw_sources, list):
            for src in raw_sources:
                if isinstance(src, str):
                    src_str = src.strip()
                    parsed = urlparse(src_str)
                    if parsed.scheme.lower() == "https" and parsed.netloc:
                        valid_sources.append(src_str)

        raw_count = item.get("frequency")
        if raw_count is None:
            raw_count = item.get("evidence_count")

        if raw_count is not None:
            try:
                evidence_count = max(0, int(raw_count))
            except (ValueError, TypeError):
                evidence_count = len(valid_sources)
        else:
            evidence_count = len(valid_sources)

        description = str(item.get("description") or "").strip()

        normalized.append(
            {
                "theme": theme_name,
                "name": theme_name,
                "description": description,
                "frequency": evidence_count,
                "evidence_count": evidence_count,
                "sources": valid_sources,
            }
        )

    return normalized


def _generate_kpi_cards(
    total_sources: int,
    eligible_sources: int,
    excluded_sources: int,
    theme_count: int,
) -> List[KPICard]:
    """Generate summary KPI metric cards from verified counts."""
    return [
        KPICard(
            id="kpi-total-sources",
            label="Total Sources Evaluated",
            value=total_sources,
            unit="sources",
            description="Total candidate sources gathered from data collection.",
        ),
        KPICard(
            id="kpi-eligible-sources",
            label="Eligible Verified Sources",
            value=eligible_sources,
            unit="sources",
            description="Sources passing all structural, HTTPS, and domain verification checks.",
        ),
        KPICard(
            id="kpi-excluded-sources",
            label="Excluded / Duplicates",
            value=excluded_sources,
            unit="sources",
            description="Sources excluded due to verification failures or duplication.",
        ),
        KPICard(
            id="kpi-theme-count",
            label="Identified Themes",
            value=theme_count,
            unit="themes",
            description="Thematic research clusters synthesized from verified evidence.",
        ),
    ]


def _derive_chart_specifications(
    total_sources: int,
    eligible_sources: int,
    excluded_sources: int,
    key_themes: List[Dict[str, Any]],
    important_keywords: List[str],
    observations: List[Dict[str, Any]],
) -> List[ChartSpec]:
    """
    Derive visual chart specifications strictly from available analysis data.

    Supported chart types:
    - pie: Source eligibility breakdown
    - horizontal_bar: Thematic source distribution
    - bar: Keyword occurrences in verified snippets (disclosed heuristic)
    """
    charts: List[ChartSpec] = []

    # 1. Source Evidence Eligibility Breakdown (Pie Chart)
    if total_sources > 0:
        charts.append(
            ChartSpec(
                id="chart-source-eligibility",
                title="Source Evidence Eligibility Breakdown",
                chart_type="pie",
                description="Proportion of candidate sources eligible for evidence synthesis versus excluded records.",
                data=[
                    ChartDataPoint(label="Eligible Sources", value=float(eligible_sources), color="#10B981"),
                    ChartDataPoint(label="Excluded / Duplicates", value=float(excluded_sources), color="#EF4444"),
                ],
                is_heuristic=False,
            )
        )

    # 2. Research Theme Distribution (Horizontal Bar Chart)
    if len(key_themes) > 0:
        theme_data = [
            ChartDataPoint(
                label=str(theme.get("theme") or theme.get("name") or f"Theme {idx + 1}"),
                value=float(
                    theme.get("frequency")
                    if theme.get("frequency") is not None
                    else theme.get("evidence_count", 0)
                ),
                color="#3B82F6",
            )
            for idx, theme in enumerate(key_themes)
        ]
        charts.append(
            ChartSpec(
                id="chart-theme-distribution",
                title="Research Theme Distribution",
                chart_type="horizontal_bar",
                description=(
                    "Heuristic thematic clusters derived from lexical analysis of verified source snippets, "
                    "representing snippet coverage count per cluster."
                ),
                x_axis_label="Source Count",
                y_axis_label="Research Theme",
                data=theme_data,
                is_heuristic=True,
            )
        )

    # 3. Prominent Keyword Occurrences (Bar Chart - Heuristic Text Frequency)
    if len(important_keywords) > 0 and eligible_sources > 0:
        corpus = " ".join(str(obs.get("statement", "")).lower() for obs in observations)
        kw_data: List[ChartDataPoint] = []

        for kw in important_keywords[:6]:
            kw_clean = str(kw).strip()
            if not kw_clean:
                continue
            # Count exact word boundaries in evidence statements
            count = len(re.findall(r"\b" + re.escape(kw_clean.lower()) + r"\b", corpus))
            kw_data.append(
                ChartDataPoint(
                    label=kw_clean,
                    value=float(max(1, count)),
                    color="#6366F1",
                )
            )

        if kw_data:
            charts.append(
                ChartSpec(
                    id="chart-keyword-frequency",
                    title="Prominent Keyword Occurrences in Source Evidence",
                    chart_type="bar",
                    description=(
                        "Lexical frequency count of prominent keywords extracted across verified snippet text "
                        "(heuristic text measure, not real-world demographic statistic)."
                    ),
                    x_axis_label="Extracted Keyword",
                    y_axis_label="Snippet Term Frequency",
                    data=kw_data,
                    is_heuristic=True,
                )
            )

    return charts


async def build_dashboard(
    analysis_data: Union[AnalysisResponse, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Asynchronously construct a validated dashboard specification JSON from an analyst report.

    Args:
        analysis_data: AnalysisResponse instance or dictionary from the Insight Analyst Agent.

    Returns:
        Structured dashboard specification dictionary conforming to DashboardResponse.

    Raises:
        DashboardValidationError: If incoming analysis is malformed or contains unsafe URLs.
    """
    if isinstance(analysis_data, AnalysisResponse):
        payload = analysis_data.model_dump()
    elif isinstance(analysis_data, dict):
        payload = analysis_data
    else:
        raise DashboardValidationError("Analysis data must be an AnalysisResponse or dictionary object")

    # Validate analysis payload and audit URLs
    _validate_analysis_payload(payload)

    topic = str(payload.get("topic", "")).strip()
    exec_summary = str(payload.get("executive_summary", "")).strip()
    total_sources = int(payload.get("total_sources_evaluated", 0))
    eligible_sources = int(payload.get("eligible_sources_count", 0))
    excluded_sources = int(payload.get("excluded_sources_count", 0))
    raw_themes = payload.get("key_themes") if payload.get("key_themes") is not None else payload.get("themes", [])
    normalized_themes = _normalize_themes(raw_themes)
    important_keywords = payload.get("important_keywords", [])
    raw_observations = payload.get("evidence_backed_observations", [])
    information_gaps = payload.get("information_gaps", [])
    recommendations = payload.get("recommendations", [])
    limitations = payload.get("limitations", [])

    generation_timestamp = datetime.now(timezone.utc).isoformat()
    dashboard_id = f"dash-{uuid.uuid4().hex[:12]}"
    dashboard_title = f"Research Intelligence Dashboard: {topic}"

    # Build KPI cards
    kpi_cards = _generate_kpi_cards(
        total_sources=total_sources,
        eligible_sources=eligible_sources,
        excluded_sources=excluded_sources,
        theme_count=len(normalized_themes),
    )

    # Derive chart specifications
    charts = _derive_chart_specifications(
        total_sources=total_sources,
        eligible_sources=eligible_sources,
        excluded_sources=excluded_sources,
        key_themes=normalized_themes,
        important_keywords=important_keywords,
        observations=raw_observations,
    )

    # Transform observations into DashboardObservation objects
    observations = [
        DashboardObservation(
            statement=obs.get("statement", ""),
            source_title=obs.get("source_title", "Untitled Source"),
            source_url=obs.get("source_url", ""),
            confidence=obs.get("confidence", "high"),
            confidence_reason=obs.get("confidence_reason"),
            is_weakly_relevant=bool(obs.get("is_weakly_relevant", False)),
        )
        for obs in raw_observations
    ]

    result = {
        "dashboard_id": dashboard_id,
        "agent": AGENT_NAME,
        "agent_name": AGENT_NAME,
        "title": dashboard_title,
        "topic": topic,
        "generated_at": generation_timestamp,
        "executive_summary": exec_summary,
        "kpi_cards": [c.model_dump() for c in kpi_cards],
        "themes": normalized_themes,
        "key_themes": normalized_themes,
        "important_keywords": important_keywords,
        "observations": [o.model_dump() for o in observations],
        "information_gaps": information_gaps,
        "recommendations": recommendations,
        "limitations": limitations,
        "charts": [c.model_dump() for c in charts],
        "metadata": {
            "schema_version": "1.0.0",
            "theme_count": len(normalized_themes),
            "observation_count": len(observations),
            "is_heuristic_clustering": True,
        },
        "render_notice": "Safe specification format for React frontend rendering. No executable code or unsafe scripts.",
    }

    # Final safety & schema validation through Pydantic
    try:
        validated_response = DashboardResponse(**result)
        return validated_response.model_dump()
    except Exception as exc:
        logger.error("Generated dashboard specification failed Pydantic validation: %s", exc)
        raise DashboardValidationError(f"Generated dashboard specification failed validation: {exc}") from exc

