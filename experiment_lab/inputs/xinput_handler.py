"""
xinput_handler.py — Handler de entrada para mandos de Xbox en Windows vía XInput.
"""

import os
import ctypes
from .base import BaseInputHandler

class XInputHandler(BaseInputHandler):
    def __init__(self):
        self.lib = None
        self.device_index = 0
        self.initialized = False
        self.state = None

    def activate(self, device_id, **kwargs):
        if os.name != 'nt':
            print("[XInput] Error: Solo disponible en Windows.")
            return

        try:
            self.lib = ctypes.windll.xinput1_4
        except Exception:
            try:
                self.lib = ctypes.windll.xinput1_3
            except Exception:
                print("[XInput] Error: No se encontró xinput DLL.")
                return

        if str(device_id).startswith("XIN_"):
            self.device_index = int(device_id.split("_")[1])
            self.initialized = True
            print(f"[XInput] Activado mando {self.device_index}")

    def poll(self):
        if not self.initialized: return
        
        class XINPUT_GAMEPAD(ctypes.Structure):
            _fields_ = [
                ("wButtons", ctypes.c_ushort),
                ("bLeftTrigger", ctypes.c_ubyte),
                ("bRightTrigger", ctypes.c_ubyte),
                ("sThumbLX", ctypes.c_short),
                ("sThumbLY", ctypes.c_short),
                ("sThumbRX", ctypes.c_short),
                ("sThumbRY", ctypes.c_short),
            ]

        class XINPUT_STATE(ctypes.Structure):
            _fields_ = [
                ("dwPacketNumber", ctypes.c_uint),
                ("Gamepad", XINPUT_GAMEPAD),
            ]

        state = XINPUT_STATE()
        res = self.lib.XInputGetState(self.device_index, ctypes.byref(state))
        if res == 0:
            self.state = state.Gamepad
        else:
            self.state = None

    def read_bind(self, bind, deadzone=0.1):
        if not self.state: return 0.0
        
        itype = bind.get("type")
        iid = bind.get("id")
        
        if itype == "axis":
            # Mapeo de ejes XInput
            axes = {
                0: self.state.sThumbLX / 32767.0,
                1: self.state.sThumbLY / 32767.0,
                2: self.state.sThumbRX / 32767.0,
                3: self.state.sThumbRY / 32767.0,
                4: self.state.bLeftTrigger / 255.0,
                5: self.state.bRightTrigger / 255.0,
            }
            val = axes.get(iid, 0.0)
            if abs(val) < deadzone: val = 0.0
            return val
            
        elif itype == "button":
            # Mapeo de botones (máscara de bits)
            btns = {
                0: 0x1000, # A
                1: 0x2000, # B
                2: 0x4000, # X
                3: 0x8000, # Y
                4: 0x0010, # Start
                5: 0x0020, # Back
                6: 0x0100, # LB
                7: 0x0200, # RB
            }
            mask = btns.get(iid, 0)
            return 1.0 if (self.state.wButtons & mask) else 0.0
            
        return 0.0

    def get_last_input(self):
        if not self.state: return None
        # Detección simple para el mapper
        if abs(self.state.sThumbLX) > 10000: return ("axis", 0)
        if abs(self.state.sThumbLY) > 10000: return ("axis", 1)
        if self.state.wButtons & 0x1000: return ("button", 0)
        return None
