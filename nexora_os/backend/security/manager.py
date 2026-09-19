from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from ..core.event_bus import EventBus


class SecurityManager:
    """Handles API authentication, rate limiting, and audit logging."""

    def __init__(self, db_path: Path, bus: EventBus) -> None:
        self.db_path = db_path
        self.bus = bus
        
        # In-memory rate limiting state: {ip: [(timestamp), ...]}
        self._rate_limits: dict[str, list[float]] = {}
        self.MAX_REQUESTS_PER_MINUTE = 200
        self._emergency_stop = False
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    ip_address TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    user_agent TEXT
                )
                """
            )
            # Example API keys table for future usage
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    key TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
                """
            )

    def is_rate_limited(self, ip_address: str) -> bool:
        """Check if an IP address has exceeded the rate limit."""
        now = time.time()
        window_start = now - 60.0
        
        if ip_address not in self._rate_limits:
            self._rate_limits[ip_address] = []
            
        # Clean up old timestamps
        self._rate_limits[ip_address] = [
            ts for ts in self._rate_limits[ip_address] if ts > window_start
        ]
        
        if len(self._rate_limits[ip_address]) >= self.MAX_REQUESTS_PER_MINUTE:
            return True
            
        self._rate_limits[ip_address].append(now)
        return False

    def log_audit(self, ip_address: str, endpoint: str, method: str, status_code: int, user_agent: str = "") -> None:
        """Log an API request to the audit database."""
        now = time.time()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO audit_logs (timestamp, ip_address, endpoint, method, status_code, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (now, ip_address, endpoint, method, status_code, user_agent)
                )
        except Exception as e:
            # Audit logging failure shouldn't crash the API, but we notify the bus
            self.bus.publish("security.audit_error", {"error": str(e)}, "security_manager")

    def get_recent_audits(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent audit logs."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT timestamp, ip_address, endpoint, method, status_code FROM audit_logs ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return [
                {
                    "timestamp": row[0],
                    "ip": row[1],
                    "endpoint": row[2],
                    "method": row[3],
                    "status": row[4],
                }
                for row in cursor.fetchall()
            ]

    def verify_api_key(self, api_key: str) -> bool:
        """Verify if a provided API key is valid."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM api_keys WHERE key = ? AND is_active = 1",
                (api_key,)
            )
            return cursor.fetchone() is not None

    def create_api_key(self, owner: str, key: str) -> None:
        """Create a new API key."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO api_keys (key, owner, created_at, is_active) VALUES (?, ?, ?, 1)",
                (key, owner, time.time())
            )

    def health(self) -> dict[str, Any]:
        """Check module health."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("SELECT 1 FROM audit_logs LIMIT 1")
            return {"status": "online", "message": "Security database is accessible"}
        except Exception as e:
            return {"status": "degraded", "error": str(e)}

    def emergency_stop(self, reason: str = "user_requested") -> dict[str, Any]:
        self._emergency_stop = True
        self.bus.publish("security.emergency_stop", {"active": True, "reason": reason}, "security_manager")
        return {"ok": True, "active": True, "reason": reason}

    def clear_emergency_stop(self) -> dict[str, Any]:
        self._emergency_stop = False
        self.bus.publish("security.emergency_stop", {"active": False}, "security_manager")
        return {"ok": True, "active": False}

    def execution_allowed(self, connector: str, action: str) -> tuple[bool, str]:
        if self._emergency_stop:
            return False, "emergency_stop_active"
        if not connector or not action:
            return False, "connector_and_action_required"
        return True, "allowed"

    @property
    def emergency_stop_active(self) -> bool:
        return self._emergency_stop
