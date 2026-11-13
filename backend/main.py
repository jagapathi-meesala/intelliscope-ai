"""
Main FastAPI application for IntelliScope AI.

Autonomous Multi-Agent Research and Intelligence Platform backend.
"""

import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from backend.agents.analyst_agent import (
    AGENT_CAPABILITIES as ANALYST_AGENT_CAPABILITIES,
    AGENT_NAME as ANALYST_AGENT_NAME,
    AGENT_STATUS as ANALYST_AGENT_STATUS,
    AGENT_VERSION as ANALYST_AGENT_VERSION,
    AnalysisValidationError,
    analyze_research,
)
from backend.agents.dashboard_builder_agent import (
    AGENT_CAPABILITIES as BUILDER_AGENT_CAPABILITIES,
    AGENT_NAME as BUILDER_AGENT_NAME,
    AGENT_STATUS as BUILDER_AGENT_STATUS,
    AGENT_VERSION as BUILDER_AGENT_VERSION,
    DashboardValidationError,
    build_dashboard,
)
from backend.agents.data_agent import (
    AGENT_CAPABILITIES as DATA_AGENT_CAPABILITIES,
    AGENT_NAME as DATA_AGENT_NAME,
    AGENT_STATUS as DATA_AGENT_STATUS,
    AGENT_VERSION as DATA_AGENT_VERSION,
    DataCollectorRateLimitError,
    DataCollectorResponseError,
    DataCollectorTimeoutError,
    DataCollectorUpstreamError,
    collect_research,
)
from backend.agents.verification_agent import (
    AGENT_CAPABILITIES as VERIFICATION_AGENT_CAPABILITIES,
    AGENT_NAME as VERIFICATION_AGENT_NAME,
    AGENT_STATUS as VERIFICATION_AGENT_STATUS,
    AGENT_VERSION as VERIFICATION_AGENT_VERSION,
    verify_research,
)
from backend.config import settings
from backend.integrations import (
    DelegationTaskRequest,
    DelegationTaskResult,
    IntegrationsStatusResponse,
    PlatformIntegrationInfo,
    integration_registry,
)
from backend.models.analyst import (
    AnalysisRequest,
    AnalysisResponse,
)
from backend.models.dashboard import (
    DashboardResponse,
)
from backend.models.pipeline import (
    PipelineHistoryResponse,
    PipelineRequest,
    PipelineResponse,
)
from backend.models.research import (
    AgentsStatusResponse,
    ResearchRequest,
    ResearchResponse,
)
from backend.models.verification import (
    VerificationRequest,
    VerificationResponse,
)
from backend.services.history_store import pipeline_history_store
from backend.services.pipeline_orchestrator import run_pipeline

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
)

