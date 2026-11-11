"""
Automated unit tests for the Unified Multi-Agent Pipeline Orchestration Service.

Verifies:
1. End-to-end execution through all 4 platform agents (Collector -> Verifier -> Analyst -> Builder).
2. Preservation of source URLs and evidence provenance.
3. Resilience to empty research search batches (zero data fabricated).
4. Graceful handling of individual agent failures (timeout, upstream errors, validation errors).
5. Accurate execution status and execution timing for each agent.
6. Pydantic request and response model validations.
"""

from unittest.mock import AsyncMock, patch
import httpx
import pytest
from pydantic import ValidationError

from backend.agents.analyst_agent import AnalysisValidationError
from backend.agents.dashboard_builder_agent import DashboardValidationError
from backend.agents.data_agent import (
    DataCollectorResponseError,
    DataCollectorTimeoutError,
    DataCollectorUpstreamError,
)
from backend.models.pipeline import (
    AgentExecutionStatus,
    PipelineRequest,
    PipelineResponse,
)
from backend.services.pipeline_orchestrator import (
    AGENT_KEY_ANALYST,
    AGENT_KEY_BUILDER,
    AGENT_KEY_DATA_COLLECTOR,
    AGENT_KEY_VERIFICATION,
    PipelineOrchestrator,
    run_pipeline,
)


# ------------------------------------------------------------------------------
# Test Fixtures & Mock Data
# ------------------------------------------------------------------------------
MOCK_WIKIPEDIA_VALID_SEARCH = {
    "query": {
        "search": [
            {
                "title": "Quantum computing",
                "snippet": "<span>Quantum</span> computing is a rapidly-emerging technology that harnesses quantum mechanics.",
            },
            {
                "title": "Quantum algorithm",
                "snippet": "A quantum algorithm is an algorithm which runs on a realistic model of quantum computation.",
            },
        ]
    }
}

MOCK_WIKIPEDIA_EMPTY_SEARCH = {
    "query": {
        "search": []
    }
}


def build_mock_client(payload: dict, status_code: int = 200) -> httpx.AsyncClient:
    """Helper to construct an AsyncClient with a mocked GET response."""
    mock_resp = httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)
    return mock_client


# ------------------------------------------------------------------------------
# 1. Pipeline Request & Model Validation Tests
# ------------------------------------------------------------------------------
class TestPipelineModels:
    """Test suite for Pipeline Pydantic request and response schemas."""

    def test_pipeline_request_valid(self):
        """Verify valid request instantiates with expected defaults."""
        req = PipelineRequest(query="Artificial Intelligence", limit=5)
        assert req.query == "Artificial Intelligence"
        assert req.limit == 5

    def test_pipeline_request_default_limit(self):
        """Verify default limit is 5."""
        req = PipelineRequest(query="Robotics")
        assert req.limit == 5

    def test_pipeline_request_whitespace_stripping(self):
        """Verify leading and trailing whitespace is stripped."""
        req = PipelineRequest(query="   Neural Networks   ")
        assert req.query == "Neural Networks"

    @pytest.mark.parametrize("invalid_query", ["", "   ", "\t\n"])
    def test_pipeline_request_empty_query_rejected(self, invalid_query):
        """Verify empty or whitespace query is rejected with ValidationError."""
        with pytest.raises(ValidationError):
            PipelineRequest(query=invalid_query)

    def test_pipeline_request_query_too_long(self):
        """Verify query exceeding 300 characters is rejected."""
        long_query = "x" * 301
        with pytest.raises(ValidationError):
            PipelineRequest(query=long_query)

    @pytest.mark.parametrize("invalid_limit", [0, -1, 11, 100])
    def test_pipeline_request_limit_out_of_bounds(self, invalid_limit):
        """Verify limit must be between 1 and 10 inclusive."""
        with pytest.raises(ValidationError):
            PipelineRequest(query="Quantum Computing", limit=invalid_limit)

    def test_agent_execution_status_model(self):
        """Verify AgentExecutionStatus model initialization."""
        status = AgentExecutionStatus(
            agent_key="data_collector",
            agent_name="Data Collector Agent",
            status="completed",
            duration_ms=45.2,
            details="Retrieved 3 sources",
        )
        assert status.agent_key == "data_collector"
        assert status.status == "completed"
        assert status.duration_ms == 45.2
        assert status.error is None


