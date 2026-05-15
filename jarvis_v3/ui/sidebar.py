from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame, QHBoxLayout
from PySide6.QtCore import Qt, QSize
from ui.theme import Theme
from ui.animations import Animations

class Sidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "Panel")
        self.setFixedWidth(220)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(5)

        # Title
        title = QLabel("J A R V I S")
        title.setFont(Theme.get_title_font(16))
        title.setStyleSheet(f"color: {Theme.ACCENT_CYAN}; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title)

        # Nav items
        nav_items = [
            ("⌂", "Home"),
            ("🎤", "Voice"),
            ("👁", "Vision"),
            ("⚙", "Automation"),
            ("🤖", "Agents"),
            ("⚡", "Workflows"),
            ("🔬", "AI Lab"),
            ("🔌", "Plugins"),
            ("🧠", "Memory"),
            ("⚙", "Settings")
        ]

        self.buttons = []
        for icon, text in nav_items:
            btn = QPushButton(f"  {icon}    {text}")
            btn.setCheckable(True)
            if text == "Home":
                btn.setChecked(True)
            self.buttons.append(btn)
            layout.addWidget(btn)

            # Ensure only one button is checked
            btn.clicked.connect(lambda checked, b=btn: self.on_nav_clicked(b))

        layout.addStretch()

        # System Status
        status_label = QLabel("SYSTEM STATUS")
        status_label.setFont(Theme.get_font(9, bold=True))
        status_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; margin-top: 20px;")
        layout.addWidget(status_label)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(5, 0, 0, 0)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 14px;")
        Animations.add_glow(self.status_dot, Theme.SUCCESS, radius=10)
        
        status_text = QLabel("ONLINE")
        status_text.setFont(Theme.get_font(10))
        status_text.setStyleSheet(f"color: {Theme.SUCCESS};")

        status_row.addWidget(self.status_dot)
        status_row.addWidget(status_text)
        status_row.addStretch()

        layout.addLayout(status_row)

    def on_nav_clicked(self, clicked_btn):
        for btn in self.buttons:
            if btn != clicked_btn:
                btn.setChecked(False)
        clicked_btn.setChecked(True)
