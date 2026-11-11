"""
Shared backend store for multi-agent pipeline execution history.

Maintains recent pipeline runs (ordered newest-first) so both BAND integration
and the React frontend always observe the latest successful run and can
restore any retained historical run without overwriting valid data on failures.
"""

import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

from backend.models.pipeline import (
    PipelineHistoryResponse,
    PipelineHistorySummary,
    PipelineResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "pipeline_history.json"


def _build_summary(run: PipelineResponse) -> PipelineHistorySummary:
    """Derive lightweight history summary strictly from an actual PipelineResponse."""
    source_count = run.research.result_count if run.research else 0
    eligible_count = run.analysis.eligible_sources_count if run.analysis else 0
    quality_score = float(run.verification.quality_score) if run.verification else 0.0
    directly_relevant_count = run.verification.directly_relevant_count if run.verification else 0
    weakly_relevant_count = run.verification.weakly_relevant_count if run.verification else 0
    excluded_count = (
        run.analysis.excluded_sources_count
        if run.analysis
        else (run.verification.excluded_count if run.verification else 0)
    )

    if run.dashboard and run.dashboard.themes:
        theme_count = len(run.dashboard.themes)
    elif run.dashboard and run.dashboard.key_themes:
        theme_count = len(run.dashboard.key_themes)
    elif run.analysis:
        theme_count = len(run.analysis.key_themes)
    else:
        theme_count = 0

    summary_text = run.summary or (run.analysis.executive_summary if run.analysis else None)

    return PipelineHistorySummary(
        pipeline_id=run.pipeline_id,
        query=run.query,
        status=run.status,
        executed_at=run.executed_at,
        total_duration_ms=run.total_duration_ms,
        source_count=source_count,
        eligible_count=eligible_count,
        directly_relevant_count=directly_relevant_count,
        weakly_relevant_count=weakly_relevant_count,
        excluded_count=excluded_count,
        quality_score=quality_score,
        theme_count=theme_count,
        summary=summary_text,
    )


class PipelineHistoryStore:
    """
    Thread-safe bounded history store for multi-agent pipeline executions.

    Guarantees:
    - Retains up to `max_entries` recent runs newest-first.
    - Failed or incomplete runs are logged in history for visibility, but
      NEVER overwrite `latest_successful_pipeline_id`.
    """

    def __init__(
        self,
        max_entries: int = 50,
        storage_path: Optional[Path] = None,
        enable_persistence: Optional[bool] = None,
    ) -> None:
        self._max_entries = max(1, max_entries)
        self._lock = Lock()
        self._runs: List[PipelineResponse] = []
        self._runs_by_id: Dict[str, PipelineResponse] = {}
        self._latest_successful_id: Optional[str] = None

        # Avoid disk writes during automated pytest runs unless explicitly requested
        is_pytest = "PYTEST_CURRENT_TEST" in os.environ
        if enable_persistence is None:
            self._persistence_enabled = not is_pytest
        else:
            self._persistence_enabled = enable_persistence

        self._storage_path = Path(storage_path) if storage_path else DEFAULT_HISTORY_PATH
        if self._persistence_enabled:
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load previously persisted runs from disk if available."""
        if not self._storage_path.exists():
            return
        try:
            raw = self._storage_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            runs_data = data.get("runs", [])
            loaded: List[PipelineResponse] = []
            for item in runs_data[: self._max_entries]:
                try:
                    loaded.append(PipelineResponse(**item))
                except Exception as exc:
                    logger.warning("Skipping invalid persisted pipeline record: %s", exc)
            self._runs = loaded
            self._runs_by_id = {r.pipeline_id: r for r in loaded}
            saved_latest_id = data.get("latest_successful_pipeline_id")
            if (
                saved_latest_id
                and saved_latest_id in self._runs_by_id
                and self._runs_by_id[saved_latest_id].status == "success"
            ):
                self._latest_successful_id = saved_latest_id
            else:
                first_ok = next((r for r in self._runs if r.status == "success"), None)
                self._latest_successful_id = first_ok.pipeline_id if first_ok else None
        except Exception as exc:
            logger.warning("Failed to load pipeline history from '%s': %s", self._storage_path, exc)

    def _save_to_disk(self) -> None:
        """Persist current history state atomically to disk when enabled."""
        if not self._persistence_enabled:
            return
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "latest_successful_pipeline_id": self._latest_successful_id,
                "runs": [r.model_dump() for r in self._runs],
            }
            tmp_path = self._storage_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_path.replace(self._storage_path)
        except Exception as exc:
            logger.warning("Failed to persist pipeline history to '%s': %s", self._storage_path, exc)

    def record_run(self, pipeline_response: PipelineResponse) -> None:
        """
        Record a pipeline execution.

        Only runs with `status == 'success'` advance `latest_successful_pipeline_id`.
        Failed runs remain recorded in history without overwriting the last good result.
        """
        with self._lock:
            # Remove previous entry with same ID if present, then prepend (newest-first)
            self._runs = [r for r in self._runs if r.pipeline_id != pipeline_response.pipeline_id]
            self._runs.insert(0, pipeline_response)

            if len(self._runs) > self._max_entries:
                removed = self._runs[self._max_entries :]
                self._runs = self._runs[: self._max_entries]
                for rem in removed:
                    if rem.pipeline_id != self._latest_successful_id:
                        self._runs_by_id.pop(rem.pipeline_id, None)

            self._runs_by_id[pipeline_response.pipeline_id] = pipeline_response

            if pipeline_response.status == "success" and pipeline_response.dashboard is not None:
                self._latest_successful_id = pipeline_response.pipeline_id

            self._save_to_disk()

    def get_latest_successful(self) -> Optional[PipelineResponse]:
        """Return the newest successful pipeline run, or None if none exists."""
        with self._lock:
            if self._latest_successful_id and self._latest_successful_id in self._runs_by_id:
                candidate = self._runs_by_id[self._latest_successful_id]
                if candidate.status == "success":
                    return candidate
            for run in self._runs:
                if run.status == "success":
                    return run
            return None

    def get_run(self, pipeline_id: str) -> Optional[PipelineResponse]:
        """Return full PipelineResponse for a specific pipeline_id, or None."""
        with self._lock:
            return self._runs_by_id.get(pipeline_id)

    def get_history_response(self, limit: int = 20) -> PipelineHistoryResponse:
        """Return structured history response including summaries and latest successful run."""
        with self._lock:
            bounded_limit = max(1, min(limit, self._max_entries))
            summaries = [_build_summary(r) for r in self._runs[:bounded_limit]]
            latest_run = None
            if self._latest_successful_id and self._latest_successful_id in self._runs_by_id:
                latest_run = self._runs_by_id[self._latest_successful_id]
            else:
                latest_run = next((r for r in self._runs if r.status == "success"), None)

            return PipelineHistoryResponse(
                total_runs=len(self._runs),
                latest_successful_pipeline_id=latest_run.pipeline_id if latest_run else None,
                latest_successful_run=latest_run,
                runs=summaries,
            )

    def clear(self) -> None:
        """Clear all retained runs from memory (and disk if persistence enabled)."""
        with self._lock:
            self._runs.clear()
            self._runs_by_id.clear()
            self._latest_successful_id = None
            if self._persistence_enabled and self._storage_path.exists():
                try:
                    self._storage_path.unlink()
                except Exception:
                    pass


pipeline_history_store = PipelineHistoryStore()

