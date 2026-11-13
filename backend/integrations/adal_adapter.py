"""
AdaL CLI / Agent SDK Adapter (SylphAI `adal` / `adal-sdk`).

Uses officially documented SylphAI AdaL integration methods:
1. Python SDK (`adal_agent_sdk`: `AdalAgentOptions`, `query()`) when installed
2. Non-interactive CLI (`adal -q <prompt> -o json --workspace <path>`) when installed
3. Project-scoped AdaL Skill (`.atskills/intelliscope-research/SKILL.md`)

Detects actual local availability without fabricating outputs or assuming paid
LLM accounts exist.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict, Optional

import httpx

from backend.config import settings
from backend.integrations.base import (
    PermanentDelegationError,
    SponsorAdapter,
    execute_with_timeout_and_retries,
)
from backend.integrations.models import (
    DelegationTaskRequest,
    DelegationTaskResult,
    IntegrationCategoryLiteral,
    PlatformIntegrationInfo,
    RuntimeStateLiteral,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ATSKILL_PATH = PROJECT_ROOT / ".atskills" / "intelliscope-research" / "SKILL.md"


class AdalAdapter(SponsorAdapter):
    """Modular adapter & runtime inspector for SylphAI AdaL CLI / adal-sdk."""

    platform_id = "adal"
    display_name = "AdaL Agent CLI / SDK"
    mandatory_for_track = True
    track_requirement_note = (
        "Mandatory hackathon sponsor for Research — Data & Build; supports `@skills` "
        "(`.atskills/intelliscope-research/SKILL.md`), `adal -q -o json`, and `adal-sdk`."
    )
    transport_protocol = "Local CLI (`adal -q -o json`) / adal-sdk / .atskills"
    required_env_vars = ["ADAL_ENABLED", "ADAL_CLI_PATH (or `adal` on PATH)"]
    official_docs_url = "https://github.com/SylphAI-Inc/adal-sdk"
    capabilities = [
        "atskills_project_skill",
        "cli_runtime_detection",
        "sdk_availability_probe",
        "non_interactive_json_delegation",
    ]

    def _detect_runtime(self) -> Dict[str, Any]:
        env_enabled = os.environ.get("ADAL_ENABLED")
        enabled = (
            env_enabled.strip().lower() in ("1", "true", "yes")
            if env_enabled is not None
            else bool(settings.ADAL_ENABLED)
        )
        explicit_path = (os.environ.get("ADAL_CLI_PATH") or settings.ADAL_CLI_PATH or "").strip() or None
        cli_path = explicit_path if (explicit_path and os.path.exists(explicit_path)) else shutil.which("adal")
        sdk_installed = importlib.util.find_spec("adal_agent_sdk") is not None
        skill_present = ATSKILL_PATH.exists()
        return {
            "enabled": enabled,
            "cli_path": cli_path,
            "sdk_installed": sdk_installed,
            "skill_present": skill_present,
            "available": bool(cli_path or sdk_installed),
        }

    def is_configured(self) -> bool:
        det = self._detect_runtime()
        return bool(det["enabled"] and det["available"])

    def integration_category(self) -> IntegrationCategoryLiteral:
        # Even with .atskills/ SKILL.md present, mark 'implemented' ONLY if runtime/SDK is installed & enabled;
        # otherwise 'partial' so missing CLI/SDK is reported honestly.
        if self.is_configured():
            return "implemented"
        return "partial"

    def runtime_state(self) -> RuntimeStateLiteral:
        det = self._detect_runtime()
        if not det["available"]:
            return "not_installed"
        return "configured" if det["enabled"] else "unconfigured"

    def status_notes(self) -> str:
        det = self._detect_runtime()
        skill_note = "Project `.atskills/intelliscope-research/SKILL.md` present." if det["skill_present"] else ""
        if not det["available"]:
            return (
                f"{skill_note} `adal` CLI and `adal_agent_sdk` are not installed on this host; "
                "install AdaL (`curl -fsSL https://adal.sylph.ai/install.sh | bash`) and set "
                "ADAL_ENABLED=true to run live AdaL sessions."
            ).strip()
        if not det["enabled"]:
            return f"{skill_note} AdaL runtime detected locally; set ADAL_ENABLED=true to activate delegation.".strip()
        return f"{skill_note} AdaL runtime active (`adal -q -o json` / `adal_agent_sdk`).".strip()

    async def check_connectivity(self) -> PlatformIntegrationInfo:
        det = self._detect_runtime()
        if not det["available"]:
            self._record_probe(
                "not_installed",
                "Local `adal` CLI binary and `adal_agent_sdk` package were not found.",
            )
        elif not det["enabled"]:
            self._record_probe("unconfigured", "Set ADAL_ENABLED=true to enable AdaL delegation.")
        else:
            self._record_probe("ready", None)
        return self.get_status()

    async def delegate_task(
        self,
        request: DelegationTaskRequest,
        client: Optional[httpx.AsyncClient] = None,
    ) -> DelegationTaskResult:
        det = self._detect_runtime()
        now_ts = datetime.now(timezone.utc).isoformat()

        if request.action == "health_check":
            info = await self.check_connectivity()
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="adal",
                action=request.action,
                status="completed" if self.is_configured() else "unconfigured",
                output={
                    "cli_detected": bool(det["cli_path"]),
                    "sdk_installed": det["sdk_installed"],
                    "skill_present": det["skill_present"],
                    "enabled": det["enabled"],
                },
                output_valid=self.is_configured(),
                error=info.last_check_error,
                error_code=None if self.is_configured() else info.runtime_state,
                timestamp=now_ts,
            )

        if request.action not in ("cli_prompt", "sdk_query"):
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="adal",
                action=request.action,
                status="rejected",
                output_valid=False,
                error=f"Unsupported AdaL action '{request.action}'.",
                error_code="unsupported_action",
                timestamp=now_ts,
            )

        if not det["available"] or not det["enabled"]:
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="adal",
                action=request.action,
                status="unconfigured",
                output_valid=False,
                error="AdaL CLI / adal_agent_sdk is not installed or ADAL_ENABLED is false.",
                error_code="not_installed" if not det["available"] else "not_configured",
                timestamp=now_ts,
            )

        prompt = str((request.payload or {}).get("prompt") or "").strip()
        if not prompt:
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="adal",
                action=request.action,
                status="rejected",
                output_valid=False,
                error="AdaL delegation requires non-empty payload 'prompt'.",
                error_code="validation_error",
                timestamp=now_ts,
            )

        # Prefer official adal_agent_sdk when installed
        if det["sdk_installed"] and (request.action == "sdk_query" or not det["cli_path"]):
            async def _run_sdk() -> Dict[str, Any]:
                sdk_mod = importlib.import_module("adal_agent_sdk")
                options = sdk_mod.AdalAgentOptions(
                    workspace=str(PROJECT_ROOT),
                    permission_mode="default",
                    enabled_default_tools=["Read", "Search"],
                )
                collected_parts = []
                async for event in sdk_mod.query(prompt=prompt, options=options):
                    if isinstance(event, dict) and event.get("type") == "assistant.message.completed":
                        content = (event.get("message") or {}).get("content")
                        if content:
                            collected_parts.append(str(content))
                final_text = "\n".join(collected_parts).strip()
                if not final_text:
                    raise PermanentDelegationError(
                        "AdaL SDK returned empty completion output.",
                        error_code="empty_sdk_output",
                    )
                return {"response": final_text, "mode": "adal_agent_sdk"}

            output, retries, dur, err, code, outcome = await execute_with_timeout_and_retries(
                _run_sdk,
                timeout_seconds=request.timeout_seconds,
                max_retries=request.max_retries,
            )
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="adal",
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

        cli_bin = det["cli_path"]
        if not cli_bin:
            return DelegationTaskResult(
                task_id=request.task_id,
                execution_id=request.execution_id,
                target_platform="adal",
                action=request.action,
                status="unconfigured",
                output_valid=False,
                error="`adal` CLI executable path unavailable.",
                error_code="not_installed",
                timestamp=now_ts,
            )

        # Official documented non-interactive AdaL CLI syntax:
        # `adal -q <prompt> -o json --workspace <path> --enabled-default-tools Read,Search`
        async def _run_cli() -> Dict[str, Any]:
            proc = await asyncio.create_subprocess_exec(
                cli_bin,
                "-q",
                prompt,
                "-o",
                "json",
                "--workspace",
                str(PROJECT_ROOT),
                "--enabled-default-tools",
                "Read,Search",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await proc.communicate()
            stdout_txt = (stdout_b or b"").decode("utf-8", errors="replace").strip()
            stderr_txt = (stderr_b or b"").decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                raise PermanentDelegationError(
                    f"AdaL CLI exited with status {proc.returncode}: {stderr_txt or stdout_txt}",
                    error_code="cli_nonzero_exit",
                )
            parsed_json: Optional[Any] = None
            try:
                parsed_json = json.loads(stdout_txt) if stdout_txt else None
            except json.JSONDecodeError:
                parsed_json = None
            return {
                "stdout": stdout_txt,
                "json_output": parsed_json,
                "exit_code": proc.returncode,
                "mode": "adal_cli",
            }

        output, retries, dur, err, code, outcome = await execute_with_timeout_and_retries(
            _run_cli,
            timeout_seconds=request.timeout_seconds,
            max_retries=request.max_retries,
        )
        return DelegationTaskResult(
            task_id=request.task_id,
            execution_id=request.execution_id,
            target_platform="adal",
            action=request.action,
            status=outcome,  # type: ignore[arg-type]
            output=output,
            output_valid=outcome == "completed" and bool(output and output.get("stdout")),
            duration_ms=dur,
            retries_used=retries,
            error=err,
            error_code=code,
            timestamp=now_ts,
        )
