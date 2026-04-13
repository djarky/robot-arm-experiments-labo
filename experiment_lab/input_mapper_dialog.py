import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QWidget, QFrame, QGridLayout, QComboBox, QScrollArea, QCheckBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QFont, QPalette, QColor

class BindButton(QPushButton):
    """Botón especializado que muestra la acción y el bind actual."""
    def __init__(self, action_name, key_name, current_val, parent=None):
        super().__init__(parent)
        self.action_name = action_name
        self.key_name = key_name # 'axes' o 'buttons'
        self.current_val = current_val
        self.is_binding = False
        self.update_text()
        
        self.setMinimumWidth(180)
        self.setStyleSheet("""
            QPushButton {
                background-color: #252525;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 10px;
                color: #ddd;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #333;
                border: 1px solid #4CAF50;
            }
        """)

    def update_text(self):
        val_str = "SIN ASIGNAR"
        if isinstance(self.current_val, dict):
            t = self.current_val.get("type", "bt")
            i = self.current_val.get("id", "?")
            val_str = f"{t.capitalize()} {i}"
        elif self.current_val is not None:
            val_str = str(self.current_val)
            
        if self.is_binding:
            self.setText(f"{self.action_name}\n>>> PRESIONA INPUT <<<")
            self.setStyleSheet(self.styleSheet() + "border: 1px solid #ff9800; background-color: #3e2723;")
        else:
            self.setText(f"{self.action_name}\n{val_str}")
            self.setStyleSheet(self.styleSheet().replace("border: 1px solid #ff9800; background-color: #3e2723;", ""))

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

        self.binding_target = None # (button_widget, action_name, key_type)
        
        self.init_ui()
        
        # Timer para detectar inputs mientras se bindea
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_input)
        self.poll_timer.start(50)

    def init_ui(self):
        self.bind_buttons = [] # Inicializar antes de que las señales disparen callbacks
        main_layout = QHBoxLayout(self)
        
        # --- LADO IZQUIERDO: Diagrama ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        header_row = QHBoxLayout()
        title_vbox = QVBoxLayout()
        title = QLabel("REMAPEO DE MANDOS")
        title.setObjectName("Title")
        subtitle = QLabel("Configura ejes, botones y estilo visual.")
        subtitle.setObjectName("Subtitle")
        title_vbox.addWidget(title)
        title_vbox.addWidget(subtitle)
        header_row.addLayout(title_vbox)
        
        header_row.addStretch()
        
        # Inicializar widgets que se usan en las callbacks
        self.ctrl_img = QLabel()
        self.ctrl_img.setAlignment(Qt.AlignCenter)
        
        self.btn_pair = QPushButton("CONECTAR WIIMOTE (PAIR)")
        self.btn_pair.setMinimumHeight(40)
        self.btn_pair.setStyleSheet("""
            QPushButton {
                background-color: #388E3C;
                color: white;
                font-weight: bold;
                padding: 10px 30px;
                border-radius: 4px;
            }
            QPushButton:disabled { background-color: #555; }
        """)
        self.btn_pair.clicked.connect(self.on_pair_clicked)
        
        # --- Categoría (Nivel 1) ---
        cat_vbox = QVBoxLayout()
        cat_label = QLabel("Categoría:")
        cat_label.setStyleSheet("font-size: 10px; color: #888;")
        self.cat_selector = QComboBox()
        categories = [
            "Mando Xbox", "Mando PS5", "Nintendo Joycons", 
            "Wiimote", "Teclado", "DSU", "Otros (Custom)"
        ]
        self.cat_selector.addItems(categories)
        
        # Cargar categoría guardada
        saved_cat = self.input_mgr.active_category
        if saved_cat in categories:
            self.cat_selector.setCurrentText(saved_cat)
            
        cat_vbox.addWidget(cat_label)
        cat_vbox.addWidget(self.cat_selector)
        header_row.addLayout(cat_vbox)

        # --- Hardware / Dispositivo (Nivel 2) ---
        hw_vbox = QVBoxLayout()
        hw_label = QLabel("Dispositivo Físico:")
        hw_label.setStyleSheet("font-size: 10px; color: #888;")
        self.hw_selector = QComboBox()
        self.hw_selector.currentIndexChanged.connect(self.on_hardware_changed)
        hw_vbox.addWidget(hw_label)
        hw_vbox.addWidget(self.hw_selector)
        
        self.chk_raw = QCheckBox("Forzar Lectura RAW UDEV")
        self.chk_raw.setChecked(self.input_mgr.custom_config.get("force_raw_udev", False))
        self.chk_raw.toggled.connect(self.on_raw_toggled)
        hw_vbox.addWidget(self.chk_raw)
        
        header_row.addLayout(hw_vbox)

        # Conectar lógica de cascada
        self.cat_selector.currentTextChanged.connect(self.on_category_changed)
        self.hw_selector.currentIndexChanged.connect(self.on_hardware_changed)
        
        # Inicializar estado inicial
        self.on_category_changed(self.cat_selector.currentText())
        
        # Seleccionar hardware guardado si existe en la lista
        saved_hw = self.input_mgr.active_device_id
        idx = self.hw_selector.findData(saved_hw)
        if idx >= 0:
            self.hw_selector.setCurrentIndex(idx)
        
        left_layout.addLayout(header_row)
        
        # layout del pair button
        pair_row = QHBoxLayout()
        pair_row.addStretch()
        pair_row.addWidget(self.btn_pair)
        left_layout.addLayout(pair_row)
        
        # Añadir imagen del diagrama
        self.update_diagram()
        left_layout.addWidget(self.ctrl_img)
        left_layout.addStretch()
        
        main_layout.addWidget(left_widget, 6)
        
        # --- LADO DERECHO: Lista de Binds (con Scroll) ---
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
            ("Muñeca J4 (-)", "j4_neg"),
            ("Muñeca J5 (+)", "j5_pos"),
            ("Muñeca J5 (-)", "j5_neg")
        ])
        
        self.create_section(scroll_layout, "CÁMARA SIMULADOR", [
            ("Cámara X (+ Der)", "cam_x_pos"),
            ("Cámara X (- Izq)", "cam_x_neg"),
            ("Cámara Y (+ Arr)", "cam_y_pos"),
            ("Cámara Y (- Aba)", "cam_y_neg"),
            ("Cámara Z (+ Fte)", "cam_z_pos"),
            ("Cámara Z (- Atr)", "cam_z_neg"),
            ("Zoom (+)", "cam_zoom_pos"),
            ("Zoom (-)", "cam_zoom_neg"),
            ("Pitch (+) Inclinación", "cam_pitch_pos"),
            ("Pitch (-) Inclinación", "cam_pitch_neg"),
            ("Yaw (+) Giro", "cam_yaw_pos"),
            ("Yaw (-) Giro", "cam_yaw_neg"),
            ("Roll (+) Ladeo", "cam_roll_pos"),
            ("Roll (-) Ladeo", "cam_roll_neg")
        ])
        
        self.create_section(scroll_layout, "BOTONES (Pinza)", [
            ("Abrir Pinza", "gripper_open_pos"),
            ("Cerrar Pinza", "gripper_close_pos")
        ])
        
        self.create_section(scroll_layout, "ACCIONES RÁPIDAS", [
            ("Snapshot (Foto)", "snapshot"),
            ("Reset Posición", "reset"),
            ("Toggle Consola", "toggle_console")
        ])
        
        scroll.setWidget(scroll_content)
        right_layout.addWidget(scroll)
        
        # Botones inferiores
        bottom_btns = QHBoxLayout()
        btn_save = QPushButton("GUARDAR Y SALIR")
        btn_save.setStyleSheet("background-color: #2e7d32; padding: 10px; font-weight: bold;")
        btn_save.clicked.connect(self.save_and_close)
        
        btn_cancel = QPushButton("CANCELAR")
        btn_cancel.setStyleSheet("background-color: #c62828; padding: 10px;")
        btn_cancel.clicked.connect(self.reject)
        
        bottom_btns.addWidget(btn_cancel)
        bottom_btns.addWidget(btn_save)
        right_layout.addLayout(bottom_btns)
        
        main_layout.addWidget(right_widget, 4)

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
            "j5_pos": {"type": "axis", "id": 5},
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
            self.bind_buttons.append(btn)
            grid.addWidget(btn, i // 2, i % 2)
            
        layout.addLayout(grid)

    def refresh_all_binds(self):
        """Actualiza el texto de todos los botones según el dispositivo actual."""
        current_binds = self.input_mgr.get_current_binds().get("inputs", {})
        for btn in self.bind_buttons:
            btn.current_val = current_binds.get(btn.action_id)
            btn.update_text()

    def start_binding(self, btn, action_id):
        # 🔥 Vaciar historial para evitar auto-mapeos erróneos
        self.input_mgr.flush_queues()
        
        # Reset anterior si lo había
        if self.binding_target:
            self.binding_target[0].set_binding(False)
        
        self.binding_target = (btn, action_id)
        btn.set_binding(True)

    def poll_input(self):
        if not self.binding_target: return
        
        # Obtenemos el input actual del manager (quien ahora escucha todo)
        input_data = self.input_mgr.get_last_input()
        if input_data:
            itype, iid = input_data
            btn, action_id = self.binding_target
            
            # Guardamos en el perfil del dispositivo activo unificado
            current_binds = self.input_mgr.get_current_binds()
            inputs_dict = current_binds.setdefault("inputs", {})
            inputs_dict[action_id] = {"type": itype, "id": iid}
            
            btn.current_val = {"type": itype, "id": iid}
            
            btn.set_binding(False)
            self.binding_target = None
            print(f"[Mapper] Mapeado {action_id} -> {itype} {iid} en perfil {self.input_mgr.active_device_id}")

    def refresh_hardware_list(self):
        """Puebla la lista con el hardware real conectado."""
        self.hw_selector.clear()
        devices = self.input_mgr.get_available_devices()
        for dev in devices:
            self.hw_selector.addItem(dev["name"], dev["id"])

    def on_hardware_selected(self):
        """Al elegir hardware manualmente, forzamos al InputManager."""
        device_id = self.hw_selector.currentData()
        if device_id:
            self.input_mgr.set_active_device(device_id)
            print(f"[Mapper] Hardware seleccionado manualmente: {device_id}")

    def on_raw_toggled(self, checked):
        self.input_mgr.custom_config["force_raw_udev"] = checked
        self.on_category_changed(self.cat_selector.currentText())

    def on_category_changed(self, category):
        """Puebla el segundo dropdown basado en la categoría elegida."""
        self.hw_selector.blockSignals(True)
        self.hw_selector.clear()
        
        force_raw = self.chk_raw.isChecked()
        cats = self.input_mgr.get_categorized_devices(force_raw=force_raw)
        devices = cats.get(category, [])
        
        for dev in devices:
            self.hw_selector.addItem(dev["name"], dev["id"])
            
        self.hw_selector.blockSignals(False)
        
        # Trigger visual layout
        style_map = {
            "Mando Xbox": "Xbox",
            "Mando PS5": "PS5",
            "Nintendo Joycons": "Joycons",
            "Wiimote": "Wiimote",
            "Teclado": "Keyboard",
            "DSU": "DSU",
            "Otros (Custom)": "Xbox"
        }
        self.input_mgr.custom_config["controller_style"] = style_map.get(category, "Xbox")
        self.update_diagram()
        
        # Visibilidad del botón Pairing
        self.btn_pair.setVisible(category == "Wiimote")
        
        # Seleccionar el primero por defecto si hay
        if self.hw_selector.count() > 0:
            self.on_hardware_changed(0)

    def on_hardware_changed(self, index):
        """Actualiza el manager cuando se selecciona un dispositivo físico."""
        category = self.cat_selector.currentText()
        device_id = self.hw_selector.currentData()
        if device_id:
            self.input_mgr.set_active_device(category, device_id)
            self.refresh_all_binds() # Refrescar botones al cambiar hardware
            print(f"[Mapper] Hardware activado: {category} -> {device_id}")

    def update_diagram(self):
        style = self.input_mgr.custom_config.get("controller_style", "Xbox")
        
        style_map = {
            "Xbox": "controller_bg.png",
            "PS5": "ps5_bg.png",
            "Joycons": "joycons_bg.png",
            "Wiimote": "wiimote_bg.png",
            "Keyboard": "keyboard_bg.png",
            "DSU": "controller_bg.png"
        }
        
        filename = style_map.get(style, "controller_bg.png")
        img_path = os.path.join(os.path.dirname(__file__), "assets", filename)
        
        if os.path.exists(img_path):
            pix = QPixmap(img_path).scaled(550, 550, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.ctrl_img.setPixmap(pix)
        else:
            self.ctrl_img.setText(f"IMAGEN {style} NO ENCONTRADA")
            self.ctrl_img.setStyleSheet("color: red; border: 1px dashed red;")

    def on_pair_clicked(self):
        self.btn_pair.setEnabled(False)
        self.btn_pair.setText("BUSCANDO (Presiona 1+2)...")
        self.input_mgr.start_pairing(self.on_pair_finished)

    def on_pair_finished(self, success):
        self.btn_pair.setEnabled(True)
        if success:
            self.btn_pair.setText("WIIMOTE CONECTADO ✓")
            self.btn_pair.setStyleSheet(self.btn_pair.styleSheet().replace("#388E3C", "#1565C0")) # Cambiar a azul
            self.on_category_changed("Wiimote") # Auto-cambiar estilo
            self.cat_selector.setCurrentText("Wiimote")
        else:
            self.btn_pair.setText("FALLÓ (REINTENTAR)")
            self.btn_pair.setStyleSheet(self.btn_pair.styleSheet().replace("#388E3C", "#c62828")) # Rojo

    def save_and_close(self):
        self.input_mgr.save_custom_mapping()
        self.accept()
