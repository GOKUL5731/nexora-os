from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout, QPushButton, QLineEdit, QFrame
from PySide6.QtCore import Qt, Signal
from ui.theme import Theme

class SystemControlPanel(QFrame):
    command_submitted = Signal(str)
    action_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "Panel")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QHBoxLayout()
        title1 = QLabel("JARVIS")
        title1.setFont(Theme.get_font(10, bold=True))
        title1.setStyleSheet(f"color: {Theme.TEXT_WHITE};")
        
        title2 = QLabel("SYSTEM CONTROL")
        title2.setFont(Theme.get_font(10, bold=True))
        title2.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        
        header.addWidget(title1)
        header.addStretch()
        header.addWidget(title2)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Grid of buttons
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(10)
        
        buttons = [
            ("Applications", "⊞", 0, 0),
            ("Files", "📁", 0, 1),
            ("Terminal", "⌨", 0, 2),
            ("Settings", "⚙", 1, 0),
            ("Devices", "🖥", 1, 1),
            ("Network", "🌐", 1, 2),
            ("Power", "⏻", 2, 0),
            ("Clipboard", "📋", 2, 1),
            ("Tasks", "☰", 2, 2),
        ]
        
        self.buttons = {}
        for name, icon, row, col in buttons:
            btn = QPushButton()
            btn.setFixedSize(80, 80)
            btn_layout = QVBoxLayout(btn)
            btn_layout.setAlignment(Qt.AlignCenter)
            
            icon_lbl = QLabel(icon)
            icon_lbl.setFont(Theme.get_font(20))
            icon_lbl.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
            icon_lbl.setAlignment(Qt.AlignCenter)
            
            name_lbl = QLabel(name)
            name_lbl.setFont(Theme.get_font(8))
            name_lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
            name_lbl.setAlignment(Qt.AlignCenter)
            
            btn_layout.addWidget(icon_lbl)
            btn_layout.addWidget(name_lbl)
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.BG_DARK};
                    border: 1px solid {Theme.BORDER};
                    border-radius: 10px;
                }}
                QPushButton:hover {{
                    border: 1px solid {Theme.ACCENT_CYAN};
                    background-color: {Theme.ACCENT_CYAN_DIM};
                }}
            """)
            
            grid.addWidget(btn, row, col)
            btn.clicked.connect(lambda _checked=False, action=name: self.action_requested.emit(action))
            self.buttons[name] = btn
            
        layout.addWidget(grid_widget, alignment=Qt.AlignCenter)
        
        # Command input
        cmd_layout = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Command...")
        self.cmd_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_DARK};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                padding: 10px;
                color: {Theme.TEXT_WHITE};
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.ACCENT_CYAN};
            }}
        """)
        
        cmd_btn = QPushButton("➤")
        cmd_btn.setFixedSize(40, 40)
        cmd_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {Theme.ACCENT_CYAN};
                font-size: 16px;
            }}
            QPushButton:hover {{
                color: {Theme.TEXT_WHITE};
            }}
        """)
        
        cmd_layout.addWidget(self.cmd_input)
        cmd_layout.addWidget(cmd_btn)
        cmd_btn.clicked.connect(self._submit_command)
        self.cmd_input.returnPressed.connect(self._submit_command)
        
        layout.addLayout(cmd_layout)

    def _submit_command(self):
        text = self.cmd_input.text().strip()
        if not text:
            return
        self.command_submitted.emit(text)
        self.cmd_input.clear()
