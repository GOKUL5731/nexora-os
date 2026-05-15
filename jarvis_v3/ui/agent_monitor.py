"""
JARVIS Phase 3 — Agent Monitor (PySide6)
Live dashboard for all running agents: status, logs, messaging, task dispatch.
"""
import asyncio, json, logging, threading
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QSplitter,
)

logger = logging.getLogger("jarvis.ui.agent_monitor")

DARK="#0a0e1a"; CARD="#131d35"; PANEL="#0f1628"
ACCENT="#00d4ff"; A2="#7b2fff"; TEXT="#e8f4ff"
MUTED="#4a6a8a"; BORDER="#1a2a4a"
SUCCESS="#00ff9d"; WARN="#ffaa00"; ERR="#ff4466"

def _card(b=BORDER):
    return f"background:{CARD};border:1px solid {b};border-radius:10px;padding:8px;"
def _btn(c=ACCENT):
    return (f"QPushButton{{background:rgba(0,0,0,0);color:{c};"
            f"border:1px solid {BORDER};border-radius:6px;padding:5px 12px;font-size:11px;}}"
            f"QPushButton:hover{{background:rgba(0,212,255,20);border-color:{c};}}")


class AgentTaskWorker(QThread):
    done  = Signal(dict)
    error = Signal(str)
    def __init__(self, agent_mgr, agent_name, task, context=None):
        super().__init__()
        self._mgr    = agent_mgr
        self._agent  = agent_name
        self._task   = task
        self._ctx    = context or {}
    def run(self):
        try:
            loop   = asyncio.new_event_loop()
            result = loop.run_until_complete(self._mgr.run_agent(self._agent, self._task, self._ctx))
            loop.close()
            self.done.emit(result if isinstance(result, dict) else {"result": str(result)})
        except Exception as e:
            self.error.emit(str(e))


class TeamTaskWorker(QThread):
    done  = Signal(dict)
    error = Signal(str)
    def __init__(self, agent_mgr, task):
        super().__init__()
        self._mgr  = agent_mgr
        self._task = task
    def run(self):
        try:
            loop   = asyncio.new_event_loop()
            result = loop.run_until_complete(self._mgr.run_team(self._task))
            loop.close()
            self.done.emit(result if isinstance(result, dict) else {"result": str(result)})
        except Exception as e:
            self.error.emit(str(e))


