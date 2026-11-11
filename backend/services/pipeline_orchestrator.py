"""
Pipeline Orchestration Service for IntelliScope AI.

Unified multi-agent execution pipeline:
User / Client Request
    │
    ▼
1. Data Collector Agent (collect_research)
    │
    ▼
2. Research Verification Agent (verify_research)
    │
    ▼
3. Insight Analyst Agent (analyze_research)
    │
    ▼
4. Dashboard Builder Agent (build_dashboard)
    │
    ▼
Complete PipelineResponse
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union
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


class PipelineOrchestrator:
    """
    Dedicated orchestration service that coordinates all four IntelliScope agents.

    Ensures:
    - Structured data passing between agents without duplication of logic.
    - Full evidence provenance and source URL preservation.
    - Resilient handling of empty research batches and individual agent failures.
    - Precise per-agent and total execution timing in milliseconds.
    - Absolute compliance with non-fabrication policies.
    """

    def __init__(self, allowed_domains: Optional[List[str]] = None) -> None:
        """
        Initialize the Pipeline Orchestrator.

        Args:
            allowed_domains: Optional list of approved domains for the Verification Agent.
                             Defaults to Wikipedia domains when None.
        """
        self.allowed_domains = allowed_domains

    async def run(
        self,
        request: Union[PipelineRequest, Dict[str, Any]],
        client: Optional[httpx.AsyncClient] = None,
    ) -> PipelineResponse:
        """
        Execute the end-to-end 4-agent intelligence pipeline and record result in history store.

        Args:
            request: PipelineRequest instance or dictionary containing 'query' and optional 'limit'.
            client: Optional shared HTTPX async client (e.g. for testing or connection pooling).

        Returns:
            PipelineResponse containing overall status, timing, individual agent execution statuses,
            concise executive summary, and structured outputs from all 4 agents.
        """
        response = await self._execute_pipeline(request=request, client=client)
        pipeline_history_store.record_run(response)
        return response

    async def _execute_pipeline(
        self,
        request: Union[PipelineRequest, Dict[str, Any]],
        client: Optional[httpx.AsyncClient] = None,
    ) -> PipelineResponse:
        # Validate input request
        if isinstance(request, dict):
            req_model = PipelineRequest(**request)
        else:
            req_model = request

        total_start = time.perf_counter()

        # Initialize tracking state
        agent_statuses: Dict[str, AgentExecutionStatus] = {
            AGENT_KEY_DATA_COLLECTOR: AgentExecutionStatus(
                agent_key=AGENT_KEY_DATA_COLLECTOR,
                agent_name=AGENT_NAMES[AGENT_KEY_DATA_COLLECTOR],
                status="skipped",
                duration_ms=0.0,
            ),
            AGENT_KEY_VERIFICATION: AgentExecutionStatus(
                agent_key=AGENT_KEY_VERIFICATION,
                agent_name=AGENT_NAMES[AGENT_KEY_VERIFICATION],
                status="skipped",
                duration_ms=0.0,
            ),
            AGENT_KEY_ANALYST: AgentExecutionStatus(
                agent_key=AGENT_KEY_ANALYST,
                agent_name=AGENT_NAMES[AGENT_KEY_ANALYST],
                status="skipped",
                duration_ms=0.0,
            ),
            AGENT_KEY_BUILDER: AgentExecutionStatus(
                agent_key=AGENT_KEY_BUILDER,
                agent_name=AGENT_NAMES[AGENT_KEY_BUILDER],
                status="skipped",
                duration_ms=0.0,
            ),
        }

        research_resp: Optional[ResearchResponse] = None
        verification_resp: Optional[VerificationResponse] = None
        analysis_resp: Optional[AnalysisResponse] = None
        dashboard_resp: Optional[DashboardResponse] = None

        logger.info("Starting pipeline execution for topic '%s' (limit=%d)...", req_model.query, req_model.limit)

        # ----------------------------------------------------------------------
        # Step 1: Data Collector Agent
        # ----------------------------------------------------------------------
        step1_start = time.perf_counter()
        try:
            research_dict = await collect_research(
                query=req_model.query,
                limit=req_model.limit,
                client=client,
            )
            step1_duration = (time.perf_counter() - step1_start) * 1000.0
            research_resp = ResearchResponse(**research_dict)
            agent_statuses[AGENT_KEY_DATA_COLLECTOR] = AgentExecutionStatus(
                agent_key=AGENT_KEY_DATA_COLLECTOR,
                agent_name=AGENT_NAMES[AGENT_KEY_DATA_COLLECTOR],
                status="completed",
                duration_ms=round(step1_duration, 2),
                details=f"Retrieved {research_resp.result_count} external source(s)",
            )
            logger.info("Step 1 (Data Collector) completed: %d sources retrieved in %.2fms",
                        research_resp.result_count, step1_duration)
        except Exception as exc:
            step1_duration = (time.perf_counter() - step1_start) * 1000.0
            error_msg = str(exc)
            logger.error("Step 1 (Data Collector) failed: %s", error_msg)
            agent_statuses[AGENT_KEY_DATA_COLLECTOR] = AgentExecutionStatus(
                agent_key=AGENT_KEY_DATA_COLLECTOR,
                agent_name=AGENT_NAMES[AGENT_KEY_DATA_COLLECTOR],
                status="failed",
                duration_ms=round(step1_duration, 2),
                error=error_msg,
            )
            # Mark subsequent agents skipped with reason
            for remaining in (AGENT_KEY_VERIFICATION, AGENT_KEY_ANALYST, AGENT_KEY_BUILDER):
                agent_statuses[remaining].details = "Skipped due to Data Collector failure"

            total_duration = (time.perf_counter() - total_start) * 1000.0
            return PipelineResponse(
                query=req_model.query,
                status="failed",
                total_duration_ms=round(total_duration, 2),
                agent_statuses=agent_statuses,
                summary=f"Pipeline execution failed at Data Collector Agent: {error_msg}",
            )

        # ----------------------------------------------------------------------
        # Step 2: Research Verification Agent
        # ----------------------------------------------------------------------
        step2_start = time.perf_counter()
        try:
            verification_dict = await verify_research(
                data=research_dict,
                allowed_domains=self.allowed_domains,
            )
            step2_duration = (time.perf_counter() - step2_start) * 1000.0
            verification_resp = VerificationResponse(**verification_dict)
            agent_statuses[AGENT_KEY_VERIFICATION] = AgentExecutionStatus(
                agent_key=AGENT_KEY_VERIFICATION,
                agent_name=AGENT_NAMES[AGENT_KEY_VERIFICATION],
                status="completed",
                duration_ms=round(step2_duration, 2),
                details=(
                    f"Quality score: {round(verification_resp.quality_score)}/100 "
                    f"({verification_resp.structurally_valid_count} valid, {verification_resp.excluded_count} excluded, "
                    f"{verification_resp.directly_relevant_count} directly relevant, {verification_resp.weakly_relevant_count} weakly relevant)"
                ),
            )
            logger.info("Step 2 (Verification Agent) completed: score %d/100 in %.2fms",
                        verification_resp.quality_score, step2_duration)
        except Exception as exc:
            step2_duration = (time.perf_counter() - step2_start) * 1000.0
            error_msg = str(exc)
            logger.error("Step 2 (Verification Agent) failed: %s", error_msg)
            agent_statuses[AGENT_KEY_VERIFICATION] = AgentExecutionStatus(
                agent_key=AGENT_KEY_VERIFICATION,
                agent_name=AGENT_NAMES[AGENT_KEY_VERIFICATION],
                status="failed",
                duration_ms=round(step2_duration, 2),
                error=error_msg,
            )
            for remaining in (AGENT_KEY_ANALYST, AGENT_KEY_BUILDER):
                agent_statuses[remaining].details = "Skipped due to Verification Agent failure"

            total_duration = (time.perf_counter() - total_start) * 1000.0
            return PipelineResponse(
                query=req_model.query,
                status="partial_success",
                total_duration_ms=round(total_duration, 2),
                agent_statuses=agent_statuses,
                summary=f"Pipeline halted at Verification Agent: {error_msg}",
                research=research_resp,
            )

        # ----------------------------------------------------------------------
        # Step 3: Insight Analyst Agent
        # ----------------------------------------------------------------------
        step3_start = time.perf_counter()
        try:
            analysis_req = AnalysisRequest(
                research=research_dict,
                verification=verification_dict,
            )
            analysis_dict = await analyze_research(analysis_req)
            step3_duration = (time.perf_counter() - step3_start) * 1000.0
            analysis_resp = AnalysisResponse(**analysis_dict)
            agent_statuses[AGENT_KEY_ANALYST] = AgentExecutionStatus(
                agent_key=AGENT_KEY_ANALYST,
                agent_name=AGENT_NAMES[AGENT_KEY_ANALYST],
                status="completed",
                duration_ms=round(step3_duration, 2),
                details=(
                    f"Analyzed {analysis_resp.eligible_sources_count} eligible source(s) "
                    f"({analysis_resp.excluded_sources_count} excluded), {len(analysis_resp.key_themes)} theme(s)"
                ),
            )
            logger.info("Step 3 (Insight Analyst) completed: %d themes, %d observations in %.2fms",
                        len(analysis_resp.key_themes), len(analysis_resp.evidence_backed_observations), step3_duration)
        except Exception as exc:
            step3_duration = (time.perf_counter() - step3_start) * 1000.0
            error_msg = str(exc)
            logger.error("Step 3 (Insight Analyst) failed: %s", error_msg)
            agent_statuses[AGENT_KEY_ANALYST] = AgentExecutionStatus(
                agent_key=AGENT_KEY_ANALYST,
                agent_name=AGENT_NAMES[AGENT_KEY_ANALYST],
                status="failed",
                duration_ms=round(step3_duration, 2),
                error=error_msg,
            )
            agent_statuses[AGENT_KEY_BUILDER].details = "Skipped due to Insight Analyst failure"

            total_duration = (time.perf_counter() - total_start) * 1000.0
            return PipelineResponse(
                query=req_model.query,
                status="partial_success",
                total_duration_ms=round(total_duration, 2),
                agent_statuses=agent_statuses,
                summary=f"Pipeline halted at Insight Analyst Agent: {error_msg}",
                research=research_resp,
                verification=verification_resp,
            )

        # ----------------------------------------------------------------------
        # Step 4: Dashboard Builder Agent
        # ----------------------------------------------------------------------
        step4_start = time.perf_counter()
        try:
            dashboard_dict = await build_dashboard(analysis_dict)
            step4_duration = (time.perf_counter() - step4_start) * 1000.0
            dashboard_resp = DashboardResponse(**dashboard_dict)
            agent_statuses[AGENT_KEY_BUILDER] = AgentExecutionStatus(
                agent_key=AGENT_KEY_BUILDER,
                agent_name=AGENT_NAMES[AGENT_KEY_BUILDER],
                status="completed",
                duration_ms=round(step4_duration, 2),
                details=(
                    f"Generated {len(dashboard_resp.kpi_cards)} KPI card(s) "
                    f"and {len(dashboard_resp.charts)} chart specification(s)"
                ),
            )
            logger.info("Step 4 (Dashboard Builder) completed: %d KPIs, %d charts in %.2fms",
                        len(dashboard_resp.kpi_cards), len(dashboard_resp.charts), step4_duration)
        except Exception as exc:
            step4_duration = (time.perf_counter() - step4_start) * 1000.0
            error_msg = str(exc)
            logger.error("Step 4 (Dashboard Builder) failed: %s", error_msg)
            agent_statuses[AGENT_KEY_BUILDER] = AgentExecutionStatus(
                agent_key=AGENT_KEY_BUILDER,
                agent_name=AGENT_NAMES[AGENT_KEY_BUILDER],
                status="failed",
                duration_ms=round(step4_duration, 2),
                error=error_msg,
            )

            total_duration = (time.perf_counter() - total_start) * 1000.0
            return PipelineResponse(
                query=req_model.query,
                status="partial_success",
                total_duration_ms=round(total_duration, 2),
                agent_statuses=agent_statuses,
                summary=analysis_resp.executive_summary if analysis_resp else f"Pipeline halted at Dashboard Builder: {error_msg}",
                research=research_resp,
                verification=verification_resp,
                analysis=analysis_resp,
            )

        # ----------------------------------------------------------------------
        # Complete Success
        # ----------------------------------------------------------------------
        total_duration = (time.perf_counter() - total_start) * 1000.0
        logger.info("End-to-end multi-agent pipeline completed successfully in %.2fms", total_duration)

        return PipelineResponse(
            query=req_model.query,
            status="success",
            total_duration_ms=round(total_duration, 2),
            agent_statuses=agent_statuses,
            summary=analysis_resp.executive_summary,
            research=research_resp,
            verification=verification_resp,
            analysis=analysis_resp,
            dashboard=dashboard_resp,
        )


async def run_pipeline(
    request: Union[PipelineRequest, Dict[str, Any]],
    client: Optional[httpx.AsyncClient] = None,
    allowed_domains: Optional[List[str]] = None,
) -> PipelineResponse:
    """
    Convenience function to execute the multi-agent pipeline.

    Args:
        request: PipelineRequest instance or dictionary.
        client: Optional shared HTTPX async client.
        allowed_domains: Optional list of approved domains for source verification.

    Returns:
        Structured PipelineResponse.
    """
    orchestrator = PipelineOrchestrator(allowed_domains=allowed_domains)
    return await orchestrator.run(request=request, client=client)
