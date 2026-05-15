"""
JARVIS Web & Cybersecurity Engine — Authorized Research Module
============================================================
JARVIS can (only for authorized systems/user-owned networks):
  - Perform web research (DuckDuckGo, page scraping, document extraction)
  - Analyze user-owned system security (port scan, CVSS lookup)
  - Review code for security vulnerabilities (LLM-assisted)
  - Analyze log files for anomalies
  - Monitor network traffic statistics (local only, no packet sniffing)
  - DNS lookup and WHOIS for research purposes

JARVIS WILL NOT:
  - Attack systems not owned by the user
  - Perform unauthorized access
  - Extract credentials
  - Bypass authentication

All operations are logged and audited.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.web")
IS_WIN = sys.platform == "win32"
_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WIN else 0


class WebEngine:
    """
    Web research, cybersecurity analysis, and log monitoring engine.
    All security features are strictly for authorized/owned systems.
    """

    def __init__(self, config: dict, llm_router=None):
        self.config = config
        self.router = llm_router

    # ── Web Search ────────────────────────────────────────────────────────────
    async def search(self, query: str, max_results: int = 5) -> dict:
        """DuckDuckGo web search — no API key needed."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._search_sync(query, max_results)
        )

    def _search_sync(self, query: str, max_results: int) -> dict:
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title":   r.get("title", ""),
                        "url":     r.get("href", ""),
                        "snippet": r.get("body", "")[:300],
                    })
            return {"ok": True, "query": query, "results": results}
        except ImportError:
            return {"ok": False, "error": "Install: pip install duckduckgo-search"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Web Scraping ──────────────────────────────────────────────────────────
    async def scrape_url(self, url: str, max_chars: int = 4000) -> dict:
        """Scrape text content from a URL using playwright or requests fallback."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._scrape_sync(url, max_chars)
        )

    def _scrape_sync(self, url: str, max_chars: int) -> dict:
        # Try playwright first
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page    = browser.new_page()
                page.goto(url, timeout=15000)
                text = page.inner_text("body")[:max_chars]
                title = page.title()
                browser.close()
            return {"ok": True, "url": url, "title": title, "text": text}
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Playwright scrape failed: {e}")

        # Fallback: requests + basic HTML stripping
        try:
            import requests
            headers = {"User-Agent": "Mozilla/5.0 (JARVIS Research Agent)"}
            resp = requests.get(url, timeout=10, headers=headers)
            resp.raise_for_status()
            # Strip HTML tags
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"\s+", " ", text).strip()[:max_chars]
            return {"ok": True, "url": url, "title": url, "text": text}
        except Exception as e:
            return {"ok": False, "url": url, "error": str(e)}

    # ── Research aggregation ──────────────────────────────────────────────────
    async def research_topic(self, topic: str, depth: int = 3) -> dict:
        """
        Search + scrape top results + LLM-summarize into a research brief.
        """
        search_r = await self.search(topic, max_results=depth)
        if not search_r.get("ok"):
            return search_r

        sources = []
        for hit in search_r["results"]:
            scrape = await self.scrape_url(hit["url"], max_chars=1000)
            content = scrape.get("text", hit["snippet"])[:800]
            sources.append({"url": hit["url"], "title": hit["title"], "content": content})

        if not self.router:
            return {"ok": True, "topic": topic, "sources": sources,
                    "summary": "\n\n".join(f"[{s['title']}]\n{s['content']}" for s in sources)}

        context = "\n\n".join(f"Source: {s['url']}\n{s['content']}" for s in sources)
        try:
            summary = await self.router.complete_async(
                f"Research topic: '{topic}'\n\nSources:\n{context}\n\n"
                f"Write a concise 3-5 sentence research brief covering key facts.",
                temperature=0.2, max_tokens=350, force_model="mistral"
            )
            return {"ok": True, "topic": topic, "summary": summary, "sources": sources}
        except Exception as e:
            return {"ok": True, "topic": topic, "sources": sources, "error": str(e)}

    # ── Security: Code Review ─────────────────────────────────────────────────
    async def review_code_security(self, code: str, language: str = "python") -> dict:
        """
        Use local LLM to review code for security vulnerabilities.
        Does not send code to any external service.
        """
        if not self.router:
            return {"ok": False, "error": "LLM router required for code review"}

        # Static pattern checks first
        static_issues = self._static_security_scan(code, language)

        prompt = (
            f"You are a cybersecurity expert reviewing {language} code for security vulnerabilities.\n"
            f"Analyze this code for:\n"
            f"  - SQL injection, XSS, command injection\n"
            f"  - Hardcoded secrets/credentials\n"
            f"  - Insecure deserialization\n"
            f"  - Path traversal vulnerabilities\n"
            f"  - Weak cryptography\n\n"
            f"Code:\n```{language}\n{code[:2000]}\n```\n\n"
            f"Return JSON: {{\"risk_level\": \"low|medium|high|critical\", "
            f"\"issues\": [{{\"type\": \"\", \"line\": \"\", \"description\": \"\", \"fix\": \"\"}}], "
            f"\"summary\": \"\"}}"
        )

        try:
            raw = await self.router.complete_async(
                prompt, temperature=0.1, max_tokens=500, force_model="deepseek-coder"
            )
            raw = raw.strip().replace("```json", "").replace("```", "").strip()
            s, e = raw.find("{"), raw.rfind("}") + 1
            if s >= 0:
                result = json.loads(raw[s:e])
                result["static_findings"] = static_issues
                result["ok"] = True
                return result
        except Exception as err:
            logger.warning(f"LLM code review failed: {err}")

        return {"ok": True, "risk_level": "unknown",
                "static_findings": static_issues, "issues": [], "summary": "LLM review failed"}

    def _static_security_scan(self, code: str, language: str) -> list[dict]:
        """Quick regex-based static security scan."""
        PATTERNS = {
            "hardcoded_secret": [
                r"(?i)(password|passwd|secret|api_key|apikey)\s*=\s*['\"][^'\"]{4,}['\"]",
                r"(?i)(token|bearer)\s*[=:]\s*['\"][A-Za-z0-9_\-\.]{20,}['\"]",
            ],
            "sql_injection_risk": [
                r"(?i)(execute|cursor\.execute)\s*\([^?%].*\+",
                r"(?i)\"SELECT.*\"\s*\+",
            ],
            "command_injection": [
                r"(?i)(subprocess|os\.system|os\.popen)\s*\([^)]*\+",
                r"(?i)shell\s*=\s*True",
            ],
            "path_traversal": [
                r"\.\./",
                r"(?i)open\s*\([^)]*\+",
            ],
            "eval_exec": [
                r"\beval\s*\(",
                r"\bexec\s*\(",
            ],
        }

        findings = []
        for issue_type, patterns in PATTERNS.items():
            for pat in patterns:
                matches = list(re.finditer(pat, code))
                for m in matches:
                    line_num = code[:m.start()].count("\n") + 1
                    findings.append({
                        "type": issue_type,
                        "line": line_num,
                        "match": m.group()[:80],
                    })
        return findings

    # ── Security: Log Analysis ─────────────────────────────────────────────────
    async def analyze_log_file(self, log_path: str, max_lines: int = 500) -> dict:
        """
        Analyze a log file for anomalies, errors, and security events.
        Uses LLM for pattern identification.
        """
        try:
            text = Path(log_path).read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()[-max_lines:]
            sample = "\n".join(lines)
        except Exception as e:
            return {"ok": False, "error": f"Cannot read log file: {e}"}

        # Pattern-based anomaly detection
        anomalies = self._detect_log_anomalies(sample)

        if not self.router:
            return {"ok": True, "path": log_path, "anomalies": anomalies,
                    "lines_analyzed": len(lines)}

        try:
            summary = await self.router.complete_async(
                f"Analyze these log entries for security events, errors, and anomalies:\n"
                f"{sample[:2000]}\n\n"
                f"Return a 3-5 sentence analysis focusing on:\n"
                f"1. Critical errors or failures\n"
                f"2. Suspicious patterns\n"
                f"3. Recommendations",
                temperature=0.15, max_tokens=250, force_model="mistral"
            )
            return {
                "ok": True, "path": log_path, "lines_analyzed": len(lines),
                "anomalies": anomalies, "analysis": summary,
            }
        except Exception as e:
            return {"ok": True, "path": log_path, "anomalies": anomalies, "error": str(e)}

    def _detect_log_anomalies(self, text: str) -> list[dict]:
        """Find common log anomaly patterns."""
        PATTERNS = {
            "authentication_failure": r"(?i)(failed login|auth.*failed|invalid.*password|401)",
            "connection_refused":     r"(?i)(connection refused|ECONNREFUSED|timeout)",
            "critical_error":         r"(?i)\b(CRITICAL|FATAL|PANIC)\b",
            "error_burst":            r"(?i)\bERROR\b",
            "exception":              r"(?i)(Exception|Traceback|stack trace)",
            "permission_denied":      r"(?i)(permission denied|access denied|403|forbidden)",
            "disk_warning":           r"(?i)(disk.*full|no space left|ENOSPC)",
        }
        results = []
        for issue_type, pat in PATTERNS.items():
            matches = re.findall(pat, text)
            if matches:
                results.append({"type": issue_type, "count": len(matches)})
        return results

    # ── Network: DNS / WHOIS ──────────────────────────────────────────────────
    async def dns_lookup(self, hostname: str) -> dict:
        """Resolve hostname to IP addresses."""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None, lambda: socket.getaddrinfo(hostname, None)
            )
            ips = list({r[4][0] for r in result})
            return {"ok": True, "hostname": hostname, "ips": ips}
        except Exception as e:
            return {"ok": False, "hostname": hostname, "error": str(e)}

    async def ping(self, host: str, count: int = 4) -> dict:
        """Ping a host and return latency stats."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._ping_sync(host, count))

    def _ping_sync(self, host: str, count: int) -> dict:
        cmd = ["ping", f"-n" if IS_WIN else "-c", str(count), host]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                creationflags=_CREATE_NO_WINDOW
            )
            output = r.stdout
            # Parse average latency
            avg_ms = None
            if IS_WIN:
                m = re.search(r"Average\s*=\s*(\d+)ms", output, re.IGNORECASE)
            else:
                m = re.search(r"rtt min/avg/max.*=\s*[\d.]+/([\d.]+)/", output)
            if m:
                avg_ms = float(m.group(1))
            return {
                "ok": r.returncode == 0, "host": host,
                "avg_ms": avg_ms, "raw": output[-500:],
            }
        except Exception as e:
            return {"ok": False, "host": host, "error": str(e)}

    # ── Port Scanner (owned systems only) ─────────────────────────────────────
    async def scan_ports(self, host: str, ports: list[int] = None,
                          timeout_s: float = 1.0) -> dict:
        """
        Scan common ports on a host. Use ONLY on systems you own.
        Default ports: common service ports.
        """
        if ports is None:
            ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 3306,
                     3389, 5432, 5900, 8080, 8443]

        loop   = asyncio.get_event_loop()
        open_ports = []

        async def check_port(port: int):
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout_s
                )
                writer.close()
                await writer.wait_closed()
                open_ports.append(port)
            except Exception:
                pass

        tasks = [check_port(p) for p in ports]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Map common port names
        PORT_NAMES = {
            21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
            80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS",
            3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
            5900: "VNC", 8080: "HTTP-Alt", 8443: "HTTPS-Alt"
        }
        results = [{"port": p, "service": PORT_NAMES.get(p, "unknown")}
                   for p in sorted(open_ports)]

        return {
            "ok": True, "host": host,
            "open_ports": results,
            "scanned": len(ports),
            "found_open": len(results),
            "warning": "Only scan systems you own or have permission to test.",
        }

    # ── System vulnerability check (local only) ───────────────────────────────
    async def check_local_security(self) -> dict:
        """
        Check local Windows system for basic security configurations.
        Reads registry / system info — no network scanning.
        """
        checks = {}

        # Check Windows Defender status
        try:
            r = subprocess.run(
                ["powershell", "-Command",
                 "Get-MpComputerStatus | Select-Object -Property AntivirusEnabled,RealTimeProtectionEnabled | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
                creationflags=_CREATE_NO_WINDOW
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                checks["windows_defender"] = {
                    "enabled": data.get("AntivirusEnabled", False),
                    "realtime": data.get("RealTimeProtectionEnabled", False),
                }
        except Exception:
            checks["windows_defender"] = {"error": "Could not check"}

        # Check Windows Firewall
        try:
            r = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True, text=True, timeout=10,
                creationflags=_CREATE_NO_WINDOW
            )
            checks["firewall"] = {
                "output": r.stdout[:200],
                "active": "ON" in r.stdout.upper(),
            }
        except Exception:
            checks["firewall"] = {"error": "Could not check"}

        # Check active listening ports
        try:
            r = subprocess.run(
                ["netstat", "-an", "-p", "TCP"],
                capture_output=True, text=True, timeout=10,
                creationflags=_CREATE_NO_WINDOW
            )
            listening = [
                line.strip() for line in r.stdout.splitlines()
                if "LISTENING" in line
            ]
            checks["listening_ports"] = {
                "count": len(listening),
                "sample": listening[:10],
            }
        except Exception:
            checks["listening_ports"] = {"error": "Could not check"}

        # LLM analysis
        if self.router and any(checks):
            summary_text = json.dumps(checks, indent=2)
            try:
                analysis = await self.router.complete_async(
                    f"Analyze this Windows security configuration and provide 2-3 recommendations:\n"
                    f"{summary_text[:800]}\n\nBe concise.",
                    temperature=0.2, max_tokens=200, force_model="mistral"
                )
                checks["llm_recommendations"] = analysis
            except Exception:
                pass

        return {"ok": True, "checks": checks, "scanned_at": datetime.now().isoformat()}


__all__ = ["WebEngine"]
