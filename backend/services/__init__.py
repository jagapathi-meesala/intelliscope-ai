"""
Services package for IntelliScope AI backend.
"""

from typing import Any

__all__ = [
    "PipelineOrchestrator",
    "run_pipeline",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve pipeline orchestration exports to prevent package circular imports."""
    if name in ("PipelineOrchestrator", "run_pipeline"):
        from backend.services.pipeline_orchestrator import PipelineOrchestrator, run_pipeline

        return PipelineOrchestrator if name == "PipelineOrchestrator" else run_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
