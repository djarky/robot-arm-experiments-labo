import json
import os
import time
import threading

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

try:
    import evdev
    from evdev import ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False


import subprocess
import socket
import struct


class DSUClient:
    """Implementación mínima del protocolo DSU (Cemuhook) para recibir datos de sensores."""
    def __init__(self, port=26760):
        self.port = port
        self.active = False
        self.data = {"accel": [0.0, 0.0, 0.0], "buttons": {}}
        self.sock = None
        self._thread = None

    def start(self):
        if self.active: return
        self.active = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind(('0.0.0.0', self.port))
            self.sock.settimeout(1.0)
            self._thread = threading.Thread(target=self._listen, daemon=True)
            self._thread.start()
            print(f"[DSU] Listening on port {self.port}")
        except Exception as e:
            print(f"[DSU] Error binding to port {self.port}: {e}")
            self.active = False

    def _listen(self):
        while self.active:
            try:
                data, addr = self.sock.recvfrom(1024)
                if len(data) < 16: continue
                # Parsear cabecera mínima
                # Magic: data[0:4] == b'DSUS'
                # Type: data[16:20]
                msg_type = struct.unpack("<I", data[16:20])[0]
                if msg_type == 0x100002: # Data message
                    # Mapeo crudo de acelerómetros (típico en byte 44 en adelante)
                    # Esto varía según el servidor, simplificamos:
                    if len(data) >= 80:
                        accel_x = struct.unpack("<f", data[70:74])[0]
                        accel_y = struct.unpack("<f", data[74:78])[0]
                        accel_z = struct.unpack("<f", data[78:82])[0]
                        self.data["accel"] = [accel_x, accel_y, accel_z]
            except socket.timeout:
                continue
            except Exception:
                break

    def stop(self):
        self.active = False
        if self.sock: self.sock.close()

