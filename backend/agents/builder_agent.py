"""
Dashboard Builder Agent module re-export.
"""

from backend.agents.dashboard_builder_agent import (
    AGENT_CAPABILITIES,
    AGENT_NAME,
    AGENT_STATUS,
    AGENT_VERSION,
    BUILDER_AGENT_CAPABILITIES,
    BUILDER_AGENT_NAME,
    BUILDER_AGENT_STATUS,
    BUILDER_AGENT_VERSION,
    DashboardBuilderError,
    DashboardValidationError,
    build_dashboard,
)

__all__ = [
    "AGENT_CAPABILITIES",
    "AGENT_NAME",
    "AGENT_STATUS",
    "AGENT_VERSION",
    "BUILDER_AGENT_CAPABILITIES",
    "BUILDER_AGENT_NAME",
    "BUILDER_AGENT_STATUS",
    "BUILDER_AGENT_VERSION",
    "DashboardBuilderError",
    "DashboardValidationError",
    "build_dashboard",
]

