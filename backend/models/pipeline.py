"""
Pydantic data models for the unified multi-agent research pipeline.

Defines request and response schemas for orchestrating:
Data Collector Agent -> Research Verification Agent -> Insight Analyst Agent -> Dashboard Builder Agent.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, Field, field_validator

from backend.models.analyst import AnalysisResponse
from backend.models.dashboard import DashboardResponse
from backend.models.research import ResearchResponse
from backend.models.verification import VerificationResponse


class AgentExecutionStatus(BaseModel):
    """
    Execution status, timing, and diagnostic details for an individual platform agent.
    """
    agent_key: str = Field(
        ...,
        description="Machine-readable agent key (e.g., 'data_collector', 'research_verification')"
    )
    agent_name: str = Field(
        ...,
        description="Canonical human-readable agent name"
    )
    status: Literal["completed", "failed", "skipped"] = Field(
        ...,
        description="Execution status of this agent within the pipeline run"
    )
    duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Execution time for this agent in milliseconds"
    )
    details: Optional[str] = Field(
        default=None,
        description="Diagnostic summary or result metric for this execution step"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error detail message if this agent failed"
    )


class PipelineRequest(BaseModel):
    """
    Request payload for executing the end-to-end multi-agent research pipeline.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Research topic or search query (1-300 characters)"
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of research sources to collect (1-10)"
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate that query is non-empty after whitespace stripping."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query string cannot be empty or whitespace only.")
        if len(stripped) > 300:
            raise ValueError("Query string cannot exceed 300 characters.")
        return stripped


class PipelineResponse(BaseModel):
    """
    Complete structured response from the unified multi-agent research pipeline.
    """
    pipeline_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique execution run UUID"
    )
    query: str = Field(
        ...,
        description="The executed research topic or query"
    )
    status: Literal["success", "partial_success", "failed"] = Field(
        ...,
        description="Overall pipeline completion status"
    )
    total_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total end-to-end pipeline execution time in milliseconds"
    )
    agent_statuses: Dict[str, AgentExecutionStatus] = Field(
        default_factory=dict,
        description="Per-agent execution status mapping"
    )
    summary: Optional[str] = Field(
        default=None,
        description="Concise executive summary of findings or diagnostic failure summary"
    )
    research: Optional[ResearchResponse] = Field(
        default=None,
        description="Output from the Data Collector Agent"
    )
    verification: Optional[VerificationResponse] = Field(
        default=None,
        description="Output from the Research Verification Agent"
    )
    analysis: Optional[AnalysisResponse] = Field(
        default=None,
        description="Output from the Insight Analyst Agent"
    )
    dashboard: Optional[DashboardResponse] = Field(
        default=None,
        description="Output from the Dashboard Builder Agent"
    )
    executed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of pipeline execution"
    )


class PipelineHistorySummary(BaseModel):
    """
    Lightweight summary of a historical pipeline run stored by the backend.
    """
    pipeline_id: str = Field(..., description="Unique execution run UUID")
    query: str = Field(..., description="Executed research topic")
    status: Literal["success", "partial_success", "failed"] = Field(
        ...,
        description="Pipeline execution completion status",
    )
    executed_at: str = Field(..., description="ISO 8601 UTC timestamp of execution")
    total_duration_ms: float = Field(default=0.0, ge=0.0, description="Total execution duration (ms)")
    source_count: int = Field(default=0, ge=0, description="Retrieved source count")
    eligible_count: int = Field(default=0, ge=0, description="Eligible verified source count")
    directly_relevant_count: int = Field(default=0, ge=0, description="Directly relevant source count")
    weakly_relevant_count: int = Field(default=0, ge=0, description="Weakly relevant source count")
    excluded_count: int = Field(default=0, ge=0, description="Excluded invalid source count")
    quality_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Structural quality score")
    theme_count: int = Field(default=0, ge=0, description="Number of themes identified")
    summary: Optional[str] = Field(default=None, description="Executive or error summary")


class PipelineHistoryResponse(BaseModel):
    """
    Backend pipeline execution history including the latest successful run and summaries.
    """
    total_runs: int = Field(..., ge=0, description="Total retained runs in history")
    latest_successful_pipeline_id: Optional[str] = Field(
        default=None,
        description="Pipeline ID of the most recent successful run",
    )
    latest_successful_run: Optional[PipelineResponse] = Field(
        default=None,
        description="Full response of the most recent successful run (never overwritten by failed runs)",
    )
    runs: List[PipelineHistorySummary] = Field(
        default_factory=list,
        description="Retained pipeline runs ordered newest-first",
    )

