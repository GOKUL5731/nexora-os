"""
JARVIS Phase 2 — Memory Panel (PySide6)
=========================================
Displays:
  - Recent learned behaviors
  - Text memories with semantic search
  - Vision event history
  - Task memory
  - Memory statistics
  - Behavior patterns timeline
"""

import json
import logging
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QTabWidget, QListWidget,
    QListWidgetItem, QSplitter,
)

logger = logging.getLogger("jarvis.ui.memory_panel")

DARK   = "#0a0e1a"; PANEL  = "#0f1628"; CARD   = "#131d35"
ACCENT = "#00d4ff"; ACCENT2 = "#7b2fff"
TEXT   = "#e8f4ff"; MUTED  = "#4a6a8a"; BORDER = "#1a2a4a"
SUCCESS = "#00ff9d"; WARN   = "#ffaa00"; ERR   = "#ff4466"


def _card(border: str = BORDER) -> str:
    return f"background:{CARD};border:1px solid {border};border-radius:10px;padding:8px;"

def _btn_style(color: str = ACCENT) -> str:
    return (
        f"QPushButton{{background:rgba(0,0,0,0);color:{color};"
        f"border:1px solid {BORDER};border-radius:6px;padding:5px 12px;font-size:11px;}}"
        f"QPushButton:hover{{background:rgba(0,212,255,20);border-color:{color};}}"
    )


