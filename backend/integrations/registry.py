"""
Sponsor Integration Registry and Delegation Dispatcher for IntelliScope AI.

Provides centralized honest inspection of configured platform adapters and
bounded telemetry of delegated tasks across BAND, Lyzr, Agent37, AdaL, and Finch.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, Optional

import httpx

from backend.integrations.adal_adapter import AdalAdapter
from backend.integrations.agent37_adapter import Agent37Adapter
from backend.integrations.band_adapter import BandSponsorAdapter
from backend.integrations.base import SponsorAdapter
from backend.integrations.finch_adapter import FinchAdapter
from backend.integrations.lyzr_adapter import LyzrAdapter
from backend.integrations.models import (
    DelegationTaskRequest,
    DelegationTaskResult,
    IntegrationsStatusResponse,
    PlatformIntegrationInfo,
)


class IntegrationRegistry:
    """Thread-safe/async-friendly registry coordinating modular sponsor adapters."""

    def __init__(
        self,
        adapters: Optional[Dict[str, SponsorAdapter]] = None,
        max_delegations: int = 25,
    ) -> None:
        self._adapters: Dict[str, SponsorAdapter] = adapters or {
            "band": BandSponsorAdapter(),
            "lyzr": LyzrAdapter(),
            "agent37": Agent37Adapter(),
            "adal": AdalAdapter(),
            "finch": FinchAdapter(),
        }
        self._recent_delegations: Deque[DelegationTaskResult] = deque(maxlen=max_delegations)

    def list_platform_ids(self) -> list[str]:
        return list(self._adapters.keys())

    def get_adapter(self, platform_id: str) -> Optional[SponsorAdapter]:
        return self._adapters.get(platform_id.strip().lower())

    def get_status_response(self) -> IntegrationsStatusResponse:
        platforms: Dict[str, PlatformIntegrationInfo] = {
            pid: adapter.get_status()
            for pid, adapter in self._adapters.items()
        }
        summary = {
            "live_tested": 0,
            "implemented": 0,
            "partial": 0,
            "not_integrated": 0,
        }
        for info in platforms.values():
            summary[info.status] = summary.get(info.status, 0) + 1

        return IntegrationsStatusResponse(
            platforms=platforms,
            summary=summary,
            recent_delegations=list(self._recent_delegations),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

    async def check_platform(self, platform_id: str) -> Optional[PlatformIntegrationInfo]:
        adapter = self.get_adapter(platform_id)
        if adapter is None:
            return None
        return await adapter.check_connectivity()

    async def delegate(
        self,
        request: DelegationTaskRequest,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[DelegationTaskResult]:
        adapter = self.get_adapter(request.target_platform)
        if adapter is None:
            return None
        result = await adapter.delegate_task(request, client=client)
        self._recent_delegations.appendleft(result)
        return result

    def clear_delegations(self) -> None:
        self._recent_delegations.clear()


integration_registry = IntegrationRegistry()

