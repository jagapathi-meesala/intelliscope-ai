"""
Agents package for IntelliScope AI.
"""

from backend.agents.analyst_agent import (
    AGENT_CAPABILITIES as ANALYST_AGENT_CAPABILITIES,
    AGENT_NAME as ANALYST_AGENT_NAME,
    AGENT_STATUS as ANALYST_AGENT_STATUS,
    AGENT_VERSION as ANALYST_AGENT_VERSION,
    AnalysisError,
    AnalysisValidationError,
    analyze_research,
)
from backend.agents.dashboard_builder_agent import (
    AGENT_CAPABILITIES as BUILDER_AGENT_CAPABILITIES,
    AGENT_NAME as BUILDER_AGENT_NAME,
    AGENT_STATUS as BUILDER_AGENT_STATUS,
    AGENT_VERSION as BUILDER_AGENT_VERSION,
    DashboardBuilderError,
    DashboardValidationError,
    build_dashboard,
)
from backend.agents.data_agent import (
    AGENT_CAPABILITIES,
    AGENT_NAME,
    AGENT_STATUS,
    AGENT_VERSION,
    DataCollectorError,
    DataCollectorResponseError,
    DataCollectorTimeoutError,
    DataCollectorUpstreamError,
    collect_research,
)
from backend.agents.verification_agent import (
    AGENT_CAPABILITIES as VERIFICATION_AGENT_CAPABILITIES,
    AGENT_NAME as VERIFICATION_AGENT_NAME,
    AGENT_STATUS as VERIFICATION_AGENT_STATUS,
    AGENT_VERSION as VERIFICATION_AGENT_VERSION,
    FACTUAL_ACCURACY_DISCLAIMER,
    verify_research,
)

__all__ = [
    "AGENT_CAPABILITIES",
    "AGENT_NAME",
    "AGENT_STATUS",
    "AGENT_VERSION",
    "ANALYST_AGENT_CAPABILITIES",
    "ANALYST_AGENT_NAME",
    "ANALYST_AGENT_STATUS",
    "ANALYST_AGENT_VERSION",
    "AnalysisError",
    "AnalysisValidationError",
    "BUILDER_AGENT_CAPABILITIES",
    "BUILDER_AGENT_NAME",
    "BUILDER_AGENT_STATUS",
    "BUILDER_AGENT_VERSION",
    "DashboardBuilderError",
    "DashboardValidationError",
    "DataCollectorError",
    "DataCollectorResponseError",
    "DataCollectorTimeoutError",
    "DataCollectorUpstreamError",
    "FACTUAL_ACCURACY_DISCLAIMER",
    "VERIFICATION_AGENT_CAPABILITIES",
    "VERIFICATION_AGENT_NAME",
    "VERIFICATION_AGENT_STATUS",
    "VERIFICATION_AGENT_VERSION",
    "analyze_research",
    "build_dashboard",
    "collect_research",
    "verify_research",
]