# ─── Memory Panel ────────────────────────────────────────────────────────────────
class MemoryPanel(QWidget):
    """
    Multimodal Memory Tab:
      - Semantic search across all memories
      - Text memory browser
      - Vision event log
      - Behavior patterns
      - Task history
    """

    def __init__(self, memory=None, self_learn=None, rnn=None, parent=None):
        super().__init__(parent)
        self.memory     = memory
        self.self_learn = self_learn
        self.rnn        = rnn
        self._build_ui()
        self._start_timers()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(8, 8, 8, 8)

        # ── Header with stats ─────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("💾  MULTIMODAL MEMORY")
        title.setStyleSheet(f"color:{ACCENT};font-size:15px;font-weight:bold;letter-spacing:2px;")
        self._stats_lbl = QLabel("Memories: --")
        self._stats_lbl.setStyleSheet(f"color:{MUTED};font-size:11px;")
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._stats_lbl)
        root.addLayout(hdr)

        # ── Search bar ────────────────────────────────────────────────────────
        search_frame = QFrame()
        search_frame.setStyleSheet(_card(ACCENT))
        s_lay = QHBoxLayout(search_frame)
        s_lay.setContentsMargins(8, 6, 8, 6)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 Semantic search memories... (e.g., 'python project last week')")
        self._search_input.setStyleSheet(
            f"background:{DARK};border:none;border-radius:6px;"
            f"color:{TEXT};padding:6px;font-size:12px;"
        )
        self._search_btn = QPushButton("Search")
        self._search_btn.setStyleSheet(_btn_style(ACCENT))
        self._search_btn.clicked.connect(self._do_search)
        self._search_input.returnPressed.connect(self._do_search)

        self._store_btn = QPushButton("+ Store Memory")
        self._store_btn.setStyleSheet(_btn_style(SUCCESS))
        self._store_btn.clicked.connect(self._store_memory)

        s_lay.addWidget(self._search_input, 1)
        s_lay.addWidget(self._search_btn)
        s_lay.addWidget(self._store_btn)
        root.addWidget(search_frame)

        # ── Search results ────────────────────────────────────────────────────
        self._search_results = QTextEdit()
        self._search_results.setReadOnly(True)
        self._search_results.setMaximumHeight(130)
        self._search_results.setStyleSheet(
            f"background:{DARK};border:1px solid {BORDER};border-radius:8px;"
            f"color:{TEXT};font-family:'Courier New';font-size:11px;padding:4px;"
        )
        self._search_results.setPlaceholderText("Search results will appear here...")
        root.addWidget(self._search_results)

        # ── Sub-tabs ──────────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setStyleSheet(
            f"QTabWidget::pane{{border:1px solid {BORDER};background:{PANEL};border-radius:8px;}}"
            f"QTabBar::tab{{background:{CARD};color:{MUTED};padding:6px 16px;"
            f"border-radius:6px 6px 0 0;margin-right:2px;font-size:11px;}}"
            f"QTabBar::tab:selected{{background:{PANEL};color:{ACCENT};"
            f"border-bottom:2px solid {ACCENT};}}"
        )

        tabs.addTab(self._build_text_tab(),     "📝 Text")
        tabs.addTab(self._build_vision_tab(),   "👁 Vision")
        tabs.addTab(self._build_behavior_tab(), "🔮 Behavior")
        tabs.addTab(self._build_tasks_tab(),    "✅ Tasks")

        root.addWidget(tabs, 1)

        # ── Bottom stats bar ──────────────────────────────────────────────────
        bot = QHBoxLayout()
        self._embed_lbl = QLabel("Embeddings: --")
        self._embed_lbl.setStyleSheet(f"color:{MUTED};font-size:10px;")
        self._db_lbl = QLabel("DB: --")
        self._db_lbl.setStyleSheet(f"color:{MUTED};font-size:10px;")
        btn_clear = QPushButton("🗑 Clear Old (30d)")
        btn_clear.setStyleSheet(_btn_style(WARN))
        btn_clear.clicked.connect(self._clear_old)
        bot.addWidget(self._embed_lbl)
        bot.addWidget(self._db_lbl)
        bot.addStretch()
        bot.addWidget(btn_clear)
        root.addLayout(bot)

    # ── Text Tab ───────────────────────────────────────────────────────────────
    def _build_text_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        self._text_refresh = QPushButton("⟳ Refresh")
        self._text_refresh.setStyleSheet(_btn_style())
        self._text_refresh.clicked.connect(self._refresh_text)
        ctrl.addStretch()
        ctrl.addWidget(self._text_refresh)
        lay.addLayout(ctrl)

        self._text_table = QTableWidget(0, 4)
        self._text_table.setHorizontalHeaderLabels(["Time", "Category", "Content", "Source"])
        self._text_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._text_table.setStyleSheet(
            f"background:{CARD};border:1px solid {BORDER};color:{TEXT};font-size:11px;"
            f"gridline-color:{BORDER};"
        )
        lay.addWidget(self._text_table, 1)
        return w

    # ── Vision Tab ─────────────────────────────────────────────────────────────
    def _build_vision_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        self._vis_refresh = QPushButton("⟳ Refresh")
        self._vis_refresh.setStyleSheet(_btn_style())
        self._vis_refresh.clicked.connect(self._refresh_vision)
        ctrl.addStretch()
        ctrl.addWidget(self._vis_refresh)
        lay.addLayout(ctrl)

        self._vis_table = QTableWidget(0, 4)
        self._vis_table.setHorizontalHeaderLabels(["Time", "Type", "Description", "Objects"])
        self._vis_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._vis_table.setStyleSheet(
            f"background:{CARD};border:1px solid {BORDER};color:{TEXT};font-size:11px;"
            f"gridline-color:{BORDER};"
        )
        lay.addWidget(self._vis_table, 1)
        return w

    # ── Behavior Tab ───────────────────────────────────────────────────────────
    def _build_behavior_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        splitter = QHBoxLayout()

        # Patterns
        left = QVBoxLayout()
        lbl = QLabel("Detected Patterns")
        lbl.setStyleSheet(f"color:{ACCENT2};font-size:12px;font-weight:bold;")
        left.addWidget(lbl)

        self._behavior_list = QListWidget()
        self._behavior_list.setStyleSheet(
            f"QListWidget{{background:{DARK};border:1px solid {BORDER};border-radius:5px;"
            f"color:{TEXT};font-size:11px;}}"
            f"QListWidget::item:hover{{background:rgba(123,47,255,20);}}"
        )
        left.addWidget(self._behavior_list, 1)
        splitter.addLayout(left, 1)

        # Routine heatmap / suggestions
        right = QVBoxLayout()
        rlbl = QLabel("Self-Learning Suggestions")
        rlbl.setStyleSheet(f"color:{SUCCESS};font-size:12px;font-weight:bold;")
        right.addWidget(rlbl)

        self._suggestions_box = QTextEdit()
        self._suggestions_box.setReadOnly(True)
        self._suggestions_box.setStyleSheet(
            f"background:{DARK};border:1px solid {BORDER};border-radius:5px;"
            f"color:{TEXT};font-size:11px;font-family:'Courier New';"
        )
        right.addWidget(self._suggestions_box, 1)

        # Performance report
        perf_lbl = QLabel("Performance Report (7d)")
        perf_lbl.setStyleSheet(f"color:{WARN};font-size:12px;font-weight:bold;")
        right.addWidget(perf_lbl)

        self._perf_box = QTextEdit()
        self._perf_box.setReadOnly(True)
        self._perf_box.setMaximumHeight(120)
        self._perf_box.setStyleSheet(
            f"background:{DARK};border:1px solid {BORDER};border-radius:5px;"
            f"color:{TEXT};font-size:10px;font-family:'Courier New';"
        )
        right.addWidget(self._perf_box)

        splitter.addLayout(right, 1)
        lay.addLayout(splitter, 1)

        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.setStyleSheet(_btn_style(ACCENT2))
        refresh_btn.clicked.connect(self._refresh_behavior)
        lay.addWidget(refresh_btn)

        return w

    # ── Tasks Tab ──────────────────────────────────────────────────────────────
    def _build_tasks_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        self._task_refresh = QPushButton("⟳ Refresh")
        self._task_refresh.setStyleSheet(_btn_style())
        self._task_refresh.clicked.connect(self._refresh_tasks)
        ctrl.addStretch()
        ctrl.addWidget(self._task_refresh)
        lay.addLayout(ctrl)

        self._task_table = QTableWidget(0, 5)
        self._task_table.setHorizontalHeaderLabels(["ID", "Title", "Status", "Created", "Result"])
        self._task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._task_table.setStyleSheet(
            f"background:{CARD};border:1px solid {BORDER};color:{TEXT};font-size:11px;"
            f"gridline-color:{BORDER};"
        )
        lay.addWidget(self._task_table, 1)
        return w

    # ── Timer / Auto-refresh ───────────────────────────────────────────────────
    def _start_timers(self):
        timer = QTimer(self)
        timer.timeout.connect(self._refresh_all)
        timer.start(8000)
        self._refresh_all()

    def _refresh_all(self):
        self._refresh_stats()
        self._refresh_text()
        self._refresh_vision()
        self._refresh_behavior()
        self._refresh_tasks()

    def _refresh_stats(self):
        if not self.memory:
            return
        try:
            stats = self.memory.get_memory_stats()
            total = (stats.get("text_memories", 0) +
                     stats.get("vision_memories", 0) +
                     stats.get("behavior_patterns", 0))
            self._stats_lbl.setText(
                f"Text: {stats.get('text_memories', 0)} | "
                f"Vision: {stats.get('vision_memories', 0)} | "
                f"Tasks: {stats.get('total_tasks', 0)}"
            )
            self._embed_lbl.setText(f"Embeddings: {stats.get('embeddings', 0)}")
            self._db_lbl.setText(f"DB: {stats.get('db_size_mb', 0)} MB | Engine: {stats.get('embedding_engine', '?')}")
        except Exception as e:
            logger.debug(f"Stats refresh error: {e}")

    def _refresh_text(self):
        if not self.memory:
            return
        try:
            rows = self.memory.get_recent_text(limit=40)
            self._text_table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                ts_item = QTableWidgetItem(r.get("timestamp", "")[:16])
                cat = r.get("category", "")
                cat_item = QTableWidgetItem(cat)
                cat_color = {"conversation": ACCENT, "fact": SUCCESS, "system": MUTED}.get(cat, TEXT)
                cat_item.setForeground(QColor(cat_color))
                self._text_table.setItem(i, 0, ts_item)
                self._text_table.setItem(i, 1, cat_item)
                self._text_table.setItem(i, 2, QTableWidgetItem(r.get("content", "")[:100]))
                self._text_table.setItem(i, 3, QTableWidgetItem(r.get("source", "")[:30]))
        except Exception as e:
            logger.debug(f"Text refresh error: {e}")

    def _refresh_vision(self):
        if not self.memory:
            return
        try:
            rows = self.memory.get_recent_vision(limit=30)
            self._vis_table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self._vis_table.setItem(i, 0, QTableWidgetItem(r.get("timestamp", "")[:16]))
                et = r.get("event_type", "")
                et_item = QTableWidgetItem(et)
                et_color = {"webcam": ACCENT, "screen_analysis": ACCENT2, "object_detection": WARN}.get(et, TEXT)
                et_item.setForeground(QColor(et_color))
                self._vis_table.setItem(i, 1, et_item)
                self._vis_table.setItem(i, 2, QTableWidgetItem(r.get("description", "")[:80]))
                objs = r.get("objects", [])
                self._vis_table.setItem(i, 3, QTableWidgetItem(", ".join(objs[:5])))
        except Exception as e:
            logger.debug(f"Vision refresh error: {e}")

    def _refresh_behavior(self):
        # Behavior patterns
        if self.memory:
            try:
                patterns = self.memory.get_behaviors(limit=20)
                self._behavior_list.clear()
                for p in patterns:
                    last = p.get("last_seen", "")[:10]
                    freq = p.get("frequency", 0)
                    item = QListWidgetItem(
                        f"[{freq}x] {p['pattern'][:40]}  (last: {last})"
                    )
                    item.setForeground(QColor(SUCCESS if freq >= 5 else TEXT))
                    self._behavior_list.addItem(item)
            except Exception as e:
                logger.debug(f"Behavior refresh error: {e}")

        # Self-learning suggestions
        if self.self_learn:
            try:
                suggestions = self.self_learn.get_suggestions()
                lines = []
                for s in suggestions:
                    icon = {"warning": "⚠", "optimization": "⚡", "automation": "🤖",
                            "learning": "📚", "error": "✗"}.get(s.get("type", ""), "•")
                    lines.append(f"{icon} {s.get('message', '')}")
                self._suggestions_box.setPlainText("\n\n".join(lines) or "No suggestions yet.")

                # Performance
                report = self.self_learn.get_performance_report(7)
                perf_lines = [
                    f"7-day success rate: {report.get('success_rate', 0)}%",
                    f"Total commands: {report.get('total', 0)}",
                    f"Avg latency: {report.get('avg_latency_ms', 0):.0f}ms",
                    "",
                    "By model:",
                ]
                for m in report.get("by_model", []):
                    perf_lines.append(
                        f"  {m['model']}: {m['success_rate']:.0f}% success, "
                        f"{m['avg_latency_ms']:.0f}ms avg, {m['count']} calls"
                    )
                self._perf_box.setPlainText("\n".join(perf_lines))
            except Exception as e:
                logger.debug(f"Self-learn refresh error: {e}")

    def _refresh_tasks(self):
        if not self.memory:
            return
        try:
            tasks = self.memory.get_tasks(limit=40)
            self._task_table.setRowCount(len(tasks))
            for i, t in enumerate(tasks):
                self._task_table.setItem(i, 0, QTableWidgetItem(str(t.get("id", ""))))
                self._task_table.setItem(i, 1, QTableWidgetItem(t.get("title", "")[:50]))
                status = t.get("status", "")
                st_item = QTableWidgetItem(status)
                st_color = {"complete": SUCCESS, "failed": ERR, "pending": WARN}.get(status, MUTED)
                st_item.setForeground(QColor(st_color))
                self._task_table.setItem(i, 2, st_item)
                self._task_table.setItem(i, 3, QTableWidgetItem(t.get("created", "")[:10]))
                self._task_table.setItem(i, 4, QTableWidgetItem(t.get("result", "")[:60]))
        except Exception as e:
            logger.debug(f"Task refresh error: {e}")

    # ── Actions ────────────────────────────────────────────────────────────────
    def _do_search(self):
        if not self.memory:
            self._search_results.setPlainText("Memory system not initialized.")
            return
        query = self._search_input.text().strip()
        if not query:
            return
        try:
            results = self.memory.search(query, top_k=6, min_similarity=0.2)
            if not results:
                self._search_results.setPlainText(f"No memories found for: '{query}'")
                return
            lines = [f"Found {len(results)} memories for '{query}':", ""]
            for r in results:
                ts  = r.get("timestamp", "")[:16]
                src = r.get("source_type", "?")
                sim = r.get("similarity", 0)
                content = r.get("content", r.get("description", ""))[:120]
                lines.append(f"[{sim:.0%}] [{src}] {ts}: {content}")
            self._search_results.setPlainText("\n".join(lines))
        except Exception as e:
            self._search_results.setPlainText(f"Search error: {e}")

    def _store_memory(self):
        query = self._search_input.text().strip()
        if not query or not self.memory:
            return
        row_id = self.memory.store_text(query, category="user_note", source="manual")
        self._search_results.setPlainText(f"✓ Memory stored (id={row_id}): {query[:80]}")
        self._refresh_text()

    def _clear_old(self):
        if not self.memory:
            return
        result = self.memory.clear_old_memories(days=30)
        deleted = result.get("deleted_text", 0) + result.get("deleted_vision", 0)
        self._search_results.setPlainText(f"Cleared {deleted} memories older than 30 days.")
        self._refresh_all()
