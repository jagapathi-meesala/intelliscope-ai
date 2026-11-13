"""
Finch Desktop Agent Integration (`finchwork.app` / `finchwork.net`).

Implements Finch's officially documented integration mechanism:
1. Local Model Context Protocol (MCP) stdio server (`scripts/intelliscope_mcp_server.py`)
2. Standard `mcpServers` JSON config (`integrations/finch/mcp_servers.json`)
3. Companion Finch Agent Skill (`integrations/finch/SKILL.md`)

Never invents unsupported external Finch REST endpoints; verifies the actual
MCP JSON-RPC 2.0 protocol locally via stdio and clearly distinguishes local
MCP implementation from live Finch Desktop GUI execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, Optional

import httpx

from backend.config import settings
from backend.integrations.base import SponsorAdapter
from backend.integrations.models import (
    DelegationTaskRequest,
    DelegationTaskResult,
    IntegrationCategoryLiteral,
    PlatformIntegrationInfo,
    RuntimeStateLiteral,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MCP_SERVER_PATH = PROJECT_ROOT / "scripts" / "intelliscope_mcp_server.py"
FINCH_MCP_CONFIG_PATH = PROJECT_ROOT / "integrations" / "finch" / "mcp_servers.json"
FINCH_SKILL_PATH = PROJECT_ROOT / "integrations" / "finch" / "SKILL.md"


class FinchAdapter(SponsorAdapter):
    """Official MCP & Skill integration adapter for Finch Desktop."""

    platform_id = "finch"
    display_name = "Finch Desktop (MCP / Skill)"
    mandatory_for_track = True
    track_requirement_note = (
        "Mandatory hackathon sponsor for Research — Data & Build; integrates via standard MCP "
        "(`mcpServers` stdio server) and Finch Agent Skill (`SKILL.md`)."
    )
    transport_protocol = "Local MCP JSON-RPC 2.0 (stdio) + SKILL.md"
    required_env_vars = ["FINCH_ENABLED (optional bridge toggle)"]
    official_docs_url = "https://finchwork.net"
    capabilities = [
        "mcp_stdio_server",
        "finch_mcp_servers_config",
        "finch_skill_markdown",
        "mcp_manifest_descriptor",
    ]

    def _local_mcp_assets_ready(self) -> bool:
        return (
            MCP_SERVER_PATH.exists()
            and FINCH_MCP_CONFIG_PATH.exists()
            and FINCH_SKILL_PATH.exists()
        )

    def _bridge_url(self) -> Optional[str]:
        env_enabled = os.environ.get("FINCH_ENABLED")
        enabled = (
            env_enabled.strip().lower() in ("1", "true", "yes")
            if env_enabled is not None
            else bool(settings.FINCH_ENABLED)
        )
        url = (os.environ.get("FINCH_MCP_URL") or settings.FINCH_MCP_URL or "").strip() or None
        return url if (enabled and url) else None

    def is_configured(self) -> bool:
        return self._local_mcp_assets_ready()

    def integration_category(self) -> IntegrationCategoryLiteral:
        if self._local_mcp_assets_ready():
            return "implemented"
        return "not_integrated"

    def runtime_state(self) -> RuntimeStateLiteral:
        if self._bridge_url():
            return "configured"
        if self._local_mcp_assets_ready():
            return "ready"
        return "not_integrated"

    def status_notes(self) -> str:
        if self._local_mcp_assets_ready():
            return (
                "Official Finch MCP JSON-RPC stdio server (scripts/intelliscope_mcp_server.py), "
                "mcp_servers.json, and SKILL.md implemented and locally protocol-verified. "
                "Live Finch Desktop GUI turn requires opening Finch Desktop on a workstation."
            )
        return "Finch MCP server assets are missing from the repository."

    @staticmethod
    def get_mcp_tool_manifest() -> Dict[str, Any]:
        """Return Finch `mcpServers` JSON configuration and declared MCP tools."""
        mcp_config: Dict[str, Any] = {}
        if FINCH_MCP_CONFIG_PATH.exists():
            try:
                mcp_config = json.loads(FINCH_MCP_CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                mcp_config = {}
        return {
            "schema": "mcp-tool-manifest-descriptor",
            "host_platform": "finch-desktop",
            "mcp_server_script": str(MCP_SERVER_PATH),
            "finch_skill_path": str(FINCH_SKILL_PATH),
            "mcp_servers_config": mcp_config,
            "tools": [
                {
                    "name": "intelliscope_research",
                    "description": "Query Wikipedia, arXiv, and Crossref via Data Collector Agent",
                    "endpoint": "POST /research",
                },
                {
                    "name": "intelliscope_verify",
                    "description": "Validate structural source integrity via Research Verification Agent",
                    "endpoint": "POST /verify",
                },
                {
                    "name": "intelliscope_pipeline",
                    "description": "Execute full 4-agent verification & synthesis pipeline",
                    "endpoint": "POST /pipeline",
                },
                {
                    "name": "intelliscope_integrations_status",
                    "description": "Inspect live sponsor interoperability readiness cleanly",
                    "endpoint": "GET /integrations/status",
                },
            ],
        }

    async def check_connectivity(self) -> PlatformIntegrationInfo:
        if not self._local_mcp_assets_ready():
            self._record_probe(
                "not_integrated",
                "MCP stdio server or Finch configuration files missing.",
            )
            return self.get_status()

        del_res = await self.delegate_task(
            DelegationTaskRequest(target_platform="finch", action="verify_mcp_handshake")
        )
        if del_res.status == "completed" and del_res.output_valid:
            self._record_probe("ready", None)
        else:
            self._record_probe("failed", del_res.error)
        return self.get_status()

    async def delegate_task(
        self,
        request: DelegationTaskRequest,
        client: Optional[httpx.AsyncClient] = None,
    ) -> DelegationTaskResult:
        now_ts = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()

        if request.action == "inspect_mcp_manifest":
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="finch",
                action=request.action,
                status="completed",
                output=self.get_mcp_tool_manifest(),
                output_valid=True,
                duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                timestamp=now_ts,
            )

        if request.action in ("health_check", "verify_mcp_handshake"):
            if not self._local_mcp_assets_ready():
                return DelegationTaskResult(
                    task_id=request.task_id,
                    execution_id=request.execution_id,
                    target_platform="finch",
                    action=request.action,
                    status="not_integrated",
                    output_valid=False,
                    error="Finch MCP stdio server script or config is not present.",
                    error_code="not_integrated",
                    timestamp=now_ts,
                )

            try:
                from scripts.intelliscope_mcp_server import handle_jsonrpc_message

                init_reply = await handle_jsonrpc_message(
                    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
                )
                list_reply = await handle_jsonrpc_message(
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
                )
                tool_names = [
                    t["name"]
                    for t in ((list_reply or {}).get("result") or {}).get("tools", [])
                ]
                return DelegationTaskResult(
                    task_id=request.task_id,
                    execution_id=request.execution_id,
                    target_platform="finch",
                    action=request.action,
                    status="completed",
                    output={
                        "protocol_version": ((init_reply or {}).get("result") or {}).get("protocolVersion"),
                        "server_info": ((init_reply or {}).get("result") or {}).get("serverInfo"),
                        "tools": tool_names,
                        "mcp_config_path": str(FINCH_MCP_CONFIG_PATH),
                    },
                    output_valid=len(tool_names) >= 4,
                    duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    timestamp=now_ts,
                )
            except Exception as exc:
                return DelegationTaskResult(
                    task_id=request.task_id,
                    execution_id=request.execution_id,
                    target_platform="finch",
                    action=request.action,
                    status="failed",
                    output_valid=False,
                    duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    error=f"MCP handshake check failed: {exc}",
                    error_code="mcp_handshake_error",
                    timestamp=now_ts,
                )

        return DelegationTaskResult(
            task_id=request.task_id,
            execution_id=request.execution_id,
            target_platform="finch",
            action=request.action,
            status="rejected",
            output_valid=False,
            duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            error=(
                f"Unsupported Finch action '{request.action}'. Finch connects as a local MCP host "
                "calling scripts/intelliscope_mcp_server.py ('inspect_mcp_manifest' / 'verify_mcp_handshake')."
            ),
            error_code="unsupported_action",
            timestamp=now_ts,
        )
