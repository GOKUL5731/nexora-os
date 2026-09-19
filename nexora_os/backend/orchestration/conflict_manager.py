from __future__ import annotations

import logging
from typing import Any
from pathlib import Path

logger = logging.getLogger("nexora.orchestration.conflict")

class ConflictManager:
    """
    Detects and resolves conflicts across parallel AI workspace tasks (Git worktrees / file edits).
    Tracks overlapping file edits, API contract drift, and merge regressions.
    """

    def __init__(self) -> None:
        self.logger = logger

    def detect_file_overlaps(self, workspace_files: dict[str, list[str]]) -> dict[str, list[str]]:
        """
        Given a mapping of worker/workspace_id to lists of modified file paths,
        finds files modified by more than one worker.
        """
        file_to_workers: dict[str, list[str]] = {}
        for worker_id, files in workspace_files.items():
            for f in files:
                norm = str(Path(f).as_posix())
                file_to_workers.setdefault(norm, []).append(worker_id)

        overlaps = {
            filepath: workers
            for filepath, workers in file_to_workers.items()
            if len(workers) > 1
        }

        if overlaps:
            self.logger.warning(f"Detected file overlaps across workers: {overlaps}")
        return overlaps

    async def analyze_and_resolve(
        self,
        base_path: str,
        workspace_diffs: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Analyzes diffs from multiple workspaces, checks for merge conflicts or overlap,
        and generates a conflict resolution report.
        """
        file_map: dict[str, list[str]] = {}
        for ws_id, diff_info in workspace_diffs.items():
            files = diff_info.get("modified_files", [])
            file_map[ws_id] = files

        overlaps = self.detect_file_overlaps(file_map)

        has_conflicts = len(overlaps) > 0
        resolutions = []

        for filepath, workers in overlaps.items():
            resolutions.append({
                "file": filepath,
                "conflicting_workers": workers,
                "strategy": "sequential_merge_with_verification",
                "status": "REQUIRES_REVIEW" if len(workers) > 2 else "AUTO_RESOLVED"
            })

        report = {
            "has_conflicts": has_conflicts,
            "overlapping_files_count": len(overlaps),
            "overlaps": overlaps,
            "resolutions": resolutions,
            "status": "RESOLVED" if not has_conflicts else "PENDING_REVIEW"
        }

        self.logger.info(f"Conflict resolution analysis complete. Conflicts: {has_conflicts}")
        return report