class InputManager:
    """
    Gestor Universal de Entradas para el Laboratorio de Experimentos.
    Soporta perfiles de mando, remapeo y simulación de sensores avanzados.
    """
    
    # Perfiles predeterminados
    PROFILES = {
        "Xbox": {
            "axes": {"base": 0, "shoulder": 1, "elbow": 3, "j3": 4},
            "buttons": {"gripper_open": 0, "gripper_close": 1, "reset": 7},
            "deadzone": 0.1
        },
        "DualShock": {
            "axes": {"base": 0, "shoulder": 1, "elbow": 2, "j3": 5},
            "buttons": {"gripper_open": 1, "gripper_close": 2, "reset": 9},
            "deadzone": 0.1
        },
        "Joycons": {
            "axes": {"base": 0, "shoulder": 1, "elbow": 2, "j3": 3},
            "buttons": {"gripper_open": 0, "gripper_close": 1, "reset": 4},
            "deadzone": 0.1
        },
        "Wiimote": {
            "axes": {"accel_x": 0, "accel_y": 1, "accel_z": 2},
            "buttons": {"A": 304, "B": 305, "1": 257, "2": 258},
            "deadzone": 0.05
        }
    }

    def __init__(self):
        # Configuración persistente
        self.custom_mapping_path = os.path.join(os.path.dirname(__file__), "custom_mapping.json")
        self.active_category = "Teclado" # Valores por defecto
        self.active_device_id = "KM"
        self.custom_config = {
            "profiles": {}, # { "device_id": { "axes": {}, "buttons": {} } }
            "active_category": "Teclado",
            "active_device_id": "KM"
        }
        self.load_custom_mapping()
        
        # Sincronizar estado inicial desde config cargada
        self.active_category = self.custom_config.get("active_category", "Teclado")
        self.active_device_id = self.custom_config.get("active_device_id", "KM")

        self.joystick = None
        self.initialized = False
        
        # Wiimote / Evdev state
        self.wiimote_nodes = []    # Lista de dispositivos evdev (Botones, Accel, etc.)
        self.wiimote_active = False
        self.wiimote_state = {"accel": [0.0, 0.0, 0.0], "buttons": {}}
        self.is_pairing = False
        
        # New Inputs
        self.dsu_client = DSUClient()
        self.available_devices = []

        if PYGAME_AVAILABLE:
            pygame.init()
            pygame.joystick.init()
            self._refresh_joysticks()

    def _refresh_joysticks(self):
        if not PYGAME_AVAILABLE: return
        
        count = pygame.joystick.get_count()
        if count > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"[Input] Mando detectado: {self.joystick.get_name()}")
            self.initialized = True
        else:
            self.joystick = None
            self.initialized = False

    def get_arm_inputs(self):
        """
        Retorna los valores de control para el brazo (-1.0 a 1.0) según el dispositivo activo.
        """
        if self.active_device_id == "Wiimote":
            return self._get_wiimote_inputs()
        elif self.active_device_id == "KM":
            return self._get_keyboard_mouse_inputs()
        elif self.active_device_id == "DSU":
            return self._get_dsu_inputs(), {}

        # Default: Gamepad

        if not self.initialized or not self.joystick:
            # Fallback a búsqueda de mandos
            pygame.event.pump()
            if pygame.joystick.get_count() > 0:
                self._refresh_joysticks()
            return [0.0] * 6, {}

        pygame.event.pump()
        
        inputs = {
            "base": self._get_axis("base"),
            "shoulder": self._get_axis("shoulder"),
            "elbow": self._get_axis("elbow"),
            "j3": self._get_axis("j3"),
            "j4": self._get_axis("j4"),
            "j5": self._get_axis("j5"),
            "gripper": 0.0
        }
        
        if self._get_button("gripper_open"): inputs["gripper"] = 1.0
        if self._get_button("gripper_close"): inputs["gripper"] = -1.0
        
        # Acciones especiales (retornamos como un diccionario extra si es necesario)
        actions = {
            "snapshot": self._get_button("snapshot"),
            "reset": self._get_button("reset"),
            "toggle_console": self._get_button("toggle_console")
        }
        
        return list(inputs.values()), actions

    def _get_wiimote_inputs(self):
        """Lee eventos de todos los nodos vinculados al Wiimote (Botones + Accel)."""
        if not self.wiimote_active or not self.wiimote_nodes: 
            return [0.0] * 6, {}
            
        # Vaciar colas de eventos de todos los dispositivos abiertos
        for dev in self.wiimote_nodes:
            try:
                for event in dev.read():
                    if event.type == ecodes.EV_ABS:
                        # Calibración para hid-wiimote (rango detectado: -500 a 500)
                        if event.code == ecodes.ABS_RX: self.wiimote_state["accel"][0] = event.value / 500.0
                        elif event.code == ecodes.ABS_RY: self.wiimote_state["accel"][1] = event.value / 500.0
                        elif event.code == ecodes.ABS_RZ: self.wiimote_state["accel"][2] = event.value / 500.0
                    elif event.type == ecodes.EV_KEY:
                        self.wiimote_state["buttons"][event.code] = event.value
            except (BlockingIOError, OSError):
                continue

        accel = self.wiimote_state["accel"]
        # Mapeo: Inclinación X -> Base, Y -> Hombro
        # Nota: Multiplicamos por sensibilidad o usamos deadzone si es necesario
        return [accel[0], accel[1], 0.0, 0.0, 0.0, 0.0], {}

    def _get_axis(self, name):
        axis_id = self.config["axes"].get(name)
        if axis_id is None: return 0.0
        
        val = self.joystick.get_axis(axis_id)
        if abs(val) < self.config["deadzone"]:
            return 0.0
        return val

    def _get_button(self, name):
        btn_id = self.config["buttons"].get(name)
        if btn_id is None: return False
        return self.joystick.get_button(btn_id)

    def set_profile(self, profile_name):
        if profile_name in self.PROFILES:
            self.active_profile = profile_name
            self.config = self.PROFILES[profile_name]
            print(f"[Input] Perfil cambiado a: {profile_name}")
        elif profile_name == "Custom":
            self.active_profile = "Custom"
            self.config = self.custom_config
            print(f"[Input] Perfil cambiado a: Custom")

    def load_custom_mapping(self):
        if os.path.exists(self.custom_mapping_path):
            try:
                with open(self.custom_mapping_path, "r") as f:
                    self.custom_config = json.load(f)
                self.PROFILES["Custom"] = self.custom_config
            except Exception as e:
                print(f"[Input] Error cargando custom_mapping: {e}")
                self._reset_custom_config()
        else:
            self._reset_custom_config()

    def _reset_custom_config(self):
        self.custom_config = {
            "axes": {
                "base": 0, "shoulder": 1, "elbow": 3, "j3": 4, "j4": 2, "j5": 5
            },
            "buttons": {
                "gripper_open": 0, "gripper_close": 1, "reset": 7,
                "snapshot": 3, "toggle_console": 6
            },
            "deadzone": 0.1,
            "controller_style": "Xbox"
        }
        self.PROFILES["Custom"] = self.custom_config

    def get_current_binds(self):
        """Retorna el sub-diccionario de binds para el dispositivo activo."""
        dev_id = self.active_device_id
        if "profiles" not in self.custom_config: self.custom_config["profiles"] = {}
        
        if dev_id not in self.custom_config["profiles"]:
            # Inicializar perfil vacío para este hardware
            self.custom_config["profiles"][dev_id] = {"axes": {}, "buttons": {}}
            
        return self.custom_config["profiles"][dev_id]

    def save_custom_mapping(self, path=None):
        if path is None: path = self.custom_mapping_path
        
        # Actualizar estado global antes de guardar
        self.custom_config["active_category"] = self.active_category
        self.custom_config["active_device_id"] = self.active_device_id
        
        with open(path, "w") as f:
            json.dump(self.custom_config, f, indent=4)
        print(f"[Input] Configuración de perfiles guardada en {path}")

    def get_last_input(self):
        """
        Detecta y retorna el primer input (eje o botón) en CUALQUIERA de los dispositivos
        activos o candidatos (Teclado, Mando, Wiimote).
        Retorna: (type, id) o None
        """
        pygame.event.pump()
        
        # 1. Check Keyboard (Prioridad si estamos mapeando teclado)
        keys = pygame.key.get_pressed()
        for k in range(len(keys)):
            if keys[k]:
                # Retornamos el nombre de la constante para que sea legible
                return ("button", k)

        # 2. Check Joysticks (Si hay alguno inicializado)
        if self.joystick:
            # Check buttons
            for i in range(self.joystick.get_numbuttons()):
                if self.joystick.get_button(i):
                    return ("button", i)
            # Check axes
            for i in range(self.joystick.get_numaxes()):
                val = self.joystick.get_axis(i)
                if abs(val) > 0.5:
                    return ("axis", i)

        # 3. Check Wiimote (Si hay nodos evdev)
        if self.wiimote_active:
            for dev in self.wiimote_nodes:
                try:
                    event = dev.read_one()
                    if event and event.value == 1: # Botón presionado
                        if event.type == ecodes.EV_KEY:
                            return ("button", event.code)
                except: pass

        return None
        
        return None

    # --- MOCKS ---
    def update_udp_motion(self, data):
        """Mock para recibir datos de acelerómetro vía UDP (Smartphone/Dolphin)"""
        self.motion_data = data
        
    def _get_keyboard_mouse_inputs(self):
        """Captura teclado y mouse con mapeo extendido para los 6 ejes."""
        if not PYGAME_AVAILABLE: return [0.0]*6
        pygame.event.pump()
        keys = pygame.key.get_pressed()
        
        # Mouse rel para Base/Hombro
        # Sensibilidad: un movimiento de 20px -> 1.0 de velocidad
        mouse_rel = pygame.mouse.get_rel()
        base = max(-1.0, min(1.0, mouse_rel[0] / 10.0))
        shoulder = max(-1.0, min(1.0, -mouse_rel[1] / 10.0))
        
        inputs = [base, shoulder, 0.0, 0.0, 0.0, 0.0]
        
        # J2 (Codo): Q / E o Rueda Mouse (si pygame captura eventos wheel)
        if keys[pygame.K_q]: inputs[2] = -1.0
        if keys[pygame.K_e]: inputs[2] = 1.0
        
        # J3 (Muñeca 1): R / F
        if keys[pygame.K_r]: inputs[3] = 1.0
        if keys[pygame.K_f]: inputs[3] = -1.0
        
        # J4 (Muñeca 2): T / G
        if keys[pygame.K_t]: inputs[4] = 1.0
        if keys[pygame.K_g]: inputs[4] = -1.0
        
        # J5 (Muñeca 3): Y / H
        if keys[pygame.K_y]: inputs[5] = 1.0
        if keys[pygame.K_h]: inputs[5] = -1.0
        
        # Pinza: Botones ratón
        mouse_btns = pygame.mouse.get_pressed()
        actions = {
            "gripper_open": mouse_btns[0],  # Click izquierdo
            "gripper_close": mouse_btns[2] # Click derecho
        }
        
        return inputs, actions

    def _get_dsu_inputs(self):
        """Retorna datos del cliente DSU."""
        if not self.dsu_client.active: self.dsu_client.start()
        accel = self.dsu_client.data["accel"]
        return [accel[0], accel[1], 0.0, 0.0, 0.0, 0.0]

    def get_categorized_devices(self):
        """Retorna dispositivos agrupados por categorías para el Mapper."""
        categories = {
            "Mando Xbox": [],
            "Mando PS5": [],
            "Nintendo Joycons": [],
            "Wiimote": [],
            "Teclado": [{"id": "KM", "name": "Teclado y Mouse Universal"}],
            "DSU": [{"id": "DSU", "name": "DSU (Control vía Red)"}],
            "Otros (Custom)": []
        }
        
        detected_phys = set() # Para evitar duplicados entre evdev y pygame
        
        # 1. Evdev Scan (Más preciso para Hardware IDs)
        if EVDEV_AVAILABLE:
            try:
                for path in evdev.list_devices():
                    dev = evdev.InputDevice(path)
                    dinfo = {"id": path, "name": dev.name}
                    
                    # Clasificación por nombre/vendor
                    lower_name = dev.name.lower()
                    if "nintendo" in lower_name or "rvl" in lower_name:
                        categories["Wiimote"].append(dinfo)
                    elif "xbox" in lower_name or dev.info.vendor == 0x045e:
                        categories["Mando Xbox"].append(dinfo)
                    elif "dualsense" in lower_name or "dualshock" in lower_name or dev.info.vendor == 0x054c:
                        categories["Mando PS5"].append(dinfo)
                    elif "joy-con" in lower_name:
                        categories["Nintendo Joycons"].append(dinfo)
                    else:
                        categories["Otros (Custom)"].append(dinfo)
                    
                    detected_phys.add(path)
            except: pass

        # 2. Pygame fallback for gamepads not caught or for generic names
        if PYGAME_AVAILABLE:
            pygame.joystick.init()
            for i in range(pygame.joystick.get_count()):
                joy = pygame.joystick.Joystick(i)
                name = joy.get_name().lower()
                jid = f"JOY_{i}"
                dinfo = {"id": jid, "name": f"Gamepad {i}: {joy.get_name()}"}
                
                # Intentar clasificar si no se hizo por evdev
                skip = False
                # Aquí podrías intentar buscar si el nombre ya está en alguna categoría para ser más agresivo
                
                if "xbox" in name: categories["Mando Xbox"].append(dinfo)
                elif "ps5" in name or "sony" in name: categories["Mando PS5"].append(dinfo)
                elif "joy-con" in name: categories["Nintendo Joycons"].append(dinfo)
                else:
                    # Solo añadir a custom si no lo vimos en evdev (heurística por nombre similar)
                    if not any(d["name"] == joy.get_name() for cat in categories.values() for d in cat):
                        categories["Otros (Custom)"].append(dinfo)

        # Eliminar categorías vacías (opcional, pero mejor dejarlas para la UI)
        return categories

    def set_active_device(self, category, device_id):
        """Configura el dispositivo activo basándose en categoría e ID."""
        self.active_category = category
        self.active_device_id = device_id
        
        print(f"[Input] Activando {category} -> {device_id}")

        if category == "Wiimote":
            self.connect_wiimote()
        elif category == "DSU":
            self.dsu_client.start()
        elif category == "Teclado":
            pass # KM captured directly
        elif str(device_id).startswith("JOY_"):
            try:
                idx = int(str(device_id).split("_")[1])
                pygame.joystick.init()
                self.joystick = pygame.joystick.Joystick(idx)
                self.joystick.init()
                self.initialized = True
            except: pass
        elif str(device_id).startswith("/dev/input/"):
            # Modo rudo evdev
            try:
                pygame.joystick.init() # Intentar re-init general
                self.initialized = False # Por ahora preferimos pygame para el loop principal
            except: pass

    def start_pairing(self, callback=None):
        """Fase 1: Escanear vía bluetoothctl. Fase 2: Detectar nodos udev."""
        if self.is_pairing: return
        self.is_pairing = True
        
        def run():
            found = False
            print("[Input] Iniciando escaneo de Wiimotes...")
            try:
                # Intento de automatizar el pairing si es necesario
                subprocess.run(["bluetoothctl", "--timeout", "10", "scan", "on"], capture_output=True)
                # Esperar un momento a que el driver cargue los nodos
                time.sleep(2)
                found = self.connect_wiimote()
            except Exception as e:
                print(f"[Input] Error en pairing: {e}")
            
            self.is_pairing = False
            if callback: callback(found)

        threading.Thread(target=run, daemon=True).start()

    def connect_wiimote(self):
        """Busca y agrega todos los nodos (Botones, Accel, IR) del Wiimote detectado."""
        if not EVDEV_AVAILABLE: return False
        
        self.wiimote_nodes = []
        try:
            device_paths = evdev.list_devices()
            devices = [evdev.InputDevice(p) for p in device_paths]
            
            # Buscamos patrones comunes de nombre: RVL, Nintendo, Remote, etc.
            potential_nodes = [d for d in devices if "Nintendo" in d.name and ("RVL" in d.name or "Remote" in d.name)]
            
            if potential_nodes:
                # Agrupamos por el ID físico (phys) para asegurarnos que pertenecen al mismo mando
                first_phys = potential_nodes[0].phys
                self.wiimote_nodes = [d for d in potential_nodes if d.phys == first_phys]
                self.wiimote_active = True
                print(f"[Input] Wiimote detectado con {len(self.wiimote_nodes)} nodos (Phys: {first_phys})")
                return True
        except Exception as e:
            print(f"[Input] Error detectando nodos: {e}")

        return False
