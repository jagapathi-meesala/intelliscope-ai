"""
Mocked unit & interoperability tests for Phase 5 sponsor adapters:
BAND, Lyzr, Agent37, AdaL, Finch, and IntegrationRegistry.

Tests:
- Environment-based configuration without secret leakage
- Honest integration category & runtime_state reporting
- Structured task delegation & schema validation
- Retry & timeout handling on transient failures (429 / 5xx / TimeoutException)
- Permanent rejection & malformed upstream payload handling
"""

import asyncio
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.integrations import (
    AdalAdapter,
    Agent37Adapter,
    BandSponsorAdapter,
    DelegationTaskRequest,
    FinchAdapter,
    IntegrationRegistry,
    LyzrAdapter,
    sanitize_error_message,
)


def test_sanitize_error_message_redacts_secrets():
    raw = "Auth failed for Bearer secret_tok_999 and x-api-key=mysecret123 sk_live_abc123"
    cleaned = sanitize_error_message(raw, secrets=["mysecret123", "secret_tok_999"])
    assert "mysecret123" not in cleaned
    assert "secret_tok_999" not in cleaned
    assert "sk_live_abc123" not in cleaned
    assert "[REDACTED]" in cleaned


@pytest.mark.asyncio
async def test_band_adapter_unconfigured_and_mocked_rest(monkeypatch, tmp_path):
    monkeypatch.delenv("BAND_AGENT_ID", raising=False)
    monkeypatch.delenv("BAND_API_KEY", raising=False)
    adapter = BandSponsorAdapter(config_path=tmp_path / "missing.yaml")

    assert adapter.is_configured() is False
    info = adapter.get_status()
    assert info.status == "implemented"
    assert info.runtime_state == "unconfigured"
    assert info.credentials_present is False

    health = await adapter.delegate_task(
        DelegationTaskRequest(target_platform="band", action="health_check")
    )
    assert health.status == "unconfigured"
    assert health.output_valid is False

    # Configured via env + mocked REST client
    monkeypatch.setenv("BAND_AGENT_ID", "agent-uuid-12345")
    monkeypatch.setenv("BAND_API_KEY", "band-secret-xyz")
    assert adapter.is_configured() is True

    mock_me = SimpleNamespace(id="agent-uuid-12345", handle="intelliscope-collector", name="IntelliScope Collector")
    mock_rest_instance = MagicMock()
    mock_rest_instance.agent_api_identity.get_agent_me = AsyncMock(
        return_value=SimpleNamespace(data=mock_me)
    )
    with patch("backend.integrations.band_adapter.AsyncRestClient", return_value=mock_rest_instance):
        checked = await adapter.check_connectivity()
        assert checked.last_check_status == "connected"
        assert checked.last_check_error is None

        res = await adapter.delegate_task(
            DelegationTaskRequest(target_platform="band", action="health_check")
        )
        assert res.status == "completed"
        assert res.output_valid is True
        assert res.output["agent_handle"] == "intelliscope-collector"


@pytest.mark.asyncio
async def test_band_adapter_peer_handoff_validation():
    adapter = BandSponsorAdapter()
    ok_res = await adapter.delegate_task(
        DelegationTaskRequest(
            execution_id="exec-band-1234",
            target_platform="band",
            action="prepare_peer_handoff",
            payload={
                "peer_handle": "@insight-analyst",
                "query": "quantum error correction",
                "summary": "Verified 2 sources.",
                "source_urls": ["https://arxiv.org/abs/2401.12345v1"],
            },
        )
    )
    assert ok_res.status == "completed"
    assert ok_res.output_valid is True
    assert "@insight-analyst" in ok_res.output["message"]

    parsed = BandSponsorAdapter.parse_delegation_envelope(ok_res.output["message"])
    assert parsed is not None
    assert parsed["execution_id"] == "exec-band-1234"
    assert parsed["source_urls"] == ["https://arxiv.org/abs/2401.12345v1"]

    # Rejects unsafe non-HTTPS URLs
    bad_url_res = await adapter.delegate_task(
        DelegationTaskRequest(
            target_platform="band",
            action="prepare_peer_handoff",
            payload={
                "peer_handle": "peer-one",
                "query": "test",
                "source_urls": ["javascript:alert(1)"],
            },
        )
    )
    assert bad_url_res.status == "rejected"
    assert bad_url_res.error_code == "unsafe_url_rejected"


