import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow
from ui.scene3d import JARVISScene3D

class JARVISMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS 3D Command Center")
        self.resize(1920, 1080)
        self.setStyleSheet("background-color: black;")
        
        # Initialize the 3D Scene
        self.scene = JARVISScene3D(self)
        self.setCentralWidget(self.scene.get_widget())
        
    def closeEvent(self, event):
        self.scene.cleanup()
        super().closeEvent(event)

if __name__ == "__main__":
    # Ensure High DPI support
    if hasattr(sys, 'frozen'):
        QApplication.setAttribute(sys.modules['PySide6.QtCore'].Qt.AA_EnableHighDPIScaling)
        
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = JARVISMainWindow()
    window.show()
    sys.exit(app.exec())
