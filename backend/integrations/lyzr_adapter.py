"""
Lyzr Agent Studio REST v3 Adapter (`https://agent-prod.studio.lyzr.ai/v3`).

Environment-configured modular HTTP adapter implementing documented Lyzr v3 APIs:
1. Agent Chat Inference: `POST /v3/inference/chat/`
2. SuperFlow / Workflow Execution: `POST /v3/workflows/{flow_id}/execute`

Authenticates via `x-api-key`, propagates `session_id=execution_id`, enforces
timeouts, retries transient 429/5xx failures, redacts credentials, and rejects
invalid schemas. Never runs paid inference unless credentials are supplied.
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
)
from backend.integrations.models import (
    DelegationTaskRequest,
    DelegationTaskResult,
    IntegrationCategoryLiteral,
    RuntimeStateLiteral,
)


class LyzrAdapter(SponsorAdapter):
    """Modular adapter for Lyzr Agent Studio REST v3 API."""

    platform_id = "lyzr"
    display_name = "Lyzr Agent Studio"
    mandatory_for_track = True
    track_requirement_note = (
        "Mandatory hackathon sponsor for Research — Data & Build; supports REST v3 "
        "chat inference (`/inference/chat/`) and workflows (`/workflows/{id}/execute`)."
    )
    transport_protocol = "REST HTTPS (v3/inference/chat & workflows)"
    required_env_vars = ["LYZR_API_KEY", "LYZR_AGENT_ID"]
    official_docs_url = "https://studio.lyzr.ai"
    capabilities = [
        "chat_inference_v3",
        "workflow_execute_v3",
        "opt_in_pipeline_handoff",
        "session_context_propagation",
        "timeout_and_retry_guard",
        "output_schema_validation",
    ]

    def _resolve_config(self) -> Dict[str, Optional[str]]:
        return {
            "api_key": (os.environ.get("LYZR_API_KEY") or settings.LYZR_API_KEY or "").strip() or None,
            "agent_id": (os.environ.get("LYZR_AGENT_ID") or settings.LYZR_AGENT_ID or "").strip() or None,
            "workflow_id": (os.environ.get("LYZR_WORKFLOW_ID") or settings.LYZR_WORKFLOW_ID or "").strip() or None,
            "base_url": (os.environ.get("LYZR_BASE_URL") or settings.LYZR_BASE_URL).strip().rstrip("/"),
            "user_id": (os.environ.get("LYZR_USER_ID") or settings.LYZR_USER_ID).strip(),
        }

    def is_configured(self) -> bool:
        cfg = self._resolve_config()
        return bool(cfg["api_key"] and (cfg["agent_id"] or cfg["workflow_id"]) and cfg["base_url"])

    def integration_category(self) -> IntegrationCategoryLiteral:
        # Honest: without env credentials, live calls have not run -> 'partial'
        if self.is_configured():
            return "implemented"
        return "partial"

    def runtime_state(self) -> RuntimeStateLiteral:
        return "configured" if self.is_configured() else "unconfigured"

    def status_notes(self) -> str:
        if self.is_configured():
            return (
                "Lyzr v3 REST adapter configured (credentials present in env). "
                "Supports chat inference, workflow execution, and opt-in pipeline delegation."
            )
        return (
            "Lyzr v3 HTTP adapter implemented and mocked-tested (`/inference/chat/` & `/workflows/{id}/execute`); "
            "awaiting LYZR_API_KEY and LYZR_AGENT_ID environment variables for live execution."
        )

    async def delegate_task(
        self,
        request: DelegationTaskRequest,
        client: Optional[httpx.AsyncClient] = None,
    ) -> DelegationTaskResult:
        cfg = self._resolve_config()
        api_key = cfg["api_key"]
        agent_id = cfg["agent_id"]
        workflow_id = cfg["workflow_id"]
        base_url = cfg["base_url"] or "https://agent-prod.studio.lyzr.ai/v3"
        user_id = cfg["user_id"] or "intelliscope-orchestrator"
        now_ts = datetime.now(timezone.utc).isoformat()

        if request.action == "health_check":
            if not api_key or not (agent_id or workflow_id):
                return DelegationTaskResult(
                    task_id=request.task_id,
                    execution_id=request.execution_id,
                    target_platform="lyzr",
                    action=request.action,
                    status="unconfigured",
                    output_valid=False,
                    error="LYZR_API_KEY and LYZR_AGENT_ID are not set.",
                    error_code="not_configured",
                    timestamp=now_ts,
                )
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="lyzr",
                action=request.action,
                status="completed",
                output={
                    "configured": True,
                    "base_url": base_url,
                    "has_workflow_id": bool(workflow_id),
                    "note": "Configuration verified without triggering paid LLM token inference.",
                },
                output_valid=True,
                timestamp=now_ts,
            )

        if request.action not in ("chat_inference", "delegate_analysis", "workflow_execute"):
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="lyzr",
                action=request.action,
                status="rejected",
                output_valid=False,
                error=f"Unsupported Lyzr action '{request.action}'.",
                error_code="unsupported_action",
                timestamp=now_ts,
            )

        payload = request.payload or {}
        headers = {
            "x-api-key": api_key or "",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if request.action == "workflow_execute":
            target_flow_id = str(payload.get("flow_id") or workflow_id or "").strip()
            if not api_key or not target_flow_id:
                return DelegationTaskResult(
                    task_id=request.task_id,
                    execution_id=request.execution_id,
                    target_platform="lyzr",
                    action=request.action,
                    status="unconfigured",
                    output_valid=False,
                    error="LYZR_API_KEY and LYZR_WORKFLOW_ID (or payload.flow_id) are required.",
                    error_code="not_configured",
                    timestamp=now_ts,
                )
            flow_input = str(payload.get("input") or payload.get("message") or "").strip()
            if not flow_input:
                return DelegationTaskResult(
                    task_id=request.task_id,
                    execution_id=request.execution_id,
                    target_platform="lyzr",
                    action=request.action,
                    status="rejected",
                    output_valid=False,
                    error="workflow_execute requires non-empty payload 'input'.",
                    error_code="validation_error",
                    timestamp=now_ts,
                )

            endpoint = f"{base_url}/workflows/{target_flow_id}/execute"
            body = {"input": flow_input, "user_id": str(payload.get("user_id") or user_id)}

            async def _post_flow(active_client: httpx.AsyncClient) -> Dict[str, Any]:
                resp = await active_client.post(endpoint, json=body, headers=headers)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise TransientDelegationError(
                        f"Lyzr workflow transient HTTP {resp.status_code}",
                        error_code=f"http_{resp.status_code}",
                    )
                if resp.status_code in (400, 401, 403, 404, 422):
                    raise PermanentDelegationError(
                        f"Lyzr workflow rejected request (HTTP {resp.status_code})",
                        error_code=f"http_{resp.status_code}",
                    )
                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception as exc:
                    raise PermanentDelegationError(
                        f"Lyzr workflow returned malformed JSON: {exc}",
                        error_code="invalid_json",
                    ) from exc
                if not isinstance(data, dict) or not data:
                    raise PermanentDelegationError(
                        "Lyzr workflow returned empty or non-object payload.",
                        error_code="invalid_output_schema",
                    )
                return {"workflow_id": target_flow_id, "result": data}

            async def _op_flow() -> Dict[str, Any]:
                if client is not None:
                    return await _post_flow(client)
                async with httpx.AsyncClient(timeout=request.timeout_seconds) as local_client:
                    return await _post_flow(local_client)

            output, retries, dur, err, code, outcome = await execute_with_timeout_and_retries(
                _op_flow,
                timeout_seconds=request.timeout_seconds,
                max_retries=request.max_retries,
                secrets_to_redact=[api_key, target_flow_id],
            )
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="lyzr",
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

        # chat_inference / delegate_analysis
        if not api_key or not agent_id:
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="lyzr",
                action=request.action,
                status="unconfigured",
                output_valid=False,
                error="LYZR_API_KEY and LYZR_AGENT_ID must be configured to invoke Lyzr Studio.",
                error_code="not_configured",
                timestamp=now_ts,
            )

        message = str(payload.get("message") or "").strip()
        if not message and request.shared_context:
            q = request.shared_context.get("query") or ""
            artifacts = request.shared_context.get("shared_artifacts") or {}
            if q:
                message = (
                    f"[IntelliScope execution_id={request.execution_id}] "
                    f"Review grounded findings for '{q}': {artifacts}"
                )
        if not message:
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="lyzr",
                action=request.action,
                status="rejected",
                output_valid=False,
                error="Lyzr delegation requires non-empty 'message' or shared_context.query.",
                error_code="validation_error",
                timestamp=now_ts,
            )

        endpoint = f"{base_url}/inference/chat/"
        body = {
            "agent_id": agent_id,
            "user_id": str(payload.get("user_id") or user_id),
            "session_id": str(payload.get("session_id") or request.execution_id),
            "message": message,
        }

        async def _post(active_client: httpx.AsyncClient) -> Dict[str, Any]:
            resp = await active_client.post(endpoint, json=body, headers=headers)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise TransientDelegationError(
                    f"Lyzr API transient status HTTP {resp.status_code}",
                    error_code=f"http_{resp.status_code}",
                )
            if resp.status_code in (400, 401, 403, 404, 422):
                raise PermanentDelegationError(
                    f"Lyzr API rejected request (HTTP {resp.status_code})",
                    error_code=f"http_{resp.status_code}",
                )
            resp.raise_for_status()
            try:
                data = resp.json()
            except Exception as exc:
                raise PermanentDelegationError(
                    f"Lyzr returned malformed JSON: {exc}",
                    error_code="invalid_json",
                ) from exc

            if not isinstance(data, dict) or not str(data.get("response") or "").strip():
                raise PermanentDelegationError(
                    "Lyzr response missing required non-empty 'response' field.",
                    error_code="invalid_output_schema",
                )

            return {
                "response": str(data["response"]),
                "session_id": body["session_id"],
                "module_outputs": data.get("module_outputs"),
            }

        async def _op() -> Dict[str, Any]:
            if client is not None:
                return await _post(client)
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as local_client:
                return await _post(local_client)

        output, retries, dur, err, code, outcome = await execute_with_timeout_and_retries(
            _op,
            timeout_seconds=request.timeout_seconds,
            max_retries=request.max_retries,
            secrets_to_redact=[api_key, agent_id],
        )
        return DelegationTaskResult(
            task_id=request.task_id,
            execution_id=request.execution_id,
            target_platform="lyzr",
            action=request.action,
            status=outcome,  # type: ignore[arg-type]
            output=output,
            output_valid=outcome == "completed" and bool(output and output.get("response")),
            duration_ms=dur,
            retries_used=retries,
            error=err,
            error_code=code,
            timestamp=now_ts,
        )
