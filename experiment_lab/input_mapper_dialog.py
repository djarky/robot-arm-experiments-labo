import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QWidget, QFrame, QGridLayout, QComboBox, QScrollArea,
    QSlider, QLineEdit
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QFont, QColor

class BindButton(QPushButton):
    """Botón especializado que muestra la acción y el bind actual."""
    def __init__(self, action_name, key_name, current_val, parent=None):
        super().__init__(parent)
        self.action_name = action_name
        self.key_name = key_name # 'axes' o 'buttons'
        self.current_val = current_val
        self.is_binding = False
        
        self.setMinimumWidth(180)
        self.setStyleSheet("""
            QPushButton {
                background-color: #252525;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 10px;
                padding-right: 35px; /* Espacio para la X */
                color: #ddd;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #333;
                border: 1px solid #4CAF50;
            }
        """)

        # Botón de limpieza individual (X)
        self.btn_clear = QPushButton("×", self)
        self.btn_clear.setFixedSize(22, 22)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setToolTip("Limpiar este bind")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 60, 60, 0.5);
                color: #888;
                border-radius: 11px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #c62828;
                color: white;
            }
        """)
        self.btn_clear.hide()
        
        # Llamar a update_text al final, una vez que todos los componentes existen
        self.update_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Posicionar el botón X en la esquina superior derecha
        self.btn_clear.move(self.width() - 28, (self.height() - 22) // 2)

    def update_text(self):
        val_str = "SIN ASIGNAR"
        has_val = False
        if isinstance(self.current_val, dict):
            t = self.current_val.get("type", "bt")
            i = self.current_val.get("id", "?")
            val_str = f"{t.capitalize()} {i}"
            has_val = True
        elif self.current_val is not None:
            val_str = str(self.current_val)
            has_val = True
            
        if self.is_binding:
            self.setText(f"{self.action_name}\n>>> PRESIONA INPUT <<<")
            self.setStyleSheet(self.styleSheet() + "border: 1px solid #ff9800; background-color: #3e2723;")
            self.btn_clear.hide()
        else:
            self.setText(f"{self.action_name}\n{val_str}")
            self.setStyleSheet(self.styleSheet().replace("border: 1px solid #ff9800; background-color: #3e2723;", ""))
            # Mostrar la X solo si hay un valor asignado y no estamos bindeando
            self.btn_clear.setVisible(has_val)

    def set_binding(self, state):
        self.is_binding = state
        self.update_text()


class InputMapperDialog(QDialog):
    def __init__(self, input_mgr, parent=None):
        super().__init__(parent)
        self.input_mgr = input_mgr
        self.setWindowTitle("Configuración de Mando | Premium Mapper")
        self.resize(1000, 650)
        self.setModal(True)
        
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; color: #eee; }
            QLabel#Title { font-size: 20px; font-weight: bold; color: #4CAF50; margin-bottom: 5px; }
            QLabel#Subtitle { color: #888; font-size: 11px; margin-bottom: 20px; }
        """)

        self.binding_target = None # (button_widget, action_id)
        
        self.init_ui()
        
        # Timer para detectar inputs mientras se bindea
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_input)
        self.poll_timer.start(50)

    def keyPressEvent(self, event):
        """Inyecta teclas presionadas al sistema de entrada para detección de binds."""
        if not event.isAutoRepeat():
            self.input_mgr.inject_key_event(event.key(), True)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Inyecta teclas soltadas al sistema de entrada."""
        if not event.isAutoRepeat():
            self.input_mgr.inject_key_event(event.key(), False)
        super().keyReleaseEvent(event)

    def init_ui(self):
        self.bind_buttons = []
        main_layout = QHBoxLayout(self)
        
        # --- LADO IZQUIERDO: Diagrama y Selectores ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        title = QLabel("CONFIGURACIÓN DE MANDOS")
        title.setObjectName("Title")
        subtitle = QLabel("Selecciona tu hardware y pulsa un botón para remapear.")
        subtitle.setObjectName("Subtitle")
        left_layout.addWidget(title)
        left_layout.addWidget(subtitle)
        
        header_row = QHBoxLayout()
        
        # Selector de Driver (Backend)
        drv_vbox = QVBoxLayout()
        drv_vbox.addWidget(QLabel("Driver de Entrada (Backend):"))
        self.driver_selector = QComboBox()
        self.driver_selector.addItems(self.input_mgr.get_available_drivers())
        self.driver_selector.setCurrentText(self.input_mgr.input_driver)
        self.driver_selector.currentTextChanged.connect(self.on_driver_changed)
        drv_vbox.addWidget(self.driver_selector)
        header_row.addLayout(drv_vbox)

        # Filtros de Categoría y Mando
        cat_vbox = QVBoxLayout()
        cat_vbox.addWidget(QLabel("Categoría de Dispositivo:"))
        self.cat_selector = QComboBox()
        self.cat_selector.addItems(["Teclado", "Mando Xbox", "Mando PS5", "Nintendo Joycons", "Wiimote", "DSU", "MIDI", "Serial", "Otros (Custom)"])
        cat_vbox.addWidget(self.cat_selector)
        header_row.addLayout(cat_vbox)
        
        hw_vbox = QVBoxLayout()
        hw_vbox.addWidget(QLabel("Seleccionar Hardware Detectado:"))
        self.hw_selector = QComboBox()
        hw_vbox.addWidget(self.hw_selector)
        
        dz_vbox = QVBoxLayout()
        self.dz_label = QLabel("Zona Muerta: 0.10")
        self.dz_slider = QSlider(Qt.Horizontal)
        self.dz_slider.setRange(0, 50)
        self.dz_slider.setValue(10)
        self.dz_slider.valueChanged.connect(self.on_deadzone_changed)
        dz_vbox.addWidget(self.dz_label)
        dz_vbox.addWidget(self.dz_slider)
        hw_vbox.addLayout(dz_vbox)
        
        header_row.addLayout(hw_vbox)
        
        # Conectar lógica de cascada
        self.cat_selector.currentTextChanged.connect(self.on_category_changed)
        self.hw_selector.currentIndexChanged.connect(self.on_hardware_changed)
        
        left_layout.addLayout(header_row)
        
        # Pair button
        self.btn_pair = QPushButton("EMPAREJAR WIIMOTE")
        self.btn_pair.setStyleSheet("background-color: #388E3C; color: white; padding: 8px; font-weight: bold;")
        self.btn_pair.clicked.connect(self.on_pair_clicked)
        pair_row = QHBoxLayout()
        pair_row.addStretch()
        pair_row.addWidget(self.btn_pair)
        left_layout.addLayout(pair_row)
        
        # DSU Config Row
        self.dsu_container = QWidget()
        dsu_vbox = QVBoxLayout(self.dsu_container)
        dsu_vbox.setContentsMargins(0, 0, 0, 0)
        
        dsu_title = QLabel("CONFIGURACIÓN SERVIDOR DSU (UDP)")
        dsu_title.setStyleSheet("color: #4CAF50; font-weight: bold; margin-top: 10px;")
        dsu_vbox.addWidget(dsu_title)
        
        dsu_ip_hbox = QHBoxLayout()
        dsu_ip_hbox.addWidget(QLabel("IP Servidor:"))
        self.dsu_ip_input = QLineEdit()
        self.dsu_ip_input.setPlaceholderText("127.0.0.1")
        self.dsu_ip_input.setText(self.input_mgr.custom_config.get("dsu_host", "127.0.0.1"))
        self.dsu_ip_input.textChanged.connect(self.on_dsu_config_changed)
        dsu_ip_hbox.addWidget(self.dsu_ip_input)
        
        dsu_ip_hbox.addWidget(QLabel("Puerto:"))
        self.dsu_port_input = QLineEdit()
        self.dsu_port_input.setPlaceholderText("26760")
        self.dsu_port_input.setText(str(self.input_mgr.custom_config.get("dsu_port", 26760)))
        self.dsu_port_input.setFixedWidth(80)
        self.dsu_port_input.textChanged.connect(self.on_dsu_config_changed)
        dsu_ip_hbox.addWidget(self.dsu_port_input)
        
        dsu_vbox.addLayout(dsu_ip_hbox)
        left_layout.addWidget(self.dsu_container)
        self.dsu_container.hide()
        
        # Serial Config Row
        self.serial_container = QWidget()
        serial_vbox = QVBoxLayout(self.serial_container)
        serial_vbox.setContentsMargins(0, 0, 0, 0)
        
        serial_title = QLabel("CONFIGURACIÓN SERIAL")
        serial_title.setStyleSheet("color: #4CAF50; font-weight: bold; margin-top: 10px;")
        serial_vbox.addWidget(serial_title)
        
        baud_hbox = QHBoxLayout()
        baud_hbox.addWidget(QLabel("Baudrate:"))
        self.baud_selector = QComboBox()
        self.baud_selector.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_selector.setCurrentText(str(self.input_mgr.custom_config.get("serial_baud", 115200)))
        self.baud_selector.currentTextChanged.connect(self.on_serial_config_changed)
        baud_hbox.addWidget(self.baud_selector)
        baud_hbox.addStretch()
        serial_vbox.addLayout(baud_hbox)
        
        left_layout.addWidget(self.serial_container)
        self.serial_container.hide()
        
        self.ctrl_img = QLabel()
        self.ctrl_img.setAlignment(Qt.AlignCenter)
        self.update_diagram()
        left_layout.addWidget(self.ctrl_img)
        left_layout.addStretch()
        
        # Inicializar estado inicial desde el manager (recordar último seleccionado)
        active_cat = self.input_mgr.active_category
        self.cat_selector.setCurrentText(active_cat)
        self.on_category_changed(active_cat)
        
        # Seleccionar el hardware específico guardado
        saved_hw = self.input_mgr.active_device_id
        idx = self.hw_selector.findData(saved_hw)
        if idx >= 0:
            self.hw_selector.setCurrentIndex(idx)
        
        main_layout.addWidget(left_widget, 6)
        
        # --- LADO DERECHO: Lista de Binds ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Herramientas de Limpieza
        tools_layout = QHBoxLayout()
        btn_clear = QPushButton("🗑️ Limpiar Mando Actual")
        btn_clear.clicked.connect(self.cmd_clear_current)
        
        btn_default = QPushButton("🎮 Binds por Defecto (Xbox)")
        btn_default.clicked.connect(self.cmd_default_current)
        
        btn_clear_all = QPushButton("🧨 Borrar TODOS los Mandos")
        btn_clear_all.setStyleSheet("color: #ffaaaa; border: 1px solid #aa0000;")
        btn_clear_all.clicked.connect(self.cmd_clear_all)
        
        tools_layout.addWidget(btn_clear)
        tools_layout.addWidget(btn_default)
        tools_layout.addWidget(btn_clear_all)
        right_layout.addLayout(tools_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Secciones
        self.create_section(scroll_layout, "EJES ROBOT (Articulaciones)", [
            ("Base J0 (+ Derecha)", "base_pos"),
            ("Base J0 (- Izquierda)", "base_neg"),
            ("Hombro J1 (+ Arriba)", "shoulder_pos"),
            ("Hombro J1 (- Abajo)", "shoulder_neg"),
            ("Codo J2 (+ Arriba)", "elbow_pos"),
            ("Codo J2 (- Abajo)", "elbow_neg"),
            ("Muñeca J3 (+)", "j3_pos"),
            ("Muñeca J3 (-)", "j3_neg"),
            ("Muñeca J4 (+)", "j4_pos"),
            ("Muñeca J4 (-)", "j4_neg")
        ])
        
        self.create_section(scroll_layout, "CÁMARA SIMULADOR", [
            ("Cámara X (+ Der)", "cam_x_pos"),
            ("Cámara X (- Izq)", "cam_x_neg"),
            ("Cámara Y (+ Arr)", "cam_y_pos"),
            ("Cámara Y (- Aba)", "cam_y_neg"),
            ("Zoom (+ Acercar)", "cam_zoom_pos"),
            ("Zoom (- Alejar)", "cam_zoom_neg"),
            ("Pitch (Inclinación +)", "cam_pitch_pos"),
            ("Pitch (Inclinación -)", "cam_pitch_neg"),
            ("Yaw (Giro +)", "cam_yaw_pos"),
            ("Yaw (Giro -)", "cam_yaw_neg")
        ])
        
        self.create_section(scroll_layout, "ACCIONES ADICIONALES", [
            ("Pinza Abrir", "gripper_open_pos"),
            ("Pinza Cerrar", "gripper_close_pos"),
            ("Reset Articulaciones", "reset"),
            ("Guardar Pose (Snapshot)", "snapshot"),
            ("Ocultar/Mostrar Consola", "toggle_console")
        ])
        
        scroll.setWidget(scroll_content)
        right_layout.addWidget(scroll)
        
        # Botones finales
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_save = QPushButton("GUARDAR Y CERRAR")
        btn_save.setMinimumWidth(200)
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; padding: 12px; font-weight: bold; font-size: 14px;")
        btn_save.clicked.connect(self.save_and_close)
        bottom_row.addWidget(btn_save)
        right_layout.addLayout(bottom_row)
        
        main_layout.addWidget(right_widget, 4)

    def create_section(self, layout, title, items):
        header = QLabel(title)
        header.setStyleSheet("color: #4CAF50; font-weight: bold; margin-top: 15px; border-bottom: 1px solid #333;")
        layout.addWidget(header)
        
        current_binds = self.input_mgr.get_current_binds().get("inputs", {})
        
        grid = QGridLayout()
        # Colocaremos en 2 columnas
        for i, (label, action_id) in enumerate(items):
            current_val = current_binds.get(action_id)
            btn = BindButton(label, "inputs", current_val)
            btn.action_id = action_id # Guardar para refresco
            btn.clicked.connect(lambda checked=False, b=btn, a=action_id: self.start_binding(b, a))
            
            # Conectar el botón X interno
            btn.btn_clear.clicked.connect(lambda checked=False, a=action_id: self.cmd_clear_specific(a))
            
            self.bind_buttons.append(btn)
            grid.addWidget(btn, i // 2, i % 2)
            
        layout.addLayout(grid)

    def cmd_clear_specific(self, action_id):
        """Elimina un bind específico del perfil actual."""
        current_binds = self.input_mgr.get_current_binds()
        inputs_dict = current_binds.get("inputs", {})
        if action_id in inputs_dict:
            del inputs_dict[action_id]
            print(f"[Mapper] Bind eliminado: {action_id}")
            self.refresh_all_binds()

    def cmd_clear_current(self):
        self.input_mgr.get_current_binds()["inputs"] = {}
        self.refresh_all_binds()

    def cmd_default_current(self):
        self.input_mgr.get_current_binds()["inputs"] = {
            "base_pos": {"type": "axis", "id": 0},
            "shoulder_pos": {"type": "axis", "id": 1},
            "elbow_pos": {"type": "axis", "id": 3},
            "j3_pos": {"type": "axis", "id": 4},
            "j4_pos": {"type": "axis", "id": 2},
            "gripper_open_pos": {"type": "button", "id": 0},
            "gripper_close_pos": {"type": "button", "id": 1},
            "reset": {"type": "button", "id": 7},
            "snapshot": {"type": "button", "id": 3},
            "toggle_console": {"type": "button", "id": 6}
        }
        self.refresh_all_binds()

    def cmd_clear_all(self):
        if "profiles" in self.input_mgr.custom_config:
            for dev in self.input_mgr.custom_config["profiles"]:
                self.input_mgr.custom_config["profiles"][dev]["inputs"] = {}
        self.refresh_all_binds()

    def refresh_all_binds(self):
        """Actualiza el texto de todos los botones según el dispositivo actual."""
        current_binds = self.input_mgr.get_current_binds().get("inputs", {})
        for btn in self.bind_buttons:
            btn.current_val = current_binds.get(btn.action_id)
            btn.update_text()

    def start_binding(self, btn, action_id):
        # 🔥 Vaciar historial para evitar auto-mapeos erróneos
        self.input_mgr.flush_queues()
        
        if self.binding_target:
            self.binding_target[0].set_binding(False)
        
        self.binding_target = (btn, action_id)
        btn.set_binding(True)

    def poll_input(self):
        if not self.binding_target: return
        
        input_data = self.input_mgr.get_last_input()
        if input_data:
            itype, iid = input_data
            btn, action_id = self.binding_target
            
            current_binds = self.input_mgr.get_current_binds()
            inputs_dict = current_binds.setdefault("inputs", {})
            inputs_dict[action_id] = {"type": itype, "id": iid}
            
            btn.current_val = {"type": itype, "id": iid}
            btn.set_binding(False)
            self.binding_target = None
            print(f"[Mapper] Mapeado {action_id} -> {itype} {iid} en perfil {self.input_mgr.active_device_id}")

    def on_driver_changed(self, driver_name):
        """Maneja el cambio del backend de entrada."""
        print(f"[Mapper] Cambiando driver a: {driver_name}")
        self.input_mgr.input_driver = driver_name
        # Refrescar categorías y dispositivos
        self.on_category_changed(self.cat_selector.currentText())


    def on_category_changed(self, category):
        self.hw_selector.blockSignals(True)
        self.hw_selector.clear()
        
        cats = self.input_mgr.get_categorized_devices()
        devices = cats.get(category, [])
        
        for dev in devices:
            self.hw_selector.addItem(dev["name"], dev["id"])
            
        self.hw_selector.blockSignals(False)
        
        style_map = {
            "Mando Xbox": "Xbox",
            "Mando PS5": "PS5",
            "Nintendo Joycons": "Joycons",
            "Wiimote": "Wiimote",
            "Teclado": "Keyboard",
            "DSU": "DSU",
            "MIDI": "MIDI",
            "Serial": "Serial",
            "Otros (Custom)": "Custom"
        }
        self.input_mgr.custom_config["controller_style"] = style_map.get(category, "Xbox")
        self.update_diagram()
        self.btn_pair.setVisible(category == "Wiimote")
        self.dsu_container.setVisible(category == "DSU")
        self.serial_container.setVisible(category == "Serial")
        
        if self.hw_selector.count() > 0:
            self.on_hardware_changed(0)

    def on_hardware_changed(self, index):
        category = self.cat_selector.currentText()
        device_id = self.hw_selector.currentData()
        if device_id:
            self.input_mgr.set_active_device(category, device_id)
            current_dz = self.input_mgr.get_current_binds().get("deadzone", 0.1)
            self.dz_slider.blockSignals(True)
            self.dz_slider.setValue(int(current_dz * 100))
            self.dz_slider.blockSignals(False)
            self.dz_label.setText(f"Zona Muerta: {current_dz:.2f}")
            self.refresh_all_binds()

    def on_deadzone_changed(self, value):
        dz = value / 100.0
        self.dz_label.setText(f"Zona Muerta: {dz:.2f}")
        self.input_mgr.get_current_binds()["deadzone"] = dz

    def update_diagram(self):
        style = self.input_mgr.custom_config.get("controller_style", "Xbox")
        style_map = {
            "Xbox": "controller_bg.png",
            "PS5": "ps5_bg.png",
            "Joycons": "joycons_bg.png",
            "Wiimote": "wiimote_bg.png",
            "Keyboard": "keyboard_bg.png",
            "DSU": "dsu_bg.png",
            "MIDI": "midi_bg.png",
            "Serial": "serial_bg.png",
            "Custom": "custom_bg.png"
        }
        filename = style_map.get(style, "controller_bg.png")
        img_path = os.path.join(os.path.dirname(__file__), "assets", filename)
        
        if os.path.exists(img_path):
            pix = QPixmap(img_path).scaled(550, 550, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.ctrl_img.setPixmap(pix)
        else:
            self.ctrl_img.setText(f"IMAGEN {style} NO ENCONTRADA")

    def on_dsu_config_changed(self):
        """Actualiza la configuración de DSU en tiempo real."""
        host = self.dsu_ip_input.text().strip()
        port_str = self.dsu_port_input.text().strip()
        
        try:
            port = int(port_str)
        except ValueError:
            port = 26760
            
        self.input_mgr.custom_config["dsu_host"] = host
        self.input_mgr.custom_config["dsu_port"] = port
        
        # Si DSU está activo, reiniciarlo con la nueva config
        if self.input_mgr.active_category == "DSU":
            self.input_mgr.set_active_device("DSU", "DSU")

    def on_serial_config_changed(self):
        """Actualiza la configuración de Serial en tiempo real."""
        baud_str = self.baud_selector.currentText()
        try:
            baud = int(baud_str)
        except ValueError:
            baud = 115200
            
        self.input_mgr.custom_config["serial_baud"] = baud
        
        # Si Serial está activo, reiniciarlo con la nueva config
        if self.input_mgr.active_category == "Serial":
            dev_id = self.hw_selector.currentData()
            if dev_id:
                self.input_mgr.set_active_device("Serial", dev_id)

    def on_pair_clicked(self):
        self.btn_pair.setEnabled(False)
        self.btn_pair.setText("BUSCANDO (Presiona 1+2)...")
        self.input_mgr.start_pairing(self.on_pair_finished)

    def on_pair_finished(self, success):
        self.btn_pair.setEnabled(True)
        if success:
            self.btn_pair.setText("WIIMOTE CONECTADO ✓")
            self.on_category_changed("Wiimote")
            self.cat_selector.setCurrentText("Wiimote")
        else:
            self.btn_pair.setText("FALLÓ (REINTENTAR)")

    def save_and_close(self):
        self.input_mgr.save_custom_mapping()
        self.accept()
