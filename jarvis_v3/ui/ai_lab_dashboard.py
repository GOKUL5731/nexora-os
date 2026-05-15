"""
JARVIS Phase 4 — AI LAB Dashboard (PySide6)
Visualizes experiments, plugin generation, agent builder,
self-improvement pipeline, and system benchmarks.
"""
import asyncio, json, logging, threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QTabWidget, QSplitter, QListWidget, QListWidgetItem,
    QComboBox, QSpinBox,
)

logger = logging.getLogger("jarvis.ui.ai_lab")

DARK=  "#0a0e1a"; CARD= "#131d35"; PANEL= "#0f1628"
ACCENT="#00d4ff"; A2=   "#7b2fff"; TEXT=  "#e8f4ff"
MUTED= "#4a6a8a"; BORDER="#1a2a4a"
SUCCESS="#00ff9d"; WARN="#ffaa00"; ERR="#ff4466"

def _card(b=BORDER):
    return f"background:{CARD};border:1px solid {b};border-radius:10px;padding:8px;"
def _btn(c=ACCENT):
    return (f"QPushButton{{background:rgba(0,0,0,0);color:{c};"
            f"border:1px solid {BORDER};border-radius:6px;padding:5px 12px;font-size:11px;}}"
            f"QPushButton:hover{{background:rgba(0,212,255,20);border-color:{c};}}")


class LabWorker(QThread):
    done = Signal(dict)
    error = Signal(str)
    def __init__(self, coro_fn, *args, **kwargs):
        super().__init__()
        self._coro_fn = coro_fn
        self._args    = args
        self._kwargs  = kwargs
    def run(self):
        try:
            loop   = asyncio.new_event_loop()
            result = loop.run_until_complete(self._coro_fn(*self._args, **self._kwargs))
            loop.close()
            self.done.emit(result if isinstance(result, dict) else {"result": str(result)})
        except Exception as e:
            self.error.emit(str(e))


