"""
Pipeline Orchestration Service for IntelliScope AI.

Unified multi-agent execution pipeline with structured task delegation,
shared ExecutionContext propagation, per-step timeouts, Pydantic validation
checkpoints, and AgentHandoffRecord telemetry:

Origin Platform (API / Web UI / BAND)
    │  [ExecutionContext + execution_id]
    ▼
1. Data Collector Agent (collect_research)
    │  [AgentHandoffRecord: validated ResearchResponse + source provenance]
    ▼
2. Research Verification Agent (verify_research)
    │  [AgentHandoffRecord: validated VerificationResponse]
    ▼
3. Insight Analyst Agent (analyze_research)
    │  [AgentHandoffRecord: validated AnalysisResponse + evidence provenance]
    ▼
4. Dashboard Builder Agent (build_dashboard)
    │  [AgentHandoffRecord: validated DashboardResponse]
    ▼
Complete PipelineResponse
"""

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Union
import uuid

import httpx

from backend.agents.analyst_agent import (
    AGENT_NAME as ANALYST_AGENT_NAME,
    analyze_research,
)
from backend.agents.dashboard_builder_agent import (
    AGENT_NAME as BUILDER_AGENT_NAME,
    build_dashboard,
)
from backend.agents.data_agent import (
    AGENT_NAME as DATA_AGENT_NAME,
    collect_research,
)
from backend.agents.verification_agent import (
    AGENT_NAME as VERIFICATION_AGENT_NAME,
    verify_research,
)
from backend.config import settings
from backend.integrations import integration_registry
from backend.integrations.models import (
    AgentHandoffRecord,
    DelegationTaskRequest,
    ExecutionContext,
)
from backend.models.analyst import (
    AnalysisRequest,
    AnalysisResponse,
)
from backend.models.dashboard import DashboardResponse
from backend.models.pipeline import (
    AgentExecutionStatus,
    PipelineRequest,
    PipelineResponse,
)
from backend.models.research import ResearchResponse
from backend.models.verification import VerificationResponse
from backend.services.history_store import pipeline_history_store

logger = logging.getLogger(__name__)

# Canonical agent keys in pipeline execution order
AGENT_KEY_DATA_COLLECTOR = "data_collector"
AGENT_KEY_VERIFICATION = "research_verification"
AGENT_KEY_ANALYST = "insight_analyst"
AGENT_KEY_BUILDER = "dashboard_builder"

