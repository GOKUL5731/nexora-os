"""
JARVIS Phase 2 — Learning Panel (PySide6)
==========================================
Displays:
  - RNN training progress and accuracy charts
  - Vision training progress bars
  - Behavior prediction statistics
  - Command frequency analytics
  - Workflow detection results
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QSplitter, QComboBox, QListWidget,
    QListWidgetItem, QGroupBox,
)

logger = logging.getLogger("jarvis.ui.learning_panel")

DARK   = "#0a0e1a"; PANEL  = "#0f1628"; CARD   = "#131d35"
ACCENT = "#00d4ff"; ACCENT2 = "#7b2fff"
TEXT   = "#e8f4ff"; MUTED  = "#4a6a8a"; BORDER = "#1a2a4a"
SUCCESS = "#00ff9d"; WARN   = "#ffaa00"; ERR   = "#ff4466"


def _card(border: str = BORDER) -> str:
    return f"background:{CARD};border:1px solid {border};border-radius:10px;padding:8px;"


class TrainingWatcher(QThread):
    """Polls trainer state and emits updates."""
    update = Signal(dict)

    def __init__(self, trainer):
        super().__init__()
        self.trainer  = trainer
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            if self.trainer:
                self.update.emit(self.trainer.get_status())
            self.msleep(1000)

    def stop(self):
        self._running = False
        self.wait(2000)


# ─── Learning Panel ──────────────────────────────────────────────────────────────
class LearningPanel(QWidget):
    """
    AI Learning Tab:
      - Vision model training controls and progress
      - RNN behavior model status
      - Prediction analytics
      - Workflow patterns
    """

    def __init__(self, trainer=None, rnn=None, predictor=None,
                 self_learn=None, gpu_manager=None, parent=None):
        super().__init__(parent)
        self.trainer    = trainer
        self.rnn        = rnn
        self.predictor  = predictor
        self.self_learn = self_learn
        self.gpu        = gpu_manager
        self._watcher: TrainingWatcher = None
        self._build_ui()
        self._start_timers()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(8, 8, 8, 8)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("🧠  LEARNING ENGINE")
        title.setStyleSheet(f"color:{ACCENT2};font-size:15px;font-weight:bold;letter-spacing:2px;")
        self._refresh_btn = QPushButton("⟳ Refresh")
        self._refresh_btn.clicked.connect(self._refresh_all)
        self._refresh_btn.setStyleSheet(
            f"QPushButton{{background:rgba(123,47,255,15);color:{ACCENT2};"
            f"border:1px solid {BORDER};border-radius:6px;padding:4px 12px;font-size:11px;}}"
            f"QPushButton:hover{{background:rgba(123,47,255,35);}}"
        )
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._refresh_btn)
        root.addLayout(hdr)

        # Main 3-column grid
        col_row = QHBoxLayout()
        col_row.setSpacing(10)

        # ── Column 1: Vision Training ────────────────────────────────────────
        vis_frame = QFrame()
        vis_frame.setStyleSheet(_card(ACCENT))
        vis_lay = QVBoxLayout(vis_frame)

        v_title = QLabel("🎓 Vision Training")
        v_title.setStyleSheet(f"color:{ACCENT};font-size:12px;font-weight:bold;")
        vis_lay.addWidget(v_title)

        # Epoch progress
        self._epoch_label = QLabel("Epoch: --/--")
        self._epoch_label.setStyleSheet(f"color:{TEXT};font-size:11px;")
        vis_lay.addWidget(self._epoch_label)

        self._train_loss_bar = QProgressBar()
        self._train_loss_bar.setRange(0, 100)
        self._train_loss_bar.setFormat("Train Loss: %p%")
        self._train_loss_bar.setStyleSheet(
            f"QProgressBar{{background:{DARK};border:1px solid {BORDER};border-radius:4px;"
            f"color:{TEXT};font-size:10px;}}"
            f"QProgressBar::chunk{{background:{ACCENT};border-radius:3px;}}"
        )
        vis_lay.addWidget(self._train_loss_bar)

        self._val_acc_bar = QProgressBar()
        self._val_acc_bar.setRange(0, 100)
        self._val_acc_bar.setFormat("Val Accuracy: %p%")
        self._val_acc_bar.setStyleSheet(
            f"QProgressBar{{background:{DARK};border:1px solid {BORDER};border-radius:4px;"
            f"color:{TEXT};font-size:10px;}}"
            f"QProgressBar::chunk{{background:{SUCCESS};border-radius:3px;}}"
        )
        vis_lay.addWidget(self._val_acc_bar)

        self._best_acc_label = QLabel("Best Accuracy: --")
        self._best_acc_label.setStyleSheet(f"color:{SUCCESS};font-size:11px;font-weight:bold;")
        vis_lay.addWidget(self._best_acc_label)

        self._train_status = QLabel("Status: idle")
        self._train_status.setStyleSheet(f"color:{MUTED};font-size:10px;")
        vis_lay.addWidget(self._train_status)

        # Training history table
        h_title = QLabel("History")
        h_title.setStyleSheet(f"color:{MUTED};font-size:10px;")
        vis_lay.addWidget(h_title)

        self._history_table = QTableWidget(0, 4)
        self._history_table.setHorizontalHeaderLabels(["Ep", "TrL", "VL", "Acc%"])
        self._history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._history_table.setStyleSheet(
            f"background:{DARK};border:1px solid {BORDER};color:{TEXT};font-size:10px;"
        )
        self._history_table.setMaximumHeight(200)
        vis_lay.addWidget(self._history_table, 1)

        # Plot button
        btn_row = QHBoxLayout()
        self._btn_plot = QPushButton("📈 Generate Plot")
        self._btn_stop = QPushButton("■ Stop")
        for btn in [self._btn_plot, self._btn_stop]:
            btn.setStyleSheet(
                f"QPushButton{{background:rgba(0,212,255,10);color:{ACCENT};"
                f"border:1px solid {BORDER};border-radius:5px;padding:4px 8px;font-size:10px;}}"
                f"QPushButton:hover{{background:rgba(0,212,255,25);}}"
            )
            btn_row.addWidget(btn)
        self._btn_plot.clicked.connect(self._generate_plot)
        self._btn_stop.clicked.connect(self._stop_training)
        vis_lay.addLayout(btn_row)

        col_row.addWidget(vis_frame, 1)

        # ── Column 2: RNN / Behavior ──────────────────────────────────────────
        rnn_frame = QFrame()
        rnn_frame.setStyleSheet(_card(ACCENT2))
        rnn_lay = QVBoxLayout(rnn_frame)

        r_title = QLabel("🔮 Behavior RNN")
        r_title.setStyleSheet(f"color:{ACCENT2};font-size:12px;font-weight:bold;")
        rnn_lay.addWidget(r_title)

        self._rnn_status = QLabel("Model: not loaded")
        self._rnn_status.setStyleSheet(f"color:{MUTED};font-size:11px;")
        rnn_lay.addWidget(self._rnn_status)

        self._rnn_events = QLabel("Events: 0")
        self._rnn_events.setStyleSheet(f"color:{TEXT};font-size:11px;")
        rnn_lay.addWidget(self._rnn_events)

        self._rnn_vocab = QLabel("Vocab: 0 tokens")
        self._rnn_vocab.setStyleSheet(f"color:{TEXT};font-size:11px;")
        rnn_lay.addWidget(self._rnn_vocab)

        # Predictions
        pred_title = QLabel("Next Action Predictions")
        pred_title.setStyleSheet(f"color:{MUTED};font-size:10px;font-weight:bold;")
        rnn_lay.addWidget(pred_title)

        self._pred_list = QListWidget()
        self._pred_list.setStyleSheet(
            f"QListWidget{{background:{DARK};border:1px solid {BORDER};border-radius:5px;"
            f"color:{TEXT};font-size:11px;}}"
            f"QListWidget::item:hover{{background:rgba(0,212,255,15);}}"
        )
        self._pred_list.setMaximumHeight(150)
        rnn_lay.addWidget(self._pred_list, 1)

        # Top commands
        top_title = QLabel("Top Commands (Frequency)")
        top_title.setStyleSheet(f"color:{MUTED};font-size:10px;font-weight:bold;")
        rnn_lay.addWidget(top_title)

        self._top_cmds_table = QTableWidget(0, 3)
        self._top_cmds_table.setHorizontalHeaderLabels(["Command", "Count", "Success%"])
        self._top_cmds_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._top_cmds_table.setStyleSheet(
            f"background:{DARK};border:1px solid {BORDER};color:{TEXT};font-size:10px;"
        )
        self._top_cmds_table.setMaximumHeight(180)
        rnn_lay.addWidget(self._top_cmds_table, 1)

        rnn_btn = QPushButton("🔁 Retrain RNN")
        rnn_btn.setStyleSheet(
            f"QPushButton{{background:rgba(123,47,255,15);color:{ACCENT2};"
            f"border:1px solid {ACCENT2};border-radius:5px;padding:4px 10px;font-size:11px;}}"
            f"QPushButton:hover{{background:rgba(123,47,255,35);}}"
        )
        rnn_btn.clicked.connect(self._retrain_rnn)
        rnn_lay.addWidget(rnn_btn)

        col_row.addWidget(rnn_frame, 1)

        # ── Column 3: GPU + Performance ───────────────────────────────────────
        gpu_frame = QFrame()
        gpu_frame.setStyleSheet(_card(SUCCESS))
        gpu_lay = QVBoxLayout(gpu_frame)

        g_title = QLabel("🖥  GPU Monitor")
        g_title.setStyleSheet(f"color:{SUCCESS};font-size:12px;font-weight:bold;")
        gpu_lay.addWidget(g_title)

        self._gpu_name_lbl = QLabel("RTX 4050")
        self._gpu_name_lbl.setStyleSheet(f"color:{TEXT};font-size:11px;")
        gpu_lay.addWidget(self._gpu_name_lbl)

        # GPU bars
        for label, attr, color in [
            ("GPU %",    "_gpu_bar",  SUCCESS),
            ("VRAM %",   "_vram_bar", ACCENT),
            ("Temp °C",  "_temp_bar", WARN),
        ]:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{MUTED};font-size:10px;")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setStyleSheet(
                f"QProgressBar{{background:{DARK};border:1px solid {BORDER};border-radius:3px;"
                f"color:{TEXT};font-size:9px;}}"
                f"QProgressBar::chunk{{background:{color};border-radius:2px;}}"
            )
            gpu_lay.addWidget(lbl)
            gpu_lay.addWidget(bar)
            setattr(self, attr, bar)

        self._gpu_detail = QLabel("--")
        self._gpu_detail.setStyleSheet(f"color:{MUTED};font-size:10px;")
        gpu_lay.addWidget(self._gpu_detail)

        # Training safety indicator
        self._safety_lbl = QLabel("Training: --")
        self._safety_lbl.setStyleSheet(f"color:{MUTED};font-size:11px;font-weight:bold;")
        gpu_lay.addWidget(self._safety_lbl)

        # Workflows
        wf_title = QLabel("Detected Workflows")
        wf_title.setStyleSheet(f"color:{MUTED};font-size:10px;font-weight:bold;margin-top:8px;")
        gpu_lay.addWidget(wf_title)

        self._workflow_list = QListWidget()
        self._workflow_list.setStyleSheet(
            f"QListWidget{{background:{DARK};border:1px solid {BORDER};border-radius:5px;"
            f"color:{TEXT};font-size:10px;}}"
            f"QListWidget::item:hover{{background:rgba(0,255,157,10);}}"
        )
        gpu_lay.addWidget(self._workflow_list, 1)

        col_row.addWidget(gpu_frame, 1)
        root.addLayout(col_row, 1)

    # ── Refresh Logic ──────────────────────────────────────────────────────────
    def _start_timers(self):
        # Training watcher
        if self.trainer:
            self._watcher = TrainingWatcher(self.trainer)
            self._watcher.update.connect(self._on_training_update)
            self._watcher.start()

        # GPU + RNN refresh
        t = QTimer(self)
        t.timeout.connect(self._refresh_all)
        t.start(3000)
        self._refresh_all()

    def _refresh_all(self):
        self._refresh_gpu()
        self._refresh_rnn()
        self._refresh_workflows()
        self._refresh_top_commands()

    def _on_training_update(self, status: dict):
        if status.get("is_training"):
            epoch  = status.get("epoch", 0)
            total  = status.get("total_epochs", 1)
            t_loss = status.get("train_loss", 0)
            v_acc  = status.get("val_acc", 0)
            best   = status.get("best_acc", 0)

            self._epoch_label.setText(f"Epoch: {epoch}/{total}")
            loss_pct = max(0, min(100, int((1 - t_loss) * 100)))
            self._train_loss_bar.setValue(loss_pct)
            self._val_acc_bar.setValue(int(v_acc))
            self._best_acc_label.setText(f"Best Accuracy: {best:.1f}%")
            self._train_status.setText(f"Status: {status.get('status', 'training')}")

            # Update history table
            history = status.get("history", [])
            self._history_table.setRowCount(len(history))
            for i, h in enumerate(history):
                self._history_table.setItem(i, 0, QTableWidgetItem(str(h["epoch"])))
                self._history_table.setItem(i, 1, QTableWidgetItem(f"{h['train_loss']:.3f}"))
                self._history_table.setItem(i, 2, QTableWidgetItem(f"{h['val_loss']:.3f}"))
                acc_item = QTableWidgetItem(f"{h['val_acc']:.1f}")
                color = SUCCESS if h["val_acc"] > 80 else (WARN if h["val_acc"] > 60 else ERR)
                acc_item.setForeground(QColor(color))
                self._history_table.setItem(i, 3, acc_item)
            if history:
                self._history_table.scrollToBottom()
        else:
            self._train_status.setText(f"Status: {status.get('status', 'idle')}")

    def _refresh_gpu(self):
        if not self.gpu:
            return
        try:
            info = self.gpu.get_gpu_info()
            name = info.get("name", "RTX 4050")
            if name and isinstance(name, str):
                self._gpu_name_lbl.setText(name[:40])

            self._gpu_bar.setValue(info.get("gpu_pct", 0)
                                   if isinstance(info.get("gpu_pct"), int) else 0)
            self._vram_bar.setValue(info.get("vram_pct", 0))

            temp = info.get("temp_c", 0)
            temp_pct = min(100, int(temp / 100 * 100)) if temp else 0
            self._temp_bar.setValue(temp_pct)

            detail = (f"VRAM: {info.get('vram_used_mb', 0):.0f}/"
                      f"{info.get('vram_total_mb', 6144):.0f}MB | "
                      f"Power: {info.get('power_w', 0):.0f}W | "
                      f"Fan: {info.get('fan_pct', 0)}%")
            self._gpu_detail.setText(detail)

            safety = self.gpu.is_training_safe()
            if safety["safe"]:
                self._safety_lbl.setText("Training: ✓ Safe")
                self._safety_lbl.setStyleSheet(f"color:{SUCCESS};font-size:11px;font-weight:bold;")
            else:
                self._safety_lbl.setText(f"Training: ✗ {safety['reason'][:40]}")
                self._safety_lbl.setStyleSheet(f"color:{WARN};font-size:10px;")
        except Exception as e:
            logger.debug(f"GPU refresh error: {e}")

    def _refresh_rnn(self):
        if not self.rnn:
            return
        try:
            stats = self.rnn.get_stats()
            trained = stats.get("model_trained", False)
            self._rnn_status.setText(f"Model: {'✓ Trained' if trained else '○ Not trained'}")
            self._rnn_status.setStyleSheet(
                f"color:{SUCCESS if trained else MUTED};font-size:11px;"
            )
            self._rnn_events.setText(f"Events: {stats.get('total_events', 0):,}")
            self._rnn_vocab.setText(f"Vocab: {stats.get('vocab_size', 0)} tokens")

            # Predictions
            if self.predictor:
                pred = self.predictor.predict_next_action()
                self._pred_list.clear()
                for p in pred.get("predictions", [])[:5]:
                    sources = "/".join(p.get("sources", ["?"]))
                    item = QListWidgetItem(
                        f"{'▶' if pred.get('top') == p else ' '} "
                        f"{p['command'].replace('_', ' ')} "
                        f"[{p['confidence']:.0%}] ({sources})"
                    )
                    item.setForeground(QColor(SUCCESS if p == pred.get("top") else TEXT))
                    self._pred_list.addItem(item)
        except Exception as e:
            logger.debug(f"RNN refresh error: {e}")

    def _refresh_top_commands(self):
        if not self.self_learn:
            return
        try:
            cmds = self.self_learn.get_favorite_commands(top_n=10)
            self._top_cmds_table.setRowCount(len(cmds))
            for i, c in enumerate(cmds):
                self._top_cmds_table.setItem(i, 0, QTableWidgetItem(c["command"][:30]))
                self._top_cmds_table.setItem(i, 1, QTableWidgetItem(str(c["count"])))
                sr_item = QTableWidgetItem(f"{c['success_rate']:.0f}%")
                color = SUCCESS if c["success_rate"] >= 80 else (WARN if c["success_rate"] >= 60 else ERR)
                sr_item.setForeground(QColor(color))
                self._top_cmds_table.setItem(i, 2, sr_item)
        except Exception as e:
            logger.debug(f"Top commands refresh error: {e}")

    def _refresh_workflows(self):
        if not self.self_learn:
            return
        try:
            workflows = self.self_learn.get_workflows()
            self._workflow_list.clear()
            for wf in workflows[:8]:
                steps = " → ".join(wf["steps"][:4])
                item = QListWidgetItem(
                    f"[{wf['frequency']}x] {wf['name'][:20]}: {steps[:50]}"
                )
                item.setForeground(QColor(SUCCESS if wf["frequency"] >= 5 else TEXT))
                self._workflow_list.addItem(item)
        except Exception as e:
            logger.debug(f"Workflow refresh error: {e}")

    def _generate_plot(self):
        if not self.trainer:
            return
        status = self.trainer.get_status()
        history = status.get("history", [])
        if not history:
            return
        try:
            path = self.trainer.generate_loss_plot(history)
            if path:
                logger.info(f"Plot saved: {path}")
        except Exception as e:
            logger.warning(f"Plot error: {e}")

    def _stop_training(self):
        if self.trainer:
            self.trainer.stop_training()

    def _retrain_rnn(self):
        if not self.rnn:
            return
        import threading

        def _do():
            import asyncio
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self.rnn.train_on_history(epochs=25))
            loop.close()
            logger.info(f"RNN retrain complete: {result}")

        threading.Thread(target=_do, daemon=True).start()

    def cleanup(self):
        if self._watcher:
            self._watcher.stop()