@pytest.mark.asyncio
async def test_lyzr_adapter_unconfigured_success_retry_and_failures(monkeypatch):
    monkeypatch.delenv("LYZR_API_KEY", raising=False)
    monkeypatch.delenv("LYZR_AGENT_ID", raising=False)
    adapter = LyzrAdapter()

    assert adapter.is_configured() is False
    assert adapter.integration_category() == "partial"
    assert adapter.runtime_state() == "unconfigured"

    unconf = await adapter.delegate_task(
        DelegationTaskRequest(
            target_platform="lyzr",
            action="chat_inference",
            payload={"message": "Summarize"},
        )
    )
    assert unconf.status == "unconfigured"

    monkeypatch.setenv("LYZR_API_KEY", "lyzr-secret-token-999")
    monkeypatch.setenv("LYZR_AGENT_ID", "lyzr-agent-abc")

    # health_check validates configuration without paid LLM call
    hc = await adapter.delegate_task(
        DelegationTaskRequest(target_platform="lyzr", action="health_check")
    )
    assert hc.status == "completed"
    assert hc.output["configured"] is True

    # Transient HTTP 503 followed by 200 success (tests retry behavior)
    attempts = {"count": 0}

    async def retry_handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        assert request.headers["x-api-key"] == "lyzr-secret-token-999"
        if attempts["count"] == 1:
            return httpx.Response(503, text="Service temporarily overloaded")
        return httpx.Response(200, json={"response": "Lyzr synthesis complete."})

    async with httpx.AsyncClient(transport=httpx.MockTransport(retry_handler)) as client:
        ok = await adapter.delegate_task(
            DelegationTaskRequest(
                execution_id="exec-lyzr-1",
                target_platform="lyzr",
                action="chat_inference",
                max_retries=1,
                payload={"message": "Analyze quantum computing summary"},
            ),
            client=client,
        )
    assert ok.status == "completed"
    assert ok.output_valid is True
    assert ok.retries_used == 1
    assert ok.output["response"] == "Lyzr synthesis complete."

    # Malformed / missing 'response' field rejected cleanly without secret leak
    async def invalid_output_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "missing response field"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(invalid_output_handler)) as client:
        bad = await adapter.delegate_task(
            DelegationTaskRequest(
                target_platform="lyzr",
                action="chat_inference",
                max_retries=0,
                payload={"message": "Analyze"},
            ),
            client=client,
        )
    assert bad.status == "failed"
    assert bad.output_valid is False
    assert bad.error_code == "invalid_output_schema"
    assert "lyzr-secret-token-999" not in (bad.error or "")

    # Timeout handling
    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
        timed = await adapter.delegate_task(
            DelegationTaskRequest(
                target_platform="lyzr",
                action="chat_inference",
                max_retries=1,
                payload={"message": "Analyze"},
            ),
            client=client,
        )
    assert timed.status == "timed_out"
    assert timed.retries_used == 1
    assert timed.error_code == "timeout"


