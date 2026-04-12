import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QWidget, QFrame, QGridLayout, QComboBox, QScrollArea
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
        prefix = "Eje" if self.key_name == "axes" else "Botón"
        val_str = f"{prefix} {self.current_val}" if self.current_val is not None else "SIN ASIGNAR"
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
        hw_vbox.addWidget(hw_label)
        hw_vbox.addWidget(self.hw_selector)
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
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Secciones
        self.create_section(scroll_layout, "EJES (Articulaciones)", "axes", [
            ("Base (J0)", "base"),
            ("Hombro (J1)", "shoulder"),
            ("Codo (J2)", "elbow"),
            ("Muñeca J3", "j3"),
            ("Muñeca J4", "j4"),
            ("Muñeca J5", "j5")
        ])
        
        self.create_section(scroll_layout, "BOTONES (Pinza)", "buttons", [
            ("Abrir Pinza", "gripper_open"),
            ("Cerrar Pinza", "gripper_close")
        ])
        
        self.create_section(scroll_layout, "ACCIONES RÁPIDAS", "buttons", [
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

    def create_section(self, layout, title, key_type, items):
        header = QLabel(title)
        header.setStyleSheet("color: #4CAF50; font-weight: bold; margin-top: 15px; border-bottom: 1px solid #333;")
        layout.addWidget(header)
        
        current_binds = self.input_mgr.get_current_binds()
        
        grid = QGridLayout()
        for i, (label, action_id) in enumerate(items):
            current_val = current_binds[key_type].get(action_id)
            btn = BindButton(label, key_type, current_val)
            btn.action_id = action_id # Guardar para refresco
            btn.clicked.connect(lambda checked=False, b=btn, a=action_id, k=key_type: self.start_binding(b, a, k))
            self.bind_buttons.append(btn)
            grid.addWidget(btn, i // 1, i % 1)
            
        layout.addLayout(grid)

    def refresh_all_binds(self):
        """Actualiza el texto de todos los botones según el dispositivo actual."""
        current_binds = self.input_mgr.get_current_binds()
        for btn in self.bind_buttons:
            btn.current_val = current_binds[btn.key_name].get(btn.action_id)
            btn.update_text()

    def start_binding(self, btn, action_id, key_type):
        # Reset anterior si lo había
        if self.binding_target:
            self.binding_target[0].set_binding(False)
        
        self.binding_target = (btn, action_id, key_type)
        btn.set_binding(True)

    def poll_input(self):
        if not self.binding_target: return
        
        # Obtenemos el input actual del manager (quien ahora escucha todo)
        input_data = self.input_mgr.get_last_input()
        if input_data:
            itype, iid = input_data
            btn, action_id, key_type = self.binding_target
            
            # Guardamos en el perfil del dispositivo activo
            current_binds = self.input_mgr.get_current_binds()
            current_binds[key_type][action_id] = iid
            
            btn.current_val = iid
            btn.key_name = "axes" if itype == "axis" else "buttons"
            
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

    def on_category_changed(self, category):
        """Puebla el segundo dropdown basado en la categoría elegida."""
        self.hw_selector.blockSignals(True)
        self.hw_selector.clear()
        
        cats = self.input_mgr.get_categorized_devices()
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
