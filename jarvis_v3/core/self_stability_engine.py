"""Self-stability controls for architecture integrity, checkpoints, and rollbacks."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "self_stability.db"
CHECKPOINT_ROOT = ROOT / "checkpoints" / "meta_stability"


class SelfStabilityEngine:
    """Prevents unsafe recursive evolution through integrity gates and rollback records."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None, root: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("self_stability", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.root = Path(root or ROOT)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_ROOT.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS integrity_snapshots (
                    id TEXT PRIMARY KEY,
                    manifest TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    files TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS stability_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def architecture_manifest(self, paths: list[str] | None = None) -> dict[str, Any]:
        paths = paths or ["core", "ui", "tests"]
        files = {}
        for rel in paths:
            target = (self.root / rel).resolve()
            if not target.exists():
                continue
            iterable = target.rglob("*.py") if target.is_dir() else [target]
            for path in iterable:
                if "__pycache__" in path.parts:
                    continue
                try:
                    data = path.read_bytes()
                except Exception:
                    continue
                files[str(path.relative_to(self.root))] = hashlib.sha256(data).hexdigest()
        digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode("utf-8")).hexdigest()
        return {"digest": digest, "files": files, "file_count": len(files), "created_at": datetime.now().isoformat()}

    def record_integrity_snapshot(self, paths: list[str] | None = None) -> dict[str, Any]:
        manifest = self.architecture_manifest(paths)
        snapshot_id = f"integrity-{uuid.uuid4().hex[:12]}"
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO integrity_snapshots VALUES (?,?,?)",
                (snapshot_id, json.dumps(manifest, ensure_ascii=False, default=str), datetime.now().isoformat()),
            )
        return {"id": snapshot_id, "manifest": manifest}

    def verify_integrity(self, baseline_id: str | None = None, paths: list[str] | None = None) -> dict[str, Any]:
        current = self.architecture_manifest(paths)
        baseline = None
        with self._lock, sqlite3.connect(self.db_path) as db:
            if baseline_id:
                row = db.execute("SELECT manifest FROM integrity_snapshots WHERE id=?", (baseline_id,)).fetchone()
            else:
                row = db.execute("SELECT manifest FROM integrity_snapshots ORDER BY created_at DESC LIMIT 1").fetchone()
            if row:
                baseline = json.loads(row[0] or "{}")
        if not baseline:
            return {"ok": True, "current": current, "baseline": None, "changes": []}
        changes = self._diff_manifest(baseline, current)
        allowed = self.config.get("self_stability", {}).get("allow_file_changes", True)
        return {"ok": allowed or not changes, "current": current, "baseline": baseline, "changes": changes}

    def create_checkpoint(self, label: str, files: list[str]) -> dict[str, Any]:
        checkpoint_id = f"checkpoint-{uuid.uuid4().hex[:12]}"
        root = CHECKPOINT_ROOT / checkpoint_id
        root.mkdir(parents=True, exist_ok=False)
        copied = []
        for rel in files:
            src = (self.root / rel).resolve()
            if not src.exists() or not self._inside(self.root, src):
                continue
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)
        record = {"id": checkpoint_id, "label": label, "files": copied, "status": "created", "created_at": datetime.now().isoformat()}
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO checkpoints VALUES (?,?,?,?,?)",
                (checkpoint_id, label, json.dumps(copied), "created", record["created_at"]),
            )
        return record

    def rollback_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT files FROM checkpoints WHERE id=?", (checkpoint_id,)).fetchone()
        if not row:
            return {"rolled_back": False, "error": f"Checkpoint not found: {checkpoint_id}"}
        files = json.loads(row[0] or "[]")
        root = CHECKPOINT_ROOT / checkpoint_id
        restored = []
        for rel in files:
            src = (root / rel).resolve()
            dst = (self.root / rel).resolve()
            if src.exists() and self._inside(root, src) and self._inside(self.root, dst):
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                restored.append(rel)
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE checkpoints SET status='rolled_back' WHERE id=?", (checkpoint_id,))
            db.execute(
                "INSERT INTO stability_events(event_type,detail,created_at) VALUES(?,?,?)",
                ("rollback", json.dumps({"checkpoint": checkpoint_id, "files": restored}), datetime.now().isoformat()),
            )
        return {"rolled_back": True, "checkpoint": checkpoint_id, "files": restored}

    def stability_gate(self, proposal: dict[str, Any], simulation: dict[str, Any] | None = None) -> dict[str, Any]:
        integrity = self.verify_integrity()
        constraints = []
        proposal_text = json.dumps(proposal, default=str).lower()
        unsafe_markers = ["recursive self-modification", "disable safety", "delete database", "shell=true"]
        for marker in unsafe_markers:
            if marker in proposal_text:
                constraints.append({"type": "unsafe_marker", "marker": marker})
        if simulation and simulation.get("risk_score", 0) > 0.65:
            constraints.append({"type": "simulation_risk", "risk_score": simulation["risk_score"]})
        stable = integrity["ok"] and not constraints
        return {"stable": stable, "integrity": integrity, "constraints": constraints}

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT event_type,detail,created_at FROM stability_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"type": row[0], "detail": json.loads(row[1] or "{}"), "created_at": row[2]} for row in rows]

    @staticmethod
    def _diff_manifest(base: dict[str, Any], current: dict[str, Any]) -> list[dict[str, str]]:
        base_files = base.get("files", {})
        current_files = current.get("files", {})
        changes = []
        for path, digest in current_files.items():
            if path not in base_files:
                changes.append({"path": path, "change": "added"})
            elif base_files[path] != digest:
                changes.append({"path": path, "change": "modified"})
        for path in base_files:
            if path not in current_files:
                changes.append({"path": path, "change": "removed"})
        return changes

    @staticmethod
    def _inside(base: Path, target: Path) -> bool:
        try:
            target.relative_to(base.resolve())
            return True
        except ValueError:
            return False