@pytest.mark.asyncio
async def test_agent37_adapter_unconfigured_exec_retry_and_validation(monkeypatch):
    monkeypatch.delenv("AGENT37_API_KEY", raising=False)
    monkeypatch.delenv("AGENT37_INSTANCE_ID", raising=False)
    adapter = Agent37Adapter()

    assert adapter.is_configured() is False
    assert adapter.integration_category() == "partial"

    monkeypatch.setenv("AGENT37_API_KEY", "sk_live_agent37_secret")
    monkeypatch.setenv("AGENT37_INSTANCE_ID", "inst-99")

    # Empty command rejected
    rejected = await adapter.delegate_task(
        DelegationTaskRequest(
            target_platform="agent37",
            action="sandbox_exec",
            payload={"command": "   "},
        )
    )
    assert rejected.status == "rejected"
    assert rejected.error_code == "validation_error"

    # Transient 429 then 200 exec success
    calls = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.headers["X-Agent37-Key"] == "sk_live_agent37_secret"
        if calls["n"] == 1:
            return httpx.Response(429, text="Rate limited")
        return httpx.Response(200, json={"exit_code": 0, "stdout": "ok"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await adapter.delegate_task(
            DelegationTaskRequest(
                target_platform="agent37",
                action="sandbox_exec",
                max_retries=1,
                payload={"command": "echo hello"},
            ),
            client=client,
        )
    assert res.status == "completed"
    assert res.output_valid is True
    assert res.retries_used == 1
    assert res.output["stdout"] == "ok"


@pytest.mark.asyncio
async def test_lyzr_workflow_execute(monkeypatch):
    monkeypatch.delenv("LYZR_API_KEY", raising=False)
    monkeypatch.delenv("LYZR_AGENT_ID", raising=False)
    monkeypatch.delenv("LYZR_WORKFLOW_ID", raising=False)
    adapter = LyzrAdapter()

    unconf = await adapter.delegate_task(
        DelegationTaskRequest(
            target_platform="lyzr",
            action="workflow_execute",
            payload={"input": "Summarize quantum computing"},
        )
    )
    assert unconf.status == "unconfigured"
    assert unconf.error_code == "not_configured"

    monkeypatch.setenv("LYZR_API_KEY", "lyzr-secret-wf")
    monkeypatch.setenv("LYZR_WORKFLOW_ID", "wf-123")
    assert adapter.is_configured() is True

    async def wf_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/workflows/wf-123/execute"
        assert request.headers["x-api-key"] == "lyzr-secret-wf"
        body = json.loads(request.content.decode("utf-8"))
        assert body["input"] == "Summarize quantum computing"
        return httpx.Response(200, json={"run_id": "run-1", "output": "Workflow done"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(wf_handler)) as client:
        ok = await adapter.delegate_task(
            DelegationTaskRequest(
                target_platform="lyzr",
                action="workflow_execute",
                payload={"input": "Summarize quantum computing"},
            ),
            client=client,
        )
    assert ok.status == "completed"
    assert ok.output_valid is True
    assert ok.output["workflow_id"] == "wf-123"
    assert ok.output["result"]["output"] == "Workflow done"


@pytest.mark.asyncio
async def test_adal_and_finch_honest_adapters(monkeypatch):
    monkeypatch.delenv("ADAL_ENABLED", raising=False)
    monkeypatch.delenv("ADAL_CLI_PATH", raising=False)
    adal = AdalAdapter()

    with patch("backend.integrations.adal_adapter.shutil.which", return_value=None), patch(
        "backend.integrations.adal_adapter.importlib.util.find_spec", return_value=None
    ):
        assert adal.is_configured() is False
        assert adal.integration_category() == "partial"
        assert adal.runtime_state() == "not_installed"
        res = await adal.delegate_task(
            DelegationTaskRequest(
                target_platform="adal",
                action="cli_prompt",
                payload={"prompt": "check"},
            )
        )
        assert res.status == "unconfigured"
        assert res.error_code == "not_installed"

    # Official CLI invocation (`adal -q <prompt> -o json --workspace ... --enabled-default-tools Read,Search`)
    monkeypatch.setenv("ADAL_ENABLED", "true")
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.communicate = AsyncMock(return_value=(b'{"ok": true, "summary": "verified"}', b""))

    with patch("backend.integrations.adal_adapter.shutil.which", return_value="/usr/local/bin/adal"), patch(
        "backend.integrations.adal_adapter.importlib.util.find_spec", return_value=None
    ), patch("backend.integrations.adal_adapter.asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_proc)) as exec_mock:
        cli_res = await adal.delegate_task(
            DelegationTaskRequest(
                target_platform="adal",
                action="cli_prompt",
                payload={"prompt": "audit repository"},
            )
        )
    assert cli_res.status == "completed"
    assert cli_res.output_valid is True
    assert cli_res.output["mode"] == "adal_cli"
    assert cli_res.output["json_output"] == {"ok": True, "summary": "verified"}
    called_args = exec_mock.call_args[0]
    assert called_args[0] == "/usr/local/bin/adal"
    assert "-q" in called_args and "audit repository" in called_args
    assert "-o" in called_args and "json" in called_args
    assert "--workspace" in called_args
    assert "--enabled-default-tools" in called_args and "Read,Search" in called_args

    # Official adal_agent_sdk query() invocation
    async def fake_sdk_query(prompt: str, options=None):
        assert prompt == "sdk check"
        assert options.enabled_default_tools == ["Read", "Search"]
        yield {"type": "assistant.message.completed", "message": {"content": "SDK audit complete."}}

    fake_sdk_mod = SimpleNamespace(
        AdalAgentOptions=lambda **kwargs: SimpleNamespace(**kwargs),
        query=fake_sdk_query,
    )
    with patch("backend.integrations.adal_adapter.shutil.which", return_value=None), patch(
        "backend.integrations.adal_adapter.importlib.util.find_spec", return_value=object()
    ), patch.dict(sys.modules, {"adal_agent_sdk": fake_sdk_mod}):
        sdk_res = await adal.delegate_task(
            DelegationTaskRequest(
                target_platform="adal",
                action="sdk_query",
                payload={"prompt": "sdk check"},
            )
        )
    assert sdk_res.status == "completed"
    assert sdk_res.output_valid is True
    assert sdk_res.output == {"response": "SDK audit complete.", "mode": "adal_agent_sdk"}

    # Finch local MCP stdio + Skill integration
    monkeypatch.delenv("FINCH_ENABLED", raising=False)
    monkeypatch.delenv("FINCH_MCP_URL", raising=False)
    finch = FinchAdapter()
    assert finch.integration_category() == "implemented"
    assert finch.runtime_state() == "ready"
    manifest = await finch.delegate_task(
        DelegationTaskRequest(target_platform="finch", action="inspect_mcp_manifest")
    )
    assert manifest.status == "completed"
    assert manifest.output_valid is True
    assert len(manifest.output["tools"]) == 4
    assert "intelliscope-ai" in manifest.output["mcp_servers_config"].get("mcpServers", {})

    handshake = await finch.delegate_task(
        DelegationTaskRequest(target_platform="finch", action="verify_mcp_handshake")
    )
    assert handshake.status == "completed"
    assert handshake.output_valid is True
    assert set(handshake.output["tools"]) == {
        "intelliscope_research",
        "intelliscope_verify",
        "intelliscope_pipeline",
        "intelliscope_integrations_status",
    }

    blocked = await finch.delegate_task(
        DelegationTaskRequest(target_platform="finch", action="run_workflow")
    )
    assert blocked.status == "rejected"
    assert blocked.error_code == "unsupported_action"


@pytest.mark.asyncio
async def test_mcp_stdio_server_jsonrpc_and_subprocess():
    from scripts.intelliscope_mcp_server import handle_jsonrpc_message

    init = await handle_jsonrpc_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["protocolVersion"] == "2024-11-05"
    assert init["result"]["serverInfo"]["name"] == "intelliscope-ai-mcp"

    assert (
        await handle_jsonrpc_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
    ) is None

    tools_list = await handle_jsonrpc_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in tools_list["result"]["tools"]]
    assert names == [
        "intelliscope_research",
        "intelliscope_verify",
        "intelliscope_pipeline",
        "intelliscope_integrations_status",
    ]

    status_call = await handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "intelliscope_integrations_status", "arguments": {}},
        }
    )
    assert status_call["result"]["isError"] is False
    parsed = json.loads(status_call["result"]["content"][0]["text"])
    assert set(parsed["platforms"].keys()) == {"band", "lyzr", "agent37", "adal", "finch"}

    # Real stdio subprocess test (newline + Content-Length framing)
    server_script = Path(__file__).resolve().parent.parent / "scripts" / "intelliscope_mcp_server.py"
    req_init = json.dumps({"jsonrpc": "2.0", "id": 10, "method": "initialize", "params": {}}) + "\n"
    ping_body = json.dumps({"jsonrpc": "2.0", "id": 11, "method": "ping"})
    req_ping = f"Content-Length: {len(ping_body.encode('utf-8'))}\r\n\r\n{ping_body}"

    proc = subprocess.run(
        [sys.executable, str(server_script)],
        input=(req_init + req_ping).encode("utf-8"),
        capture_output=True,
        timeout=15,
        check=True,
    )
    lines = [json.loads(line) for line in proc.stdout.decode("utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0]["id"] == 10
    assert lines[0]["result"]["serverInfo"]["name"] == "intelliscope-ai-mcp"
    assert lines[1] == {"jsonrpc": "2.0", "id": 11, "result": {}}


@pytest.mark.asyncio
async def test_integration_registry_status_and_unknown_platform(monkeypatch, tmp_path):
    monkeypatch.delenv("BAND_AGENT_ID", raising=False)
    monkeypatch.delenv("BAND_API_KEY", raising=False)
    monkeypatch.delenv("LYZR_API_KEY", raising=False)
    monkeypatch.delenv("LYZR_AGENT_ID", raising=False)
    monkeypatch.delenv("LYZR_WORKFLOW_ID", raising=False)
    monkeypatch.delenv("AGENT37_API_KEY", raising=False)
    monkeypatch.delenv("AGENT37_INSTANCE_ID", raising=False)
    monkeypatch.delenv("ADAL_ENABLED", raising=False)
    monkeypatch.delenv("ADAL_CLI_PATH", raising=False)

    missing_live = tmp_path / "missing_live_band.json"
    monkeypatch.setattr("backend.integrations.band_adapter.LIVE_BAND_VERIFICATION_FILE", missing_live)

    with patch("backend.integrations.adal_adapter.shutil.which", return_value=None), patch(
        "backend.integrations.adal_adapter.importlib.util.find_spec", return_value=None
    ):
        registry = IntegrationRegistry(
            adapters={
                "band": BandSponsorAdapter(config_path=tmp_path / "missing.yaml"),
                "lyzr": LyzrAdapter(),
                "agent37": Agent37Adapter(),
                "adal": AdalAdapter(),
                "finch": FinchAdapter(),
            }
        )
        status_resp = registry.get_status_response()

    assert set(status_resp.platforms.keys()) == {"band", "lyzr", "agent37", "adal", "finch"}
    assert status_resp.summary["live_tested"] == 0
    assert status_resp.summary["implemented"] == 2
    assert status_resp.summary["partial"] == 3
    assert status_resp.summary["not_integrated"] == 0

    for pid in ("band", "lyzr", "adal", "finch"):
        assert status_resp.platforms[pid].mandatory_for_track is True
    assert status_resp.platforms["agent37"].mandatory_for_track is False

    for pid in ("band", "lyzr", "agent37", "adal"):
        assert status_resp.platforms[pid].credentials_present is False
    assert status_resp.platforms["finch"].credentials_present is True

    # Honest BAND live_tested status only when recorded e2e artifact passes AND credentials exist
    live_file = tmp_path / "live_band_ok.json"
    live_file.write_text(
        json.dumps({"e2e_room_roundtrip_passed": True, "verified_at": "2026-11-12T00:00:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.integrations.band_adapter.LIVE_BAND_VERIFICATION_FILE", live_file)
    monkeypatch.setenv("BAND_AGENT_ID", "agent-live-1")
    monkeypatch.setenv("BAND_API_KEY", "key-live-1")
    live_band = BandSponsorAdapter(config_path=tmp_path / "missing.yaml")
    assert live_band.integration_category() == "live_tested"

    assert await registry.check_platform("nonexistent") is None

