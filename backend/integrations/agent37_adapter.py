"""
Agent37 Cloud Sandbox Adapter (`https://sandbox.agent37.app` & `https://api.agent37.com`).

Uses documented `X-Agent37-Key` header authentication, instance health probing
(`/v1/health`), and bounded command execution (`/v1/instances/{id}/exec`) with
timeouts, retries, input validation, and secret redaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Dict, Optional

import httpx

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


class Agent37Adapter(SponsorAdapter):
    """Modular HTTP adapter for Agent37 Cloud Sandbox instances."""

    platform_id = "agent37"
    display_name = "Agent37 Cloud Sandbox"
    mandatory_for_track = False
    track_requirement_note = (
        "Optional hackathon sandbox/hosting sponsor (credits & prize track; not mandatory for local Research — Data & Build)."
    )
    transport_protocol = "REST HTTPS (X-Agent37-Key /v1)"
    required_env_vars = ["AGENT37_API_KEY", "AGENT37_INSTANCE_ID"]
    official_docs_url = "https://www.agent37.com/docs"
    capabilities = [
        "sandbox_health_check",
        "instance_command_exec",
        "timeout_and_retry_guard",
        "output_schema_validation",
    ]

    def _resolve_config(self) -> Dict[str, Optional[str]]:
        return {
            "api_key": (os.environ.get("AGENT37_API_KEY") or settings.AGENT37_API_KEY or "").strip() or None,
            "instance_id": (os.environ.get("AGENT37_INSTANCE_ID") or settings.AGENT37_INSTANCE_ID or "").strip() or None,
            "sandbox_url": (os.environ.get("AGENT37_SANDBOX_URL") or settings.AGENT37_SANDBOX_URL).strip().rstrip("/"),
            "api_url": (os.environ.get("AGENT37_API_URL") or settings.AGENT37_API_URL).strip().rstrip("/"),
        }

    def is_configured(self) -> bool:
        cfg = self._resolve_config()
        return bool(cfg["api_key"] and cfg["instance_id"])

    def integration_category(self) -> IntegrationCategoryLiteral:
        return "partial"

    def runtime_state(self) -> RuntimeStateLiteral:
        return "configured" if self.is_configured() else "unconfigured"

    def status_notes(self) -> str:
        if self.is_configured():
            return (
                "Optional Agent37 sandbox credentials detected in environment. "
                "Supports health checks and bounded instance exec calls."
            )
        return (
            "Optional sponsor adapter implemented and mocked-tested; not active because "
            "AGENT37_API_KEY and AGENT37_INSTANCE_ID are not set (deployment deferred)."
        )

    async def check_connectivity(self, timeout_seconds: float = 10.0) -> PlatformIntegrationInfo:
        cfg = self._resolve_config()
        api_key = cfg["api_key"]
        instance_id = cfg["instance_id"]
        if not api_key or not instance_id:
            self._record_probe(
                "unconfigured",
                "Missing AGENT37_API_KEY or AGENT37_INSTANCE_ID environment variables.",
            )
            return self.get_status()

        result = await self.delegate_task(
            DelegationTaskRequest(
                target_platform="agent37",
                action="health_check",
                timeout_seconds=timeout_seconds,
                max_retries=0,
            )
        )
        self._record_probe(result.status, result.error)
        return self.get_status()

    async def delegate_task(
        self,
        request: DelegationTaskRequest,
        client: Optional[httpx.AsyncClient] = None,
    ) -> DelegationTaskResult:
        cfg = self._resolve_config()
        api_key = cfg["api_key"]
        instance_id = cfg["instance_id"]
        sandbox_url = cfg["sandbox_url"] or "https://sandbox.agent37.app"
        now_ts = datetime.now(timezone.utc).isoformat()

        if request.action not in ("health_check", "sandbox_exec"):
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="agent37",
                action=request.action,
                status="rejected",
                output_valid=False,
                error=f"Unsupported Agent37 action '{request.action}'.",
                error_code="unsupported_action",
                timestamp=now_ts,
            )

        if not api_key or not instance_id:
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="agent37",
                action=request.action,
                status="unconfigured",
                output_valid=False,
                error="AGENT37_API_KEY and AGENT37_INSTANCE_ID must be configured.",
                error_code="not_configured",
                timestamp=now_ts,
            )

        headers = {
            "X-Agent37-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if request.action == "health_check":
            endpoint = f"{sandbox_url}/v1/health"

            async def _get_health(active_client: httpx.AsyncClient) -> Dict[str, Any]:
                resp = await active_client.get(endpoint, headers=headers)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise TransientDelegationError(
                        f"Agent37 health returned HTTP {resp.status_code}",
                        error_code=f"http_{resp.status_code}",
                    )
                if resp.status_code in (401, 403, 404):
                    raise PermanentDelegationError(
                        f"Agent37 health rejected HTTP {resp.status_code}",
                        error_code=f"http_{resp.status_code}",
                    )
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    raise PermanentDelegationError("Agent37 health returned non-object JSON", error_code="invalid_output_schema")
                return data

            async def _op_health() -> Dict[str, Any]:
                if client is not None:
                    return await _get_health(client)
                async with httpx.AsyncClient(timeout=request.timeout_seconds) as local_client:
                    return await _get_health(local_client)

            output, retries, dur, err, code, outcome = await execute_with_timeout_and_retries(
                _op_health,
                timeout_seconds=request.timeout_seconds,
                max_retries=request.max_retries,
                secrets_to_redact=[api_key],
            )
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="agent37",
                action=request.action,
                status=outcome,  # type: ignore[arg-type]
                output=output,
                output_valid=outcome == "completed" and isinstance(output, dict),
                duration_ms=dur,
                retries_used=retries,
                error=sanitize_error_message(err or "", [api_key]) if err else None,
                error_code=code,
                timestamp=now_ts,
            )

        # sandbox_exec
        command = str((request.payload or {}).get("command") or "").strip()
        if not command or len(command) > 1000:
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="agent37",
                action=request.action,
                status="rejected",
                output_valid=False,
                error="sandbox_exec requires non-empty payload 'command' (<= 1000 chars).",
                error_code="validation_error",
                timestamp=now_ts,
            )

        endpoint = f"{sandbox_url}/v1/instances/{instance_id}/exec"

        async def _post_exec(active_client: httpx.AsyncClient) -> Dict[str, Any]:
            resp = await active_client.post(
                endpoint,
                json={"command": command},
                headers=headers,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise TransientDelegationError(
                    f"Agent37 exec transient HTTP {resp.status_code}",
                    error_code=f"http_{resp.status_code}",
                )
            if resp.status_code in (400, 401, 403, 404, 422):
                raise PermanentDelegationError(
                    f"Agent37 exec rejected request (HTTP {resp.status_code})",
                    error_code=f"http_{resp.status_code}",
                )
            resp.raise_for_status()
            try:
                data = resp.json()
            except Exception as exc:
                raise PermanentDelegationError(
                    f"Agent37 returned malformed JSON: {exc}",
                    error_code="invalid_json",
                ) from exc
            if not isinstance(data, dict):
                raise PermanentDelegationError("Agent37 exec returned non-object response", error_code="invalid_output_schema")
            return data

        async def _op_exec() -> Dict[str, Any]:
            if client is not None:
                return await _post_exec(client)
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as local_client:
                return await _post_exec(local_client)

        output, retries, dur, err, code, outcome = await execute_with_timeout_and_retries(
            _op_exec,
            timeout_seconds=request.timeout_seconds,
            max_retries=request.max_retries,
            secrets_to_redact=[api_key],
        )
        return DelegationTaskResult(
            task_id=request.task_id,
            execution_id=request.execution_id,
            target_platform="agent37",
            action=request.action,
            status=outcome,  # type: ignore[arg-type]
            output=output,
            output_valid=outcome == "completed" and isinstance(output, dict),
            duration_ms=dur,
            retries_used=retries,
            error=err,
            error_code=code,
            timestamp=now_ts,
        )