# ------------------------------------------------------------------------------
# 2. End-to-End Successful Pipeline Tests
# ------------------------------------------------------------------------------
class TestPipelineExecutionSuccess:
    """Test suite for successful end-to-end 4-agent pipeline execution."""

    @pytest.mark.asyncio
    async def test_run_pipeline_full_success(self):
        """
        Verify all 4 agents complete successfully on valid research data.
        Collector -> Verifier -> Analyst -> Builder.
        """
        mock_client = build_mock_client(MOCK_WIKIPEDIA_VALID_SEARCH)

        orchestrator = PipelineOrchestrator()
        result = await orchestrator.run(
            request=PipelineRequest(query="Quantum Computing", limit=2),
            client=mock_client,
        )

        assert isinstance(result, PipelineResponse)
        assert result.status == "success"
        assert result.query == "Quantum Computing"
        assert result.total_duration_ms > 0

        # Check all 4 agents are recorded as completed
        statuses = result.agent_statuses
        assert len(statuses) == 4

        for key in (AGENT_KEY_DATA_COLLECTOR, AGENT_KEY_VERIFICATION, AGENT_KEY_ANALYST, AGENT_KEY_BUILDER):
            assert key in statuses
            assert statuses[key].status == "completed"
            assert statuses[key].duration_ms >= 0.0
            assert statuses[key].error is None

        # Verify Data Collector output
        assert result.research is not None
        assert result.research.result_count == 2
        assert len(result.research.results) == 2
        assert result.research.results[0].title == "Quantum computing"

        # Verify Research Verification output
        assert result.verification is not None
        assert result.verification.quality_score == 100
        assert result.verification.valid_results_count == 2
        assert result.verification.invalid_results_count == 0

        # Verify Insight Analyst output
        assert result.analysis is not None
        assert result.analysis.eligible_sources_count == 2
        assert result.analysis.excluded_sources_count == 0
        assert len(result.analysis.evidence_backed_observations) == 2
        assert result.analysis.executive_summary != ""

        # Summary matches analyst executive summary
        assert result.summary == result.analysis.executive_summary

        # Verify Dashboard Builder output
        assert result.dashboard is not None
        assert len(result.dashboard.kpi_cards) == 4
        kpis = {k.id: k.value for k in result.dashboard.kpi_cards}
        assert kpis["kpi-total-sources"] == 2
        assert kpis["kpi-eligible-sources"] == 2
        assert kpis["kpi-excluded-sources"] == 0
        assert len(result.dashboard.charts) >= 1

        # Evidence URLs preserved
        for obs in result.dashboard.observations:
            assert obs.source_url.startswith("https://en.wikipedia.org/wiki/")

    @pytest.mark.asyncio
    async def test_run_pipeline_with_dict_request(self):
        """Verify run_pipeline accepts plain dictionary input."""
        mock_client = build_mock_client(MOCK_WIKIPEDIA_VALID_SEARCH)

        result = await run_pipeline(
            request={"query": "Quantum Computing", "limit": 2},
            client=mock_client,
        )

        assert result.status == "success"
        assert result.research.result_count == 2

    @pytest.mark.asyncio
    async def test_run_pipeline_empty_research_results(self):
        """
        Verify pipeline gracefully completes when search yields zero results.
        Zero data must be fabricated.
        """
        mock_client = build_mock_client(MOCK_WIKIPEDIA_EMPTY_SEARCH)

        result = await run_pipeline(
            request=PipelineRequest(query="NonexistentTopicXYZ12345", limit=5),
            client=mock_client,
        )

        assert result.status == "success"
        assert result.research.result_count == 0
        assert result.verification.valid_results_count == 0
        assert result.analysis.eligible_sources_count == 0
        assert len(result.analysis.evidence_backed_observations) == 0
        assert "no eligible" in result.analysis.executive_summary.lower()

        # All 4 agents completed without error
        for key in (AGENT_KEY_DATA_COLLECTOR, AGENT_KEY_VERIFICATION, AGENT_KEY_ANALYST, AGENT_KEY_BUILDER):
            assert result.agent_statuses[key].status == "completed"

        # Dashboard specs reflect zero values
        kpis = {k.id: k.value for k in result.dashboard.kpi_cards}
        assert kpis["kpi-total-sources"] == 0
        assert kpis["kpi-eligible-sources"] == 0
        assert len(result.dashboard.observations) == 0
        assert len(result.dashboard.charts) == 0


