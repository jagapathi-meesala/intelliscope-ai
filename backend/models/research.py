"""
Pydantic models for research requests, responses, and agent status.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


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
        description="Maximum number of search results to retrieve (1 to 10)",
        examples=[5]
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


class ResearchResultItem(BaseModel):
    """
    Individual research result item retrieved from an external source.
    """
    title: str = Field(..., description="Title of the source article or document")
    snippet: str = Field(..., description="Text snippet or excerpt summarizing the article")
    source_url: str = Field(..., description="Direct URL to the external source")
    source: str = Field(..., description="Canonical source URL reference")
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
        description="Source provenance: 'wikipedia_extract' or 'wikipedia_search_snippet'"
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
    result_count: int = Field(..., description="Count of retrieved research results")
    total_results: int = Field(..., description="Total count of retrieved research results")
    retrieved_at: str = Field(..., description="ISO 8601 UTC timestamp of retrieval execution")
    results: List[ResearchResultItem] = Field(
        default_factory=list,
        description="List of retrieved research result items"
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

