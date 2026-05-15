"""
JARVIS Sandbox Engine.

Runs generated code and plugin candidates in a bounded workspace before anything
is deployed. This is a process-level sandbox, not a VM: it controls working
directory, avoids shell execution by default, validates file paths, captures
output, and writes an audit trail for every run.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
SANDBOX_ROOT = ROOT / "sandbox"
LOG_FILE = ROOT / "logs" / "sandbox_audit.jsonl"


@dataclass
class SandboxSession:
    id: str
    root: Path
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SandboxRunResult:
    ok: bool
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: float
    cwd: str

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": round(self.duration_ms, 1),
            "cwd": self.cwd,
        }


class SandboxEngine:
    """Create isolated workspaces and execute bounded subprocess tests."""

    def __init__(self, config: dict | None = None, root: str | Path | None = None):
        self.config = config or {}
        self.root = Path(root or self.config.get("sandbox", {}).get("root", SANDBOX_ROOT)).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    def create_session(self, label: str = "run") -> SandboxSession:
        safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in label)[:32]
        sid = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_label}_{uuid.uuid4().hex[:6]}"
        path = (self.root / sid).resolve()
        path.mkdir(parents=True, exist_ok=False)
        session = SandboxSession(id=sid, root=path)
        self._audit("create_session", {"session": session.id, "root": str(session.root)})
        return session

    def cleanup_session(self, session: SandboxSession) -> dict:
        target = session.root.resolve()
        if not self._inside(self.root, target):
            return {"ok": False, "error": f"Refusing cleanup outside sandbox: {target}"}
        shutil.rmtree(target, ignore_errors=True)
        self._audit("cleanup_session", {"session": session.id})
        return {"ok": True, "session": session.id}

    def write_file(self, session: SandboxSession, relative_path: str, content: str) -> Path:
        target = self._session_path(session, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self._audit("write_file", {"session": session.id, "path": str(target), "bytes": len(content.encode("utf-8"))})
        return target

    def copy_into(self, session: SandboxSession, source: str | Path, relative_path: str | None = None) -> Path:
        src = Path(source).resolve()
        if not src.exists():
            raise FileNotFoundError(src)
        target = self._session_path(session, relative_path or src.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)
        self._audit("copy_into", {"session": session.id, "source": str(src), "target": str(target)})
        return target

    def run_python(
        self,
        session: SandboxSession,
        entry: str,
        args: Iterable[str] | None = None,
        timeout: int = 20,
        extra_pythonpath: Iterable[str | Path] | None = None,
    ) -> SandboxRunResult:
        script = self._session_path(session, entry)
        pythonpath = [str(ROOT)]
        pythonpath.extend(str(Path(p).resolve()) for p in (extra_pythonpath or []))
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(pythonpath + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        return self.run_command(
            session,
            [sys.executable, str(script), *(args or [])],
            timeout=timeout,
            env=env,
        )

    def run_py_compile(self, session: SandboxSession, relative_path: str, timeout: int = 15) -> SandboxRunResult:
        script = self._session_path(session, relative_path)
        return self.run_command(session, [sys.executable, "-m", "py_compile", str(script)], timeout=timeout)

    def run_command(
        self,
        session: SandboxSession,
        command: list[str],
        timeout: int = 20,
        env: dict | None = None,
    ) -> SandboxRunResult:
        if not command:
            raise ValueError("Sandbox command cannot be empty")

        cwd = session.root.resolve()
        if not self._inside(self.root, cwd):
            raise ValueError(f"Session root is outside sandbox: {cwd}")

        start = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            result = SandboxRunResult(
                ok=completed.returncode == 0,
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout[:4000],
                stderr=completed.stderr[:2000],
                duration_ms=(time.perf_counter() - start) * 1000,
                cwd=str(cwd),
            )
        except subprocess.TimeoutExpired as exc:
            result = SandboxRunResult(
                ok=False,
                command=command,
                returncode=124,
                stdout=(exc.stdout or "")[:4000] if isinstance(exc.stdout, str) else "",
                stderr=f"Timed out after {timeout}s",
                duration_ms=(time.perf_counter() - start) * 1000,
                cwd=str(cwd),
            )

        self._audit("run_command", {"session": session.id, **result.to_dict()})
        return result

    def import_check(self, session: SandboxSession, relative_path: str, timeout: int = 15) -> SandboxRunResult:
        target = self._session_path(session, relative_path)
        check_code = (
            "import importlib.util, pathlib\n"
            f"path = pathlib.Path(r'{target}')\n"
            "spec = importlib.util.spec_from_file_location('candidate_module', path)\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "print('IMPORT_OK')\n"
        )
        check_path = self.write_file(session, "_import_check.py", check_code)
        return self.run_python(session, check_path.name, timeout=timeout)

    def _session_path(self, session: SandboxSession, relative_path: str) -> Path:
        target = (session.root / relative_path).resolve()
        if not self._inside(session.root.resolve(), target):
            raise ValueError(f"Path escapes sandbox session: {relative_path}")
        return target

    @staticmethod
    def _inside(base: Path, target: Path) -> bool:
        try:
            target.relative_to(base.resolve())
            return True
        except ValueError:
            return False

    def _audit(self, action: str, detail: dict) -> None:
        entry = {"ts": datetime.now().isoformat(), "action": action, "detail": detail}
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
