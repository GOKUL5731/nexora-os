"""
JARVIS Phase 3 — Workflow Builder (PySide6)
Visual workflow builder: create, edit, run, and schedule automation pipelines.
"""
import asyncio, json, logging, threading, time
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QSpinBox, QSplitter,
)

logger = logging.getLogger("jarvis.ui.workflow_builder")

DARK="#0a0e1a"; CARD="#131d35"; PANEL="#0f1628"
ACCENT="#00d4ff"; A2="#7b2fff"; TEXT="#e8f4ff"
MUTED="#4a6a8a"; BORDER="#1a2a4a"
SUCCESS="#00ff9d"; WARN="#ffaa00"; ERR="#ff4466"

ACTIONS = ["log","notify","run_command","open_app","llm_query",
           "file_operation","http_request","wait","set_variable","condition_branch"]

def _card(b=BORDER):
    return f"background:{CARD};border:1px solid {b};border-radius:10px;padding:8px;"
def _btn(c=ACCENT):
    return (f"QPushButton{{background:rgba(0,0,0,0);color:{c};"
            f"border:1px solid {BORDER};border-radius:6px;padding:5px 12px;font-size:11px;}}"
            f"QPushButton:hover{{background:rgba(0,212,255,20);border-color:{c};}}")


class WorkflowRunWorker(QThread):
    done  = Signal(dict)
    error = Signal(str)
    def __init__(self, engine, name):
        super().__init__()
        self._engine = engine
        self._name   = name
    def run(self):
        try:
            loop   = asyncio.new_event_loop()
            result = loop.run_until_complete(self._engine.run(self._name))
            loop.close()
            self.done.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class WorkflowBuilder(QWidget):
    """
    n8n-style visual workflow builder:
    - Create workflows via step list editor
    - AI-generate workflows from description
    - Run / schedule / manage workflows
    - View run history
    """

    def __init__(self, workflow_engine=None, parent=None):
        super().__init__(parent)
        self.engine   = workflow_engine
        self._workers = []
        self._current_steps = []  # list of step dicts
        self._build_ui()
        QTimer(self).timeout.connect(self._refresh_list)
        QTimer(self).start(3000)
        self._refresh_list()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        t = QLabel("⚡  WORKFLOW BUILDER")
        t.setStyleSheet(f"color:{ACCENT};font-size:15px;font-weight:bold;letter-spacing:2px;")
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color:{MUTED};font-size:11px;")
        hdr.addWidget(t); hdr.addStretch(); hdr.addWidget(self._status_lbl)
        root.addLayout(hdr)

        # ── AI Generation Bar ──────────────────────────────────────────────────
        gen_frame = QFrame(); gen_frame.setStyleSheet(_card(A2))
        gf = QHBoxLayout(gen_frame)
        gf.setContentsMargins(8, 6, 8, 6)
        self._ai_desc = QLineEdit()
        self._ai_desc.setPlaceholderText("✨ Describe a workflow in plain English... (AI will generate it)")
        self._ai_desc.setStyleSheet(f"background:{DARK};border:none;color:{TEXT};padding:6px;border-radius:5px;font-size:12px;")
        btn_ai = QPushButton("✨ AI Generate"); btn_ai.setStyleSheet(_btn(A2))
        btn_ai.clicked.connect(self._ai_generate)
        gf.addWidget(self._ai_desc, 1)
        gf.addWidget(btn_ai)
        root.addWidget(gen_frame)

        # ── Main 2-column layout ───────────────────────────────────────────────
        cols = QHBoxLayout(); cols.setSpacing(8)

        # Left: Workflow list + controls
        left = QFrame(); left.setStyleSheet(_card())
        ll = QVBoxLayout(left)

        wf_hdr = QHBoxLayout()
        wf_t = QLabel("Saved Workflows")
        wf_t.setStyleSheet(f"color:{ACCENT};font-size:12px;font-weight:bold;")
        btn_refresh = QPushButton("⟳"); btn_refresh.setStyleSheet(_btn(MUTED))
        btn_refresh.setFixedWidth(32); btn_refresh.clicked.connect(self._refresh_list)
        wf_hdr.addWidget(wf_t); wf_hdr.addStretch(); wf_hdr.addWidget(btn_refresh)
        ll.addLayout(wf_hdr)

        self._wf_table = QTableWidget(0, 4)
        self._wf_table.setHorizontalHeaderLabels(["Name","Status","Runs","Last Run"])
        self._wf_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._wf_table.setStyleSheet(f"background:{DARK};border:none;color:{TEXT};font-size:11px;gridline-color:{BORDER};")
        self._wf_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._wf_table.clicked.connect(self._on_wf_selected)
        ll.addWidget(self._wf_table, 1)

        btn_row = QHBoxLayout()
        btn_run  = QPushButton("▶ Run");   btn_run.setStyleSheet(_btn(SUCCESS))
        btn_del  = QPushButton("🗑 Delete"); btn_del.setStyleSheet(_btn(ERR))
        btn_sched = QPushButton("⏰ Schedule"); btn_sched.setStyleSheet(_btn(WARN))
        btn_run.clicked.connect(self._run_selected)
        btn_del.clicked.connect(self._delete_selected)
        btn_sched.clicked.connect(self._schedule_selected)
        for b in [btn_run, btn_del, btn_sched]: btn_row.addWidget(b)
        ll.addLayout(btn_row)

        # Schedule interval
        sched_row = QHBoxLayout()
        sl = QLabel("Interval (sec):")
        sl.setStyleSheet(f"color:{MUTED};font-size:10px;")
        self._sched_interval = QSpinBox()
        self._sched_interval.setRange(60, 86400); self._sched_interval.setValue(3600)
        self._sched_interval.setStyleSheet(f"background:{DARK};color:{TEXT};border:1px solid {BORDER};padding:2px;")
        sched_row.addWidget(sl); sched_row.addWidget(self._sched_interval); sched_row.addStretch()
        ll.addLayout(sched_row)

        cols.addWidget(left, 1)

        # Right: Step editor + run output
        right = QVBoxLayout(); right.setSpacing(6)

        # Workflow name
        name_row = QHBoxLayout()
        nl = QLabel("Name:")
        nl.setStyleSheet(f"color:{MUTED};font-size:11px;")
        self._wf_name_input = QLineEdit()
        self._wf_name_input.setPlaceholderText("workflow_name")
        self._wf_name_input.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;font-size:11px;")
        name_row.addWidget(nl); name_row.addWidget(self._wf_name_input, 1)
        right.addLayout(name_row)

        # Step editor
        step_frame = QFrame(); step_frame.setStyleSheet(_card(ACCENT))
        sf = QVBoxLayout(step_frame)
        st = QLabel("Steps (visual editor)")
        st.setStyleSheet(f"color:{ACCENT};font-size:12px;font-weight:bold;")
        sf.addWidget(st)

        # Add step controls
        add_row = QHBoxLayout()
        self._action_combo = QComboBox()
        self._action_combo.addItems(ACTIONS)
        self._action_combo.setStyleSheet(f"background:{CARD};color:{TEXT};border:1px solid {BORDER};padding:3px;")
        self._params_input = QLineEdit()
        self._params_input.setPlaceholderText('Params JSON (e.g. {"message": "Hello"})')
        self._params_input.setStyleSheet(f"background:{DARK};border:1px solid {BORDER};color:{TEXT};padding:4px;border-radius:5px;font-size:11px;")
        btn_add  = QPushButton("+ Add Step"); btn_add.setStyleSheet(_btn(ACCENT))
        btn_add.clicked.connect(self._add_step)
        btn_clr  = QPushButton("Clear All"); btn_clr.setStyleSheet(_btn(MUTED))
        btn_clr.clicked.connect(self._clear_steps)
        add_row.addWidget(self._action_combo); add_row.addWidget(self._params_input, 1)
        add_row.addWidget(btn_add); add_row.addWidget(btn_clr)
        sf.addLayout(add_row)

        self._step_list = QListWidget()
        self._step_list.setStyleSheet(
            f"QListWidget{{background:{DARK};border:1px solid {BORDER};border-radius:5px;color:{TEXT};font-size:11px;}}"
            f"QListWidget::item:hover{{background:rgba(0,212,255,15);}}"
        )
        self._step_list.setMaximumHeight(200)
        sf.addWidget(self._step_list)

        # Remove step button
        btn_rm = QPushButton("✕ Remove Selected Step"); btn_rm.setStyleSheet(_btn(ERR))
        btn_rm.clicked.connect(self._remove_step)
        sf.addWidget(btn_rm)

        btn_save = QPushButton("💾 Save Workflow"); btn_save.setStyleSheet(_btn(SUCCESS))
        btn_save.clicked.connect(self._save_workflow)
        sf.addWidget(btn_save)
        right.addWidget(step_frame)

        # JSON preview
        json_frame = QFrame(); json_frame.setStyleSheet(_card())
        jf = QVBoxLayout(json_frame)
        jt = QLabel("Workflow JSON")
        jt.setStyleSheet(f"color:{MUTED};font-size:10px;font-weight:bold;")
        jf.addWidget(jt)
        self._json_box = QTextEdit(); self._json_box.setReadOnly(True)
        self._json_box.setMaximumHeight(100)
        self._json_box.setStyleSheet(f"background:{DARK};border:none;color:{TEXT};font-family:'Courier New';font-size:9px;")
        jf.addWidget(self._json_box)
        right.addWidget(json_frame)

        # Run output
        out_frame = QFrame(); out_frame.setStyleSheet(_card(SUCCESS))
        of = QVBoxLayout(out_frame)
        ot = QLabel("Run Output")
        ot.setStyleSheet(f"color:{SUCCESS};font-size:12px;font-weight:bold;")
        of.addWidget(ot)
        self._run_output = QTextEdit(); self._run_output.setReadOnly(True)
        self._run_output.setMaximumHeight(130)
        self._run_output.setStyleSheet(f"background:{DARK};border:none;color:{TEXT};font-family:'Courier New';font-size:10px;")
        of.addWidget(self._run_output)
        right.addWidget(out_frame)

        cols.addLayout(right, 1)
        root.addLayout(cols, 1)

    # ── Actions ────────────────────────────────────────────────────────────────
    def _add_step(self):
        action = self._action_combo.currentText()
        params_str = self._params_input.text().strip() or "{}"
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError:
            params = {"value": params_str}

        step = {"action": action, "params": params}
        self._current_steps.append(step)

        num = len(self._current_steps)
        item = QListWidgetItem(f"{num}. {action}  →  {json.dumps(params)[:60]}")
        item.setForeground(QColor(ACCENT))
        self._step_list.addItem(item)
        self._params_input.clear()
        self._update_json_preview()

    def _remove_step(self):
        row = self._step_list.currentRow()
        if row >= 0:
            self._step_list.takeItem(row)
            if row < len(self._current_steps):
                self._current_steps.pop(row)
        # Re-number
        for i in range(self._step_list.count()):
            item = self._step_list.item(i)
            text = item.text()
            item.setText(f"{i+1}. {'.'.join(text.split('.')[1:]).strip()}")
        self._update_json_preview()

    def _clear_steps(self):
        self._current_steps.clear()
        self._step_list.clear()
        self._update_json_preview()

    def _update_json_preview(self):
        name = self._wf_name_input.text().strip() or "my_workflow"
        spec = {"name": name, "steps": self._current_steps}
        self._json_box.setPlainText(json.dumps(spec, indent=2))

    def _save_workflow(self):
        if not self.engine: return
        name = self._wf_name_input.text().strip()
        if not name:
            self._run_output.append("⚠ Enter a workflow name first")
            return
        spec = {"name": name, "description": f"Created via builder at {datetime.now():%H:%M}", "steps": self._current_steps}
        wf_id = self.engine.save_workflow(spec)
        self._run_output.append(f"✓ Saved workflow '{name}' (id={wf_id})")
        self._refresh_list()

    def _run_selected(self):
        if not self.engine: return
        row = self._wf_table.currentRow()
        if row < 0: return
        name = self._wf_table.item(row, 0).text()
        self._status_lbl.setText(f"Running: {name}...")
        w = WorkflowRunWorker(self.engine, name)
        w.done.connect(self._on_run_done)
        w.error.connect(lambda e: self._run_output.append(f"✗ Error: {e}"))
        w.start(); self._workers.append(w)

    def _on_run_done(self, result: dict):
        self._status_lbl.setText("Run complete")
        status = result.get("status", "?")
        steps  = result.get("steps", 0)
        ts     = datetime.now().strftime("%H:%M:%S")
        color_tag = SUCCESS if status == "success" else ERR
        self._run_output.append(f"[{ts}] {result.get('workflow','')} → {status} ({steps} steps)")
        for r in result.get("results", [])[:10]:
            self._run_output.append(f"  Step {r['step']}: {r['action']} → {json.dumps(r['result'])[:80]}")
        self._run_output.append("─" * 40)
        self._refresh_list()

    def _delete_selected(self):
        if not self.engine: return
        row = self._wf_table.currentRow()
        if row < 0: return
        name = self._wf_table.item(row, 0).text()
        self.engine.delete_workflow(name)
        self._run_output.append(f"Deleted: {name}")
        self._refresh_list()

    def _schedule_selected(self):
        if not self.engine: return
        row = self._wf_table.currentRow()
        if row < 0: return
        name     = self._wf_table.item(row, 0).text()
        interval = self._sched_interval.value()
        self.engine.schedule(name, interval)
        self._run_output.append(f"⏰ Scheduled '{name}' every {interval}s")
        self._status_lbl.setText(f"Scheduled: {name}")

    def _on_wf_selected(self, index):
        if not self.engine: return
        row  = index.row()
        name = self._wf_table.item(row, 0).text() if self._wf_table.item(row, 0) else ""
        if not name: return
        spec = self.engine.get_workflow(name)
        if spec:
            self._wf_name_input.setText(name)
            self._current_steps = spec.get("steps", [])
            self._step_list.clear()
            for i, s in enumerate(self._current_steps, 1):
                item = QListWidgetItem(f"{i}. {s['action']}  →  {json.dumps(s.get('params',{}))[:60]}")
                item.setForeground(QColor(ACCENT))
                self._step_list.addItem(item)
            self._update_json_preview()

    def _ai_generate(self):
        if not self.engine: return
        desc = self._ai_desc.text().strip()
        if not desc: return
        self._status_lbl.setText("AI generating workflow...")
        def _do():
            loop   = asyncio.new_event_loop()
            result = loop.run_until_complete(
                self.engine.generate_workflow_from_description(desc)
            )
            loop.close()
            if "spec" in result:
                spec = result["spec"]
                self.engine.save_workflow(spec)
                name = spec.get("name", "ai_workflow")
                self._wf_name_input.setText(name)
                self._current_steps = spec.get("steps", [])
                self._step_list.clear()
                for i, s in enumerate(self._current_steps, 1):
                    item = QListWidgetItem(f"{i}. {s['action']}  →  {json.dumps(s.get('params',{}))[:60]}")
                    item.setForeground(QColor(A2))
                    self._step_list.addItem(item)
                self._update_json_preview()
                self._run_output.append(f"✨ AI generated workflow: {name} ({len(self._current_steps)} steps)")
                self._refresh_list()
                self._status_lbl.setText("AI workflow ready")
            else:
                self._run_output.append(f"✗ AI generation failed: {result.get('error','?')}")
                self._status_lbl.setText("Generation failed")
        threading.Thread(target=_do, daemon=True).start()

    def _refresh_list(self):
        if not self.engine: return
        workflows = self.engine.list_workflows()
        self._wf_table.setRowCount(len(workflows))
        for i, wf in enumerate(workflows):
            self._wf_table.setItem(i, 0, QTableWidgetItem(wf["name"]))
            st = QTableWidgetItem(wf["last_status"])
            st.setForeground(QColor(
                SUCCESS if wf["last_status"]=="success" else
                ERR     if wf["last_status"]=="failed"  else TEXT
            ))
            self._wf_table.setItem(i, 1, st)
            self._wf_table.setItem(i, 2, QTableWidgetItem(str(wf["run_count"])))
            lr = (wf["last_run"] or "Never")[:16]
            self._wf_table.setItem(i, 3, QTableWidgetItem(lr))

    def cleanup(self):
        for w in self._workers:
            if w.isRunning(): w.terminate()
