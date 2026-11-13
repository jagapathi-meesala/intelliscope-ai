"""
BAND Platform Sponsor Adapter (band.ai / band-sdk 6.0.1).

Audits and exposes BAND SDK connectivity, credential presence (without secret
exposure), structured peer-to-peer delegation formatting/validation, and live
REST health checks using AsyncRestClient.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from band.client.rest import AsyncRestClient
from band.config import load_agent_config
from band.config.settings import DEFAULT_REST_URL, DEFAULT_WS_URL

from backend.config import settings
from backend.integrations.base import (
    PermanentDelegationError,
    SponsorAdapter,
    TransientDelegationError,
    execute_with_timeout_and_retries,
    sanitize_error_message,
)
from backend.integrations.models import (
    DelegationTaskRequest,
    DelegationTaskResult,
    IntegrationCategoryLiteral,
    PlatformIntegrationInfo,
    RuntimeStateLiteral,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9_.\-/]{2,64}$")
LIVE_BAND_VERIFICATION_FILE = PROJECT_ROOT / "test-results" / "live-band" / "latest_status.json"


def resolve_band_credentials(
    agent_key: str = "data_collector",
    config_path: Optional[Path | str] = None,
) -> Tuple[Optional[str], Optional[str], str]:
    """
    Resolve BAND credentials from environment variables or local YAML config
    without throwing when absent.

    Returns:
        (agent_id, api_key, source_label)
    """
    env_id = (os.environ.get("BAND_AGENT_ID") or settings.BAND_AGENT_ID or "").strip()
    env_key = (os.environ.get("BAND_API_KEY") or settings.BAND_API_KEY or "").strip()
    if env_id and env_key:
        return env_id, env_key, "environment"

    resolved_path = Path(config_path) if config_path else Path(settings.BAND_CONFIG_PATH)
    if not resolved_path.is_absolute():
        resolved_path = PROJECT_ROOT / resolved_path

    if resolved_path.exists():
        try:
            cfg_id, cfg_key = load_agent_config(agent_key, config_path=resolved_path)
            if cfg_id and cfg_key:
                return cfg_id.strip(), cfg_key.strip(), resolved_path.name
        except Exception:
            return None, None, f"{resolved_path.name} (unreadable)"

    return None, None, "none"


def _is_valid_https_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme == "https" and bool(parsed.netloc)
    except Exception:
        return False


class BandSponsorAdapter(SponsorAdapter):
    """Modular adapter for BAND Agentic Mesh (band-sdk 6.0.1)."""

    platform_id = "band"
    display_name = "BAND (Agentic Mesh)"
    mandatory_for_track = True
    track_requirement_note = (
        "Mandatory hackathon sponsor for Research — Data & Build; coordinates live room "
        "interactions, WS streaming, structured events, and @peer handoffs."
    )
    transport_protocol = "band-sdk 6.0.1 (REST + Phoenix WebSocket)"
    required_env_vars = ["BAND_AGENT_ID", "BAND_API_KEY"]
    official_docs_url = "https://docs.band.ai/quickstart"
    capabilities = [
        "room_mention_listener",
        "rest_identity_verification",
        "websocket_auto_reconnect_supersede",
        "structured_room_events",
        "peer_handoff_formatting",
        "task_board_hooks",
    ]

    def __init__(self, config_path: Optional[Path | str] = None) -> None:
        super().__init__()
        self._config_path = config_path

    def _credentials(self) -> Tuple[Optional[str], Optional[str], str]:
        return resolve_band_credentials(config_path=self._config_path)

    def _has_verified_live_room_e2e(self) -> Optional[Dict[str, Any]]:
        """Check genuine recorded live room verification artifact if present on disk."""
        if not self.is_configured() or not LIVE_BAND_VERIFICATION_FILE.exists():
            return None
        try:
            data = json.loads(LIVE_BAND_VERIFICATION_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("e2e_room_roundtrip_passed") is True:
                return data
        except Exception:
            return None
        return None

    def is_configured(self) -> bool:
        agent_id, api_key, _ = self._credentials()
        return bool(agent_id and api_key)

    def integration_category(self) -> IntegrationCategoryLiteral:
        if self._has_verified_live_room_e2e():
            return "live_tested"
        return "implemented"

    def runtime_state(self) -> RuntimeStateLiteral:
        if self.is_configured():
            return "ready"
        return "unconfigured"

    def status_notes(self) -> str:
        _, _, source = self._credentials()
        live_e2e = self._has_verified_live_room_e2e()
        if self.is_configured():
            if live_e2e:
                return (
                    f"Live-verified BAND SimpleAdapter runtime ({source}); real room message & agent "
                    f"response tested at {live_e2e.get('verified_at')}."
                )
            return (
                f"Active SimpleAdapter runtime (credentials loaded from {source}; never exposed). "
                "Supports REST auth pre-flight, Phoenix WS SUPERSEDE reconnect, structured task/result events, "
                "and @peer delegation formatting via scripts/band_collector_agent.py."
            )
        return (
            "BAND SDK adapter implemented; configure BAND_AGENT_ID & BAND_API_KEY env vars "
            "or agent_config.yaml to enable live BAND room connectivity."
        )

    async def check_connectivity(self, timeout_seconds: float = 10.0) -> PlatformIntegrationInfo:
        """
        Verify BAND REST API authentication (`GET /api/v1/agent/me`) safely
        without leaking credentials or mutating platform state.
        """
        agent_id, api_key, _ = self._credentials()
        if not agent_id or not api_key:
            self._record_probe(
                "unconfigured",
                "Missing BAND credentials (set BAND_AGENT_ID/BAND_API_KEY or agent_config.yaml).",
            )
            return self.get_status()

        rest_url = os.environ.get("BAND_REST_URL") or settings.BAND_REST_URL or DEFAULT_REST_URL
        try:
            rest = AsyncRestClient(api_key=api_key, base_url=rest_url)
            resp = await asyncio.wait_for(
                rest.agent_api_identity.get_agent_me(),
                timeout=timeout_seconds,
            )
            me = getattr(resp, "data", None)
            if not me:
                self._record_probe("failed", "BAND REST response contained empty agent profile.")
                return self.get_status()

            id_matched = getattr(me, "id", None) == agent_id
            handle = getattr(me, "handle", None) or "unknown"
            note = f"REST 200 OK (@{handle}, id_match={id_matched})"
            self._record_probe("connected", None if id_matched else f"ID mismatch detected ({note})")
        except asyncio.TimeoutError:
            self._record_probe("timed_out", f"BAND REST check timed out after {timeout_seconds:.1f}s")
        except Exception as exc:
            err = sanitize_error_message(f"{type(exc).__name__}: {exc}", [api_key, agent_id])
            self._record_probe("failed", err)

        return self.get_status()

    @staticmethod
    def build_delegation_message(
        *,
        peer_handle: str,
        execution_id: str,
        task_id: str,
        query: str,
        summary: str = "",
        source_urls: Optional[List[str]] = None,
        action: str = "follow_up_analysis",
    ) -> str:
        """
        Format a deterministic, parseable @peer delegation message for BAND rooms
        carrying structured execution context and validated HTTPS provenance URLs.
        """
        clean_handle = peer_handle.strip().lstrip("@")
        if not clean_handle or not HANDLE_PATTERN.match(clean_handle):
            raise ValueError(f"Invalid BAND peer handle '{peer_handle}'.")

        safe_urls = [u for u in (source_urls or []) if isinstance(u, str) and _is_valid_https_url(u)]
        envelope = {
            "schema": "intelliscope.a2a.v1",
            "execution_id": execution_id,
            "task_id": task_id,
            "action": action,
            "query": query,
            "summary": summary[:400],
            "source_urls": safe_urls[:10],
        }
        return (
            f"@{clean_handle} [IntelliScope Delegation | exec={execution_id[:8]} | task={task_id}]\n"
            f"Topic: {query}\n"
            f"```json\n{json.dumps(envelope, indent=2)}\n```"
        )

    @staticmethod
    def parse_delegation_envelope(content: str) -> Optional[Dict[str, Any]]:
        """Extract and validate an intelliscope.a2a.v1 JSON delegation envelope if present."""
        if not content or not isinstance(content, str):
            return None
        match = re.search(r"```json\s*(\{.*?\})\s*```", content, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict) or data.get("schema") != "intelliscope.a2a.v1":
            return None
        for url in data.get("source_urls") or []:
            if not isinstance(url, str) or not _is_valid_https_url(url):
                return None
        return data

    async def delegate_task(
        self,
        request: DelegationTaskRequest,
        client: Optional[httpx.AsyncClient] = None,
    ) -> DelegationTaskResult:
        """
        Execute structured BAND adapter actions:
        - 'health_check': verifies live BAND REST identity
        - 'prepare_peer_handoff': validates peer_handle, query, and HTTPS provenance
          to emit a structured BAND @mention handoff envelope
        """
        agent_id, api_key, _ = self._credentials()
        now_ts = datetime.now(timezone.utc).isoformat()

        if request.action == "prepare_peer_handoff":
            t0 = time.perf_counter()
            payload = request.payload or {}
            peer_handle = str(payload.get("peer_handle") or "").strip()
            query = str(payload.get("query") or (request.shared_context or {}).get("query") or "").strip()
            raw_urls = payload.get("source_urls") or []
            if not peer_handle or not query:
                return DelegationTaskResult(
                    task_id=request.task_id,
                    execution_id=request.execution_id,
                    target_platform="band",
                    action=request.action,
                    status="rejected",
                    output_valid=False,
                    duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    error="Payload requires non-empty 'peer_handle' and 'query'.",
                    error_code="validation_error",
                    timestamp=now_ts,
                )

            invalid_urls = [u for u in raw_urls if not isinstance(u, str) or not _is_valid_https_url(u)]
            if invalid_urls:
                return DelegationTaskResult(
                    task_id=request.task_id,
                    execution_id=request.execution_id,
                    target_platform="band",
                    action=request.action,
                    status="rejected",
                    output_valid=False,
                    duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    error="All delegated source_urls must use valid https:// URLs.",
                    error_code="unsafe_url_rejected",
                    timestamp=now_ts,
                )

            try:
                formatted_msg = self.build_delegation_message(
                    peer_handle=peer_handle,
                    execution_id=request.execution_id,
                    task_id=request.task_id,
                    query=query,
                    summary=str(payload.get("summary") or ""),
                    source_urls=raw_urls,
                    action=str(payload.get("delegated_action") or "follow_up_analysis"),
                )
            except ValueError as exc:
                return DelegationTaskResult(
                    task_id=request.task_id,
                    execution_id=request.execution_id,
                    target_platform="band",
                    action=request.action,
                    status="rejected",
                    output_valid=False,
                    duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    error=str(exc),
                    error_code="validation_error",
                    timestamp=now_ts,
                )

            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="band",
                action=request.action,
                status="completed",
                output={
                    "peer_handle": peer_handle.lstrip("@"),
                    "message": formatted_msg,
                    "mention_target": peer_handle.lstrip("@"),
                    "ws_url": os.environ.get("BAND_WS_URL") or settings.BAND_WS_URL or DEFAULT_WS_URL,
                },
                output_valid=True,
                duration_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                retries_used=0,
                timestamp=now_ts,
            )

        if request.action == "health_check":
            if not agent_id or not api_key:
                return DelegationTaskResult(
                    task_id=request.task_id,
                    execution_id=request.execution_id,
                    target_platform="band",
                    action=request.action,
                    status="unconfigured",
                    output_valid=False,
                    error="BAND credentials not configured in environment or agent_config.yaml.",
                    error_code="not_configured",
                    timestamp=now_ts,
                )

            rest_url = os.environ.get("BAND_REST_URL") or settings.BAND_REST_URL or DEFAULT_REST_URL

            async def _op() -> Dict[str, Any]:
                rest = AsyncRestClient(api_key=api_key, base_url=rest_url)
                resp = await rest.agent_api_identity.get_agent_me()
                me = getattr(resp, "data", None)
                if not me:
                    raise TransientDelegationError("Empty BAND profile payload", error_code="empty_response")
                return {
                    "authenticated": True,
                    "agent_handle": getattr(me, "handle", None),
                    "agent_name": getattr(me, "name", None),
                    "id_matched": getattr(me, "id", None) == agent_id,
                }

            output, retries, dur, err, code, outcome = await execute_with_timeout_and_retries(
                _op,
                timeout_seconds=request.timeout_seconds,
                max_retries=request.max_retries,
                secrets_to_redact=[api_key, agent_id],
            )
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="band",
                action=request.action,
                status=outcome,  # type: ignore[arg-type]
                output=output,
                output_valid=outcome == "completed" and bool(output and output.get("authenticated")),
                duration_ms=dur,
                retries_used=retries,
                error=err,
                error_code=code,
                timestamp=now_ts,
            )

        return DelegationTaskResult(
            task_id=request.task_id,
            execution_id=request.execution_id,
            target_platform="band",
            action=request.action,
            status="rejected",
            output_valid=False,
            error=f"Unsupported BAND delegation action '{request.action}'.",
            error_code="unsupported_action",
            timestamp=now_ts,
        )

