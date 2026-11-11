"""
Automated tests for BAND Data Collector Agent integration.

Tests message parsing, response formatting, backend HTTP communication,
error handling, configuration loading, and SimpleAdapter on_message dispatch
using FakeAgentTools from the official BAND Python SDK.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from band import PlatformMessage
from band.testing.fake_tools import FakeAgentTools
from scripts.band_collector_agent import (
    BandDataCollectorAdapter,
    call_pipeline_api,
    call_research_api,
    create_band_collector_agent,
    format_error_reply,
    format_pipeline_reply,
    format_research_reply,
    format_usage_reply,
    load_band_credentials,
    parse_research_request,
    send_band_reply,
)


@pytest.fixture
def sample_research_response():
    """Sample valid research data from FastAPI POST /research."""
    return {
        "agent": "Data Collector Agent",
        "agent_name": "Data Collector Agent",
        "query": "Artificial intelligence",
        "result_count": 2,
        "total_results": 2,
        "retrieved_at": "2026-11-05T00:00:00Z",
        "results": [
            {
                "title": "Artificial intelligence",
                "snippet": "Artificial intelligence is intelligence demonstrated by machines.",
                "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "source": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "retrieved_at": "2026-11-05T00:00:00Z",
            },
            {
                "title": "Artificial general intelligence",
                "snippet": "Artificial general intelligence is the intelligence of a machine that can understand or learn any intellectual task.",
                "source_url": "https://en.wikipedia.org/wiki/Artificial_general_intelligence",
                "source": "https://en.wikipedia.org/wiki/Artificial_general_intelligence",
                "retrieved_at": "2026-11-05T00:00:00Z",
            },
        ],
    }


@pytest.fixture
def sample_empty_research_response():
    """Sample empty research data from FastAPI POST /research."""
    return {
        "agent": "Data Collector Agent",
        "agent_name": "Data Collector Agent",
        "query": "Nonexistent topic xyz",
        "result_count": 0,
        "total_results": 0,
        "retrieved_at": "2026-11-05T00:00:00Z",
        "results": [],
    }


@pytest.fixture
def sample_pipeline_response():
    """Sample valid structured PipelineResponse from FastAPI POST /pipeline."""
    return {
        "pipeline_id": "pipe-test-1234",
        "query": "Artificial intelligence",
        "status": "success",
        "total_duration_ms": 154.2,
        "summary": "Artificial intelligence research encompasses machine intelligence and reasoning.",
        "agent_statuses": {
            "data_collector": {
                "agent_key": "data_collector",
                "agent_name": "Data Collector Agent",
                "status": "completed",
                "duration_ms": 50.1,
                "details": "Retrieved 2 external source(s)",
            },
            "research_verification": {
                "agent_key": "research_verification",
                "agent_name": "Research Verification Agent",
                "status": "completed",
                "duration_ms": 25.3,
                "details": "Quality score: 100/100 (2 valid, 0 invalid)",
            },
            "insight_analyst": {
                "agent_key": "insight_analyst",
                "agent_name": "Insight Analyst Agent",
                "status": "completed",
                "duration_ms": 40.5,
                "details": "Analyzed 2 eligible source(s) (0 excluded), 2 theme(s)",
            },
            "dashboard_builder": {
                "agent_key": "dashboard_builder",
                "agent_name": "Dashboard Builder Agent",
                "status": "completed",
                "duration_ms": 38.3,
                "details": "Generated 4 KPI card(s) and 2 chart specification(s)",
            },
        },
        "research": {
            "agent": "Data Collector Agent",
            "query": "Artificial intelligence",
            "result_count": 2,
            "total_results": 2,
            "retrieved_at": "2026-11-05T00:00:00Z",
            "results": [
                {
                    "title": "Artificial intelligence",
                    "snippet": "Artificial intelligence is intelligence demonstrated by machines.",
                    "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                    "source": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                    "retrieved_at": "2026-11-05T00:00:00Z",
                },
            ],
        },
        "verification": {
            "query": "Artificial intelligence",
            "total_results": 2,
            "valid_results_count": 2,
            "invalid_results_count": 0,
            "quality_score": 100.0,
        },
        "analysis": {
            "topic": "Artificial intelligence",
            "executive_summary": "Artificial intelligence research encompasses machine intelligence and reasoning.",
            "total_sources_evaluated": 2,
            "eligible_sources_count": 2,
            "excluded_sources_count": 0,
            "key_themes": [{"name": "Machine Intelligence", "theme": "Machine Intelligence"}],
            "evidence_backed_observations": [
                {
                    "statement": "AI demonstrates machine intelligence.",
                    "source_title": "Artificial intelligence",
                    "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                    "observation": "AI demonstrates machine intelligence.",
                }
            ],
        },
        "dashboard": {
            "dashboard_id": "dash-test-1234",
            "topic": "Artificial intelligence",
            "title": "Intelligence Brief: Artificial intelligence",
            "kpi_cards": [
                {"id": "kpi-total-sources", "label": "Total Sources", "value": 2},
                {"id": "kpi-eligible-sources", "label": "Eligible Sources", "value": 2},
            ],
            "themes": [{"theme": "Machine Intelligence"}],
            "charts": [{"id": "chart-1", "title": "Source Eligibility", "type": "pie", "data": []}],
            "metadata": {"version": "1.0.0"},
        },
    }


def create_platform_message(
    content: str,
    sender_id: str = "user-123",
    sender_name: str = "Alice",
    room_id: str = "room-test-001",
) -> PlatformMessage:
    """Helper to construct a typed PlatformMessage for adapter testing."""
    return PlatformMessage(
        id="msg-test-001",
        room_id=room_id,
        content=content,
        sender_id=sender_id,
        sender_type="User",
        sender_name=sender_name,
        message_type="chat",
        metadata={},
        created_at=datetime.now(timezone.utc),
    )


def create_test_fake_tools(sender_name: str = "Alice", sender_id: str = "user-123") -> FakeAgentTools:
    """Helper to create FakeAgentTools with participant roster satisfying mention rules."""
    return FakeAgentTools(
        room_id="room-test-001",
        participants=[
            {
                "id": sender_id,
                "name": sender_name,
                "role": "member",
                "status": "active",
                "type": "user",
            },
            {
                "id": "agent-collector-001",
                "name": "DataCollector",
                "role": "member",
                "status": "active",
                "type": "agent",
            },
        ],
    )


# ==============================================================================
# 1. Message Parsing Tests
# ==============================================================================
class TestMessageParsing:
    """Test suite for message parsing logic."""

    def test_parse_research_basic(self):
        """Verify standard query extraction with agent mention."""
        query, limit = parse_research_request("@DataCollector research Quantum computing")
        assert query == "Quantum computing"
        assert limit == 3

    def test_parse_search_colon(self):
        """Verify search with colon separator."""
        query, limit = parse_research_request("@collector search: Artificial intelligence")
        assert query == "Artificial intelligence"
        assert limit == 3

    def test_parse_with_explicit_limit(self):
        """Verify extraction of limit parameter."""
        query, limit = parse_research_request("@DataCollector research Renewable energy limit=5")
        assert query == "Renewable energy"
        assert limit == 5

    def test_parse_with_parenthesized_limit(self):
        """Verify extraction of parenthesized limit."""
        query, limit = parse_research_request("@DataCollector find: Neural networks (limit: 4)")
        assert query == "Neural networks"
        assert limit == 4

    def test_parse_limit_clamping(self):
        """Verify limit is clamped within allowed bounds [1, 10]."""
        _, low_limit = parse_research_request("@DataCollector research Topic limit=0")
        assert low_limit == 1

        _, high_limit = parse_research_request("@DataCollector research Topic limit=50")
        assert high_limit == 10

    def test_parse_action_keywords(self):
        """Verify various leading research/search action phrases are stripped."""
        cases = [
            ("research on Deep learning", "Deep learning"),
            ("please research: Cyber security", "Cyber security"),
            ("find information about Photosynthesis", "Photosynthesis"),
            ("what is Astrophysics?", "Astrophysics?"),
            ("tell me about Nanotechnology", "Nanotechnology"),
        ]
        for msg, expected in cases:
            query, _ = parse_research_request(msg)
            assert query == expected

    def test_parse_empty_content(self):
        """Verify empty and whitespace content yields empty query."""
        assert parse_research_request("")[0] == ""
        assert parse_research_request("   ")[0] == ""
        assert parse_research_request("@DataCollector")[0] == ""
        assert parse_research_request("<@01928374-1234-7890>")[0] == ""

    def test_parse_max_length_truncation(self):
        """Verify queries exceeding 300 characters are safely truncated."""
        long_query = "word " * 100  # 500 characters
        query, _ = parse_research_request(f"@DataCollector research {long_query}")
        assert len(query) <= 300

    def test_parse_agent_mention_intelliscope_collector(self):
        """
        Verify '@IntelliScope Collector Research quantum computing'
        correctly extracts 'quantum computing'.
        """
        query, limit = parse_research_request("@IntelliScope Collector Research quantum computing")
        assert query == "quantum computing"
        assert limit == 3

    def test_parse_agent_mention_with_colon(self):
        """Verify '@IntelliScope Collector: Research quantum computing' yields 'quantum computing'."""
        query, limit = parse_research_request("@IntelliScope Collector: Research quantum computing")
        assert query == "quantum computing"
        assert limit == 3

    def test_parse_agent_mention_hyphenated(self):
        """Verify '@IntelliScope-Collector Research quantum computing' yields 'quantum computing'."""
        query, limit = parse_research_request("@IntelliScope-Collector Research quantum computing")
        assert query == "quantum computing"
        assert limit == 3

    def test_parse_slash_handle_command(self):
        """
        Verify leading slash handle '/intelliscope-collector Research quantum computing'
        is stripped and yields 'quantum computing'.
        """
        query, limit = parse_research_request("/intelliscope-collector Research quantum computing")
        assert query == "quantum computing"
        assert limit == 3

    def test_parse_owner_path_handle(self):
        """Verify '@owner/intelliscope-collector Research quantum computing' yields 'quantum computing'."""
        query, limit = parse_research_request("@owner/intelliscope-collector Research quantum computing")
        assert query == "quantum computing"
        assert limit == 3

    def test_parse_relative_slash_handle(self):
        """Verify '@/intelliscope-collector Research quantum computing' yields 'quantum computing'."""
        query, limit = parse_research_request("@/intelliscope-collector Research quantum computing")
        assert query == "quantum computing"
        assert limit == 3

    def test_parse_bare_agent_prefix(self):
        """Verify bare 'IntelliScope Collector: Research quantum computing' yields 'quantum computing'."""
        query, limit = parse_research_request("IntelliScope Collector: Research quantum computing")
        assert query == "quantum computing"
        assert limit == 3

    def test_parse_multiple_mentions(self):
        """Verify message with multiple agent and user mentions yields clean query."""
        cases = [
            ("@Alice @Bob @IntelliScope Collector Research quantum computing", "quantum computing"),
            ("@DataCollector @Charlie search: Machine learning", "Machine learning"),
            ("@[[01928374-1234-7890]] @[[01928374-5678-9999]] Research quantum computing", "quantum computing"),
        ]
        for msg, expected in cases:
            query, _ = parse_research_request(msg)
            assert query == expected

    def test_parse_research_instruction_direct(self):
        """
        Verify 'Research quantum computing' directly strips instruction and yields 'quantum computing'.
        """
        query, limit = parse_research_request("Research quantum computing")
        assert query == "quantum computing"
        assert limit == 3

    def test_parse_preserve_legitimate_topic_words(self):
        """
        Verify parser preserves legitimate topic words (e.g. 'research', 'search') when part of the query.
        """
        cases = [
            ("Operations research", "Operations research"),
            ("Market research", "Market research"),
            ("Search algorithms", "Search algorithms"),
            ("Research operations research", "operations research"),
            ("@DataCollector research Search engines", "Search engines"),
        ]
        for msg, expected in cases:
            query, _ = parse_research_request(msg)
            assert query == expected

    def test_parse_normal_query_without_mentions(self):
        """Verify plain topic query without any mentions or instructions is preserved."""
        cases = [
            ("quantum computing", "quantum computing"),
            ("artificial intelligence", "artificial intelligence"),
            ("Photosynthesis", "Photosynthesis"),
        ]
        for msg, expected in cases:
            query, _ = parse_research_request(msg)
            assert query == expected

    def test_phase_3_3_seven_regression_cases(self):
        """
        Verify the 7 explicit test cases required in Phase 3.3:
        1. @IntelliScope Collector Research quantum computing -> quantum computing
        2. @IntelliScope Collector: Research quantum computing -> quantum computing
        3. @owner/intelliscope-collector Research quantum computing -> quantum computing
        4. Research quantum computing -> quantum computing
        5. Operations research -> Operations research
        6. Market research -> Market research
        7. Quantum computing without a mention -> Quantum computing without a mention
        Both with raw strings and with metadata containing agent mentions.
        """
        cases = [
            ("@IntelliScope Collector Research quantum computing", "quantum computing"),
            ("@IntelliScope Collector: Research quantum computing", "quantum computing"),
            ("@owner/intelliscope-collector Research quantum computing", "quantum computing"),
            ("Research quantum computing", "quantum computing"),
            ("Operations research", "Operations research"),
            ("Market research", "Market research"),
            ("Quantum computing without a mention", "Quantum computing without a mention"),
        ]

        metadata_with_mention = {
            "mentions": [
                {"name": "IntelliScope", "handle": "collector", "id": "agent-001"}
            ]
        }

        for input_text, expected_query in cases:
            # Test without metadata
            q_raw, _ = parse_research_request(input_text)
            assert q_raw == expected_query, f"Failed raw parsing for '{input_text}': got '{q_raw}'"

            # Test with metadata containing agent mention
            q_meta, _ = parse_research_request(input_text, metadata=metadata_with_mention)
            assert q_meta == expected_query, f"Failed metadata parsing for '{input_text}': got '{q_meta}'"

            # Test wrapped in PlatformMessage
            msg = create_platform_message(input_text)
            msg.metadata = metadata_with_mention
            q_pm, _ = parse_research_request(msg)
            assert q_pm == expected_query, f"Failed PlatformMessage parsing for '{input_text}': got '{q_pm}'"

    def test_parse_empty_and_missing_messages(self):
        """Verify empty strings, None, and mention-only messages return empty query."""
        assert parse_research_request(None)[0] == ""
        assert parse_research_request("")[0] == ""
        assert parse_research_request("   ")[0] == ""
        assert parse_research_request("@IntelliScope Collector")[0] == ""
        assert parse_research_request("/intelliscope-collector")[0] == ""
        assert parse_research_request("@owner/intelliscope-collector")[0] == ""

    def test_parse_platform_message_object(self):
        """Verify parse_research_request directly accepts PlatformMessage instances."""
        msg = create_platform_message("@IntelliScope Collector Research quantum computing limit=4")
        query, limit = parse_research_request(msg)
        assert query == "quantum computing"
        assert limit == 4

    def test_parse_metadata_mention_stripping(self):
        """Verify metadata mentions list is sanitized from message content."""
        metadata = {
            "mentions": [
                {"id": "agent-123", "handle": "intelliscope-collector", "name": "IntelliScope Collector"},
                {"id": "user-456", "handle": "alice", "name": "Alice"},
            ]
        }
        query, limit = parse_research_request(
            content="@intelliscope-collector Research quantum computing",
            metadata=metadata
        )
        assert query == "quantum computing"


# ==============================================================================
# 2. Response Formatting Tests
# ==============================================================================
class TestResponseFormatting:
    """Test suite for Markdown formatting."""

    def test_format_research_reply_success(self, sample_research_response):
        """Verify successful research result formatting."""
        formatted = format_research_reply(sample_research_response, "Artificial intelligence")
        assert "IntelliScope Research Collector" in formatted
        assert "Artificial intelligence" in formatted
        assert "Found 2 verified source(s)" in formatted
        assert "[Artificial intelligence](https://en.wikipedia.org/wiki/Artificial_intelligence)" in formatted
        assert "[Artificial general intelligence](https://en.wikipedia.org/wiki/Artificial_general_intelligence)" in formatted
        assert "Retrieved: 2026-11-05T00:00:00Z" in formatted

    def test_format_research_reply_empty(self, sample_empty_research_response):
        """Verify empty results formatting discloses zero sources without hallucination."""
        formatted = format_research_reply(sample_empty_research_response, "Nonexistent topic xyz")
        assert "IntelliScope Research Collector" in formatted
        assert "No verified articles or summary snippets were found" in formatted
        assert "Nonexistent topic xyz" in formatted

    def test_format_error_reply(self):
        """Verify error reply formatting."""
        formatted = format_error_reply("Upstream provider timed out.", "Quantum Computing")
        assert "IntelliScope Research Collector Error" in formatted
        assert "Quantum Computing" in formatted
        assert "Upstream provider timed out." in formatted
        assert "uvicorn backend.main:app --port 8010" in formatted

    def test_format_usage_reply(self):
        """Verify usage instructions reply."""
        formatted = format_usage_reply()
        assert "Data Collector Agent for IntelliScope AI" in formatted
        assert "@DataCollector research" in formatted


# ==============================================================================
# 3. Backend HTTP Communication Tests
# ==============================================================================
class TestBackendCommunication:
    """Test suite for async HTTP calls to FastAPI /research."""

    @pytest.mark.asyncio
    async def test_call_research_api_success(self, sample_research_response):
        """Verify successful backend 200 response handling."""
        mock_resp = httpx.Response(
            status_code=200,
            json=sample_research_response,
            request=httpx.Request("POST", "http://127.0.0.1:8010/research"),
        )
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            success, data = await call_research_api("Artificial intelligence", limit=2)
            assert success is True
            assert isinstance(data, dict)
            assert data["result_count"] == 2

    @pytest.mark.asyncio
    async def test_call_research_api_timeout(self):
        """Verify 504 timeout mapping."""
        mock_resp = httpx.Response(
            status_code=504,
            json={"detail": "Upstream timed out"},
            request=httpx.Request("POST", "http://127.0.0.1:8010/research"),
        )
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            success, error_msg = await call_research_api("Quantum Computing")
            assert success is False
            assert "timed out" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_call_research_api_bad_gateway(self):
        """Verify 502 bad gateway mapping."""
        mock_resp = httpx.Response(
            status_code=502,
            json={"detail": "Upstream error"},
            request=httpx.Request("POST", "http://127.0.0.1:8010/research"),
        )
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            success, error_msg = await call_research_api("Quantum Computing")
            assert success is False
            assert "upstream research provider encountered an error" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_call_research_api_connect_error(self):
        """Verify backend connection error is handled gracefully."""
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused on port 8010")
            success, error_msg = await call_research_api("Quantum Computing")
            assert success is False
            assert "cannot connect to intelliscope backend" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_call_research_api_validation_error(self):
        """Verify 422 validation error handling."""
        mock_resp = httpx.Response(
            status_code=422,
            json={"detail": "Query cannot be blank"},
            request=httpx.Request("POST", "http://127.0.0.1:8010/research"),
        )
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            success, error_msg = await call_research_api("")
            assert success is False
            assert "validation failed" in error_msg.lower()


# ==============================================================================
# 4. SimpleAdapter on_message Flow Tests with FakeAgentTools
# ==============================================================================
class TestBandCollectorAdapter:
    """Test suite for BandDataCollectorAdapter using official BAND SDK FakeAgentTools."""

    @pytest.mark.asyncio
    async def test_adapter_on_message_success(self, sample_research_response):
        """Verify full adapter turn when valid research is requested."""
        adapter = BandDataCollectorAdapter(backend_url="http://127.0.0.1:8010")
        tools = create_test_fake_tools(sender_name="Alice", sender_id="user-123")
        msg = create_platform_message("@DataCollector research Artificial intelligence", sender_name="Alice")

        with patch("scripts.band_collector_agent.call_research_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = (True, sample_research_response)

            await adapter.on_message(
                msg=msg,
                tools=tools,
                history=[],
                participants_msg=None,
                contacts_msg=None,
                is_session_bootstrap=False,
                room_id="room-test-001",
            )

            # Check that call_research_api was invoked with parsed parameters
            mock_call.assert_called_once_with(
                query="Artificial intelligence",
                limit=3,
                backend_url="http://127.0.0.1:8010",
            )

            # Verify that message was sent through tools
            assert len(tools.messages_sent) == 1
            sent = tools.messages_sent[0]
            assert "Alice" in sent["mentions"]
            assert "Artificial intelligence" in sent["content"]
            assert "https://en.wikipedia.org/wiki/Artificial_intelligence" in sent["content"]
            assert tools.turn.replied is True

    @pytest.mark.asyncio
    async def test_adapter_on_message_empty_query_sends_usage(self):
        """Verify empty mention results in usage guidance sent to the room."""
        adapter = BandDataCollectorAdapter(backend_url="http://127.0.0.1:8010")
        tools = create_test_fake_tools(sender_name="Bob", sender_id="user-456")
        msg = create_platform_message("@DataCollector   ", sender_name="Bob", sender_id="user-456")

        with patch("scripts.band_collector_agent.call_research_api", new_callable=AsyncMock) as mock_call:
            await adapter.on_message(
                msg=msg,
                tools=tools,
                history=[],
                participants_msg=None,
                contacts_msg=None,
                is_session_bootstrap=False,
                room_id="room-test-001",
            )

            # Backend should NOT be called
            mock_call.assert_not_called()

            # Usage instructions should be sent
            assert len(tools.messages_sent) == 1
            sent = tools.messages_sent[0]
            assert "Bob" in sent["mentions"]
            assert "To research a topic, mention me with your query" in sent["content"]
            assert tools.turn.replied is True

    @pytest.mark.asyncio
    async def test_adapter_on_message_empty_results_notification(self, sample_empty_research_response):
        """Verify empty research results are communicated without fabricating data."""
        adapter = BandDataCollectorAdapter(backend_url="http://127.0.0.1:8010")
        tools = create_test_fake_tools(sender_name="Charlie")
        msg = create_platform_message("@DataCollector research Nonexistent topic xyz", sender_name="Charlie")

        with patch("scripts.band_collector_agent.call_research_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = (True, sample_empty_research_response)

            await adapter.on_message(
                msg=msg,
                tools=tools,
                history=[],
                participants_msg=None,
                contacts_msg=None,
                is_session_bootstrap=False,
                room_id="room-test-001",
            )

            assert len(tools.messages_sent) == 1
            sent = tools.messages_sent[0]
            assert "Charlie" in sent["mentions"]
            assert "No verified articles or summary snippets were found" in sent["content"]
            assert tools.turn.replied is True

    @pytest.mark.asyncio
    async def test_adapter_on_message_backend_failure_reply(self):
        """Verify backend error is cleanly communicated to the chat room."""
        adapter = BandDataCollectorAdapter(backend_url="http://127.0.0.1:8010")
        tools = create_test_fake_tools(sender_name="Dana")
        msg = create_platform_message("@DataCollector research Quantum computing", sender_name="Dana")

        with patch("scripts.band_collector_agent.call_research_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = (False, "Cannot connect to IntelliScope backend at http://127.0.0.1:8010.")

            await adapter.on_message(
                msg=msg,
                tools=tools,
                history=[],
                participants_msg=None,
                contacts_msg=None,
                is_session_bootstrap=False,
                room_id="room-test-001",
            )

            assert len(tools.messages_sent) == 1
            sent = tools.messages_sent[0]
            assert "Dana" in sent["mentions"]
            assert "IntelliScope Research Collector Error" in sent["content"]
            assert "Cannot connect to IntelliScope backend" in sent["content"]
            assert tools.turn.replied is True


# ==============================================================================
# 5. Configuration & Agent Creation Tests
# ==============================================================================
class TestConfigAndAgentCreation:
    """Test suite for credential loading and agent instantiation."""

    def test_load_credentials_from_yaml(self, tmp_path):
        """Verify credentials loaded from local YAML file."""
        config_file = tmp_path / "agent_config.yaml"
        config_file.write_text(
            "data_collector:\n"
            "  agent_id: 'test-agent-id-1234'\n"
            "  api_key: 'band_sk_test_5678'\n"
        )
        # Clear env vars if set
        with patch.dict(os.environ, {}, clear=True):
            agent_id, api_key = load_band_credentials(
                agent_key="data_collector",
                config_path=config_file,
            )
            assert agent_id == "test-agent-id-1234"
            assert api_key == "band_sk_test_5678"

    def test_load_credentials_from_environment_variables(self):
        """Verify environment variables take precedence."""
        env_vars = {
            "BAND_AGENT_ID": "env-agent-id-9999",
            "BAND_API_KEY": "env-band-api-key-8888",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            agent_id, api_key = load_band_credentials()
            assert agent_id == "env-agent-id-9999"
            assert api_key == "env-band-api-key-8888"

    def test_load_credentials_missing_file_raises(self, tmp_path):
        """Verify FileNotFoundError if config file is absent and no env vars."""
        nonexistent = tmp_path / "does_not_exist.yaml"
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(FileNotFoundError):
                load_band_credentials(config_path=nonexistent)

    def test_create_band_collector_agent_instance(self):
        """Verify create_band_collector_agent instantiates official Agent."""
        agent = create_band_collector_agent(
            agent_id="00000000-0000-0000-0000-000000000000",
            api_key="band_sk_test_12345",
            backend_url="http://127.0.0.1:8010",
        )
        assert agent is not None
        assert hasattr(agent, "run")
        assert hasattr(agent, "start")
        assert hasattr(agent, "stop")

    @pytest.mark.asyncio
    async def test_verify_band_connectivity_matching_ids(self):
        """Verify diagnostic check succeeds when configured and registered IDs match."""
        from unittest.mock import MagicMock
        from scripts.band_collector_agent import verify_band_connectivity

        mock_me = MagicMock()
        mock_me.id = "f00ed576-fbfe-4dfb-95a7-82f6db3c6825"
        mock_me.name = "IntelliScope Collector"
        mock_me.handle = "collector"
        mock_me.description = "Test Description"

        mock_response = MagicMock()
        mock_response.data = mock_me

        with patch("scripts.band_collector_agent.AsyncRestClient") as mock_rest_cls:
            mock_rest_instance = MagicMock()
            mock_rest_instance.agent_api_identity.get_agent_me = AsyncMock(return_value=mock_response)
            mock_rest_cls.return_value = mock_rest_instance

            ok, eff_id, diag = await verify_band_connectivity(
                agent_id="f00ed576-fbfe-4dfb-95a7-82f6db3c6825",
                api_key="band_sk_test",
            )
            assert ok is True
            assert eff_id == "f00ed576-fbfe-4dfb-95a7-82f6db3c6825"
            assert diag["rest_authenticated"] is True
            assert diag["agent_id_match"] is True
            assert diag["agent_name"] == "IntelliScope Collector"

    @pytest.mark.asyncio
    async def test_verify_band_connectivity_mismatched_ids_reconciles(self):
        """Verify diagnostic check detects mismatched/stale Agent ID and reconciles to registered ID."""
        from unittest.mock import MagicMock
        from scripts.band_collector_agent import verify_band_connectivity

        mock_me = MagicMock()
        mock_me.id = "real-registered-uuid-5678"
        mock_me.name = "Real Agent"
        mock_me.handle = "real_agent"
        mock_me.description = "Real Description"

        mock_response = MagicMock()
        mock_response.data = mock_me

        with patch("scripts.band_collector_agent.AsyncRestClient") as mock_rest_cls:
            mock_rest_instance = MagicMock()
            mock_rest_instance.agent_api_identity.get_agent_me = AsyncMock(return_value=mock_response)
            mock_rest_cls.return_value = mock_rest_instance

            # Provide a stale/different agent_id
            stale_id = "stale-old-uuid-1234"
            ok, eff_id, diag = await verify_band_connectivity(
                agent_id=stale_id,
                api_key="band_sk_test",
            )
            assert ok is True
            # Must reconcile to registered ID to prevent WebSocket failures
            assert eff_id == "real-registered-uuid-5678"
            assert diag["rest_authenticated"] is True
            assert diag["agent_id_match"] is False
            assert "notice" in diag

    @pytest.mark.asyncio
    async def test_verify_band_connectivity_rest_failure(self):
        """Verify diagnostic check handles REST API errors safely."""
        from scripts.band_collector_agent import verify_band_connectivity

        with patch("scripts.band_collector_agent.AsyncRestClient") as mock_rest_cls:
            mock_rest_instance = MagicMock()
            mock_rest_instance.agent_api_identity.get_agent_me = AsyncMock(
                side_effect=Exception("HTTP 401 Unauthorized: Invalid API key")
            )
            mock_rest_cls.return_value = mock_rest_instance

            ok, eff_id, diag = await verify_band_connectivity(
                agent_id="agent-uuid-1234",
                api_key="invalid_key",
            )
            assert ok is False
            assert eff_id == "agent-uuid-1234"
            assert diag["rest_authenticated"] is False
            assert "401" in diag["error"]


# ==============================================================================
# 6. Unified Multi-Agent Pipeline BAND Tests
# ==============================================================================
class TestPipelineBackendCommunication:
    """Test suite for call_pipeline_api communication with FastAPI backend."""

    @pytest.mark.asyncio
    async def test_call_pipeline_api_success(self, sample_pipeline_response):
        """Verify successful call to POST /pipeline returns parsed response."""
        mock_response = httpx.Response(
            status_code=200,
            json=sample_pipeline_response,
            request=httpx.Request("POST", "http://127.0.0.1:8010/pipeline")
        )

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            ok, data = await call_pipeline_api(query="Artificial intelligence", limit=2)
            assert ok is True
            assert isinstance(data, dict)
            assert data["status"] == "success"
            assert data["pipeline_id"] == "pipe-test-1234"

    @pytest.mark.asyncio
    async def test_call_pipeline_api_failed_status(self):
        """Verify pipeline failure returns False with diagnostic summary."""
        mock_response = httpx.Response(
            status_code=200,
            json={
                "status": "failed",
                "summary": "Pipeline execution failed at Data Collector Agent: Upstream timeout",
                "agent_statuses": {
                    "data_collector": {"status": "failed", "error": "Upstream timeout"}
                }
            },
            request=httpx.Request("POST", "http://127.0.0.1:8010/pipeline")
        )

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            ok, err = await call_pipeline_api(query="Timeout query", limit=3)
            assert ok is False
            assert "failed at Data Collector Agent" in err

    @pytest.mark.asyncio
    async def test_call_pipeline_api_connect_error(self):
        """Verify connection failure returns informative offline message."""
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            ok, err = await call_pipeline_api(query="Any topic")
            assert ok is False
            assert "Cannot connect to IntelliScope backend" in err

    @pytest.mark.asyncio
    async def test_call_pipeline_api_timeout(self):
        """Verify timeout returns descriptive error."""
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Read timed out")

            ok, err = await call_pipeline_api(query="Slow topic")
            assert ok is False
            assert "timed out" in err.lower()


class TestPipelineResponseFormatting:
    """Test suite for format_pipeline_reply rendering in BAND room."""

    def test_format_pipeline_reply_success(self, sample_pipeline_response):
        """Verify comprehensive markdown rendering with all 4 agents, summary, and dashboard JSON."""
        reply = format_pipeline_reply(sample_pipeline_response, "Artificial intelligence")

        assert "IntelliScope Multi-Agent Intelligence Pipeline" in reply
        assert "Artificial intelligence" in reply
        assert "SUCCESS" in reply

        # Check all 4 agents listed
        assert "Data Collector Agent" in reply
        assert "Research Verification Agent" in reply
        assert "Insight Analyst Agent" in reply
        assert "Dashboard Builder Agent" in reply

        # Check Executive Summary
        assert "Artificial intelligence research encompasses machine intelligence" in reply

        # Check Verified Sources with URL
        assert "[Artificial intelligence](https://en.wikipedia.org/wiki/Artificial_intelligence)" in reply

        # Check KPI Overview
        assert "Total Sources" in reply

        # Check Dashboard Specification JSON block
        assert "```json" in reply
        assert "dash-test-1234" in reply
        assert "chart-1" in reply

    def test_format_pipeline_reply_empty(self):
        """Verify zero-evidence pipeline reply communicates absence of data truthfully."""
        empty_pipeline_data = {
            "status": "success",
            "total_duration_ms": 42.0,
            "summary": "No verified encyclopedia sources were available for this topic.",
            "agent_statuses": {
                "data_collector": {"agent_name": "Data Collector Agent", "status": "completed", "duration_ms": 10.0, "details": "Retrieved 0 external source(s)"},
                "research_verification": {"agent_name": "Research Verification Agent", "status": "completed", "duration_ms": 8.0, "details": "Quality score: 0/100 (0 valid, 0 invalid)"},
                "insight_analyst": {"agent_name": "Insight Analyst Agent", "status": "completed", "duration_ms": 12.0, "details": "Analyzed 0 eligible source(s)"},
                "dashboard_builder": {"agent_name": "Dashboard Builder Agent", "status": "completed", "duration_ms": 12.0, "details": "Generated 4 KPI card(s)"},
            },
            "research": {"result_count": 0, "results": []},
            "dashboard": {"kpi_cards": []},
        }

        reply = format_pipeline_reply(empty_pipeline_data, "NonexistentTopic")
        assert "No verified articles or summary snippets were found" in reply
        assert "Zero data fabricated" in reply


class TestBandPipelineAdapterTurn:
    """Test suite for BandDataCollectorAdapter executing the unified multi-agent pipeline."""

    @pytest.mark.asyncio
    async def test_adapter_on_message_pipeline_turn_success(self, sample_pipeline_response):
        """Verify full adapter turn calling POST /pipeline and sending summary + dashboard JSON."""
        adapter = BandDataCollectorAdapter(backend_url="http://127.0.0.1:8010")
        tools = create_test_fake_tools(sender_name="Alice", sender_id="user-123")
        msg = create_platform_message("@DataCollector research Artificial intelligence", sender_name="Alice")

        with patch("scripts.band_collector_agent.call_pipeline_api", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = (True, sample_pipeline_response)

            await adapter.on_message(
                msg=msg,
                tools=tools,
                history=[],
                participants_msg=None,
                contacts_msg=None,
                is_session_bootstrap=False,
                room_id="room-test-001",
            )

            # Check that call_pipeline_api was called with query and limit
            mock_pipeline.assert_called_once_with(
                query="Artificial intelligence",
                limit=3,
                backend_url="http://127.0.0.1:8010",
            )

            # Check message delivery to room
            assert len(tools.messages_sent) == 1
            sent = tools.messages_sent[0]
            assert "Alice" in sent["mentions"]
            assert "IntelliScope Multi-Agent Intelligence Pipeline" in sent["content"]
            assert "Artificial intelligence" in sent["content"]
            assert "https://en.wikipedia.org/wiki/Artificial_intelligence" in sent["content"]
            assert "Dashboard Specification JSON" in sent["content"]
            assert "```json" in sent["content"]
            assert tools.turn.replied is True

    @pytest.mark.asyncio
    async def test_adapter_on_message_pipeline_failure(self):
        """Verify failure in pipeline execution is reported safely to room."""
        adapter = BandDataCollectorAdapter(backend_url="http://127.0.0.1:8010")
        tools = create_test_fake_tools(sender_name="Bob")
        msg = create_platform_message("@DataCollector research Quantum computing", sender_name="Bob")

        with patch("scripts.band_collector_agent.call_pipeline_api", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = (False, "Pipeline execution failed at Data Collector Agent: Timeout")

            await adapter.on_message(
                msg=msg,
                tools=tools,
                history=[],
                participants_msg=None,
                contacts_msg=None,
                is_session_bootstrap=False,
                room_id="room-test-001",
            )

            assert len(tools.messages_sent) == 1
            sent = tools.messages_sent[0]
            assert "Bob" in sent["mentions"]
            assert "Pipeline execution failed at Data Collector Agent" in sent["content"]
            assert tools.turn.replied is True

    @pytest.mark.asyncio
    async def test_adapter_on_message_passes_sanitized_query_to_pipeline(self, sample_pipeline_response):
        """
        Verify '@IntelliScope Collector Research quantum computing'
        correctly extracts 'quantum computing' and passes it to POST /pipeline.
        """
        adapter = BandDataCollectorAdapter(backend_url="http://127.0.0.1:8010")
        tools = create_test_fake_tools(sender_name="Alice")
        msg = create_platform_message("@IntelliScope Collector Research quantum computing", sender_name="Alice")

        with patch("scripts.band_collector_agent.call_pipeline_api", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = (True, sample_pipeline_response)

            await adapter.on_message(
                msg=msg,
                tools=tools,
                history=[],
                participants_msg=None,
                contacts_msg=None,
                is_session_bootstrap=False,
                room_id="room-test-001",
            )

            # Must call pipeline with 'quantum computing' - NOT '/intelliscope-collector...'
            mock_pipeline.assert_called_once_with(
                query="quantum computing",
                limit=3,
                backend_url="http://127.0.0.1:8010",
            )

    @pytest.mark.asyncio
    async def test_adapter_on_message_slash_handle_passes_sanitized_query_to_pipeline(self, sample_pipeline_response):
        """
        Verify '/intelliscope-collector Research quantum computing'
        strips the leading command handle and passes 'quantum computing' to POST /pipeline.
        """
        adapter = BandDataCollectorAdapter(backend_url="http://127.0.0.1:8010")
        tools = create_test_fake_tools(sender_name="Alice")
        msg = create_platform_message("/intelliscope-collector Research quantum computing", sender_name="Alice")

        with patch("scripts.band_collector_agent.call_pipeline_api", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = (True, sample_pipeline_response)

            await adapter.on_message(
                msg=msg,
                tools=tools,
                history=[],
                participants_msg=None,
                contacts_msg=None,
                is_session_bootstrap=False,
                room_id="room-test-001",
            )

            mock_pipeline.assert_called_once_with(
                query="quantum computing",
                limit=3,
                backend_url="http://127.0.0.1:8010",
            )

    @pytest.mark.asyncio
    async def test_adapter_on_message_integration_research_quantum_computing_becomes_quantum_computing(
        self, sample_pipeline_response
    ):
        """
        Integration test verifying 'Research quantum computing' becomes 'quantum computing'
        and executes successfully through the adapter pipeline dispatch.
        """
        adapter = BandDataCollectorAdapter(backend_url="http://127.0.0.1:8010")
        tools = create_test_fake_tools(sender_name="Researcher")
        msg = create_platform_message("Research quantum computing", sender_name="Researcher")

        with patch("scripts.band_collector_agent.call_pipeline_api", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = (True, sample_pipeline_response)

            await adapter.on_message(
                msg=msg,
                tools=tools,
                history=[],
                participants_msg=None,
                contacts_msg=None,
                is_session_bootstrap=False,
                room_id="room-test-001",
            )

            # Assert exact sanitized query passed to pipeline
            mock_pipeline.assert_called_once_with(
                query="quantum computing",
                limit=3,
                backend_url="http://127.0.0.1:8010",
            )
            assert tools.turn.replied is True

    @pytest.mark.asyncio
    async def test_adapter_on_message_multiple_mentions_to_pipeline(self, sample_pipeline_response):
        """Verify multiple mentions are stripped and query with limit dispatched to pipeline."""
        adapter = BandDataCollectorAdapter(backend_url="http://127.0.0.1:8010")
        tools = create_test_fake_tools(sender_name="Dan")
        msg = create_platform_message("@Alice @Bob @IntelliScope Collector Research quantum computing limit=5", sender_name="Dan")

        with patch("scripts.band_collector_agent.call_pipeline_api", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = (True, sample_pipeline_response)

            await adapter.on_message(
                msg=msg,
                tools=tools,
                history=[],
                participants_msg=None,
                contacts_msg=None,
                is_session_bootstrap=False,
                room_id="room-test-001",
            )

            mock_pipeline.assert_called_once_with(
                query="quantum computing",
                limit=5,
                backend_url="http://127.0.0.1:8010",
            )


class TestPhase34BandDashboardConsistency:
    """Regression suite for Phase 3.4 BAND and frontend payload parity."""

    def test_phase_3_4_band_reply_preserves_three_themes_and_provenance(self):
        """
        Verify BAND format_pipeline_reply renders all 3 analyst themes with names
        and evidence counts, includes non-empty dashboard themes JSON (never []),
        and preserves verification counts, provenance, confidence reasons, and chart heuristic flags.
        """
        import json as _json
        import re as _re

        real_backend_payload = {
            "pipeline_id": "pipe-nn-001",
            "query": "neural networks",
            "status": "success",
            "total_duration_ms": 210.5,
            "summary": "Artificial neural networks are computational models inspired by biological neurons.",
            "agent_statuses": {
                "data_collector": {"agent_name": "Data Collector Agent", "status": "completed", "duration_ms": 80.0, "details": "Retrieved 3 external source(s)"},
                "research_verification": {"agent_name": "Research Verification Agent", "status": "completed", "duration_ms": 20.0, "details": "Quality score: 100/100 (3 valid, 0 excluded, 2 directly relevant, 1 weakly relevant)"},
                "insight_analyst": {"agent_name": "Insight Analyst Agent", "status": "completed", "duration_ms": 60.0, "details": "Analyzed 3 eligible source(s) (0 excluded), 3 theme(s)"},
                "dashboard_builder": {"agent_name": "Dashboard Builder Agent", "status": "completed", "duration_ms": 50.5, "details": "Generated 4 KPI card(s) and 3 chart specification(s)"},
            },
            "research": {
                "query": "neural networks",
                "result_count": 3,
                "results": [
                    {
                        "title": "Neural network (machine learning)",
                        "snippet": "A neural network is a model inspired by biological neurons.",
                        "source_url": "https://en.wikipedia.org/wiki/Neural_network_(machine_learning)",
                        "source_type": "wikipedia_extract",
                        "relevance": "relevant",
                        "is_weakly_relevant": False,
                    },
                    {
                        "title": "Deep learning",
                        "snippet": "Deep learning uses multiple neural network layers.",
                        "source_url": "https://en.wikipedia.org/wiki/Deep_learning",
                        "source_type": "wikipedia_extract",
                        "relevance": "relevant",
                        "is_weakly_relevant": False,
                    },
                    {
                        "title": "Frank Rosenblatt",
                        "snippet": "American psychologist known for the perceptron in neural networks.",
                        "source_url": "https://en.wikipedia.org/wiki/Frank_Rosenblatt",
                        "source_type": "wikipedia_search_snippet",
                        "relevance": "weakly_relevant",
                        "is_weakly_relevant": True,
                    },
                ],
            },
            "verification": {
                "quality_score": 100.0,
                "structurally_valid_count": 3,
                "excluded_count": 0,
                "directly_relevant_count": 2,
                "weakly_relevant_count": 1,
                "is_factually_verified": False,
            },
            "analysis": {
                "topic": "neural networks",
                "key_themes": [
                    {"theme": "Systems, Architectures & Methods", "description": "Multilayer architectures.", "frequency": 3, "sources": ["https://en.wikipedia.org/wiki/Deep_learning"]},
                    {"theme": "Foundations & Core Principles", "description": "Artificial neurons.", "frequency": 2, "sources": ["https://en.wikipedia.org/wiki/Neural_network_(machine_learning)"]},
                    {"theme": "Historical & Pioneers", "description": "Early perceptron work.", "frequency": 1, "sources": ["https://en.wikipedia.org/wiki/Frank_Rosenblatt"]},
                ],
                "evidence_backed_observations": [
                    {
                        "statement": "Neural networks use interconnected artificial nodes.",
                        "source_title": "Neural network (machine learning)",
                        "source_url": "https://en.wikipedia.org/wiki/Neural_network_(machine_learning)",
                        "confidence": "high",
                        "confidence_reason": "Substantive wikipedia_extract directly relevant to query.",
                        "is_weakly_relevant": False,
                    },
                ],
            },
            "dashboard": {
                "dashboard_id": "dash-nn-001",
                "topic": "neural networks",
                "title": "Research Intelligence Dashboard: neural networks",
                "kpi_cards": [
                    {"id": "kpi-total-sources", "label": "Total Sources Evaluated", "value": 3},
                    {"id": "kpi-theme-count", "label": "Identified Themes", "value": 3},
                ],
                "themes": [
                    {"theme": "Systems, Architectures & Methods", "name": "Systems, Architectures & Methods", "frequency": 3, "evidence_count": 3, "description": "Multilayer architectures."},
                    {"theme": "Foundations & Core Principles", "name": "Foundations & Core Principles", "frequency": 2, "evidence_count": 2, "description": "Artificial neurons."},
                    {"theme": "Historical & Pioneers", "name": "Historical & Pioneers", "frequency": 1, "evidence_count": 1, "description": "Early perceptron work."},
                ],
                "key_themes": [
                    {"theme": "Systems, Architectures & Methods", "name": "Systems, Architectures & Methods", "frequency": 3, "evidence_count": 3},
                    {"theme": "Foundations & Core Principles", "name": "Foundations & Core Principles", "frequency": 2, "evidence_count": 2},
                    {"theme": "Historical & Pioneers", "name": "Historical & Pioneers", "frequency": 1, "evidence_count": 1},
                ],
                "charts": [
                    {
                        "id": "chart-theme-distribution",
                        "title": "Research Theme Distribution",
                        "chart_type": "horizontal_bar",
                        "is_heuristic": True,
                        "data": [
                            {"label": "Systems, Architectures & Methods", "value": 3.0},
                            {"label": "Foundations & Core Principles", "value": 2.0},
                            {"label": "Historical & Pioneers", "value": 1.0},
                        ],
                    }
                ],
                "metadata": {"schema_version": "1.0.0", "theme_count": 3, "is_heuristic_clustering": True},
            },
        }

        reply = format_pipeline_reply(real_backend_payload, "neural networks")

        # All 3 themes appear in summary markdown
        assert "Key Themes (3)" in reply
        assert "Systems, Architectures & Methods" in reply
        assert "Foundations & Core Principles" in reply
        assert "Historical & Pioneers" in reply

        # Verification counts & factual boundary included
        assert "Directly Relevant: **2**" in reply
        assert "Weakly Relevant: **1**" in reply
        assert "Factually Verified: False" in reply

        # Provenance & confidence rationale included
        assert "wikipedia_extract" in reply
        assert "Substantive wikipedia_extract directly relevant to query." in reply

        # Embedded Dashboard JSON must have 3 themes (never []) and heuristic flag preserved
        match = _re.search(r"```json\n(.*?)\n```", reply, flags=_re.DOTALL)
        assert match is not None
        dash_json = _json.loads(match.group(1))
        assert len(dash_json["themes"]) == 3
        assert dash_json["themes"][0]["name"] == "Systems, Architectures & Methods"
        assert dash_json["themes"][0]["evidence_count"] == 3
        assert dash_json["charts"][0]["is_heuristic"] is True

    def test_phase_3_4_band_reply_empty_themes_honest(self):
        """Verify BAND format_pipeline_reply handles empty themes honestly without fabrication."""
        import json as _json
        import re as _re

        payload = {
            "pipeline_id": "pipe-empty-themes",
            "query": "obscure stub topic",
            "status": "success",
            "total_duration_ms": 100.0,
            "summary": "One valid source found, no distinct thematic clusters identified.",
            "agent_statuses": {},
            "research": {
                "result_count": 1,
                "results": [
                    {
                        "title": "Obscure stub",
                        "snippet": "Brief valid encyclopedia mention.",
                        "source_url": "https://en.wikipedia.org/wiki/Obscure_stub",
                        "source_type": "wikipedia_extract",
                    }
                ],
            },
            "verification": {
                "quality_score": 100.0,
                "structurally_valid_count": 1,
                "excluded_count": 0,
                "directly_relevant_count": 1,
                "weakly_relevant_count": 0,
                "is_factually_verified": False,
            },
            "analysis": {
                "topic": "obscure stub topic",
                "key_themes": [],
                "evidence_backed_observations": [],
            },
            "dashboard": {
                "dashboard_id": "dash-empty-themes",
                "topic": "obscure stub topic",
                "title": "Research Intelligence Dashboard: obscure stub topic",
                "kpi_cards": [{"id": "kpi-theme-count", "label": "Identified Themes", "value": 0}],
                "themes": [],
                "key_themes": [],
                "charts": [],
                "metadata": {"theme_count": 0},
            },
        }

        reply = format_pipeline_reply(payload, "obscure stub topic")
        assert "Key Themes (0)" in reply
        assert "None identified" in reply

        match = _re.search(r"```json\n(.*?)\n```", reply, flags=_re.DOTALL)
        assert match is not None
        dash_json = _json.loads(match.group(1))
        assert dash_json["themes"] == []