class AgentMonitor(QWidget):
    """
    Live agent monitoring panel:
    - Status table for all registered agents
    - Task dispatch (single agent or full team)
    - Per-agent log viewer
    - Inter-agent messaging
    """

    def __init__(self, agent_manager=None, agent_builder=None, parent=None):
        super().__init__(parent)
        self.mgr     = agent_manager
        self.builder = agent_builder
        self._workers = []
        self._build_ui()
        QTimer(self).timeout.connect(self._refresh)
        QTimer(self).start(2000)
        self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("🤖  AGENT MONITOR")
        t.setStyleSheet(f"color:{A2};font-size:15px;font-weight:bold;letter-spacing:2px;")
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color:{MUTED};font-size:11px;")
        hdr.addWidget(t); hdr.addStretch(); hdr.addWidget(self._status_lbl)
        root.addLayout(hdr)

        # ── Task Dispatch ──────────────────────────────────────────────────────
        dispatch = QFrame(); dispatch.setStyleSheet(_card(ACCENT))
        dl = QHBoxLayout(dispatch)
        dl.setContentsMargins(8, 6, 8, 6)

        self._task_input = QLineEdit()
        self._task_input.setPlaceholderText("Enter task for agent(s)...")
        self._task_input.setStyleSheet(
            f"background:{DARK};border:none;color:{TEXT};padding:6px;border-radius:5px;font-size:12px;"
        )

        self._agent_selector = QComboBox()
        self._agent_selector.setStyleSheet(
            f"background:{CARD};color:{TEXT};border:1px solid {BORDER};padding:4px;min-width:120px;"
        )

        btn_single = QPushButton("▶ Run Agent"); btn_single.setStyleSheet(_btn(ACCENT))
        btn_team   = QPushButton("🤝 Run Team");  btn_team.setStyleSheet(_btn(A2))
        btn_single.clicked.connect(self._dispatch_single)
        btn_team.clicked.connect(self._dispatch_team)

        for w in [self._task_input, self._agent_selector, btn_single, btn_team]:
            dl.addWidget(w)
        root.addWidget(dispatch)

        # ── Main Split: Agent Table + Logs ─────────────────────────────────────
        split = QHBoxLayout(); split.setSpacing(8)

        # Agent table
        left = QFrame(); left.setStyleSheet(_card())
        ll = QVBoxLayout(left)

        lt = QLabel("Registered Agents")
        lt.setStyleSheet(f"color:{ACCENT};font-size:12px;font-weight:bold;")
        ll.addWidget(lt)

        self._agent_table = QTableWidget(0, 5)
        self._agent_table.setHorizontalHeaderLabels(["Name","Type","Status","Runs","Last Used"])
        self._agent_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._agent_table.setStyleSheet(
            f"background:{DARK};border:none;color:{TEXT};font-size:11px;gridline-color:{BORDER};"
        )
        self._agent_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._agent_table.clicked.connect(self._on_agent_selected)
        ll.addWidget(self._agent_table, 1)

        # Build agent button
        build_row = QHBoxLayout()
        self._new_agent_name = QLineEdit()
        self._new_agent_name.setPlaceholderText("New agent description...")
        self._new_agent_name.setStyleSheet(
            f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;font-size:11px;"
        )
        btn_build = QPushButton("⚡ Build New Agent"); btn_build.setStyleSheet(_btn(A2))
        btn_build.clicked.connect(self._build_new_agent)
        build_row.addWidget(self._new_agent_name, 1)
        build_row.addWidget(btn_build)
        ll.addLayout(build_row)
        split.addWidget(left, 1)

        # Right: Log viewer + messaging
        right = QVBoxLayout(); right.setSpacing(6)

        # Log viewer
        log_frame = QFrame(); log_frame.setStyleSheet(_card(A2))
        lf = QVBoxLayout(log_frame)
        log_hdr = QHBoxLayout()
        self._log_title = QLabel("Logs — select an agent")
        self._log_title.setStyleSheet(f"color:{A2};font-size:12px;font-weight:bold;")
        btn_clear_log = QPushButton("Clear"); btn_clear_log.setStyleSheet(_btn(MUTED))
        btn_clear_log.clicked.connect(lambda: self._log_box.clear())
        log_hdr.addWidget(self._log_title); log_hdr.addStretch(); log_hdr.addWidget(btn_clear_log)
        lf.addLayout(log_hdr)

        self._log_box = QTextEdit(); self._log_box.setReadOnly(True)
        self._log_box.setStyleSheet(
            f"background:{DARK};border:none;color:{TEXT};font-family:'Courier New';font-size:10px;"
        )
        lf.addWidget(self._log_box, 1)
        right.addWidget(log_frame, 1)

        # Result viewer
        res_frame = QFrame(); res_frame.setStyleSheet(_card(SUCCESS))
        rf = QVBoxLayout(res_frame)
        rt = QLabel("Task Results")
        rt.setStyleSheet(f"color:{SUCCESS};font-size:12px;font-weight:bold;")
        rf.addWidget(rt)
        self._result_box = QTextEdit(); self._result_box.setReadOnly(True)
        self._result_box.setMaximumHeight(140)
        self._result_box.setStyleSheet(
            f"background:{DARK};border:none;color:{TEXT};font-family:'Courier New';font-size:10px;"
        )
        rf.addWidget(self._result_box)
        right.addWidget(res_frame)

        # Message sender
        msg_frame = QFrame(); msg_frame.setStyleSheet(_card(WARN))
        mf = QHBoxLayout(msg_frame)
        mt = QLabel("Message:"); mt.setStyleSheet(f"color:{WARN};font-size:11px;")
        self._msg_to = QComboBox()
        self._msg_to.setStyleSheet(f"background:{CARD};color:{TEXT};border:1px solid {BORDER};padding:3px;")
        self._msg_input = QLineEdit(); self._msg_input.setPlaceholderText("Message content...")
        self._msg_input.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;font-size:11px;")
        btn_send = QPushButton("Send"); btn_send.setStyleSheet(_btn(WARN))
        btn_send.clicked.connect(self._send_message)
        for w in [mt, self._msg_to, self._msg_input, btn_send]:
            mf.addWidget(w)
        right.addWidget(msg_frame)

        split.addLayout(right, 1)
        root.addLayout(split, 1)

    # ── Actions ────────────────────────────────────────────────────────────────
    def _dispatch_single(self):
        if not self.mgr: return
        agent = self._agent_selector.currentText()
        task  = self._task_input.text().strip()
        if not task or not agent: return
        self._status_lbl.setText(f"Running {agent}...")
        w = AgentTaskWorker(self.mgr, agent, task)
        w.done.connect(self._on_task_done)
        w.error.connect(lambda e: self._result_box.append(f"✗ Error: {e}"))
        w.start(); self._workers.append(w)

    def _dispatch_team(self):
        if not self.mgr: return
        task = self._task_input.text().strip()
        if not task: return
        self._status_lbl.setText("Running agent team...")
        w = TeamTaskWorker(self.mgr, task)
        w.done.connect(self._on_task_done)
        w.error.connect(lambda e: self._result_box.append(f"✗ Team error: {e}"))
        w.start(); self._workers.append(w)

    def _on_task_done(self, result: dict):
        self._status_lbl.setText("Task complete")
        self._result_box.append(f"[{datetime.now().strftime('%H:%M:%S')}]")
        self._result_box.append(json.dumps(result, indent=2, default=str)[:800])
        self._result_box.append("─" * 40)
        self._refresh()

    def _on_agent_selected(self, index):
        if not self.mgr: return
        row  = index.row()
        name = self._agent_table.item(row, 0).text() if self._agent_table.item(row, 0) else ""
        if not name: return
        self._log_title.setText(f"Logs — {name}")
        logs = self.mgr.get_agent_logs(name, limit=20)
        self._log_box.clear()
        for entry in reversed(logs):
            ts = entry["timestamp"][:19]
            ev = entry["event"]
            d  = json.dumps(entry["data"])[:100]
            self._log_box.append(f"[{ts}] {ev}: {d}")

    def _build_new_agent(self):
        if not self.builder: return
        desc = self._new_agent_name.text().strip()
        if not desc: return
        def _do():
            loop   = asyncio.new_event_loop()
            result = loop.run_until_complete(self.builder.build_agent(desc))
            loop.close()
            self._result_box.append(f"✓ Agent built: {result.get('name')} | registered={result.get('registered')}")
            self._refresh()
        threading.Thread(target=_do, daemon=True).start()
        self._status_lbl.setText("Building agent...")

    def _send_message(self):
        if not self.mgr: return
        to      = self._msg_to.currentText()
        content = self._msg_input.text().strip()
        if not to or not content: return
        self.mgr.send_message("ui_user", to, content)
        self._msg_input.clear()
        self._result_box.append(f"✉ Sent to {to}: {content[:60]}")

    # ── Refresh ────────────────────────────────────────────────────────────────
    def _refresh(self):
        if not self.mgr: return
        agents = self.mgr.list_agents()

        # Update table
        self._agent_table.setRowCount(len(agents))
        names = []
        for i, a in enumerate(agents):
            self._agent_table.setItem(i, 0, QTableWidgetItem(a["name"]))
            self._agent_table.setItem(i, 1, QTableWidgetItem(a["type"]))
            st = QTableWidgetItem(a["status"])
            st.setForeground(QColor(
                SUCCESS if a["status"]=="idle" else
                WARN    if a["status"]=="running" else ERR
            ))
            self._agent_table.setItem(i, 2, st)
            self._agent_table.setItem(i, 3, QTableWidgetItem(str(a["runs"])))
            lu = (a["last_used"] or "")[:16]
            self._agent_table.setItem(i, 4, QTableWidgetItem(lu))
            names.append(a["name"])

        # Update selectors
        current_sel = self._agent_selector.currentText()
        self._agent_selector.clear()
        self._agent_selector.addItems(names)
        if current_sel in names:
            self._agent_selector.setCurrentText(current_sel)

        current_to = self._msg_to.currentText()
        self._msg_to.clear()
        self._msg_to.addItems(names)
        if current_to in names:
            self._msg_to.setCurrentText(current_to)

    def cleanup(self):
        for w in self._workers:
            if w.isRunning(): w.terminate()
