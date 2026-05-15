"""
JARVIS Example Plugin — Timer & Reminder tools.
Demonstrates the plugin contract: a register() function returning tool specs.
Drop any .py file with register() into the plugins/ folder and it auto-loads.
"""

import asyncio
import threading
import time
from datetime import datetime


def register(config: dict) -> dict:
    """Called by PluginManager. Must return a registration dict."""

    _reminders: list[dict] = []

    def set_timer(args: dict) -> dict:
        seconds = int(args.get("seconds", 60))
        label   = args.get("label", "Timer")
        def _ring():
            time.sleep(seconds)
            print(f"\n🔔 JARVIS Timer: {label} — {seconds}s elapsed\n")
        threading.Thread(target=_ring, daemon=True).start()
        return {"ok": True, "label": label, "seconds": seconds,
                "fires_at": datetime.now().strftime("%H:%M:%S")}

    def add_reminder(args: dict) -> dict:
        rem = {"text": args.get("text","Reminder"), "at": args.get("at",""), "done": False}
        _reminders.append(rem)
        return {"ok": True, "reminder": rem, "total": len(_reminders)}

    def list_reminders(args: dict) -> dict:
        return {"reminders": _reminders, "count": len(_reminders)}

    def clear_reminders(args: dict) -> dict:
        _reminders.clear()
        return {"ok": True}

    def get_datetime(args: dict) -> dict:
        now = datetime.now()
        return {
            "date": now.strftime("%A, %d %B %Y"),
            "time": now.strftime("%I:%M:%S %p"),
            "iso":  now.isoformat(),
            "unix": int(now.timestamp()),
        }

    return {
        "name":        "Timers & Reminders",
        "version":     "1.0.0",
        "description": "Set timers, add reminders, get current date/time.",
        "author":      "jarvis-core",
        "tools": {
            "set_timer":       set_timer,
            "add_reminder":    add_reminder,
            "list_reminders":  list_reminders,
            "clear_reminders": clear_reminders,
            "get_datetime":    get_datetime,
        },
    }
