from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QProgressBar, QGroupBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal
import os

class CNCControlWidget(QGroupBox):
    """
    Widget modular para el control de trayectorias CNC basadas en SVG.
    """
    # Señales para comunicar con la ventana principal del Lab
    start_requested = Signal()
    stop_requested = Signal()
    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Trayectoria CNC (SVG)", parent)
        self.current_svg_path = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Info de archivo
        self.lbl_status = QLabel("SVG: Ninguno cargado")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.lbl_status)
        
        # Botones de Acción
        btn_row = QHBoxLayout()
        
        self.btn_load = QPushButton("Cargar SVG")
        self.btn_load.clicked.connect(self.on_load_clicked)
        self.btn_load.setStyleSheet("background-color: #333;")
        
        self.btn_start = QPushButton("INICIAR")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.start_requested.emit)
        self.btn_start.setStyleSheet("background-color: #2e7d32; font-weight: bold;")
        
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        self.btn_stop.setStyleSheet("background-color: #c62828; font-weight: bold;")
        
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_stop)
        layout.addLayout(btn_row)
        
        # Barra de Progreso
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setStyleSheet("""
            QProgressBar { border: 1px solid #444; border-radius: 3px; background: #222; text-align: center; }
            QProgressBar::chunk { background-color: #4CAF50; }
        """)
        layout.addWidget(self.progress)
        
        # Opciones adicionales
        self.btn_reset = QPushButton("Reset Posición Blueprint")
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        self.btn_reset.setStyleSheet("font-size: 10px; color: #bbb;")
        layout.addWidget(self.btn_reset)

    def on_load_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar Vector SVG", "", "Archivos SVG (*.svg)"
        )
        if path:
            self.set_svg_file(path)
            self.file_selected.emit(path)

    def set_svg_file(self, path):
        self.current_svg_path = path
        filename = os.path.basename(path)
        self.lbl_status.setText(f"SVG: {filename}")
        self.lbl_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(True)

    def on_reset_clicked(self):
        # Esta funcionalidad se comunicará vía lab_main -> comm -> sim
        pass

    def update_progress(self, val):
        self.progress.setValue(val)
        
    def set_running(self, running):
        self.btn_start.setEnabled(not running)
        self.btn_load.setEnabled(not running)
        self.btn_stop.setEnabled(True)
