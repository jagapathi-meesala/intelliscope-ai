"""
Shared interoperability schemas for agent handoffs, shared execution context,
structured task delegation, and honest sponsor platform integration reporting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


PlatformIdLiteral = Literal["band", "lyzr", "agent37", "adal", "finch"]
IntegrationCategoryLiteral = Literal["live_tested", "implemented", "partial", "not_integrated"]
RuntimeStateLiteral = Literal["ready", "configured", "unconfigured", "not_installed", "not_integrated"]


class ExecutionContext(BaseModel):
    """
    Shared context passed across internal IntelliScope agents and optional
    external sponsor delegation targets under one correlation execution ID.
    """

    execution_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="End-to-end execution correlation UUID shared across agents and handoffs",
    )
    parent_task_id: Optional[str] = Field(
        default=None,
        description="Optional parent task or BAND message identifier",
    )
    origin_platform: str = Field(
        default="api",
        description="Entrypoint platform triggering execution ('api', 'web_ui', 'band', 'cli')",
    )
    origin_room_id: Optional[str] = Field(
        default=None,
        description="Optional collaboration room identifier (e.g., BAND room_id)",
    )
    requester: Optional[str] = Field(
        default=None,
        description="Optional requester identifier or handle (non-secret)",
    )
    query: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Sanitized research topic for the shared execution",
    )
    sources_requested: List[str] = Field(
        default_factory=lambda: ["wikipedia"],
        description="Ordered research source providers requested for this run",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp when shared context was initialized",
    )
    shared_artifacts: Dict[str, Any] = Field(
        default_factory=dict,
        description="Validated intermediate summary artifacts (provenance URLs, counts, themes)",
    )


class AgentHandoffRecord(BaseModel):
    """
    Telemetry record capturing an agent-to-agent delegation or pipeline handoff,
    validation checkpoints, retries, provenance count, and execution timing.
    """

    handoff_id: str = Field(
        default_factory=lambda: f"hoff-{uuid.uuid4().hex[:12]}",
        description="Unique handoff record identifier",
    )
    execution_id: str = Field(
        ...,
        description="Correlation execution ID tying all handoffs in a run together",
    )
    task_id: str = Field(
        default_factory=lambda: f"task-{uuid.uuid4().hex[:12]}",
        description="Structured task delegation identifier",
    )
    from_agent: str = Field(..., description="Originating agent or platform adapter key")
    to_agent: str = Field(..., description="Target receiving agent or platform adapter key")
    protocol: str = Field(
        default="pydantic_validated_handoff",
        description="Handoff transport or validation contract",
    )
    status: Literal["completed", "failed", "timed_out", "rejected", "skipped"] = Field(
        ...,
        description="Handoff outcome",
    )
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC start timestamp",
    )
    completed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC completion timestamp",
    )
    duration_ms: float = Field(default=0.0, ge=0.0, description="Duration in milliseconds")
    retries: int = Field(default=0, ge=0, description="Retry attempts performed")
    input_validation_passed: bool = Field(
        default=True,
        description="Whether handoff input satisfied Pydantic / schema constraints",
    )
    output_validation_passed: bool = Field(
        default=True,
        description="Whether target agent output satisfied schema & consistency constraints",
    )
    validation_error: Optional[str] = Field(
        default=None,
        description="Validation failure detail if input/output contract failed",
    )
    source_provenance_count: int = Field(
        default=0,
        ge=0,
        description="Number of grounded source records carried across this handoff",
    )
    source_providers: List[str] = Field(
        default_factory=list,
        description="Distinct data source providers represented in handed-off evidence",
    )
    error: Optional[str] = Field(
        default=None,
        description="Execution error detail if handoff failed or timed out",
    )


class DelegationTaskRequest(BaseModel):
    """Structured task delegation request sent to a sponsor platform adapter."""

    task_id: str = Field(
        default_factory=lambda: f"del-{uuid.uuid4().hex[:12]}",
        description="Unique task delegation identifier",
    )
    execution_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Parent pipeline or session correlation UUID",
    )
    target_platform: PlatformIdLiteral = Field(
        ...,
        description="Target sponsor platform adapter ('band', 'lyzr', 'agent37', 'adal', 'finch')",
    )
    action: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Adapter action identifier (e.g., 'health_check', 'chat_inference', 'sandbox_exec', 'prepare_peer_handoff')",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured action arguments validated by the target adapter",
    )
    timeout_seconds: float = Field(
        default=15.0,
        gt=0.0,
        le=120.0,
        description="Maximum execution time in seconds before timeout enforcement",
    )
    max_retries: int = Field(
        default=1,
        ge=0,
        le=5,
        description="Maximum transient failure retries",
    )
    shared_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional serialized ExecutionContext snapshot shared with the target",
    )

    @field_validator("action")
    @classmethod
    def validate_action_non_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Delegation action cannot be empty or whitespace.")
        return cleaned


class DelegationTaskResult(BaseModel):
    """Structured, validated outcome returned by a sponsor platform adapter."""

    task_id: str = Field(..., description="Task delegation identifier")
    execution_id: str = Field(..., description="Correlated execution identifier")
    target_platform: PlatformIdLiteral = Field(..., description="Target platform identifier")
    action: str = Field(..., description="Executed action name")
    status: Literal["completed", "failed", "timed_out", "rejected", "unconfigured", "not_integrated"] = Field(
        ...,
        description="Honest execution outcome",
    )
    output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Validated structured result payload when completed",
    )
    output_valid: bool = Field(
        default=False,
        description="Whether adapter response passed structural output validation",
    )
    duration_ms: float = Field(default=0.0, ge=0.0, description="Total execution latency in ms")
    retries_used: int = Field(default=0, ge=0, description="Number of retry attempts consumed")
    error: Optional[str] = Field(default=None, description="Non-secret failure or status reason")
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error/status code (e.g., 'not_configured', 'timeout', 'validation_error')",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of result completion",
    )


class PlatformIntegrationInfo(BaseModel):
    """Honest status descriptor for one sponsor platform integration."""

    platform_id: PlatformIdLiteral = Field(..., description="Canonical platform key")
    display_name: str = Field(..., description="Human-readable platform name")
    mandatory_for_track: bool = Field(
        default=True,
        description="Whether this sponsor platform is mandatory for 'Research — Data & Build'",
    )
    track_requirement_note: Optional[str] = Field(
        default=None,
        description="Hackathon track applicability note (mandatory vs optional credits/hosting)",
    )
    status: IntegrationCategoryLiteral = Field(
        ...,
        description="Honest integration category: 'live_tested', 'implemented', 'partial', or 'not_integrated'",
    )
    runtime_state: RuntimeStateLiteral = Field(
        ...,
        description="Live environment configuration / availability state",
    )
    credentials_present: bool = Field(
        default=False,
        description="Boolean flag indicating whether required credentials/runtime are present (never exposes values)",
    )
    required_env_vars: List[str] = Field(
        default_factory=list,
        description="Environment variable names required for full live activation",
    )
    transport_protocol: str = Field(..., description="SDK / REST / WebSocket / CLI / MCP transport")
    official_docs_url: str = Field(..., description="Official platform documentation reference")
    capabilities: List[str] = Field(default_factory=list, description="Supported adapter capabilities")
    notes: str = Field(..., description="Transparent explanation of current integration scope and gaps")
    last_check_status: Optional[str] = Field(
        default=None,
        description="Outcome of latest connectivity or capability probe",
    )
    last_check_error: Optional[str] = Field(
        default=None,
        description="Non-secret error detail from latest probe, if any",
    )
    last_checked_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 UTC timestamp of latest probe",
    )


class IntegrationsStatusResponse(BaseModel):
    """Aggregated integration status and delegation telemetry for UI and monitoring."""

    platforms: Dict[str, PlatformIntegrationInfo] = Field(
        default_factory=dict,
        description="Map of platform_id -> honest PlatformIntegrationInfo",
    )
    summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Counts by status category ('implemented', 'tested', 'partial', 'not_integrated')",
    )
    recent_delegations: List[DelegationTaskResult] = Field(
        default_factory=list,
        description="Most recent external task delegation attempts (bounded list)",
    )
    checked_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of status inspection",
    )