class AILabDashboard(QWidget):
    def __init__(self, lab=None, improver=None, agent_manager=None, parent=None):
        super().__init__(parent)
        self.lab      = lab
        self.improver = improver
        self.agents   = agent_manager
        self._workers = []
        self._build_ui()
        QTimer(self).timeout.connect(self._refresh), QTimer(self).start(5000)
        self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("🧪  AI LABORATORY")
        t.setStyleSheet(f"color:{A2};font-size:15px;font-weight:bold;letter-spacing:2px;")
        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"color:{MUTED};font-size:11px;")
        hdr.addWidget(t); hdr.addStretch(); hdr.addWidget(self._status)
        root.addLayout(hdr)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            f"QTabWidget::pane{{border:1px solid {BORDER};background:{PANEL};border-radius:8px;}}"
            f"QTabBar::tab{{background:{CARD};color:{MUTED};padding:6px 14px;border-radius:6px 6px 0 0;margin-right:2px;font-size:11px;}}"
            f"QTabBar::tab:selected{{background:{PANEL};color:{A2};border-bottom:2px solid {A2};}}"
        )
        tabs.addTab(self._build_experiments_tab(), "🔬 Experiments")
        tabs.addTab(self._build_plugins_tab(),     "🔌 Plugin Gen")
        tabs.addTab(self._build_agents_tab(),      "🤖 Agent Builder")
        tabs.addTab(self._build_improve_tab(),     "⚡ Self-Improve")
        tabs.addTab(self._build_benchmark_tab(),   "📊 Benchmarks")
        root.addWidget(tabs, 1)

    # ── Experiments Tab ────────────────────────────────────────────────────────
    def _build_experiments_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        self._exp_name  = QLineEdit(); self._exp_name.setPlaceholderText("Experiment name...")
        self._exp_name.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;")
        self._exp_type  = QComboBox()
        self._exp_type.addItems(["code_generation","plugin_generation","agent_generation",
                                 "prompt_optimization","model_benchmark"])
        self._exp_type.setStyleSheet(f"background:{CARD};color:{TEXT};border:1px solid {BORDER};padding:4px;")
        self._exp_desc  = QLineEdit(); self._exp_desc.setPlaceholderText("Description / goal...")
        self._exp_desc.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;")
        btn_run = QPushButton("▶ Run Experiment"); btn_run.setStyleSheet(_btn(A2))
        btn_run.clicked.connect(self._run_experiment)

        for w_ in [self._exp_name, self._exp_type, self._exp_desc, btn_run]:
            ctrl.addWidget(w_)
        lay.addLayout(ctrl)

        self._exp_table = QTableWidget(0, 5)
        self._exp_table.setHorizontalHeaderLabels(["ID","Name","Type","Status","Score"])
        self._exp_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._exp_table.setStyleSheet(f"background:{CARD};border:1px solid {BORDER};color:{TEXT};font-size:11px;")
        lay.addWidget(self._exp_table, 1)

        self._exp_log = QTextEdit(); self._exp_log.setReadOnly(True)
        self._exp_log.setMaximumHeight(130)
        self._exp_log.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};font-family:'Courier New';font-size:10px;")
        lay.addWidget(self._exp_log)
        return w

    # ── Plugin Gen Tab ─────────────────────────────────────────────────────────
    def _build_plugins_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        self._plug_name = QLineEdit(); self._plug_name.setPlaceholderText("Plugin name (snake_case)...")
        self._plug_name.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;")
        self._plug_desc = QLineEdit(); self._plug_desc.setPlaceholderText("What should this plugin do?")
        self._plug_desc.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;")
        btn_gen  = QPushButton("⚡ Generate Plugin"); btn_gen.setStyleSheet(_btn(SUCCESS))
        btn_gen.clicked.connect(self._generate_plugin)
        btn_dep  = QPushButton("🚀 Deploy Selected"); btn_dep.setStyleSheet(_btn(A2))
        btn_dep.clicked.connect(self._deploy_plugin)
        for w_ in [self._plug_name, self._plug_desc, btn_gen, btn_dep]:
            ctrl.addWidget(w_)
        lay.addLayout(ctrl)

        self._plug_table = QTableWidget(0, 4)
        self._plug_table.setHorizontalHeaderLabels(["Name","Status","Created","Deployed"])
        self._plug_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._plug_table.setStyleSheet(f"background:{CARD};border:1px solid {BORDER};color:{TEXT};font-size:11px;")
        lay.addWidget(self._plug_table, 1)

        self._plug_code = QTextEdit(); self._plug_code.setReadOnly(True)
        self._plug_code.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};font-family:'Courier New';font-size:10px;")
        lay.addWidget(self._plug_code, 1)
        return w

    # ── Agent Builder Tab ──────────────────────────────────────────────────────
    def _build_agents_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        self._ag_name = QLineEdit(); self._ag_name.setPlaceholderText("Agent name...")
        self._ag_name.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;")
        self._ag_desc = QLineEdit(); self._ag_desc.setPlaceholderText("What should this agent do?")
        self._ag_desc.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;")
        btn_build = QPushButton("🤖 Build Agent"); btn_build.setStyleSheet(_btn(A2))
        btn_build.clicked.connect(self._build_agent)
        btn_task  = QPushButton("▶ Run Selected"); btn_task.setStyleSheet(_btn(SUCCESS))
        btn_task.clicked.connect(self._run_agent_task)
        for w_ in [self._ag_name, self._ag_desc, btn_build, btn_task]:
            ctrl.addWidget(w_)
        lay.addLayout(ctrl)

        self._ag_table = QTableWidget(0, 4)
        self._ag_table.setHorizontalHeaderLabels(["Name","Type","Status","Runs"])
        self._ag_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._ag_table.setStyleSheet(f"background:{CARD};border:1px solid {BORDER};color:{TEXT};font-size:11px;")
        lay.addWidget(self._ag_table, 1)

        self._ag_log = QTextEdit(); self._ag_log.setReadOnly(True)
        self._ag_log.setMaximumHeight(130)
        self._ag_log.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};font-family:'Courier New';font-size:10px;")
        lay.addWidget(self._ag_log)
        return w

    # ── Self-Improve Tab ───────────────────────────────────────────────────────
    def _build_improve_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        self._imp_file  = QLineEdit(); self._imp_file.setPlaceholderText("File path to improve (relative to jarvis_v3/)...")
        self._imp_file.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;")
        self._imp_issue = QLineEdit(); self._imp_issue.setPlaceholderText("Issue to fix (or 'general optimization')...")
        self._imp_issue.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;")
        btn_analyze  = QPushButton("🔍 Analyze"); btn_analyze.setStyleSheet(_btn(WARN))
        btn_analyze.clicked.connect(self._analyze_file)
        btn_improve  = QPushButton("⚡ Improve"); btn_improve.setStyleSheet(_btn(A2))
        btn_improve.clicked.connect(self._run_improvement)
        for w_ in [self._imp_file, self._imp_issue, btn_analyze, btn_improve]:
            ctrl.addWidget(w_)
        lay.addLayout(ctrl)

        self._imp_table = QTableWidget(0, 5)
        self._imp_table.setHorizontalHeaderLabels(["ID","File","Issue","Status","Deployed"])
        self._imp_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._imp_table.setStyleSheet(f"background:{CARD};border:1px solid {BORDER};color:{TEXT};font-size:11px;")
        lay.addWidget(self._imp_table, 1)

        btn_row = QHBoxLayout()
        btn_rollback = QPushButton("↩ Rollback Selected"); btn_rollback.setStyleSheet(_btn(ERR))
        btn_rollback.clicked.connect(self._rollback)
        btn_scan = QPushButton("🔎 Scan Codebase"); btn_scan.setStyleSheet(_btn())
        btn_scan.clicked.connect(self._scan_codebase)
        btn_row.addWidget(btn_rollback); btn_row.addWidget(btn_scan); btn_row.addStretch()
        lay.addLayout(btn_row)

        self._imp_log = QTextEdit(); self._imp_log.setReadOnly(True)
        self._imp_log.setMaximumHeight(130)
        self._imp_log.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};font-family:'Courier New';font-size:10px;")
        lay.addWidget(self._imp_log)
        return w

    # ── Benchmark Tab ──────────────────────────────────────────────────────────
    def _build_benchmark_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)
        btn_bench = QPushButton("▶ Run System Benchmark"); btn_bench.setStyleSheet(_btn(SUCCESS))
        btn_bench.clicked.connect(self._run_benchmark)
        lay.addWidget(btn_bench)

        self._bench_table = QTableWidget(0, 3)
        self._bench_table.setHorizontalHeaderLabels(["Name","Timestamp","Key Metrics"])
        self._bench_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._bench_table.setStyleSheet(f"background:{CARD};border:1px solid {BORDER};color:{TEXT};font-size:11px;")
        lay.addWidget(self._bench_table, 1)
        return w

    # ── Actions ────────────────────────────────────────────────────────────────
    def _run_experiment(self):
        if not self.lab: return
        name = self._exp_name.text().strip() or f"exp_{int(__import__('time').time())}"
        exp_type = self._exp_type.currentText()
        desc = self._exp_desc.text().strip()
        exp_id = self.lab.create_experiment(name, exp_type, {"description": desc})
        self._exp_log.append(f"Created experiment #{exp_id}: {name} ({exp_type})")
        w = LabWorker(self.lab.run_experiment, exp_id)
        w.done.connect(lambda r: self._exp_log.append(f"✓ Done: {json.dumps(r)[:200]}"))
        w.error.connect(lambda e: self._exp_log.append(f"✗ Error: {e}"))
        w.start(); self._workers.append(w)
        self._set_status(f"Running experiment: {name}")

    def _generate_plugin(self):
        if not self.lab: return
        name = self._plug_name.text().strip()
        desc = self._plug_desc.text().strip()
        if not desc: return
        w = LabWorker(self.lab.generate_plugin, desc, name or None)
        w.done.connect(lambda r: (
            self._plug_code.setPlainText(f"Plugin '{r.get('name')}' generated.\nFile: {r.get('file')}\nSandbox: {'✓' if r.get('sandbox_passed') else '✗'}"),
            self._refresh()
        ))
        w.error.connect(lambda e: self._plug_code.append(f"Error: {e}"))
        w.start(); self._workers.append(w)

    def _deploy_plugin(self):
        if not self.lab: return
        row = self._plug_table.currentRow()
        if row < 0: return
        name = self._plug_table.item(row, 0).text()
        w = LabWorker(self.lab.deploy_plugin, name)
        w.done.connect(lambda r: self._plug_code.append(f"Deployed: {r}"))
        w.start(); self._workers.append(w)

    def _build_agent(self):
        if not self.lab: return
        name = self._ag_name.text().strip()
        desc = self._ag_desc.text().strip()
        if not desc: return
        exp_id = self.lab.create_experiment(
            name or desc[:20], "agent_generation", {"description": desc}
        )
        w = LabWorker(self.lab.run_experiment, exp_id)
        w.done.connect(lambda r: self._ag_log.append(f"✓ Agent built: {r}"))
        w.error.connect(lambda e: self._ag_log.append(f"✗ {e}"))
        w.start(); self._workers.append(w)

    def _run_agent_task(self):
        if not self.agents: return
        row = self._ag_table.currentRow()
        if row < 0: return
        name = self._ag_table.item(row, 0).text()
        task = self._ag_desc.text().strip() or "summarize your capabilities"
        w = LabWorker(self.agents.run_agent, name, task)
        w.done.connect(lambda r: self._ag_log.append(f"[{name}] {r}"))
        w.start(); self._workers.append(w)

    def _analyze_file(self):
        if not self.improver: return
        path = self._imp_file.text().strip()
        if not path: return
        from pathlib import Path as P
        full = P(__file__).resolve().parent.parent / path
        w = LabWorker(self.improver.analyze_file, str(full))
        w.done.connect(lambda r: self._imp_log.append(f"Analysis: {json.dumps(r)[:400]}"))
        w.start(); self._workers.append(w)

    def _run_improvement(self):
        if not self.improver: return
        path  = self._imp_file.text().strip()
        issue = self._imp_issue.text().strip() or "general optimization"
        if not path: return
        from pathlib import Path as P
        full = P(__file__).resolve().parent.parent / path
        w = LabWorker(self.improver.run_improvement_pipeline, str(full), issue, False)
        w.done.connect(lambda r: (self._imp_log.append(f"Result: {json.dumps(r)[:400]}"), self._refresh()))
        w.start(); self._workers.append(w)

    def _rollback(self):
        if not self.improver: return
        row = self._imp_table.currentRow()
        if row < 0: return
        rec_id = int(self._imp_table.item(row, 0).text())
        result = self.improver.rollback(rec_id)
        self._imp_log.append(f"Rollback: {result}")
        self._refresh()

    def _scan_codebase(self):
        if not self.improver: return
        w = LabWorker(self.improver.scan_codebase)
        w.done.connect(lambda r: self._imp_log.append(f"Scan results: {json.dumps(r)[:500]}"))
        w.start(); self._workers.append(w)

    def _run_benchmark(self):
        if not self.lab: return
        w = LabWorker(self.lab.run_system_benchmark)
        w.done.connect(lambda r: (self._refresh(), self._set_status("Benchmark complete")))
        w.start(); self._workers.append(w)

    # ── Refresh ────────────────────────────────────────────────────────────────
    def _refresh(self):
        if self.lab:
            exps = self.lab.list_experiments()
            self._exp_table.setRowCount(len(exps))
            for i, e in enumerate(exps):
                self._exp_table.setItem(i, 0, QTableWidgetItem(str(e["id"])))
                self._exp_table.setItem(i, 1, QTableWidgetItem(e["name"][:30]))
                self._exp_table.setItem(i, 2, QTableWidgetItem(e["type"]))
                st = QTableWidgetItem(e["status"])
                st.setForeground(QColor(SUCCESS if e["status"]=="completed" else
                                        ERR if e["status"]=="failed" else WARN))
                self._exp_table.setItem(i, 3, st)
                self._exp_table.setItem(i, 4, QTableWidgetItem(f"{e['score']:.0f}"))

            plugs = self.lab.list_plugins()
            self._plug_table.setRowCount(len(plugs))
            for i, p in enumerate(plugs):
                self._plug_table.setItem(i, 0, QTableWidgetItem(p["name"]))
                st = QTableWidgetItem(p["status"])
                st.setForeground(QColor(SUCCESS if p["status"]=="deployed" else TEXT))
                self._plug_table.setItem(i, 1, st)
                self._plug_table.setItem(i, 2, QTableWidgetItem(p["created"][:10]))
                self._plug_table.setItem(i, 3, QTableWidgetItem("✓" if p["deployed"] else "○"))

            benches = self.lab.get_benchmarks()
            self._bench_table.setRowCount(len(benches))
            for i, b in enumerate(benches):
                self._bench_table.setItem(i, 0, QTableWidgetItem(b["name"]))
                self._bench_table.setItem(i, 1, QTableWidgetItem(b["timestamp"][:16]))
                m = b["metrics"]
                summary = f"LLM:{m.get('llm_latency_ms','?')}ms | GPU:{m.get('gpu','N/A')} | CUDA:{m.get('cuda','?')}"
                self._bench_table.setItem(i, 2, QTableWidgetItem(summary))

        if self.agents:
            ags = self.agents.list_agents()
            self._ag_table.setRowCount(len(ags))
            for i, a in enumerate(ags):
                self._ag_table.setItem(i, 0, QTableWidgetItem(a["name"]))
                self._ag_table.setItem(i, 1, QTableWidgetItem(a["type"]))
                st = QTableWidgetItem(a["status"])
                st.setForeground(QColor(SUCCESS if a["status"]=="idle" else
                                        WARN if a["status"]=="running" else ERR))
                self._ag_table.setItem(i, 2, st)
                self._ag_table.setItem(i, 3, QTableWidgetItem(str(a["runs"])))

        if self.improver:
            hist = self.improver.get_history()
            self._imp_table.setRowCount(len(hist))
            for i, h in enumerate(hist):
                self._imp_table.setItem(i, 0, QTableWidgetItem(str(h["id"])))
                self._imp_table.setItem(i, 1, QTableWidgetItem(Path(h["file"]).name[:25]))
                self._imp_table.setItem(i, 2, QTableWidgetItem(h["issue"][:30]))
                st = QTableWidgetItem(h["status"])
                st.setForeground(QColor(SUCCESS if h["status"]=="deployed" else
                                        ERR if "failed" in h["status"] else TEXT))
                self._imp_table.setItem(i, 3, st)
                self._imp_table.setItem(i, 4, QTableWidgetItem("✓" if h["deployed"] else "○"))

    def _set_status(self, msg: str):
        self._status.setText(msg)

    def cleanup(self):
        for w in self._workers:
            if w.isRunning():
                w.terminate()
