import sys
import os
import json
import subprocess
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QComboBox, QTextEdit, QFrame, QGroupBox,
    QSplitter, QSlider, QCheckBox
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QColor, QPalette

from communication import LabCommunication
from input_manager import InputManager
from input_mapper_dialog import InputMapperDialog

class ExperimentLabUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("INEXP-ursina | Laboratorio de Experimentos")
        self.resize(1000, 700)
        
        # Estilo Dark Premium
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; color: #e0e0e0; }
            QGroupBox { border: 2px solid #333; border-radius: 8px; margin-top: 15px; font-weight: bold; color: #4CAF50; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QPushButton { background-color: #1e1e1e; border: 1px solid #444; color: white; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #333; border: 1px solid #4CAF50; }
            QPushButton#btn_connect { background-color: #2e7d32; }
            QLabel { color: #bbb; }
            QTextEdit { background-color: #000; color: #00ff00; border: 1px solid #222; font-family: 'Courier New'; }
        """)

        self.comm = LabCommunication()
        self.input_mgr = InputManager()
        self.current_angles = [0.0] * 6
        self.last_sent_angles = [0.0] * 6
        self.last_interaction_time = 0
        self.sim_process = None
        
        self.init_ui()
        
        # Lanzar simulación automáticamente
        QTimer.singleShot(500, self.launch_simulation)
        
        # Timers
        self.loop_timer = QTimer()
        self.loop_timer.timeout.connect(self.main_loop)
        self.loop_timer.start(30) # ~33 FPS

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.global_layout = QVBoxLayout(central)
        self.global_layout.setContentsMargins(5, 5, 5, 5)
        self.global_layout.setSpacing(5)
        
        # WIDGET SUPERIOR (Splitter Horizontal: Controles | Simulación) ---
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        self.top_splitter = QSplitter(Qt.Horizontal)
        
        # PANEL IZQUIERDO (Controles)
        left_panel_widget = QWidget()
        left_panel = QVBoxLayout(left_panel_widget)
        
        # Conexión Hardware
        conn_group = QGroupBox("Hardware / Arduino")
        conn_layout = QVBoxLayout()
        
        # Filtro de puertos
        port_header = QHBoxLayout()
        port_header.addWidget(QLabel("Puerto Serial:"))
        self.chk_exp_mode = QCheckBox("Modo Exp.")
        self.chk_exp_mode.setToolTip("Muestra todos los puertos, no solo Arduinos")
        self.chk_exp_mode.stateChanged.connect(self.refresh_ports)
        port_header.addWidget(self.chk_exp_mode)
        conn_layout.addLayout(port_header)
        
        self.port_selector = QComboBox()
        # self.refresh_ports() se movió al final de init_ui para evitar error de ai_console
        
        self.btn_connect = QPushButton("CONECTAR ARDUINO")
        self.btn_connect.setObjectName("btn_connect")
        self.btn_connect.clicked.connect(self.toggle_arduino)
        
        conn_layout.addWidget(self.port_selector)
        conn_layout.addWidget(self.btn_connect)
        conn_group.setLayout(conn_layout)
        left_panel.addWidget(conn_group)
        
        # Gestión de Mandos
        input_group = QGroupBox("Entrada / Dispositivo")
        input_layout = QVBoxLayout()
        
        self.btn_configure_binds = QPushButton("⚙ CONFIGURAR BINDS")
        self.btn_configure_binds.setMinimumHeight(45)
        self.btn_configure_binds.clicked.connect(self.open_mapper_dialog)
        
        self.input_status = QLabel("Mando: Esperando...")
        input_layout.addWidget(self.btn_configure_binds)
        input_layout.addWidget(self.input_status)
        input_group.setLayout(input_layout)
        left_panel.addWidget(input_group)

        # Estado de Ángulos y Sliders Manuales
        angles_group = QGroupBox("Estado del Brazo / Control Manual")
        angles_layout = QVBoxLayout()
        self.angle_labels = []
        self.sliders = []
        for i in range(6):
            # Label
            lbl = QLabel(f"J{i}: 0.0°")
            angles_layout.addWidget(lbl)
            self.angle_labels.append(lbl)
            
            # Slider
            s = QSlider(Qt.Horizontal)
            s.setRange(-90, 90)
            s.setValue(0)
            s.setTickPosition(QSlider.TicksBelow)
            s.setTickInterval(15)
            # Conectamos el cambio del slider al envío de ángulos
            s.valueChanged.connect(lambda val, idx=i: self.on_slider_change(idx, val))
            angles_layout.addWidget(s)
            self.sliders.append(s)

        angles_group.setLayout(angles_layout)
        left_panel.addWidget(angles_group)
        left_panel.addStretch()
        
        self.top_splitter.addWidget(left_panel_widget)
        
        # PANEL CENTRAL (Simulación Ursina)
        self.sim_container = QGroupBox("Visualización 3D (Ursina)")
        sim_layout = QVBoxLayout()
        self.sim_view = QWidget()
        self.sim_view.setStyleSheet("background-color: #000;")
        self.sim_view.setMinimumSize(500, 400)
        sim_layout.addWidget(self.sim_view)
        self.sim_container.setLayout(sim_layout)
        
        self.top_splitter.addWidget(self.sim_container)
        top_layout.addWidget(self.top_splitter)
        
        # Añadimos el widget superior al layout global con factor de expansión 1
        self.global_layout.addWidget(top_widget, 1)
        
        # --- BOTTOM PANEL (Consola Colapsable) ---
        self.console_container = QGroupBox("Consola de Experimentos")
        console_layout = QVBoxLayout()
        
        self.btn_toggle_console = QPushButton("▲ EXPANDIR CONSOLA")
        self.btn_toggle_console.clicked.connect(self.toggle_console)
        
        self.ai_console = QTextEdit()
        self.ai_console.setReadOnly(True)
        self.ai_console.append(">> Sistema Lab inicializado. Ursina cargando...")
        
        console_layout.addWidget(self.btn_toggle_console)
        console_layout.addWidget(self.ai_console)
        self.console_container.setLayout(console_layout)
        
        # Añadimos la consola al layout global con factor de expansión 0 (fijo abajo)
        self.global_layout.addWidget(self.console_container, 0)
        
        self.ai_console.hide() # Empezamos con la caja de texto oculta
        
        # Ahora que todo está inicializado, refrescamos los puertos
        self.refresh_ports()

    def refresh_ports(self):
        """Refresca la lista de puertos aplicando el filtro si Modo Exp está apagado."""
        self.port_selector.clear()
        filter_arduino = not self.chk_exp_mode.isChecked()
        ports = self.comm.list_ports(filter_arduino=filter_arduino)
        self.port_selector.addItems(ports)
        if not ports:
            self.ai_console.append(">> [Hardware] No se detectaron puertos compatibles.")

    def toggle_console(self):
        """Muestra/Oculta la caja de texto de la consola de forma limpia."""
        if self.ai_console.isVisible():
            self.ai_console.hide()
            self.btn_toggle_console.setText("▲ EXPANDIR CONSOLA")
        else:
            self.ai_console.show()
            self.btn_toggle_console.setText("▼ MINIMIZAR CONSOLA")
        
        # Forzamos al layout a re-calcular el espacio
        self.global_layout.invalidate()
        self.global_layout.activate()

    def launch_simulation(self):
        """Lanza la simulación Ursina incrustada."""
        win_id = str(int(self.sim_view.winId()))
        w = str(self.sim_view.width())
        h = str(self.sim_view.height())
        
        # Usar el venv del proyecto
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        python_exe = os.path.join(base_dir, "venv", "bin", "python3")
        sim_script = os.path.join(base_dir, "sim_3d.py")
        
        # Forzar X11 para la simulación también si es Linux
        env = os.environ.copy()
        if sys.platform == "linux" or sys.platform == "linux2":
            env["QT_X11_NO_MITSHM"] = "1"
            env["QT_QPA_PLATFORM"] = "xcb"

        try:
            self.sim_process = subprocess.Popen(
                [python_exe, sim_script, win_id, w, h],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            self.ai_console.append(f">> Simulación lanzada en Window ID: {win_id}")
            
            # Hilo para leer logs de la simulación
            self.log_timer = QTimer()
            self.log_timer.timeout.connect(self.read_sim_logs)
            self.log_timer.start(100)
        except Exception as e:
            self.ai_console.append(f">> ERROR al lanzar simulación: {e}")

    def read_sim_logs(self):
        if self.sim_process and self.sim_process.stdout:
            while True:
                # Leer línea de forma no bloqueante
                import select
                # Comprobar si hay datos
                if select.select([self.sim_process.stdout], [], [], 0)[0]:
                    line = self.sim_process.stdout.readline()
                    if line:
                        print(f"[Sim] {line.strip()}")
                        # Solo mostrar errores o avisos importantes en la consola del lab
                        if "Error" in line or "fail" in line.lower():
                            self.ai_console.append(f"<span style='color:red;'>[Sim] {line.strip()}</span>")
                    else:
                        break
                else:
                    break

    def toggle_arduino(self):
        if not self.comm.ser or not self.comm.ser.is_open:
            port = self.port_selector.currentText()
            if self.comm.connect_arduino(port):
                self.btn_connect.setText("DESCONECTAR")
                self.btn_connect.setStyleSheet("background-color: #c62828;")
        else:
            self.comm.ser.close()
            self.btn_connect.setText("CONECTAR ARDUINO")
            self.btn_connect.setStyleSheet("background-color: #2e7d32;")

    def open_mapper_dialog(self):
        """Abre la ventana premium de configuración de mandos."""
        dialog = InputMapperDialog(self.input_mgr, self)
        if dialog.exec_():
            self.ai_console.append(">> [Input] Configuración de dispositivo actualizada.")

    def on_slider_change(self, index, value):
        """Maneja el movimiento manual de un slider."""
        self.current_angles[index] = float(value)
        self.angle_labels[index].setText(f"J{index}: {self.current_angles[index]:.1f}°")
        self.last_interaction_time = time.time() # Registrar interacción manual

    def save_current_pose(self):
        """Guarda la posición actual en el archivo de poses."""
        try:
            poses_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "poses.json")
            poses = {}
            if os.path.exists(poses_path):
                with open(poses_path, "r") as f:
                    poses = json.load(f)
            
            pose_name = f"JoypadSnapshot_{int(time.time())}"
            poses[pose_name] = self.current_angles
            
            with open(poses_path, "w") as f:
                json.dump(poses, f, indent=4)
            print(f"[Lab] Pose guardada: {pose_name}")
        except Exception as e:
            print(f"[Lab] Error al guardar pose: {e}")

    def main_loop(self):
        # 1. Leer entradas de la simulación (Feedback) - Vaciado completo del buffer
        fb = self.comm.get_feedback()
        if fb:
            if fb.get("type") == "sync_angles":
                # Solo sincronizamos desde Ursina si NO estamos operando los controles del Lab
                # damos un margen de 0.5 segundos tras la última interacción local
                if time.time() - self.last_interaction_time > 0.5:
                    angles = fb["data"]
                    self.sync_ui_from_sim(angles)
            elif fb.get("type") == "collision_status" and fb.get("colliding"):
                self.ai_console.append("!! ALERTA: Colisión detectada en simulación.")

        # 2. Leer entradas de mandos
        joy_inputs, actions = self.input_mgr.get_arm_inputs()
        
        # UI status mando... (mantener igual)
        if self.input_mgr.initialized:
            self.input_status.setText(f"Mando: {self.input_mgr.joystick.get_name()}")
            self.input_status.setStyleSheet("color: #4CAF50;")
        elif self.input_mgr.wiimote_active:
            self.input_status.setText("Wiimote: Activo")
            self.input_status.setStyleSheet("color: #4CAF50;")
        else:
            self.input_status.setText("Mando: No detectado")
            self.input_status.setStyleSheet("color: #f44336;")

        # Aplicar deltas de mandos
        mando_movido = False
        if self.input_mgr.initialized or self.input_mgr.wiimote_active:
            # Control de los 6 ejes
            for i in range(min(len(joy_inputs), 6)):
                if abs(joy_inputs[i]) > 0.1: # Deadzone
                    self.current_angles[i] += joy_inputs[i] * 2.0
                    self.current_angles[i] = max(-90, min(90, self.current_angles[i]))
                    self.sliders[i].blockSignals(True)
                    self.sliders[i].setValue(int(self.current_angles[i]))
                    self.sliders[i].blockSignals(False)
                    mando_movido = True
            
            # Manejar Acciones Especiales (Snapshot, Console, Reset)
            if actions.get("snapshot") and not hasattr(self, "_last_joy_snapshot"):
                self.save_current_pose()
                self.ai_console.append(">> [Joypad] Pose guardada vía Snapshot.")
                self._last_joy_snapshot = True
            elif not actions.get("snapshot"):
                if hasattr(self, "_last_joy_snapshot"): del self._last_joy_snapshot
                
            if actions.get("toggle_console") and not hasattr(self, "_last_joy_console"):
                self.toggle_console()
                self._last_joy_console = True
            elif not actions.get("toggle_console"):
                if hasattr(self, "_last_joy_console"): del self._last_joy_console

            if actions.get("reset"):
                self.current_angles = [0.0] * 6
                for s in self.sliders: s.setValue(0)
                mando_movido = True
        
        if mando_movido:
            self.last_interaction_time = time.time()

        # 3. ¿Debemos enviar ángulos a la simulación?
        if time.time() - self.last_interaction_time < 2.0:
            diff = sum(abs(a - b) for a, b in zip(self.current_angles, self.last_sent_angles))
            if diff > 0.1:
                self.comm.send_angles(self.current_angles)
                self.last_sent_angles = list(self.current_angles)
        
        # 4. Actualizar Labels (siempre para feedback visual)
        for i, val in enumerate(self.current_angles):
            self.angle_labels[i].setText(f"J{i}: {val:.1f}°")

    def sync_ui_from_sim(self, angles):
        """Actualiza mandos y UI basándose en la posición real de Ursina."""
        for i in range(min(len(angles), 6)):
            self.current_angles[i] = angles[i]
            self.sliders[i].blockSignals(True)
            self.sliders[i].setValue(int(angles[i]))
            self.sliders[i].blockSignals(False)
            self.angle_labels[i].setText(f"J{i}: {angles[i]:.1f}°")

if __name__ == "__main__":
    if sys.platform == "linux" or sys.platform == "linux2":
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    
    app = QApplication(sys.argv)
    window = ExperimentLabUI()
    window.show()
    sys.exit(app.exec())
