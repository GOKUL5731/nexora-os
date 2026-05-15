"""
JARVIS Evolution / Self-Upgrade Engine.

Controlled pipeline:
Analyze -> Generate -> Sandbox -> Test -> Benchmark -> Compare -> Deploy -> Log -> Backup

Core boot files are never overwritten by this engine. New plugins can be
generated and deployed after syntax/import/register checks. Existing modules
are patched only through SelfUpdater, which creates backups and supports
rollback.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.benchmark import BenchmarkEngine
from core.coder import CodingCopilot
from core.sandbox_engine import SandboxEngine
from core.updater import SelfUpdater


logger = logging.getLogger("jarvis.evolution")
ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = ROOT / "plugins"
LOG_FILE = ROOT / "logs" / "evolution_log.jsonl"
MANIFEST = PLUGIN_DIR / ".plugin_versions.json"

PROTECTED_BOOT_FILES = {
    "main.py",
    "jarvis_gui.py",
    "core/config.py",
    "core/updater.py",
    "core/upgrade_engine.py",
    "core/safety.py",
    "core/safety_engine.py",
    "core/permission_engine.py",
    "agents/agent_registry.py",
}

FORBIDDEN_PLUGIN_PATTERNS = [
    r"\bos\.remove\b",
    r"\bos\.rmdir\b",
    r"\bshutil\.rmtree\b",
    r"\bsubprocess\.Popen\b",
    r"\bsubprocess\.run\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bctypes\b",
    r"\bwinreg\b",
]


class EvolutionEngine:
    """Self-analysis, sandboxed candidate testing, and safe deployment."""

    def __init__(self, config: dict, router=None):
        self.config = config
        self.router = router
        self.sandbox = SandboxEngine(config)
        self.updater = SelfUpdater(config)
        self.benchmark = BenchmarkEngine(config)
        PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    def analyze_codebase(self, paths: list[str] | None = None) -> dict:
        """Inspect Python modules for size, TODOs, imports, and simple complexity signals."""
        started = time.perf_counter()
        targets = [ROOT / p for p in paths] if paths else [ROOT / "core", ROOT / "agents", ROOT / "memory", ROOT / "self_learning"]
        files: list[Path] = []
        for target in targets:
            if target.is_file() and target.suffix == ".py":
                files.append(target)
            elif target.exists():
                files.extend(target.rglob("*.py"))

        ignored = {"__pycache__", "node_modules", ".venv", "venv"}
        modules = []
        for path in sorted(set(files)):
            if any(part in ignored for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            lines = text.splitlines()
            functions = len(re.findall(r"^\s*def\s+\w+", text, re.MULTILINE))
            async_functions = len(re.findall(r"^\s*async\s+def\s+\w+", text, re.MULTILINE))
            classes = len(re.findall(r"^\s*class\s+\w+", text, re.MULTILINE))
            todos = len(re.findall(r"\b(TODO|FIXME|HACK)\b", text, re.IGNORECASE))
            broad_excepts = len(re.findall(r"except\s+Exception", text))
            shell_calls = len(re.findall(r"shell\s*=\s*True", text))
            protected = rel in PROTECTED_BOOT_FILES
            complexity = len(lines) + functions * 6 + async_functions * 8 + classes * 12 + broad_excepts * 5 + shell_calls * 20
            modules.append({
                "path": rel,
                "lines": len(lines),
                "functions": functions,
                "async_functions": async_functions,
                "classes": classes,
                "todos": todos,
                "broad_excepts": broad_excepts,
                "shell_true": shell_calls,
                "protected": protected,
                "complexity_score": complexity,
            })

        modules.sort(key=lambda item: item["complexity_score"], reverse=True)
        recommendations = self._recommend_from_analysis(modules)
        elapsed = (time.perf_counter() - started) * 1000
        self.benchmark.record("evolution_analyze", elapsed, True)
        report = {
            "generated_at": datetime.now().isoformat(),
            "module_count": len(modules),
            "top_modules": modules[:20],
            "recommendations": recommendations,
            "duration_ms": round(elapsed, 1),
        }
        self._log("analyze", report)
        return report

    async def generate_plugin(self, description: str) -> dict:
        """Ask the local coding model to generate a plugin candidate."""
        if not description.strip():
            return {"ok": False, "error": "Plugin description is required"}

        coder = CodingCopilot(self.config, self.router)
        generated = await coder.generate_plugin(description)
        if not generated.get("ok"):
            self._log("generate_plugin_failed", generated)
            return generated
        generated["safety"] = self.static_safety_scan(generated["code"])
        generated["ok"] = generated["safety"]["ok"]
        self._log("generate_plugin", {"description": description, "ok": generated["ok"]})
        return generated

    def static_safety_scan(self, code: str) -> dict:
        findings = []
        for pattern in FORBIDDEN_PLUGIN_PATTERNS:
            if re.search(pattern, code):
                findings.append(pattern)
        return {"ok": not findings, "findings": findings}

    def sandbox_plugin(self, code: str, name: str = "candidate_plugin") -> dict:
        """Compile, import, and validate a plugin register() contract in sandbox."""
        safety = self.static_safety_scan(code)
        if not safety["ok"]:
            return {"ok": False, "stage": "static_safety", "safety": safety}

        session = self.sandbox.create_session("plugin")
        filename = self._safe_plugin_filename(name)
        passed = False
        try:
            self.sandbox.write_file(session, filename, code)

            compile_result = self.sandbox.run_py_compile(session, filename)
            if not compile_result.ok:
                return {"ok": False, "stage": "compile", "compile": compile_result.to_dict(), "session": session.id}

            import_result = self.sandbox.import_check(session, filename)
            if not import_result.ok:
                return {"ok": False, "stage": "import", "import": import_result.to_dict(), "session": session.id}

            contract_code = (
                "import importlib.util, pathlib\n"
                f"path = pathlib.Path(r'{session.root / filename}')\n"
                "spec = importlib.util.spec_from_file_location('candidate_plugin', path)\n"
                "mod = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(mod)\n"
                "assert hasattr(mod, 'register'), 'missing register()'\n"
                "registration = mod.register({})\n"
                "assert isinstance(registration, dict), 'register() must return dict'\n"
                "tools = registration.get('tools')\n"
                "assert isinstance(tools, dict) and tools, 'plugin must expose at least one tool'\n"
                "for tool_name, handler in tools.items():\n"
                "    assert callable(handler), f'tool {tool_name} is not callable'\n"
                "print('PLUGIN_CONTRACT_OK')\n"
            )
            self.sandbox.write_file(session, "_contract_check.py", contract_code)
            contract_result = self.sandbox.run_python(session, "_contract_check.py", timeout=10)
            ok = contract_result.ok and "PLUGIN_CONTRACT_OK" in contract_result.stdout
            passed = ok
            return {
                "ok": ok,
                "stage": "contract" if not ok else "passed",
                "compile": compile_result.to_dict(),
                "import": import_result.to_dict(),
                "contract": contract_result.to_dict(),
                "session": session.id,
            }
        finally:
            keep = self.config.get("sandbox", {}).get("keep_failed_sessions", True)
            if passed or not keep:
                self.sandbox.cleanup_session(session)

    def deploy_plugin(self, code: str, name: str, description: str = "") -> dict:
        """Deploy a validated plugin with version history and rollback metadata."""
        test = self.sandbox_plugin(code, name)
        if not test.get("ok"):
            self._log("deploy_plugin_failed", {"name": name, "test": test})
            return {"ok": False, "message": "Plugin failed sandbox validation", "test": test}

        filename = self._safe_plugin_filename(name)
        target = (PLUGIN_DIR / filename).resolve()
        if not self._inside(PLUGIN_DIR.resolve(), target):
            return {"ok": False, "message": "Unsafe plugin path"}

        backup_path = None
        if target.exists():
            backup_dir = ROOT / "backups" / "plugins"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"{target.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{target.suffix}"
            shutil.copy2(target, backup_path)

        target.write_text(code, encoding="utf-8")
        record = {
            "id": hashlib.md5(f"{filename}{datetime.now().isoformat()}".encode()).hexdigest()[:10],
            "name": name,
            "file": str(target.relative_to(ROOT)).replace("\\", "/"),
            "description": description,
            "backup": str(backup_path) if backup_path else "",
            "deployed_at": datetime.now().isoformat(),
            "test": test,
        }
        self._append_manifest(record)
        self._log("deploy_plugin", record)
        return {"ok": True, "message": f"Plugin deployed: {filename}", "record": record}

    def rollback_plugin(self, name: str) -> dict:
        filename = self._safe_plugin_filename(name)
        manifest = self._read_manifest()
        records = [r for r in manifest if Path(r.get("file", "")).name == filename and r.get("backup")]
        if not records:
            return {"ok": False, "message": "No rollback backup found for plugin"}
        record = records[-1]
        backup = Path(record["backup"])
        target = ROOT / record["file"]
        if not backup.exists():
            return {"ok": False, "message": f"Backup missing: {backup}"}
        shutil.copy2(backup, target)
        self._log("rollback_plugin", {"name": name, "backup": str(backup), "target": str(target)})
        return {"ok": True, "message": f"Rolled back {filename}", "backup": str(backup)}

    async def run_plugin_pipeline(self, description: str, name: str = "") -> dict:
        """Generate a plugin with the local coder model, sandbox it, deploy it, and log every stage."""
        started = time.perf_counter()
        generated = await self.generate_plugin(description)
        if not generated.get("ok"):
            return {"ok": False, "stage": "generate", "result": generated}

        plugin_name = name or self._infer_plugin_name(description)
        deployed = self.deploy_plugin(generated["code"], plugin_name, description)
        elapsed = (time.perf_counter() - started) * 1000
        self.benchmark.record("evolution_plugin_pipeline", elapsed, deployed.get("ok", False), extra={"name": plugin_name})
        return {"ok": deployed.get("ok", False), "stage": "deploy", "duration_ms": round(elapsed, 1), "result": deployed}

    async def apply_candidate_module(self, target_path: str, new_code: str,
                                     description: str = "") -> dict:
        """Sandbox-test a full replacement module and deploy through SelfUpdater."""
        target = Path(target_path).resolve()
        if not self._inside(ROOT, target):
            return {"ok": False, "message": "Target must be inside the JARVIS project"}
        rel = str(target.relative_to(ROOT)).replace("\\", "/")
        if rel in PROTECTED_BOOT_FILES:
            return {"ok": False, "message": f"Protected boot file cannot be auto-updated: {rel}"}

        session = self.sandbox.create_session("module")
        self.sandbox.write_file(session, "candidate.py", new_code)
        compile_result = self.sandbox.run_py_compile(session, "candidate.py")
        if not compile_result.ok:
            return {"ok": False, "message": "Candidate failed syntax check", "compile": compile_result.to_dict()}
        import_result = self.sandbox.import_check(session, "candidate.py")
        if not import_result.ok:
            return {"ok": False, "message": "Candidate failed import check", "import": import_result.to_dict()}

        started = time.perf_counter()
        deployed = await self.updater.apply_patch(str(target), new_code, description=description)
        elapsed = (time.perf_counter() - started) * 1000
        self.benchmark.record("evolution_module_deploy", elapsed, deployed.get("ok", False), extra={"target": rel})
        self._log("apply_candidate_module", {"target": rel, "deployed": deployed})
        return deployed

    def _recommend_from_analysis(self, modules: list[dict]) -> list[str]:
        recommendations: list[str] = []
        large = [m for m in modules if m["lines"] > 300 and not m["protected"]][:5]
        if large:
            recommendations.append("Review large non-protected modules for extraction: " + ", ".join(m["path"] for m in large))
        shell = [m for m in modules if m["shell_true"] > 0][:5]
        if shell:
            recommendations.append("Audit shell=True usage for command injection risk: " + ", ".join(m["path"] for m in shell))
        broad = [m for m in modules if m["broad_excepts"] > 8][:5]
        if broad:
            recommendations.append("Tighten broad exception handling in: " + ", ".join(m["path"] for m in broad))
        if not recommendations:
            recommendations.append("No urgent structural issues detected by static analysis.")
        return recommendations

    def _safe_plugin_filename(self, name: str) -> str:
        stem = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower()).strip("_") or "generated"
        if not stem.endswith("_plugin"):
            stem += "_plugin"
        return f"{stem[:80]}.py"

    def _infer_plugin_name(self, description: str) -> str:
        words = re.findall(r"[a-zA-Z0-9]+", description.lower())[:4]
        return "_".join(words) or "generated_plugin"

    def _read_manifest(self) -> list[dict]:
        if not MANIFEST.exists():
            return []
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _append_manifest(self, record: dict) -> None:
        data = self._read_manifest()
        data.append(record)
        MANIFEST.write_text(json.dumps(data[-200:], indent=2, ensure_ascii=False), encoding="utf-8")

    def _log(self, action: str, detail: dict) -> None:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(), "action": action, "detail": detail}, ensure_ascii=False, default=str) + "\n")

    @staticmethod
    def _inside(base: Path, target: Path) -> bool:
        try:
            target.relative_to(base.resolve())
            return True
        except ValueError:
            return False


UpgradeEngine = EvolutionEngine

__all__ = ["EvolutionEngine", "UpgradeEngine"]