# Enable CORS for frontend applications (default port 5173 / localhost)
cors_origins_raw = getattr(settings, "CORS_ALLOWED_ORIGINS", "*") or "*"
cors_origins = (
    ["*"]
    if cors_origins_raw.strip() == "*"
    else [origin.strip().rstrip("/") for origin in cors_origins_raw.split(",") if origin.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", summary="Root Status")
def home():
    """Welcome endpoint confirming API availability."""
    return {
        "project": "IntelliScope AI",
        "status": "running",
        "message": "Welcome to IntelliScope AI"
    }


@app.get("/health", summary="Health Check")
def health():
    """Health check endpoint for container probes and monitoring."""
    return {
        "status": "healthy",
        "backend": "operational"
    }


@app.get(
    "/agents/status",
    response_model=AgentsStatusResponse,
    summary="Agent Fleet Status",
    description="Returns the operational status and capabilities of all agents in the platform."
)
def agents_status() -> AgentsStatusResponse:
    """
    Return operational status and implemented capabilities of platform agents.
    All platform agents (Data Collector, Research Verification, Insight Analyst,
    and Dashboard Builder) are active and operational.
    """
    return AgentsStatusResponse(
        agents={
            "data_collector": {
                "name": DATA_AGENT_NAME,
                "status": DATA_AGENT_STATUS,
                "operational": True,
                "description": "Asynchronously collects external research data via official APIs.",
                "capabilities": DATA_AGENT_CAPABILITIES,
                "version": DATA_AGENT_VERSION,
            },
            "research_verification": {
                "name": VERIFICATION_AGENT_NAME,
                "status": VERIFICATION_AGENT_STATUS,
                "operational": True,
                "description": "Validates structural integrity, URL protocol, domain compliance, and deduplication of research results.",
                "capabilities": VERIFICATION_AGENT_CAPABILITIES,
                "version": VERIFICATION_AGENT_VERSION,
            },
            "insight_analyst": {
                "name": ANALYST_AGENT_NAME,
                "status": ANALYST_AGENT_STATUS,
                "operational": True,
                "description": "Performs deterministic, explainable text analysis, keyword extraction, and theme clustering on verified evidence.",
                "capabilities": ANALYST_AGENT_CAPABILITIES,
                "version": ANALYST_AGENT_VERSION,
            },
            "dashboard_builder": {
                "name": BUILDER_AGENT_NAME,
                "status": BUILDER_AGENT_STATUS,
                "operational": True,
                "description": "Generates safe, validated dashboard specification JSON including KPIs, themes, evidence citations, and chart specifications.",
                "capabilities": BUILDER_AGENT_CAPABILITIES,
                "version": BUILDER_AGENT_VERSION,
            },
        }
    )


@app.post(
    "/research",
    response_model=ResearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Collect Research Data",
    description="Accepts a search query and uses the Data Collector Agent to gather verified external data."
)
async def research(payload: ResearchRequest) -> ResearchResponse:
    """
    Collect research information for a given query via the Data Collector Agent.

    Args:
        payload: ResearchRequest containing search query and limit.

    Returns:
        Structured research data including titles, snippets, source URLs, and timestamps.
    """
    try:
        data = await collect_research(
            query=payload.query,
            limit=payload.limit,
            sources=payload.sources,
        )
        return ResearchResponse(**data)
    except DataCollectorTimeoutError as exc:
        logger.warning("Research collection timed out for query '%s': %s", payload.query, exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream research provider timed out. Please try again."
        ) from exc
    except DataCollectorRateLimitError as exc:
        logger.warning("Upstream rate limit hit for query '%s': %s", payload.query, exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc)
        ) from exc
    except (DataCollectorUpstreamError, DataCollectorResponseError) as exc:
        logger.error("Upstream research provider failure for query '%s': %s", payload.query, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream research provider encountered an error."
        ) from exc
    except ValueError as exc:
        logger.warning("Validation error in research collection: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during research collection: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while retrieving research."
        ) from exc


@app.post(
    "/verify",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Research Data",
    description="Validates structural integrity, HTTPS protocol, allowed domains, deduplication, and timestamps of research results."
)
async def verify(payload: VerificationRequest) -> VerificationResponse:
    """
    Verify research data collected by the Data Collector Agent.

    Args:
        payload: VerificationRequest containing query and results to evaluate.

    Returns:
        Detailed VerificationResponse with quality score, check diagnostics, and counts.
    """
    try:
        report = await verify_research(payload)
        return VerificationResponse(**report)
    except Exception as exc:
        logger.exception("Unexpected error during research verification: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while verifying research data."
        ) from exc


@app.post(
    "/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Research Data",
    description="Consumes research data and its verification report to produce a structured, deterministic intelligence analysis."
)
async def analyze(payload: AnalysisRequest) -> AnalysisResponse:
    """
    Analyze research data vetted by the Research Verification Agent.

    Args:
        payload: AnalysisRequest containing research data and verification report.

    Returns:
        AnalysisResponse containing executive summary, themes, keywords, observations, gaps, and recommendations.
    """
    try:
        result = await analyze_research(payload)
        return AnalysisResponse(**result)
    except AnalysisValidationError as exc:
        logger.warning("Analysis validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during research analysis: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while analyzing research data."
        ) from exc


@app.post(
    "/dashboard",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Build Research Dashboard Specification",
    description="Consumes structured output from the Insight Analyst Agent and generates a validated dashboard specification JSON for frontend visualization."
)
async def dashboard(payload: AnalysisResponse) -> DashboardResponse:
    """
    Generate a validated dashboard specification from an Insight Analyst Agent report.

    Args:
        payload: AnalysisResponse from the Insight Analyst Agent.

    Returns:
        DashboardResponse containing title, KPIs, themes, observations, and chart specifications.
    """
    try:
        spec = await build_dashboard(payload)
        return DashboardResponse(**spec)
    except DashboardValidationError as exc:
        logger.warning("Dashboard validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during dashboard generation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while building the dashboard specification."
        ) from exc


@app.post(
    "/pipeline",
    response_model=PipelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Unified Multi-Agent Research Pipeline",
    description="Orchestrates the end-to-end 4-agent intelligence pipeline: Data Collector -> Research Verification -> Insight Analyst -> Dashboard Builder."
)
async def pipeline_endpoint(payload: PipelineRequest) -> PipelineResponse:
    """
    Execute the unified multi-agent research pipeline end-to-end for a given query.

    Args:
        payload: PipelineRequest containing research query and limit.

    Returns:
        Structured PipelineResponse containing individual agent execution statuses,
        concise executive summary, and outputs from all four platform agents.
    """
    try:
        result = await run_pipeline(payload)
        return result
    except Exception as exc:
        logger.exception("Unexpected error during pipeline execution: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while executing the research pipeline."
        ) from exc


@app.get(
    "/pipeline/history",
    response_model=PipelineHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Pipeline Run History",
    description="Returns retained pipeline run summaries ordered newest-first alongside the latest successful run.",
)
def get_pipeline_history(
    limit: int = Query(default=20, ge=1, le=50, description="Maximum history items to return"),
) -> PipelineHistoryResponse:
    """Return shared execution history for synchronizing BAND and frontend dashboards."""
    return pipeline_history_store.get_history_response(limit=limit)


@app.get(
    "/pipeline/latest",
    response_model=Optional[PipelineResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Latest Successful Pipeline Run",
    description="Returns the most recent successful pipeline run (never overwritten by failed executions), or null if none exists.",
)
def get_latest_pipeline() -> Optional[PipelineResponse]:
    """Return the latest successful PipelineResponse across all platform entrypoints."""
    return pipeline_history_store.get_latest_successful()


@app.get(
    "/pipeline/{pipeline_id}",
    response_model=PipelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Historical Pipeline Run by ID",
    description="Returns the full structured PipelineResponse snapshot for a specific historical run.",
)
def get_pipeline_by_id(pipeline_id: str) -> PipelineResponse:
    """Retrieve a specific historical pipeline run by UUID."""
    run = pipeline_history_store.get_run(pipeline_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run '{pipeline_id}' not found in history.",
        )
    return run


@app.get(
    "/integrations/status",
    response_model=IntegrationsStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Sponsor Platform Integrations Status",
    description="Returns honest readiness, credential presence booleans (never secret values), and delegation telemetry across BAND, Lyzr, Agent37, AdaL, and Finch.",
)
def get_integrations_status() -> IntegrationsStatusResponse:
    """Inspect genuine runtime configuration and integration capabilities across sponsor platforms."""
    return integration_registry.get_status_response()


@app.post(
    "/integrations/check/{platform_id}",
    response_model=PlatformIntegrationInfo,
    status_code=status.HTTP_200_OK,
    summary="Probe Sponsor Platform Connectivity",
    description="Runs a non-mutating credential/runtime verification check for the requested sponsor platform.",
)
async def check_integration_platform(platform_id: str) -> PlatformIntegrationInfo:
    """Run an explicit diagnostic probe against a registered sponsor adapter."""
    info = await integration_registry.check_platform(platform_id)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown integration platform '{platform_id}'.",
        )
    return info


@app.post(
    "/integrations/delegate",
    response_model=DelegationTaskResult,
    status_code=status.HTTP_200_OK,
    summary="Delegate Structured Task to Sponsor Adapter",
    description="Executes validated, timeout-bounded task delegation through a modular sponsor adapter and records telemetry.",
)
async def delegate_integration_task(payload: DelegationTaskRequest) -> DelegationTaskResult:
    """Validate and dispatch a structured task delegation request to a target sponsor adapter."""
    result = await integration_registry.delegate(payload)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown integration target platform '{payload.target_platform}'.",
        )
    return result


