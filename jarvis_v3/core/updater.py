"""
JARVIS Self-Upgrade Engine (Safe)
Pipeline: Observe → Diagnose → Generate Patch → Test → Backup → Deploy → Log → Allow Rollback
NEVER modifies core files without backup. NEVER deploys failing code.
"""

import hashlib
import json
import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.updater")

ROOT    = Path(__file__).resolve().parent.parent
BACKUP  = ROOT / "backups"
PATCHES = ROOT / "backups" / "patches"
LOG_FILE = ROOT / "logs" / "update_log.json"

# Files that can NEVER be touched by auto-updater
PROTECTED = {
    "core/config.py",
    "core/safety.py",
    "core/updater.py",
    "main.py",
    "agents/agent_registry.py",
}


class UpdateRecord:
    def __init__(self, patch_id: str, target: str, description: str):
        self.id          = patch_id
        self.target      = target
        self.description = description
        self.status      = "pending"   # pending|tested|deployed|failed|rolled_back
        self.backup_path = None
        self.ts          = datetime.now().isoformat()

    def to_dict(self):
        return vars(self)


class SelfUpdater:
    """
    Controlled self-improvement pipeline.
    Each update is sandboxed, tested, and logged before deployment.
    """

    def __init__(self, config: dict):
        self.config = config
        BACKUP.mkdir(parents=True, exist_ok=True)
        PATCHES.mkdir(parents=True, exist_ok=True)
        self._history: list[UpdateRecord] = []
        self._load_log()

    # ── Audit log ────────────────────────────────────────────────────────────
    def _load_log(self):
        if LOG_FILE.exists():
            try:
                data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
                for d in data:
                    rec = UpdateRecord(d["id"], d["target"], d["description"])
                    rec.__dict__.update(d)
                    self._history.append(rec)
            except Exception:
                pass

    def _save_log(self):
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text(
            json.dumps([r.to_dict() for r in self._history], indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # ── Protection checks ────────────────────────────────────────────────────
    def _is_protected(self, relative_path: str) -> bool:
        rel = relative_path.replace("\\", "/").lstrip("./")
        return rel in PROTECTED

    def _validate_target(self, target_path: str) -> tuple[bool, str]:
        p = Path(target_path)
        if not p.exists():
            return False, f"Target does not exist: {target_path}"
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if self._is_protected(rel):
            return False, f"Protected file — cannot auto-update: {rel}"
        if not target_path.endswith(".py"):
            return False, "Only .py files may be auto-updated"
        return True, "ok"

    # ── Step 1: Backup ───────────────────────────────────────────────────────
    def create_backup(self, target_path: str) -> Optional[str]:
        src = Path(target_path)
        if not src.exists():
            return None
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUP / f"{src.stem}_{ts}{src.suffix}"
        shutil.copy2(src, dest)
        logger.info(f"Backup: {src.name} → {dest.name}")
        return str(dest)

    # ── Step 2: Write patch to sandbox ───────────────────────────────────────
    def write_patch(self, patch_id: str, code: str) -> Path:
        patch_file = PATCHES / f"{patch_id}.py"
        patch_file.write_text(code, encoding="utf-8")
        return patch_file

    # ── Step 3: Syntax test ──────────────────────────────────────────────────
    def test_syntax(self, file_path: Path) -> tuple[bool, str]:
        """Run py_compile to check for syntax errors."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(file_path)],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode == 0:
                return True, "syntax ok"
            return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    # ── Step 4: Import test ──────────────────────────────────────────────────
    def test_import(self, file_path: Path) -> tuple[bool, str]:
        """Try importing the patch in a subprocess to catch runtime errors."""
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import importlib.util; "
                 f"spec = importlib.util.spec_from_file_location('test_patch', r'{file_path}'); "
                 f"mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)"],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode == 0:
                return True, "import ok"
            return False, result.stderr.strip()[:500]
        except Exception as e:
            return False, str(e)

    # ── Step 5: Deploy ───────────────────────────────────────────────────────
    def deploy(self, patch_path: Path, target_path: str) -> tuple[bool, str]:
        try:
            shutil.copy2(patch_path, target_path)
            logger.info(f"Deployed patch → {target_path}")
            return True, "deployed"
        except Exception as e:
            return False, str(e)

    # ── Step 6: Rollback ─────────────────────────────────────────────────────
    def rollback(self, patch_id: str) -> tuple[bool, str]:
        for rec in reversed(self._history):
            if rec.id == patch_id and rec.status == "deployed":
                if rec.backup_path and Path(rec.backup_path).exists():
                    try:
                        shutil.copy2(rec.backup_path, rec.target)
                        rec.status = "rolled_back"
                        self._save_log()
                        logger.info(f"Rolled back {rec.target}")
                        return True, f"Rolled back to {rec.backup_path}"
                    except Exception as e:
                        return False, str(e)
                return False, "No backup available"
        return False, "Patch not found or not deployed"

    # ── Full pipeline ─────────────────────────────────────────────────────────
    async def apply_patch(self, target_path: str, new_code: str,
                          description: str = "") -> dict:
        """
        Full safe-update pipeline.
        Returns dict with keys: ok, patch_id, steps, message
        """
        patch_id = hashlib.md5(f"{target_path}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
        rec = UpdateRecord(patch_id, target_path, description)
        self._history.append(rec)
        steps = []

        # Validate target
        valid, reason = self._validate_target(target_path)
        if not valid:
            rec.status = "failed"
            self._save_log()
            return {"ok": False, "patch_id": patch_id, "message": reason, "steps": steps}
        steps.append("✓ Target validated")

        # Backup
        backup = self.create_backup(target_path)
        rec.backup_path = backup
        steps.append(f"✓ Backup: {Path(backup).name if backup else 'none'}")

        # Write patch
        patch_file = self.write_patch(patch_id, new_code)
        steps.append(f"✓ Patch written: {patch_file.name}")

        # Syntax test
        ok, msg = self.test_syntax(patch_file)
        if not ok:
            rec.status = "failed"
            self._save_log()
            patch_file.unlink(missing_ok=True)
            return {"ok": False, "patch_id": patch_id,
                    "message": f"Syntax error: {msg}", "steps": steps}
        steps.append("✓ Syntax OK")

        # Import test
        ok, msg = self.test_import(patch_file)
        if not ok:
            rec.status = "failed"
            self._save_log()
            patch_file.unlink(missing_ok=True)
            return {"ok": False, "patch_id": patch_id,
                    "message": f"Import error: {msg}", "steps": steps}
        steps.append("✓ Import OK")

        # Deploy
        ok, msg = self.deploy(patch_file, target_path)
        if not ok:
            rec.status = "failed"
            self._save_log()
            return {"ok": False, "patch_id": patch_id, "message": msg, "steps": steps}

        rec.status = "deployed"
        self._save_log()
        steps.append("✓ Deployed")
        logger.info(f"Update {patch_id} deployed: {description}")

        return {
            "ok": True,
            "patch_id": patch_id,
            "message": f"Update deployed successfully. Rollback ID: {patch_id}",
            "steps": steps,
            "backup": backup,
        }

    # ── History ───────────────────────────────────────────────────────────────
    def get_history(self, limit: int = 20) -> list[dict]:
        return [r.to_dict() for r in reversed(self._history[-limit:])]

    def get_rollbackable(self) -> list[dict]:
        return [r.to_dict() for r in self._history if r.status == "deployed"]
