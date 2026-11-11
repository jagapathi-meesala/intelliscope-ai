"""
Pydantic models for the Dashboard Builder Agent.
Defines schemas for KPI metric cards, chart specifications, dashboard sections,
and the complete dashboard specification response.
"""

from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse
import uuid
from pydantic import BaseModel, Field, field_validator


ChartType = Literal["bar", "pie", "horizontal_bar"]


class ChartDataPoint(BaseModel):
    """
    Individual data point within a chart specification.
    """
    label: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Category or series label"
    )
    value: float = Field(
        ...,
        ge=0.0,
        description="Non-negative numeric value"
    )
    color: Optional[str] = Field(
        default=None,
        max_length=30,
        description="Optional hex or design token color"
    )


class ChartSpec(BaseModel):
    """
    Configuration specification for rendering an interactive chart in the frontend.
    """
    id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique machine-readable chart identifier"
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Descriptive chart title"
    )
    chart_type: ChartType = Field(
        ...,
        description="Supported chart visualization type (bar, pie, horizontal_bar)"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Contextual explanation clarifying the metric meaning"
    )
    x_axis_label: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Horizontal axis description"
    )
    y_axis_label: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Vertical axis description"
    )
    data: List[ChartDataPoint] = Field(
        default_factory=list,
        description="List of validated numeric data points"
    )
    is_heuristic: bool = Field(
        default=False,
        description="Flag indicating whether values represent heuristic or lexical approximations"
    )


class KPICard(BaseModel):
    """
    Key Performance Indicator summary metric card.
    """
    id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique machine identifier for the KPI card"
    )
    label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable title for the KPI"
    )
    value: int = Field(
        ...,
        ge=0,
        description="Non-negative integer metric count"
    )
    unit: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Optional unit label (e.g. 'sources', 'themes')"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Short explanation of what this metric measures"
    )


class DashboardObservation(BaseModel):
    """
    Observation item displayed on the dashboard with a validated HTTPS source citation.
    """
    statement: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Observation statement derived from evidence"
    )
    source_title: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Title of the source supporting this observation"
    )
    source_url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Validated HTTPS URL referencing the source"
    )
    confidence: str = Field(
        default="high",
        max_length=50,
        description="Source verification confidence rating"
    )
    confidence_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for the assigned confidence rating"
    )
    is_weakly_relevant: bool = Field(
        default=False,
        description="Flag indicating the underlying source was classified as weakly relevant"
    )

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: str) -> str:
        """Ensure observation source URL is a safe, valid HTTPS link."""
        url_str = v.strip()
        if not url_str:
            raise ValueError("Observation source URL cannot be empty")
        parsed = urlparse(url_str)
        if parsed.scheme.lower() != "https":
            raise ValueError(f"Unsafe URL protocol: '{parsed.scheme}'. Dashboard sources must use secure HTTPS.")
        if not parsed.netloc:
            raise ValueError("Observation source URL missing network host")
        return url_str


class DashboardResponse(BaseModel):
    """
    Validated dashboard specification JSON produced by the Dashboard Builder Agent.
    Consumable by the React frontend for visual rendering.
    """
    dashboard_id: str = Field(
        default_factory=lambda: f"dash-{uuid.uuid4().hex[:12]}",
        description="Unique dashboard specification identifier"
    )
    agent: str = Field(
        default="Dashboard Builder Agent",
        description="Name of the agent responsible for dashboard generation"
    )
    agent_name: str = Field(
        default="Dashboard Builder Agent",
        description="Canonical agent name identifier"
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="High-level dashboard display title"
    )
    topic: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Research topic or search query"
    )
    generated_at: str = Field(
        ...,
        description="ISO 8601 UTC timestamp of dashboard specification creation"
    )
    executive_summary: str = Field(
        ...,
        min_length=1,
        description="High-level synthesis summary of research findings"
    )
    kpi_cards: List[KPICard] = Field(
        default_factory=list,
        description="Summary KPI metric cards"
    )
    themes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Normalized thematic clusters with names and evidence counts"
    )
    key_themes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Thematic groupings identified across research"
    )
    important_keywords: List[str] = Field(
        default_factory=list,
        description="Important keywords extracted from research"
    )
    observations: List[DashboardObservation] = Field(
        default_factory=list,
        description="Evidence-backed observations with validated HTTPS citations"
    )
    information_gaps: List[str] = Field(
        default_factory=list,
        description="Identified research gaps and missing contextual dimensions"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable guidance and research next steps"
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Methodological limitations and analytical boundaries"
    )
    charts: List[ChartSpec] = Field(
        default_factory=list,
        description="Validated visual chart specifications derived from analysis data"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Specification metadata including schema version and theme/heuristic indicators"
    )
    render_notice: str = Field(
        default="Safe specification format for React frontend rendering. No executable code or unsafe scripts.",
        description="Security notice confirming static specification nature"
    )

