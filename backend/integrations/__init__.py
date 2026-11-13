"""
Sponsor integrations and agent interoperability package for IntelliScope AI.
"""

from backend.integrations.adal_adapter import AdalAdapter
from backend.integrations.agent37_adapter import Agent37Adapter
from backend.integrations.band_adapter import BandSponsorAdapter, resolve_band_credentials
from backend.integrations.base import (
    PermanentDelegationError,
    SponsorAdapter,
    TransientDelegationError,
    execute_with_timeout_and_retries,
    sanitize_error_message,
)
from backend.integrations.finch_adapter import FinchAdapter
from backend.integrations.lyzr_adapter import LyzrAdapter
from backend.integrations.models import (
    AgentHandoffRecord,
    DelegationTaskRequest,
    DelegationTaskResult,
    ExecutionContext,
    IntegrationsStatusResponse,
    PlatformIntegrationInfo,
)
from backend.integrations.registry import IntegrationRegistry, integration_registry

__all__ = [
    "AdalAdapter",
    "Agent37Adapter",
    "AgentHandoffRecord",
    "BandSponsorAdapter",
    "DelegationTaskRequest",
    "DelegationTaskResult",
    "ExecutionContext",
    "FinchAdapter",
    "IntegrationRegistry",
    "IntegrationsStatusResponse",
    "LyzrAdapter",
    "PermanentDelegationError",
    "PlatformIntegrationInfo",
    "SponsorAdapter",
    "TransientDelegationError",
    "execute_with_timeout_and_retries",
    "integration_registry",
    "resolve_band_credentials",
    "sanitize_error_message",
]

