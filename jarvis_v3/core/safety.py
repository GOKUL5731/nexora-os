"""
JARVIS Safety Engine
Guards against dangerous operations. Backup-before-change enforcement.
"""

import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("jarvis.safety")

# ── Risk classification ──────────────────────────────────────────────────────
DESTRUCTIVE_KEYWORDS = {
    "delete", "remove", "erase", "wipe", "format", "uninstall",
    "drop", "truncate", "kill", "terminate", "shutdown", "reboot",
    "rmdir", "del ", "rm -", "reg delete", "registry",
}

SAFE_KEYWORDS = {
    "open", "read", "list", "show", "display", "search", "find",
    "check", "status", "info", "help", "hello", "what", "how",
    "summarize", "explain", "tell", "report", "get",
}

HIGH_RISK_TOOLS = {
    "delete_file", "run_command", "system_command", "write_file",
    "registry_edit", "format_drive", "uninstall_app",
}

ALWAYS_CONFIRM = {
    "delete_file", "registry_edit", "format_drive",
    "uninstall_app", "send_email", "purchase",
}


class SafetyEngine:
    """Assess risk and enforce safety policies."""

    def __init__(self, config: dict):
        self.config = config
        self.always_ask = set(config.get("always_ask_for", list(ALWAYS_CONFIRM)))
        self.overrides  = config.get("permission_overrides", {})
        self._audit_log: list[dict] = []

    # ── Risk assessment ──────────────────────────────────────────────────────
    def assess_text(self, text: str) -> str:
        """Return 'low', 'medium', or 'high' risk for free-form text."""
        low = text.lower()
        if any(k in low for k in DESTRUCTIVE_KEYWORDS):
            return "high"
        if any(k in low for k in SAFE_KEYWORDS):
            return "low"
        return "medium"

    def assess_tool(self, tool: str, args: dict) -> str:
        """Return risk level for a specific tool call."""
        if tool in self.always_ask:
            return "high"
        if tool in HIGH_RISK_TOOLS:
            # run_command is high only for dangerous commands
            if tool in ("run_command", "system_command"):
                cmd = args.get("command", "").lower()
                if any(k in cmd for k in DESTRUCTIVE_KEYWORDS):
                    return "high"
                return "medium"
            return "high"
        return "low"

    def requires_confirmation(self, tool: str, args: dict) -> bool:
        if self.overrides.get(tool) == "allow":
            return False
        if self.overrides.get(tool) == "deny":
            return True
        return self.assess_tool(tool, args) == "high"

    # ── Audit trail ──────────────────────────────────────────────────────────
    def log_action(self, tool: str, args: dict, result: dict, confirmed: bool = True):
        entry = {
            "ts": datetime.now().isoformat(),
            "tool": tool,
            "args": str(args)[:200],
            "result": str(result)[:200],
            "confirmed": confirmed,
            "risk": self.assess_tool(tool, args),
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > 500:
            self._audit_log = self._audit_log[-500:]
        if entry["risk"] == "high":
            logger.warning(f"HIGH-RISK action: {tool} | confirmed={confirmed}")

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        return self._audit_log[-limit:]

    # ── File safety ──────────────────────────────────────────────────────────
    def safe_delete_check(self, path: str) -> dict:
        """Return warning info before deleting."""
        p = Path(path)
        if not p.exists():
            return {"ok": False, "reason": "Path does not exist"}
        size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size
        return {
            "ok": True,
            "path": str(p),
            "type": "directory" if p.is_dir() else "file",
            "size_bytes": size,
            "warning": f"This will permanently delete {'directory' if p.is_dir() else 'file'}: {p.name}",
        }

    def create_backup(self, source_path: str, backup_dir: str = None) -> dict:
        """Backup a file or directory before modification."""
        src = Path(source_path)
        if not src.exists():
            return {"ok": False, "reason": f"Source not found: {source_path}"}

        bk_root = Path(backup_dir or "backups")
        bk_root.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = bk_root / f"{src.name}_{ts}"

        try:
            if src.is_dir():
                shutil.copytree(src, dest)
            else:
                shutil.copy2(src, dest)
            logger.info(f"Backup created: {dest}")
            return {"ok": True, "backup": str(dest), "source": str(src)}
        except Exception as e:
            return {"ok": False, "reason": str(e)}