AGENT_NAMES = {
    AGENT_KEY_DATA_COLLECTOR: DATA_AGENT_NAME,
    AGENT_KEY_VERIFICATION: VERIFICATION_AGENT_NAME,
    AGENT_KEY_ANALYST: ANALYST_AGENT_NAME,
    AGENT_KEY_BUILDER: BUILDER_AGENT_NAME,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _skipped_handoff(
    *,
    execution_id: str,
    from_agent: str,
    to_agent: str,
    reason: str,
) -> AgentHandoffRecord:
    ts = _now_iso()
    return AgentHandoffRecord(
        execution_id=execution_id,
        from_agent=from_agent,
        to_agent=to_agent,
        protocol="pydantic_validated_handoff",
        status="skipped",
        started_at=ts,
        completed_at=ts,
        duration_ms=0.0,
        input_validation_passed=False,
        output_validation_passed=False,
        error=reason,
    )


class PipelineOrchestrator:
    """
    Dedicated orchestration service coordinating all four IntelliScope agents
    with shared context, execution IDs, timeouts, result validation, and
    structured handoff telemetry.
    """

    def __init__(self, allowed_domains: Optional[List[str]] = None) -> None:
        self.allowed_domains = allowed_domains

    async def run(
        self,
        request: Union[PipelineRequest, Dict[str, Any]],
        client: Optional[httpx.AsyncClient] = None,
    ) -> PipelineResponse:
        """
        Execute the end-to-end 4-agent intelligence pipeline and record result in history store.
        """
        response = await self._execute_pipeline(request=request, client=client)
        pipeline_history_store.record_run(response)
        return response

    async def _execute_pipeline(
        self,
        request: Union[PipelineRequest, Dict[str, Any]],
        client: Optional[httpx.AsyncClient] = None,
    ) -> PipelineResponse:
        if isinstance(request, dict):
            req_model = PipelineRequest(**request)
        else:
            req_model = request

        total_start = time.perf_counter()
        execution_id = (req_model.execution_id or "").strip() or str(uuid.uuid4())
        step_timeout = float(req_model.step_timeout_seconds or settings.PIPELINE_STEP_TIMEOUT_SECONDS)

        shared_context = ExecutionContext(
            execution_id=execution_id,
            parent_task_id=req_model.origin_room_id,
            origin_platform=(req_model.origin_platform or "api").strip(),
            origin_room_id=req_model.origin_room_id,
            requester=req_model.requester,
            query=req_model.query,
            sources_requested=list(req_model.sources),
            shared_artifacts={},
        )

        handoffs: List[AgentHandoffRecord] = []
        if shared_context.origin_platform == "band":
            handoffs.append(
                AgentHandoffRecord(
                    execution_id=execution_id,
                    from_agent="band_room",
                    to_agent="orchestrator",
                    protocol="band_room_event",
                    status="completed",
                    duration_ms=0.0,
                    input_validation_passed=True,
                    output_validation_passed=True,
                    source_providers=list(req_model.sources),
                )
            )

        agent_statuses: Dict[str, AgentExecutionStatus] = {
            key: AgentExecutionStatus(
                agent_key=key,
                agent_name=AGENT_NAMES[key],
                status="skipped",
                duration_ms=0.0,
            )
            for key in (
                AGENT_KEY_DATA_COLLECTOR,
                AGENT_KEY_VERIFICATION,
                AGENT_KEY_ANALYST,
                AGENT_KEY_BUILDER,
            )
        }

        research_resp: Optional[ResearchResponse] = None
        verification_resp: Optional[VerificationResponse] = None
        analysis_resp: Optional[AnalysisResponse] = None
        dashboard_resp: Optional[DashboardResponse] = None

        logger.info(
            "Starting pipeline execution %s (origin=%s) for topic '%s' (limit=%d, sources=%s)...",
            execution_id[:8],
            shared_context.origin_platform,
            req_model.query,
            req_model.limit,
            req_model.sources,
        )

        # ----------------------------------------------------------------------
        # Step 1: Data Collector Agent
        # ----------------------------------------------------------------------
        step1_task_id = f"task-collect-{uuid.uuid4().hex[:8]}"
        step1_started_at = _now_iso()
        step1_start = time.perf_counter()
        try:
            research_dict = await asyncio.wait_for(
                collect_research(
                    query=req_model.query,
                    limit=req_model.limit,
                    client=client,
                    sources=req_model.sources,
                ),
                timeout=step_timeout,
            )
            step1_duration = round((time.perf_counter() - step1_start) * 1000.0, 2)
            step1_completed_at = _now_iso()
            research_resp = ResearchResponse(**research_dict)

            step1_details = f"Retrieved {research_resp.result_count} external source(s)"
            if research_resp.sources_requested and (
                len(research_resp.sources_requested) > 1 or research_resp.sources_requested != ["wikipedia"]
            ):
                step1_details += f" across {', '.join(research_resp.sources_requested)}"
            if research_resp.source_errors:
                step1_details += f" (partial error: {', '.join(research_resp.source_errors.keys())})"

            providers_active = [
                k for k, v in (research_resp.source_breakdown or {}).items() if v > 0
            ] or list(research_resp.sources_requested or [])
            shared_context.shared_artifacts.update(
                {
                    "sources_retrieved": research_resp.result_count,
                    "source_breakdown": dict(research_resp.source_breakdown),
                    "source_errors": dict(research_resp.source_errors),
                    "retrieved_urls": [item.source_url for item in research_resp.results],
                }
            )

            agent_statuses[AGENT_KEY_DATA_COLLECTOR] = AgentExecutionStatus(
                agent_key=AGENT_KEY_DATA_COLLECTOR,
                agent_name=AGENT_NAMES[AGENT_KEY_DATA_COLLECTOR],
                status="completed",
                duration_ms=step1_duration,
                task_id=step1_task_id,
                started_at=step1_started_at,
                completed_at=step1_completed_at,
                input_valid=True,
                output_valid=True,
                details=step1_details,
            )
            handoffs.append(
                AgentHandoffRecord(
                    execution_id=execution_id,
                    task_id=step1_task_id,
                    from_agent="orchestrator",
                    to_agent=AGENT_KEY_DATA_COLLECTOR,
                    protocol="internal_async_delegation",
                    status="completed",
                    started_at=step1_started_at,
                    completed_at=step1_completed_at,
                    duration_ms=step1_duration,
                    input_validation_passed=True,
                    output_validation_passed=True,
                    source_provenance_count=research_resp.result_count,
                    source_providers=providers_active,
                )
            )
            logger.info(
                "Step 1 (Data Collector) completed: %d sources retrieved in %.2fms",
                research_resp.result_count,
                step1_duration,
            )
        except Exception as exc:
            is_timeout = isinstance(exc, asyncio.TimeoutError)
            step1_duration = round((time.perf_counter() - step1_start) * 1000.0, 2)
            step1_completed_at = _now_iso()
            error_msg = (
                f"Data Collector exceeded step timeout ({step_timeout:.1f}s)"
                if is_timeout
                else str(exc)
            )
            logger.error("Step 1 (Data Collector) failed: %s", error_msg)
            agent_statuses[AGENT_KEY_DATA_COLLECTOR] = AgentExecutionStatus(
                agent_key=AGENT_KEY_DATA_COLLECTOR,
                agent_name=AGENT_NAMES[AGENT_KEY_DATA_COLLECTOR],
                status="failed",
                duration_ms=step1_duration,
                task_id=step1_task_id,
                started_at=step1_started_at,
                completed_at=step1_completed_at,
                input_valid=True,
                output_valid=False,
                error=error_msg,
            )
            handoffs.append(
                AgentHandoffRecord(
                    execution_id=execution_id,
                    task_id=step1_task_id,
                    from_agent="orchestrator",
                    to_agent=AGENT_KEY_DATA_COLLECTOR,
                    protocol="internal_async_delegation",
                    status="timed_out" if is_timeout else "failed",
                    started_at=step1_started_at,
                    completed_at=step1_completed_at,
                    duration_ms=step1_duration,
                    input_validation_passed=True,
                    output_validation_passed=False,
                    error=error_msg,
                )
            )
            for remaining in (AGENT_KEY_VERIFICATION, AGENT_KEY_ANALYST, AGENT_KEY_BUILDER):
                agent_statuses[remaining].details = "Skipped due to Data Collector failure"

            handoffs.extend(
                [
                    _skipped_handoff(
                        execution_id=execution_id,
                        from_agent=AGENT_KEY_DATA_COLLECTOR,
                        to_agent=AGENT_KEY_VERIFICATION,
                        reason="Skipped due to Data Collector failure",
                    ),
                    _skipped_handoff(
                        execution_id=execution_id,
                        from_agent=AGENT_KEY_VERIFICATION,
                        to_agent=AGENT_KEY_ANALYST,
                        reason="Skipped due to upstream failure",
                    ),
                    _skipped_handoff(
                        execution_id=execution_id,
                        from_agent=AGENT_KEY_ANALYST,
                        to_agent=AGENT_KEY_BUILDER,
                        reason="Skipped due to upstream failure",
                    ),
                ]
            )

            total_duration = (time.perf_counter() - total_start) * 1000.0
            return PipelineResponse(
                pipeline_id=execution_id,
                execution_id=execution_id,
                query=req_model.query,
                status="failed",
                total_duration_ms=round(total_duration, 2),
                agent_statuses=agent_statuses,
                summary=f"Pipeline execution failed at Data Collector Agent: {error_msg}",
                shared_context=shared_context,
                handoffs=handoffs,
            )

        # ----------------------------------------------------------------------
        # Step 2: Research Verification Agent
        # ----------------------------------------------------------------------
        step2_task_id = f"task-verify-{uuid.uuid4().hex[:8]}"
        step2_started_at = _now_iso()
        step2_start = time.perf_counter()
        try:
            verification_dict = await asyncio.wait_for(
                verify_research(
                    data=research_dict,
                    allowed_domains=self.allowed_domains,
                ),
                timeout=step_timeout,
            )
            step2_duration = round((time.perf_counter() - step2_start) * 1000.0, 2)
            step2_completed_at = _now_iso()
            verification_resp = VerificationResponse(**verification_dict)

            shared_context.shared_artifacts.update(
                {
                    "quality_score": verification_resp.quality_score,
                    "structurally_valid_count": verification_resp.structurally_valid_count,
                    "excluded_count": verification_resp.excluded_count,
                    "is_factually_verified": verification_resp.is_factually_verified,
                }
            )

            agent_statuses[AGENT_KEY_VERIFICATION] = AgentExecutionStatus(
                agent_key=AGENT_KEY_VERIFICATION,
                agent_name=AGENT_NAMES[AGENT_KEY_VERIFICATION],
                status="completed",
                duration_ms=step2_duration,
                task_id=step2_task_id,
                started_at=step2_started_at,
                completed_at=step2_completed_at,
                input_valid=True,
                output_valid=True,
                details=(
                    f"Quality score: {round(verification_resp.quality_score)}/100 "
                    f"({verification_resp.structurally_valid_count} valid, {verification_resp.excluded_count} excluded, "
                    f"{verification_resp.directly_relevant_count} directly relevant, {verification_resp.weakly_relevant_count} weakly relevant)"
                ),
            )
            handoffs.append(
                AgentHandoffRecord(
                    execution_id=execution_id,
                    task_id=step2_task_id,
                    from_agent=AGENT_KEY_DATA_COLLECTOR,
                    to_agent=AGENT_KEY_VERIFICATION,
                    protocol="pydantic_validated_handoff",
                    status="completed",
                    started_at=step2_started_at,
                    completed_at=step2_completed_at,
                    duration_ms=step2_duration,
                    input_validation_passed=True,
                    output_validation_passed=True,
                    source_provenance_count=verification_resp.structurally_valid_count,
                    source_providers=providers_active,
                )
            )
            logger.info(
                "Step 2 (Verification Agent) completed: score %d/100 in %.2fms",
                verification_resp.quality_score,
                step2_duration,
            )
        except Exception as exc:
            is_timeout = isinstance(exc, asyncio.TimeoutError)
            step2_duration = round((time.perf_counter() - step2_start) * 1000.0, 2)
            step2_completed_at = _now_iso()
            error_msg = (
                f"Verification Agent exceeded step timeout ({step_timeout:.1f}s)"
                if is_timeout
                else str(exc)
            )
            logger.error("Step 2 (Verification Agent) failed: %s", error_msg)
            agent_statuses[AGENT_KEY_VERIFICATION] = AgentExecutionStatus(
                agent_key=AGENT_KEY_VERIFICATION,
                agent_name=AGENT_NAMES[AGENT_KEY_VERIFICATION],
                status="failed",
                duration_ms=step2_duration,
                task_id=step2_task_id,
                started_at=step2_started_at,
                completed_at=step2_completed_at,
                input_valid=True,
                output_valid=False,
                error=error_msg,
            )
            handoffs.append(
                AgentHandoffRecord(
                    execution_id=execution_id,
                    task_id=step2_task_id,
                    from_agent=AGENT_KEY_DATA_COLLECTOR,
                    to_agent=AGENT_KEY_VERIFICATION,
                    protocol="pydantic_validated_handoff",
                    status="timed_out" if is_timeout else "failed",
                    started_at=step2_started_at,
                    completed_at=step2_completed_at,
                    duration_ms=step2_duration,
                    input_validation_passed=True,
                    output_validation_passed=False,
                    source_provenance_count=research_resp.result_count if research_resp else 0,
                    source_providers=providers_active,
                    error=error_msg,
                )
            )
            for remaining in (AGENT_KEY_ANALYST, AGENT_KEY_BUILDER):
                agent_statuses[remaining].details = "Skipped due to Verification Agent failure"

            handoffs.extend(
                [
                    _skipped_handoff(
                        execution_id=execution_id,
                        from_agent=AGENT_KEY_VERIFICATION,
                        to_agent=AGENT_KEY_ANALYST,
                        reason="Skipped due to Verification Agent failure",
                    ),
                    _skipped_handoff(
                        execution_id=execution_id,
                        from_agent=AGENT_KEY_ANALYST,
                        to_agent=AGENT_KEY_BUILDER,
                        reason="Skipped due to upstream failure",
                    ),
                ]
            )

            total_duration = (time.perf_counter() - total_start) * 1000.0
            return PipelineResponse(
                pipeline_id=execution_id,
                execution_id=execution_id,
                query=req_model.query,
                status="partial_success",
                total_duration_ms=round(total_duration, 2),
                agent_statuses=agent_statuses,
                summary=f"Pipeline halted at Verification Agent: {error_msg}",
                research=research_resp,
                shared_context=shared_context,
                handoffs=handoffs,
            )

        # ----------------------------------------------------------------------
        # Step 3: Insight Analyst Agent
        # ----------------------------------------------------------------------
        step3_task_id = f"task-analyze-{uuid.uuid4().hex[:8]}"
        step3_started_at = _now_iso()
        step3_start = time.perf_counter()
        try:
            analysis_req = AnalysisRequest(
                research=research_dict,
                verification=verification_dict,
            )
            analysis_dict = await asyncio.wait_for(
                analyze_research(analysis_req),
                timeout=step_timeout,
            )
            step3_duration = round((time.perf_counter() - step3_start) * 1000.0, 2)
            step3_completed_at = _now_iso()
            analysis_resp = AnalysisResponse(**analysis_dict)

            eligible_providers = sorted(
                {k for k, v in (analysis_resp.source_distribution or {}).items() if v > 0}
            ) or providers_active
            shared_context.shared_artifacts.update(
                {
                    "eligible_sources_count": analysis_resp.eligible_sources_count,
                    "source_distribution": dict(analysis_resp.source_distribution),
                    "themes": [t.theme for t in analysis_resp.key_themes],
                }
            )

            agent_statuses[AGENT_KEY_ANALYST] = AgentExecutionStatus(
                agent_key=AGENT_KEY_ANALYST,
                agent_name=AGENT_NAMES[AGENT_KEY_ANALYST],
                status="completed",
                duration_ms=step3_duration,
                task_id=step3_task_id,
                started_at=step3_started_at,
                completed_at=step3_completed_at,
                input_valid=True,
                output_valid=True,
                details=(
                    f"Analyzed {analysis_resp.eligible_sources_count} eligible source(s) "
                    f"({analysis_resp.excluded_sources_count} excluded), {len(analysis_resp.key_themes)} theme(s)"
                ),
            )
            handoffs.append(
                AgentHandoffRecord(
                    execution_id=execution_id,
                    task_id=step3_task_id,
                    from_agent=AGENT_KEY_VERIFICATION,
                    to_agent=AGENT_KEY_ANALYST,
                    protocol="pydantic_validated_handoff",
                    status="completed",
                    started_at=step3_started_at,
                    completed_at=step3_completed_at,
                    duration_ms=step3_duration,
                    input_validation_passed=True,
                    output_validation_passed=True,
                    source_provenance_count=len(analysis_resp.evidence_backed_observations),
                    source_providers=eligible_providers,
                )
            )
            logger.info(
                "Step 3 (Insight Analyst) completed: %d themes, %d observations in %.2fms",
                len(analysis_resp.key_themes),
                len(analysis_resp.evidence_backed_observations),
                step3_duration,
            )
        except Exception as exc:
            is_timeout = isinstance(exc, asyncio.TimeoutError)
            step3_duration = round((time.perf_counter() - step3_start) * 1000.0, 2)
            step3_completed_at = _now_iso()
            error_msg = (
                f"Insight Analyst exceeded step timeout ({step_timeout:.1f}s)"
                if is_timeout
                else str(exc)
            )
            logger.error("Step 3 (Insight Analyst) failed: %s", error_msg)
            agent_statuses[AGENT_KEY_ANALYST] = AgentExecutionStatus(
                agent_key=AGENT_KEY_ANALYST,
                agent_name=AGENT_NAMES[AGENT_KEY_ANALYST],
                status="failed",
                duration_ms=step3_duration,
                task_id=step3_task_id,
                started_at=step3_started_at,
                completed_at=step3_completed_at,
                input_valid=True,
                output_valid=False,
                error=error_msg,
            )
            handoffs.append(
                AgentHandoffRecord(
                    execution_id=execution_id,
                    task_id=step3_task_id,
                    from_agent=AGENT_KEY_VERIFICATION,
                    to_agent=AGENT_KEY_ANALYST,
                    protocol="pydantic_validated_handoff",
                    status="timed_out" if is_timeout else "failed",
                    started_at=step3_started_at,
                    completed_at=step3_completed_at,
                    duration_ms=step3_duration,
                    input_validation_passed=True,
                    output_validation_passed=False,
                    source_provenance_count=verification_resp.structurally_valid_count if verification_resp else 0,
                    source_providers=providers_active,
                    error=error_msg,
                )
            )
            agent_statuses[AGENT_KEY_BUILDER].details = "Skipped due to Insight Analyst failure"
            handoffs.append(
                _skipped_handoff(
                    execution_id=execution_id,
                    from_agent=AGENT_KEY_ANALYST,
                    to_agent=AGENT_KEY_BUILDER,
                    reason="Skipped due to Insight Analyst failure",
                )
            )

            total_duration = (time.perf_counter() - total_start) * 1000.0
            return PipelineResponse(
                pipeline_id=execution_id,
                execution_id=execution_id,
                query=req_model.query,
                status="partial_success",
                total_duration_ms=round(total_duration, 2),
                agent_statuses=agent_statuses,
                summary=f"Pipeline halted at Insight Analyst Agent: {error_msg}",
                research=research_resp,
                verification=verification_resp,
                shared_context=shared_context,
                handoffs=handoffs,
            )

        # ----------------------------------------------------------------------
        # Step 4: Dashboard Builder Agent
        # ----------------------------------------------------------------------
        step4_task_id = f"task-dashboard-{uuid.uuid4().hex[:8]}"
        step4_started_at = _now_iso()
        step4_start = time.perf_counter()
        try:
            dashboard_dict = await asyncio.wait_for(
                build_dashboard(analysis_dict),
                timeout=step_timeout,
            )
            step4_duration = round((time.perf_counter() - step4_start) * 1000.0, 2)
            step4_completed_at = _now_iso()
            dashboard_resp = DashboardResponse(**dashboard_dict)

            shared_context.shared_artifacts.update(
                {
                    "dashboard_id": dashboard_resp.dashboard_id,
                    "chart_ids": [c.id for c in dashboard_resp.charts],
                    "dashboard_observations_count": len(dashboard_resp.observations),
                }
            )

            agent_statuses[AGENT_KEY_BUILDER] = AgentExecutionStatus(
                agent_key=AGENT_KEY_BUILDER,
                agent_name=AGENT_NAMES[AGENT_KEY_BUILDER],
                status="completed",
                duration_ms=step4_duration,
                task_id=step4_task_id,
                started_at=step4_started_at,
                completed_at=step4_completed_at,
                input_valid=True,
                output_valid=True,
                details=(
                    f"Generated {len(dashboard_resp.kpi_cards)} KPI card(s) "
                    f"and {len(dashboard_resp.charts)} chart specification(s)"
                ),
            )
            handoffs.append(
                AgentHandoffRecord(
                    execution_id=execution_id,
                    task_id=step4_task_id,
                    from_agent=AGENT_KEY_ANALYST,
                    to_agent=AGENT_KEY_BUILDER,
                    protocol="pydantic_validated_handoff",
                    status="completed",
                    started_at=step4_started_at,
                    completed_at=step4_completed_at,
                    duration_ms=step4_duration,
                    input_validation_passed=True,
                    output_validation_passed=True,
                    source_provenance_count=len(dashboard_resp.observations),
                    source_providers=list(
                        (dashboard_resp.metadata or {}).get("sources_represented")
                        or eligible_providers
                    ),
                )
            )
            logger.info(
                "Step 4 (Dashboard Builder) completed: %d KPIs, %d charts in %.2fms",
                len(dashboard_resp.kpi_cards),
                len(dashboard_resp.charts),
                step4_duration,
            )
        except Exception as exc:
            is_timeout = isinstance(exc, asyncio.TimeoutError)
            step4_duration = round((time.perf_counter() - step4_start) * 1000.0, 2)
            step4_completed_at = _now_iso()
            error_msg = (
                f"Dashboard Builder exceeded step timeout ({step_timeout:.1f}s)"
                if is_timeout
                else str(exc)
            )
            logger.error("Step 4 (Dashboard Builder) failed: %s", error_msg)
            agent_statuses[AGENT_KEY_BUILDER] = AgentExecutionStatus(
                agent_key=AGENT_KEY_BUILDER,
                agent_name=AGENT_NAMES[AGENT_KEY_BUILDER],
                status="failed",
                duration_ms=step4_duration,
                task_id=step4_task_id,
                started_at=step4_started_at,
                completed_at=step4_completed_at,
                input_valid=True,
                output_valid=False,
                error=error_msg,
            )
            handoffs.append(
                AgentHandoffRecord(
                    execution_id=execution_id,
                    task_id=step4_task_id,
                    from_agent=AGENT_KEY_ANALYST,
                    to_agent=AGENT_KEY_BUILDER,
                    protocol="pydantic_validated_handoff",
                    status="timed_out" if is_timeout else "failed",
                    started_at=step4_started_at,
                    completed_at=step4_completed_at,
                    duration_ms=step4_duration,
                    input_validation_passed=True,
                    output_validation_passed=False,
                    source_provenance_count=len(analysis_resp.evidence_backed_observations) if analysis_resp else 0,
                    source_providers=eligible_providers,
                    error=error_msg,
                )
            )

            total_duration = (time.perf_counter() - total_start) * 1000.0
            return PipelineResponse(
                pipeline_id=execution_id,
                execution_id=execution_id,
                query=req_model.query,
                status="partial_success",
                total_duration_ms=round(total_duration, 2),
                agent_statuses=agent_statuses,
                summary=analysis_resp.executive_summary if analysis_resp else f"Pipeline halted at Dashboard Builder: {error_msg}",
                research=research_resp,
                verification=verification_resp,
                analysis=analysis_resp,
                shared_context=shared_context,
                handoffs=handoffs,
            )

        # ----------------------------------------------------------------------
        # Optional Opt-In External Delegation: Lyzr Agent Studio (v3 REST API)
        # ----------------------------------------------------------------------
        should_delegate_lyzr = bool(
            req_model.delegate_to_lyzr or getattr(settings, "LYZR_ENABLE_PIPELINE_DELEGATION", False)
        )
        if should_delegate_lyzr:
            lyzr_req = DelegationTaskRequest(
                execution_id=execution_id,
                target_platform="lyzr",
                action="delegate_analysis",
                payload={"query": req_model.query},
                timeout_seconds=min(step_timeout, settings.INTEGRATION_DEFAULT_TIMEOUT_SECONDS),
                max_retries=settings.INTEGRATION_MAX_RETRIES,
                shared_context=shared_context.model_dump(),
            )
            lyzr_started = _now_iso()
            lyzr_res = await integration_registry.delegate(lyzr_req)
            lyzr_completed = _now_iso()
            if lyzr_res is not None:
                if lyzr_res.status == "completed" and lyzr_res.output_valid:
                    shared_context.shared_artifacts["lyzr_review"] = lyzr_res.output
                    handoff_status = "completed"
                elif lyzr_res.status == "timed_out":
                    handoff_status = "timed_out"
                elif lyzr_res.status in ("unconfigured", "rejected"):
                    handoff_status = "rejected"
                else:
                    handoff_status = "failed"
                handoffs.append(
                    AgentHandoffRecord(
                        execution_id=execution_id,
                        task_id=lyzr_req.task_id,
                        from_agent=AGENT_KEY_ANALYST,
                        to_agent="lyzr_studio",
                        protocol="lyzr_rest_v3",
                        status=handoff_status,
                        started_at=lyzr_started,
                        completed_at=lyzr_completed,
                        duration_ms=lyzr_res.duration_ms,
                        retries=lyzr_res.retries_used,
                        input_validation_passed=True,
                        output_validation_passed=lyzr_res.output_valid,
                        source_provenance_count=len(analysis_resp.evidence_backed_observations),
                        source_providers=eligible_providers,
                        error=lyzr_res.error,
                    )
                )

        # ----------------------------------------------------------------------
        # Complete Success
        # ----------------------------------------------------------------------
        total_duration = (time.perf_counter() - total_start) * 1000.0
        logger.info("End-to-end multi-agent pipeline %s completed successfully in %.2fms", execution_id[:8], total_duration)

        return PipelineResponse(
            pipeline_id=execution_id,
            execution_id=execution_id,
            query=req_model.query,
            status="success",
            total_duration_ms=round(total_duration, 2),
            agent_statuses=agent_statuses,
            summary=analysis_resp.executive_summary,
            research=research_resp,
            verification=verification_resp,
            analysis=analysis_resp,
            dashboard=dashboard_resp,
            shared_context=shared_context,
            handoffs=handoffs,
        )


async def run_pipeline(
    request: Union[PipelineRequest, Dict[str, Any]],
    client: Optional[httpx.AsyncClient] = None,
    allowed_domains: Optional[List[str]] = None,
) -> PipelineResponse:
    """
    Convenience function to execute the multi-agent pipeline.
    """
    orchestrator = PipelineOrchestrator(allowed_domains=allowed_domains)
    return await orchestrator.run(request=request, client=client)
