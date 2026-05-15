from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QHBoxLayout, QFrame
from PySide6.QtCore import Qt
from ui.theme import Theme

class SystemPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # 1. System Overview Section
        overview_container = QFrame()
        overview_container.setProperty("class", "Panel")
        overview_layout = QVBoxLayout(overview_container)
        overview_layout.setContentsMargins(15, 15, 15, 15)
        overview_layout.setSpacing(15)

        title1 = QLabel("SYSTEM OVERVIEW")
        title1.setFont(Theme.get_font(9, bold=True))
        title1.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        overview_layout.addWidget(title1)

        self.bars = {}
        for stat in ["CPU", "RAM", "GPU", "STORAGE"]:
            row = QHBoxLayout()
            label = QLabel(stat)
            label.setFont(Theme.get_font(10))
            label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
            
            val = QLabel("0%")
            val.setFont(Theme.get_font(10, bold=True))
            val.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
            
            row.addWidget(label)
            row.addStretch()
            row.addWidget(val)
            
            bar = QProgressBar()
            bar.setFixedHeight(4)
            bar.setTextVisible(False)
            bar.setRange(0, 100)
            bar.setValue(0)
            
            overview_layout.addLayout(row)
            overview_layout.addWidget(bar)
            overview_layout.addSpacing(5)
            
            self.bars[stat] = (bar, val)

        layout.addWidget(overview_container)

        # 2. Active Modules Section
        modules_container = QFrame()
        modules_container.setProperty("class", "Panel")
        modules_layout = QVBoxLayout(modules_container)
        modules_layout.setContentsMargins(15, 15, 15, 15)
        modules_layout.setSpacing(12)

        title2 = QLabel("ACTIVE MODULES")
        title2.setFont(Theme.get_font(9, bold=True))
        title2.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        modules_layout.addWidget(title2)

        self._default_modules = [
            "Voice Engine",
            "Vision Engine",
            "LLM Core",
            "Automation Engine",
            "Memory System",
            "Agent System"
        ]

        self.module_labels = {}
        for mod in self._default_modules:
            row = QHBoxLayout()
            row.setSpacing(8)
            
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 10px;")
            
            name = QLabel(mod)
            name.setFont(Theme.get_font(10))
            name.setStyleSheet(f"color: {Theme.TEXT_WHITE};")
            
            status = QLabel("Running")
            status.setFont(Theme.get_font(9))
            status.setStyleSheet(f"color: {Theme.SUCCESS};")
            
            row.addWidget(dot)
            row.addWidget(name)
            row.addStretch()
            row.addWidget(status)
            
            modules_layout.addLayout(row)
            self.module_labels[mod] = (dot, status)
        self._modules_layout = modules_layout

        layout.addWidget(modules_container)

        diag_container = QFrame()
        diag_container.setProperty("class", "Panel")
        diag_layout = QVBoxLayout(diag_container)
        diag_layout.setContentsMargins(15, 15, 15, 15)
        diag_layout.setSpacing(8)
        diag_title = QLabel("DIAGNOSTICS")
        diag_title.setFont(Theme.get_font(9, bold=True))
        diag_title.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        self.diagnostics = QLabel("Starting health checks...")
        self.diagnostics.setWordWrap(True)
        self.diagnostics.setFont(Theme.get_font(9))
        self.diagnostics.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        diag_layout.addWidget(diag_title)
        diag_layout.addWidget(self.diagnostics)
        layout.addWidget(diag_container)
        layout.addStretch()

    def update_system_stats(self, cpu, ram, gpu, storage):
        self.bars["CPU"][0].setValue(int(cpu))
        self.bars["CPU"][1].setText(f"{int(cpu)}%")
        
        self.bars["RAM"][0].setValue(int(ram))
        self.bars["RAM"][1].setText(f"{int(ram)}%")
        
        self.bars["GPU"][0].setValue(int(gpu))
        self.bars["GPU"][1].setText(f"{int(gpu)}%")
        
        self.bars["STORAGE"][0].setValue(int(storage))
        self.bars["STORAGE"][1].setText(f"{int(storage)}%")

    def update_modules(self, modules):
        name_map = {
            "voice_engine": "Voice Engine",
            "vision_engine": "Vision Engine",
            "orchestrator": "LLM Core",
            "workflow_engine": "Automation Engine",
            "memory": "Memory System",
            "agent_manager": "Agent System",
            "agent_registry": "Agent System",
        }
        statuses = {}
        for mod in modules or []:
            label = name_map.get(mod.get("name"), mod.get("name", "Module").replace("_", " ").title())
            statuses[label] = mod.get("status", "unknown")
            if label not in self.module_labels:
                row = QHBoxLayout()
                dot = QLabel("●")
                name = QLabel(label)
                name.setFont(Theme.get_font(10))
                name.setStyleSheet(f"color: {Theme.TEXT_WHITE};")
                status = QLabel("Unknown")
                status.setFont(Theme.get_font(9))
                row.addWidget(dot)
                row.addWidget(name)
                row.addStretch()
                row.addWidget(status)
                self._modules_layout.addLayout(row)
                self.module_labels[label] = (dot, status)
        for label, (dot, status_widget) in self.module_labels.items():
            status = statuses.get(label, "offline")
            color = Theme.SUCCESS if status in {"online", "idle", "running"} else Theme.TEXT_MUTED
            if status in {"failed", "error"}:
                color = "#ff4d4d"
            dot.setText("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            status_widget.setText(status.title())
            status_widget.setStyleSheet(f"color: {color};")

    def update_diagnostics(self, health: dict, logs=None):
        logs = logs or []
        gpu = health.get("gpu", {})
        voice = health.get("voice", {})
        failed = health.get("failed_modules", [])
        agents = health.get("agents", [])
        workflows = health.get("workflows", [])
        plugins = health.get("plugins", [])
        recent = ""
        if logs:
            recent = "\nLog: " + logs[-1].payload.get("raw_message", "")[:80]
        self.diagnostics.setText(
            f"Agents: {len(agents)} | Workflows: {len(workflows)} | Plugins: {len(plugins)}\n"
            f"GPU: {gpu.get('utilization', 0)}% | Voice: {voice.get('status', 'idle')}\n"
            f"Failed modules: {len(failed)}{recent}"
        )
