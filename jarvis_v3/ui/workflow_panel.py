from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.theme import Theme


class NodeGraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 200)
        self.nodes = ["manual_trigger"]

    def set_workflow(self, workflow: dict | None = None):
        actions = (workflow or {}).get("actions", [])
        self.nodes = (actions or ["manual_trigger"])[:8]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen_grid = QPen(QColor(Theme.BORDER))
        pen_grid.setWidth(1)
        painter.setPen(pen_grid)
        for x in range(0, self.width(), 20):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 20):
            painter.drawLine(0, y, self.width(), y)

        nodes = self._layout_nodes()
        connections = [(nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1)]

        pen_conn = QPen(QColor(Theme.ACCENT_CYAN))
        pen_conn.setWidth(2)
        painter.setPen(pen_conn)
        for n1, n2 in connections:
            r1 = n1["rect"]
            r2 = n2["rect"]
            p1 = r1.center()
            p1.setX(r1.right())
            p2 = r2.center()
            p2.setX(r2.left())
            path = QPainterPath(p1)
            ctrl1 = p1
            ctrl2 = p2
            ctrl1.setX(p1.x() + 20)
            ctrl2.setX(p2.x() - 20)
            path.cubicTo(ctrl1, ctrl2, p2)
            painter.drawPath(path)

        for node in nodes:
            rect = node["rect"]
            painter.setPen(QPen(QColor(node["color"]), 1))
            painter.setBrush(QColor(Theme.BG_DARK))
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QColor(Theme.TEXT_WHITE))
            painter.setFont(Theme.get_font(8))
            painter.drawText(rect, Qt.AlignCenter, node["text"])

    def _layout_nodes(self):
        nodes = []
        x, y = 20, 50
        for index, action in enumerate(self.nodes):
            if x + 110 > self.width():
                x = 20
                y += 60
            nodes.append(
                {
                    "rect": QRectF(x, y, 105, 32),
                    "text": action.replace("_", " ").title(),
                    "color": Theme.SUCCESS if index == 0 else Theme.ACCENT_CYAN,
                }
            )
            x += 135
        return nodes


class WorkflowPanel(QFrame):
    run_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "Panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        header = QHBoxLayout()
        title1 = QLabel("JARVIS")
        title1.setFont(Theme.get_font(10, bold=True))
        title1.setStyleSheet(f"color: {Theme.TEXT_WHITE};")
        title2 = QLabel("WORKFLOW BUILDER")
        title2.setFont(Theme.get_font(10, bold=True))
        title2.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        header.addWidget(title1)
        header.addStretch()
        header.addWidget(title2)
        header.addStretch()
        layout.addLayout(header)

        main_layout = QHBoxLayout()

        tools_layout = QVBoxLayout()
        tools_layout.setSpacing(5)
        for title, items in [
            ("TRIGGERS", ["Manual Trigger", "Schedule", "Event", "Webhook", "AI Trigger"]),
            ("ACTIONS", ["Run Script", "Open Application", "Send Message", "HTTP Request", "AI Prompt"]),
        ]:
            label = QLabel(title)
            label.setFont(Theme.get_font(8, bold=True))
            label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
            tools_layout.addWidget(label)
            for item in items:
                row = QLabel(f"  {item}")
                row.setFont(Theme.get_font(8))
                row.setStyleSheet(f"color: {Theme.TEXT_WHITE};")
                tools_layout.addWidget(row)
            tools_layout.addSpacing(10)
        tools_layout.addStretch()
        main_layout.addLayout(tools_layout, 1)

        self.graph = NodeGraphWidget()
        main_layout.addWidget(self.graph, 3)

        details_layout = QVBoxLayout()
        label = QLabel("DETAILS")
        label.setFont(Theme.get_font(8, bold=True))
        label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        details_layout.addWidget(label)

        self.workflow_select = QComboBox()
        self.workflow_select.setStyleSheet(
            f"background:{Theme.BG_DARK}; color:{Theme.TEXT_WHITE}; border:1px solid {Theme.BORDER}; padding:6px;"
        )
        details_layout.addWidget(self.workflow_select)

        self.run_btn = QPushButton("Run")
        self.run_btn.setStyleSheet(
            f"background:{Theme.BG_DARK}; color:{Theme.ACCENT_CYAN}; border:1px solid {Theme.ACCENT_CYAN}; padding:8px;"
        )
        self.run_btn.clicked.connect(self._emit_run)
        details_layout.addWidget(self.run_btn)

        self.detail_labels = {}
        for field, value, color in [
            ("Workflow Name", "None", Theme.TEXT_WHITE),
            ("Status", "Never", Theme.SUCCESS),
            ("Last Run", "Never", Theme.TEXT_WHITE),
            ("Runs", "0", Theme.SUCCESS),
        ]:
            key = QLabel(field)
            key.setFont(Theme.get_font(8))
            key.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
            val = QLabel(value)
            val.setFont(Theme.get_font(9, bold=True))
            val.setStyleSheet(f"color: {color};")
            details_layout.addWidget(key)
            details_layout.addWidget(val)
            self.detail_labels[field] = val
            details_layout.addSpacing(5)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(80)
        self.log_view.setStyleSheet(
            f"background:{Theme.BG_DARK}; color:{Theme.TEXT_MUTED}; border:1px solid {Theme.BORDER};"
        )
        details_layout.addWidget(self.log_view)
        details_layout.addStretch()
        main_layout.addLayout(details_layout, 1)

        layout.addLayout(main_layout)

    def _emit_run(self):
        name = self.workflow_select.currentText().strip()
        if name:
            self.run_requested.emit(name)

    def update_workflows(self, workflows, running=None):
        running = set(running or [])
        current = self.workflow_select.currentText()
        names = [w.get("name", "") for w in workflows or [] if w.get("name")]

        self.workflow_select.blockSignals(True)
        self.workflow_select.clear()
        self.workflow_select.addItems(names)
        if current in names:
            self.workflow_select.setCurrentText(current)
        self.workflow_select.blockSignals(False)

        selected = self.workflow_select.currentText()
        item = next((w for w in workflows or [] if w.get("name") == selected), None)
        if not item and workflows:
            item = workflows[0]

        if item:
            status = "running" if item.get("name") in running else item.get("last_status", "never")
            self.detail_labels["Workflow Name"].setText(item.get("name", ""))
            self.detail_labels["Status"].setText(str(status).title())
            self.detail_labels["Last Run"].setText(item.get("last_run") or "Never")
            self.detail_labels["Runs"].setText(str(item.get("run_count", 0)))
            self.graph.set_workflow(item)

    def append_log(self, text: str):
        self.log_view.append(text)
