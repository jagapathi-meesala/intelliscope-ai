"""
Base SponsorAdapter interface and shared async timeout, retry, credential
redaction, and output-validation primitives.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import httpx

from backend.integrations.models import (
    DelegationTaskRequest,
    DelegationTaskResult,
    IntegrationCategoryLiteral,
    PlatformIdLiteral,
    PlatformIntegrationInfo,
    RuntimeStateLiteral,
)


class TransientDelegationError(Exception):
    """Raised when a remote sponsor call fails transiently (429, 5xx, network)."""

    def __init__(self, message: str, error_code: str = "transient_upstream_error") -> None:
        super().__init__(message)
        self.error_code = error_code


class PermanentDelegationError(Exception):
    """Raised when a remote sponsor call fails permanently (4xx auth/validation)."""

    def __init__(self, message: str, error_code: str = "permanent_error") -> None:
        super().__init__(message)
        self.error_code = error_code


def sanitize_error_message(raw_message: str, secrets: Optional[List[Optional[str]]] = None) -> str:
    """
    Remove potential API keys, bearer tokens, or credential substrings before
    logging or returning diagnostic messages to callers/UI.
    """
    msg = str(raw_message or "").strip()
    if not msg:
        return "Unknown error"

    for secret in secrets or []:
        if secret and isinstance(secret, str) and len(secret.strip()) >= 4:
            msg = msg.replace(secret.strip(), "[REDACTED]")

    msg = re.sub(r"(Bearer\s+)[A-Za-z0-9._\-+/=]+", r"\1[REDACTED]", msg, flags=re.IGNORECASE)
    msg = re.sub(
        r"(x-api-key|x-agent37-key|api_key|apikey|authorization)([:=]\s*)([^\s,;'\"]+)",
        r"\1\2[REDACTED]",
        msg,
        flags=re.IGNORECASE,
    )
    msg = re.sub(r"\bsk_(?:live|test)_[A-Za-z0-9_\-]+", "[REDACTED]", msg)
    return msg


async def execute_with_timeout_and_retries(
    operation: Callable[[], Awaitable[Dict[str, Any]]],
    *,
    timeout_seconds: float,
    max_retries: int,
    backoff_base_seconds: float = 0.25,
    secrets_to_redact: Optional[List[Optional[str]]] = None,
) -> Tuple[Optional[Dict[str, Any]], int, float, Optional[str], Optional[str], str]:
    """
    Execute an async operation with per-attempt asyncio.wait_for timeout,
    bounded exponential backoff retries on transient failures/timeouts,
    and strict error classification.

    Returns:
        (output_dict, retries_used, total_duration_ms, error_msg, error_code, outcome_status)
        where outcome_status is one of: 'completed', 'timed_out', 'failed'.
    """
    start_time = time.perf_counter()
    retries_used = 0
    last_error = "Execution failed"
    last_code = "unknown_error"
    last_status = "failed"

    attempts = max(1, max_retries + 1)
    for attempt in range(attempts):
        if attempt > 0:
            retries_used += 1
            await asyncio.sleep(backoff_base_seconds * (2 ** (attempt - 1)))

        try:
            output = await asyncio.wait_for(operation(), timeout=timeout_seconds)
            if not isinstance(output, dict):
                raise PermanentDelegationError(
                    f"Adapter returned non-dictionary output type '{type(output).__name__}'.",
                    error_code="invalid_output_schema",
                )
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return output, retries_used, duration_ms, None, None, "completed"

        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            last_error = sanitize_error_message(
                f"Operation timed out after {timeout_seconds:.1f}s ({exc or 'timeout'})",
                secrets_to_redact,
            )
            last_code = "timeout"
            last_status = "timed_out"
            continue

        except httpx.RequestError as exc:
            last_error = sanitize_error_message(
                f"Network error contacting platform endpoint: {exc}",
                secrets_to_redact,
            )
            last_code = "network_error"
            last_status = "failed"
            continue

        except TransientDelegationError as exc:
            last_error = sanitize_error_message(str(exc), secrets_to_redact)
            last_code = exc.error_code
            last_status = "failed"
            continue

        except PermanentDelegationError as exc:
            last_error = sanitize_error_message(str(exc), secrets_to_redact)
            last_code = exc.error_code
            last_status = "failed"
            break

        except Exception as exc:
            last_error = sanitize_error_message(str(exc), secrets_to_redact)
            last_code = "unexpected_error"
            last_status = "failed"
            break

    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    return None, retries_used, duration_ms, last_error, last_code, last_status


class SponsorAdapter(ABC):
    """Abstract interface implemented cleanly by every sponsor platform adapter."""

    platform_id: PlatformIdLiteral
    display_name: str
    mandatory_for_track: bool = True
    track_requirement_note: str = "Mandatory hackathon sponsor for Research — Data & Build."
    transport_protocol: str
    required_env_vars: List[str]
    official_docs_url: str
    capabilities: List[str]

    def __init__(self) -> None:
        self.last_check_status: Optional[str] = None
        self.last_check_error: Optional[str] = None
        self.last_checked_at: Optional[str] = None

    def _record_probe(self, status: str, error: Optional[str] = None) -> None:
        self.last_check_status = status
        self.last_check_error = error
        self.last_checked_at = datetime.now(timezone.utc).isoformat()

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True iff minimum required configuration/credentials are present."""

    @abstractmethod
    def integration_category(self) -> IntegrationCategoryLiteral:
        """Return honest status category ('live_tested', 'implemented', 'partial', 'not_integrated')."""

    @abstractmethod
    def runtime_state(self) -> RuntimeStateLiteral:
        """Return runtime availability state without exposing secrets."""

    @abstractmethod
    def status_notes(self) -> str:
        """Concise description of current capability and remaining prerequisites."""

    def get_status(self) -> PlatformIntegrationInfo:
        """Build safe PlatformIntegrationInfo (never includes secrets)."""
        return PlatformIntegrationInfo(
            platform_id=self.platform_id,
            display_name=self.display_name,
            mandatory_for_track=self.mandatory_for_track,
            track_requirement_note=self.track_requirement_note,
            status=self.integration_category(),
            runtime_state=self.runtime_state(),
            credentials_present=self.is_configured(),
            required_env_vars=list(self.required_env_vars),
            transport_protocol=self.transport_protocol,
            official_docs_url=self.official_docs_url,
            capabilities=list(self.capabilities),
            notes=self.status_notes(),
            last_check_status=self.last_check_status,
            last_check_error=self.last_check_error,
            last_checked_at=self.last_checked_at,
        )

    async def check_connectivity(self) -> PlatformIntegrationInfo:
        """Run a non-mutating health or capability probe and update status metadata."""
        if not self.is_configured():
            self._record_probe(
                self.runtime_state(),
                f"Prerequisites missing: {', '.join(self.required_env_vars) or 'runtime not installed'}.",
            )
            return self.get_status()
        self._record_probe("configured", None)
        return self.get_status()

    @abstractmethod
    async def delegate_task(
        self,
        request: DelegationTaskRequest,
        client: Optional[httpx.AsyncClient] = None,
    ) -> DelegationTaskResult:
        """Validate, dispatch (when configured), validate output, and return DelegationTaskResult."""

