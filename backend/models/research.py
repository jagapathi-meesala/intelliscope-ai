"""
Pydantic models for research requests, responses, and agent status.
"""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


SourceLiteral = Literal["wikipedia", "arxiv", "crossref"]
VALID_SOURCES = ("wikipedia", "arxiv", "crossref")


def validate_and_normalize_sources(v: Optional[List[str]]) -> List[str]:
    """Validate selected research sources, deduplicating while preserving order."""
    if v is None:
        return ["wikipedia"]
    if not isinstance(v, list):
        raise ValueError("Field 'sources' must be a non-empty list of source identifiers")
    if len(v) == 0:
        raise ValueError("At least one research source must be selected")

    normalized: List[str] = []
    seen = set()
    for item in v:
        if not isinstance(item, str):
            raise ValueError(f"Invalid source type: expected string, got {type(item).__name__}")
        cleaned = item.strip().lower()
        if cleaned not in VALID_SOURCES:
            raise ValueError(
                f"Unsupported research source '{item}'. Allowed sources: {', '.join(VALID_SOURCES)}"
            )
        if cleaned not in seen:
            seen.add(cleaned)
            normalized.append(cleaned)
    return normalized


class ResearchRequest(BaseModel):
    """
    Request model for research data collection queries.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Search query string for research collection",
        examples=["Artificial Intelligence"]
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of search results to retrieve per source (1 to 10)",
        examples=[5]
    )
    sources: List[SourceLiteral] = Field(
        default_factory=lambda: ["wikipedia"],
        min_length=1,
        description="Research providers to query: one or more of 'wikipedia', 'arxiv', 'crossref'",
        examples=[["wikipedia", "arxiv", "crossref"]]
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query is non-empty after trimming and within allowed length."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Research query cannot be empty or contain only whitespace")
        if len(stripped) > 300:
            raise ValueError("Research query cannot exceed 300 characters")
        return stripped

    @field_validator("sources", mode="before")
    @classmethod
    def validate_sources(cls, v: Optional[List[str]]) -> List[str]:
        """Validate and normalize selected source list."""
        return validate_and_normalize_sources(v)


class ResearchResultItem(BaseModel):
    """
    Normalized multi-source research result item retrieved from an external provider.
    """
    title: str = Field(..., description="Title of the article or publication")
    snippet: str = Field(..., description="Text snippet or abstract summarizing the work")
    abstract: Optional[str] = Field(
        default=None,
        description="Normalized abstract or summary excerpt matching snippet"
    )
    source_name: str = Field(
        default="wikipedia",
        description="Provider name identifier ('wikipedia', 'arxiv', or 'crossref')"
    )
    source_url: str = Field(..., description="Direct HTTPS URL to the external source")
    source: str = Field(..., description="Canonical source URL reference")
    publication_date: Optional[str] = Field(
        default=None,
        description="ISO publication date or year-month string when available"
    )
    doi: Optional[str] = Field(
        default=None,
        description="Digital Object Identifier (DOI) when available"
    )
    authors: List[str] = Field(
        default_factory=list,
        description="List of author names when available"
    )
    retrieved_at: str = Field(..., description="ISO 8601 UTC timestamp when result was retrieved")
    relevance: str = Field(
        default="relevant",
        description="Relevance classification: 'relevant' or 'weakly_relevant'"
    )
    is_weakly_relevant: bool = Field(
        default=False,
        description="Flag indicating source is only weakly related to the query"
    )
    relevance_reason: Optional[str] = Field(
        default=None,
        description="Transparent explanation of the relevance determination"
    )
    source_type: str = Field(
        default="wikipedia_extract",
        description="Source provenance (e.g., 'wikipedia_extract', 'arxiv_paper', 'crossref_abstract', 'crossref_work')"
    )


class ResearchResponse(BaseModel):
    """
    Structured response returned by the Data Collector Agent.
    """
    agent: str = Field(
        default="Data Collector Agent",
        description="Name of the agent responsible for data collection"
    )
    agent_name: str = Field(
        default="Data Collector Agent",
        description="Canonical agent name identifier"
    )
    query: str = Field(..., description="The query that was executed")
    sources_requested: List[str] = Field(
        default_factory=lambda: ["wikipedia"],
        description="Selected research providers queried"
    )
    source_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of retrieved items grouped by provider source_name"
    )
    source_errors: Dict[str, str] = Field(
        default_factory=dict,
        description="Non-fatal provider error diagnostics when partial sources succeed"
    )
    result_count: int = Field(..., description="Count of retrieved research results")
    total_results: int = Field(..., description="Total count of retrieved research results")
    retrieved_at: str = Field(..., description="ISO 8601 UTC timestamp of retrieval execution")
    results: List[ResearchResultItem] = Field(
        default_factory=list,
        description="List of retrieved normalized research result items"
    )


class AgentInfo(BaseModel):
    """
    Operational status and metadata for an agent in the platform.
    """
    name: str = Field(..., description="Human-readable agent name")
    status: str = Field(..., description="Operational status: 'operational' or 'planned'")
    operational: bool = Field(..., description="Whether the agent is actively operational")
    description: str = Field(..., description="Summary of the agent's responsibilities")
    capabilities: List[str] = Field(
        default_factory=list,
        description="List of currently implemented capabilities"
    )
    version: Optional[str] = Field(
        default=None,
        description="Agent implementation version, if operational"
    )


class AgentsStatusResponse(BaseModel):
    """
    Response model for the agent fleet status endpoint.
    """
    agents: Dict[str, AgentInfo] = Field(
        ...,
        description="Mapping of agent identifiers to their status details"
    )


# Re-export verification models for convenience
from backend.models.verification import (  # noqa: E402
    VerificationItemChecks,
    VerificationItemReport,
    VerificationRequest,
    VerificationResponse,
    VerificationSummary,
)

# Re-export analyst models for convenience
from backend.models.analyst import (  # noqa: E402
    AnalysisRequest,
    AnalysisResponse,
    EvidenceObservation,
    KeyTheme,
)

# Re-export dashboard models for convenience
from backend.models.dashboard import (  # noqa: E402
    ChartDataPoint,
    ChartSpec,
    ChartType,
    DashboardObservation,
    DashboardResponse,
    KPICard,
)

