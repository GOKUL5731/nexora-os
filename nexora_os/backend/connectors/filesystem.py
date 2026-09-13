from __future__ import annotations

from pathlib import Path
from typing import Any

STATUS_AVAILABLE = "AVAILABLE"
STATUS_FAILED = "FAILED"

MAX_READ_BYTES = 100_000  # 100 KB read limit


class FilesystemConnector:
    """Connector for safe filesystem operations: read, write, list, check, create, delete."""

    def __init__(self, root_path: str | None = None) -> None:
        self.root = (Path(root_path) if root_path else Path.home()).expanduser().resolve()

    def connect(self) -> dict[str, Any]:
        return {"ok": True, "status": self.health(), "root": str(self.root)}

    def disconnect(self) -> dict[str, Any]:
        return {"ok": True}

    def health(self) -> str:
        return STATUS_AVAILABLE if self.root.exists() else STATUS_FAILED

    def get_capabilities(self) -> list[str]:
        return ["read_file", "write_file", "list_dir", "file_exists", "create_dir", "delete_file"]

    def _resolve_path(self, raw_path: Any) -> tuple[Path | None, dict[str, Any] | None]:
        value = str(raw_path or "").strip().strip('"').strip("'")
        if not value:
            return None, {"ok": False, "error": "Path is required", "permission_checked": True}
        requested = Path(value).expanduser()
        path = requested if requested.is_absolute() else self.root / requested
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError:
            return None, {
                "ok": False,
                "error": f"Path outside allowed project root: {resolved}",
                "root": str(self.root),
                "permission_checked": True,
                "permission": "filesystem",
            }
        return resolved, None

    def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action == "read_file":
            path, error = self._resolve_path(params.get("path", ""))
            if error:
                return error
            assert path is not None
            if not path.exists():
                return {"ok": False, "error": f"File not found: {path}", "permission_checked": True, "permission": "filesystem_read"}
            if not path.is_file():
                return {"ok": False, "error": f"Not a file: {path}", "permission_checked": True, "permission": "filesystem_read"}
            try:
                content = path.read_bytes()[:MAX_READ_BYTES].decode("utf-8", errors="replace")
                return {
                    "ok": True,
                    "content": content,
                    "size_bytes": path.stat().st_size,
                    "path": str(path),
                    "permission_checked": True,
                    "permission": "filesystem_read",
                    "verification": {"exists": path.exists(), "is_file": path.is_file()},
                }
            except Exception as exc:
                return {"ok": False, "error": str(exc), "permission_checked": True, "permission": "filesystem_read"}

        elif action == "write_file":
            path, error = self._resolve_path(params.get("path", ""))
            if error:
                return error
            assert path is not None
            content = str(params.get("content", ""))
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                read_back = path.read_text(encoding="utf-8")
                verified = path.exists() and path.is_file() and read_back == content
                return {
                    "ok": verified,
                    "path": str(path),
                    "bytes_written": len(content.encode("utf-8")),
                    "permission_checked": True,
                    "permission": "filesystem_write",
                    "verification": {
                        "exists": path.exists(),
                        "is_file": path.is_file(),
                        "content_matches": read_back == content,
                    },
                    "content": read_back[:MAX_READ_BYTES],
                    "message": f"Created file: {path}" if verified else f"Write verification failed: {path}",
                }
            except Exception as exc:
                return {"ok": False, "error": str(exc), "permission_checked": True, "permission": "filesystem_write"}

        elif action == "list_dir":
            path, error = self._resolve_path(params.get("path", str(self.root)))
            if error:
                return error
            assert path is not None
            if not path.exists():
                return {"ok": False, "error": f"Directory not found: {path}", "permission_checked": True, "permission": "filesystem_read"}
            if not path.is_dir():
                return {"ok": False, "error": f"Not a directory: {path}", "permission_checked": True, "permission": "filesystem_read"}
            try:
                entries = [
                    {"name": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size if p.is_file() else 0}
                    for p in sorted(path.iterdir())
                ]
                return {"ok": True, "path": str(path), "entries": entries, "permission_checked": True, "permission": "filesystem_read"}
            except Exception as exc:
                return {"ok": False, "error": str(exc), "permission_checked": True, "permission": "filesystem_read"}

        elif action == "file_exists":
            path, error = self._resolve_path(params.get("path", ""))
            if error:
                return error
            assert path is not None
            return {"ok": True, "exists": path.exists(), "path": str(path), "permission_checked": True, "permission": "filesystem_read"}

        elif action == "create_dir":
            path, error = self._resolve_path(params.get("path", ""))
            if error:
                return error
            assert path is not None
            try:
                path.mkdir(parents=True, exist_ok=True)
                return {
                    "ok": path.exists() and path.is_dir(),
                    "path": str(path),
                    "permission_checked": True,
                    "permission": "filesystem_write",
                    "verification": {"exists": path.exists(), "is_dir": path.is_dir()},
                }
            except Exception as exc:
                return {"ok": False, "error": str(exc), "permission_checked": True, "permission": "filesystem_write"}

        elif action == "delete_file":
            if not params.get("confirm", False):
                return {"ok": False, "error": "Confirmation required: pass confirm=True to delete", "permission_checked": True}
            path, error = self._resolve_path(params.get("path", ""))
            if error:
                return error
            assert path is not None
            if not path.exists():
                return {"ok": False, "error": f"File not found: {path}", "permission_checked": True, "permission": "filesystem_write"}
            try:
                path.unlink() if path.is_file() else path.rmdir()
                return {
                    "ok": not path.exists(),
                    "path": str(path),
                    "message": f"Deleted: {path}",
                    "permission_checked": True,
                    "permission": "filesystem_write",
                    "verification": {"exists": path.exists()},
                }
            except Exception as exc:
                return {"ok": False, "error": str(exc), "permission_checked": True, "permission": "filesystem_write"}

        return {"ok": False, "error": f"Unknown action: {action}"}