# ------------------------------------------------------------------------------
# 3. Individual Agent Failure & Resilience Tests
# ------------------------------------------------------------------------------
class TestPipelineFailureResilience:
    """Test suite verifying pipeline error containment and execution tracking."""

    @pytest.mark.asyncio
    async def test_data_collector_timeout_failure(self):
        """Verify timeout in Data Collector marks agent failed and skips rest."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("Connection timed out"))

        result = await run_pipeline(
            request=PipelineRequest(query="Timeout Test", limit=3),
            client=mock_client,
        )

        assert result.status == "failed"
        assert "timed out" in result.summary.lower()
        assert result.agent_statuses[AGENT_KEY_DATA_COLLECTOR].status == "failed"
        assert "timed out" in result.agent_statuses[AGENT_KEY_DATA_COLLECTOR].error.lower()

        # Remaining agents skipped
        assert result.agent_statuses[AGENT_KEY_VERIFICATION].status == "skipped"
        assert result.agent_statuses[AGENT_KEY_ANALYST].status == "skipped"
        assert result.agent_statuses[AGENT_KEY_BUILDER].status == "skipped"

        # Downstream models are None
        assert result.research is None
        assert result.verification is None
        assert result.analysis is None
        assert result.dashboard is None

    @pytest.mark.asyncio
    async def test_data_collector_upstream_error(self):
        """Verify upstream 503 error in Data Collector marks agent failed."""
        mock_resp = httpx.Response(
            status_code=503,
            request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)

        result = await run_pipeline(
            request=PipelineRequest(query="Upstream Error Test", limit=3),
            client=mock_client,
        )

        assert result.status == "failed"
        assert result.agent_statuses[AGENT_KEY_DATA_COLLECTOR].status == "failed"
        assert result.agent_statuses[AGENT_KEY_VERIFICATION].status == "skipped"

    @pytest.mark.asyncio
    async def test_verification_agent_failure(self):
        """Verify failure in Verification Agent stops pipeline with partial_success."""
        mock_client = build_mock_client(MOCK_WIKIPEDIA_VALID_SEARCH)

        with patch("backend.services.pipeline_orchestrator.verify_research", side_effect=RuntimeError("Simulated verification engine crash")):
            result = await run_pipeline(
                request=PipelineRequest(query="Quantum Computing", limit=2),
                client=mock_client,
            )

            assert result.status == "partial_success"
            assert result.agent_statuses[AGENT_KEY_DATA_COLLECTOR].status == "completed"
            assert result.agent_statuses[AGENT_KEY_VERIFICATION].status == "failed"
            assert "Simulated verification engine crash" in result.agent_statuses[AGENT_KEY_VERIFICATION].error
            assert result.agent_statuses[AGENT_KEY_ANALYST].status == "skipped"
            assert result.agent_statuses[AGENT_KEY_BUILDER].status == "skipped"
            assert result.research is not None
            assert result.verification is None

    @pytest.mark.asyncio
    async def test_insight_analyst_failure(self):
        """Verify failure in Insight Analyst halts builder with partial_success."""
        mock_client = build_mock_client(MOCK_WIKIPEDIA_VALID_SEARCH)

        with patch("backend.services.pipeline_orchestrator.analyze_research", side_effect=AnalysisValidationError("Simulated analysis validation failure")):
            result = await run_pipeline(
                request=PipelineRequest(query="Quantum Computing", limit=2),
                client=mock_client,
            )

            assert result.status == "partial_success"
            assert result.agent_statuses[AGENT_KEY_DATA_COLLECTOR].status == "completed"
            assert result.agent_statuses[AGENT_KEY_VERIFICATION].status == "completed"
            assert result.agent_statuses[AGENT_KEY_ANALYST].status == "failed"
            assert result.agent_statuses[AGENT_KEY_BUILDER].status == "skipped"
            assert result.research is not None
            assert result.verification is not None
            assert result.analysis is None
            assert result.dashboard is None

    @pytest.mark.asyncio
    async def test_dashboard_builder_failure(self):
        """Verify failure in Dashboard Builder marks builder failed with partial_success."""
        mock_client = build_mock_client(MOCK_WIKIPEDIA_VALID_SEARCH)

        with patch("backend.services.pipeline_orchestrator.build_dashboard", side_effect=DashboardValidationError("Simulated dashboard specification error")):
            result = await run_pipeline(
                request=PipelineRequest(query="Quantum Computing", limit=2),
                client=mock_client,
            )

            assert result.status == "partial_success"
            assert result.agent_statuses[AGENT_KEY_DATA_COLLECTOR].status == "completed"
            assert result.agent_statuses[AGENT_KEY_VERIFICATION].status == "completed"
            assert result.agent_statuses[AGENT_KEY_ANALYST].status == "completed"
            assert result.agent_statuses[AGENT_KEY_BUILDER].status == "failed"
            assert result.dashboard is None
            assert result.analysis is not None

    @pytest.mark.asyncio
    async def test_phase_3_3_pipeline_relevance_and_heuristic_metadata(self):
        """
        Phase 3.3 End-to-end regression test:
        Verify multi-agent pipeline with search results:
        1. Correctly identifies directly relevant vs weakly relevant items.
        2. Explicitly exposes structurally_valid_count, directly_relevant_count, weakly_relevant_count, excluded_count.
        3. Exposes is_heuristic=True on theme distribution and keyword charts.
        """
        mock_payload = {
            "query": {
                "search": [
                    {
                        "title": "Quantum computing",
                        "snippet": "Quantum computing is a rapidly-emerging technology.",
                        "pageid": 100,
                    },
                    {
                        "title": "Michael J. Biercuk",
                        "snippet": "Michael J. Biercuk is an experimental physicist specializing in quantum computing.",
                        "pageid": 101,
                    },
                ]
            }
        }
        mock_client = build_mock_client(mock_payload)

        result = await run_pipeline(
            request=PipelineRequest(query="quantum computing", limit=2),
            client=mock_client,
        )

        assert result.status == "success"
        assert result.query == "quantum computing"

        # Verification metrics
        ver = result.verification
        assert ver is not None
        assert ver.structurally_valid_count == 2
        assert ver.excluded_count == 0
        assert ver.directly_relevant_count == 1
        assert ver.weakly_relevant_count == 1
        assert ver.is_factually_verified is False

        # Check agent execution details
        ver_details = result.agent_statuses[AGENT_KEY_VERIFICATION].details
        assert "directly relevant" in ver_details
        assert "weakly relevant" in ver_details

        # Dashboard heuristic metadata
        dash = result.dashboard
        assert dash is not None
        theme_chart = next((c for c in dash.charts if c.id == "chart-theme-distribution"), None)
        assert theme_chart is not None
        assert theme_chart.is_heuristic is True
        assert "heuristic" in theme_chart.description.lower()

    @pytest.mark.asyncio
    async def test_phase_3_4_history_retention_latest_and_failure_preservation(self, tmp_path):
        """
        Phase 3.4 Regression test:
        - Run 1 ('quantum computing') produces 3 themes populated in dashboard.themes and key_themes.
        - Run 2 ('neural networks') becomes latest successful run replacing stale overview.
        - Failed Run 3 does NOT overwrite latest successful run ('neural networks').
        - Previous Run 1 ('quantum computing') remains accessible in history with its own sources,
          verification, insights, and dashboard.
        """
        from backend.services.history_store import PipelineHistoryStore, pipeline_history_store

        pipeline_history_store.clear()

        # Rich snippet covering multiple theme categories in analyst_agent
        quantum_payload = {
            "query": {
                "search": [
                    {
                        "title": "Quantum computing",
                        "snippet": (
                            "Quantum computing research algorithms and architecture enable hardware systems "
                            "applications with enterprise optimization impact."
                        ),
                        "pageid": 10,
                    },
                    {
                        "title": "Quantum supremacy",
                        "snippet": (
                            "Experimental history theory demonstrated computational challenge risks "
                            "in benchmark systems."
                        ),
                        "pageid": 11,
                    },
                ]
            }
        }
        nn_payload = {
            "query": {
                "search": [
                    {
                        "title": "Artificial neural network",
                        "snippet": (
                            "Neural network architecture models and training optimization algorithms "
                            "for deep learning systems."
                        ),
                        "pageid": 20,
                    },
                ]
            }
        }

        # 1. Run Quantum Computing
        quantum_res = await run_pipeline(
            request=PipelineRequest(query="quantum computing", limit=2),
            client=build_mock_client(quantum_payload),
        )
        assert quantum_res.status == "success"
        # Dashboard must carry themes matching analyst key_themes
        assert len(quantum_res.dashboard.themes) == len(quantum_res.analysis.key_themes)
        assert len(quantum_res.dashboard.themes) >= 3
        kpis = {k.id: k.value for k in quantum_res.dashboard.kpi_cards}
        assert kpis["kpi-theme-count"] == len(quantum_res.dashboard.themes)

        # 2. Run Neural Networks -> replaces latest
        nn_res = await run_pipeline(
            request=PipelineRequest(query="neural networks", limit=1),
            client=build_mock_client(nn_payload),
        )
        assert nn_res.status == "success"
        assert pipeline_history_store.get_latest_successful().pipeline_id == nn_res.pipeline_id
        assert pipeline_history_store.get_latest_successful().query == "neural networks"

        # 3. Failed Run -> recorded in history, NEVER overwrites 'neural networks'
        failing_client = AsyncMock(spec=httpx.AsyncClient)
        failing_client.get = AsyncMock(side_effect=httpx.ReadTimeout("Simulated failure"))
        failed_res = await run_pipeline(
            request=PipelineRequest(query="broken query", limit=2),
            client=failing_client,
        )
        assert failed_res.status == "failed"

        latest = pipeline_history_store.get_latest_successful()
        assert latest is not None
        assert latest.pipeline_id == nn_res.pipeline_id
        assert latest.query == "neural networks"

        # 4. History retains all 3 runs newest-first and allows restoring Quantum run cleanly
        hist = pipeline_history_store.get_history_response()
        assert hist.total_runs == 3
        assert hist.latest_successful_pipeline_id == nn_res.pipeline_id
        assert [r.query for r in hist.runs] == ["broken query", "neural networks", "quantum computing"]

        restored_quantum = pipeline_history_store.get_run(quantum_res.pipeline_id)
        assert restored_quantum is not None
        assert restored_quantum.query == "quantum computing"
        assert restored_quantum.research.results[0].title == "Quantum computing"
        assert len(restored_quantum.dashboard.themes) == len(quantum_res.dashboard.themes)

        # 5. Persistence round-trip check
        persist_file = tmp_path / "pipeline_history.json"
        store1 = PipelineHistoryStore(storage_path=persist_file, enable_persistence=True)
        store1.record_run(quantum_res)
        store1.record_run(nn_res)
        store1.record_run(failed_res)

        store2 = PipelineHistoryStore(storage_path=persist_file, enable_persistence=True)
        assert store2.get_latest_successful().pipeline_id == nn_res.pipeline_id
        assert store2.get_run(quantum_res.pipeline_id).query == "quantum computing"
        assert store2.get_history_response().total_runs == 3

        pipeline_history_store.clear()

