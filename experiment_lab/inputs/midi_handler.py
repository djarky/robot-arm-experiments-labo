"""
midi_handler.py — Backend para lectura de controladores MIDI.

Usa pygame.midi para capturar eventos de Control Change (ejes) 
y Note On/Off (botones).
"""

import time
import threading

try:
    import pygame.midi
    MIDI_AVAILABLE = True
except ImportError:
    MIDI_AVAILABLE = False

from .base import BaseInputHandler

class MIDIHandler(BaseInputHandler):
    """Handler especializado para dispositivos MIDI (Teclados, Launchpads, Mixers)."""

    def __init__(self):
        self.device = None
        self.device_id = None
        self.last_input = None
        self.axes_state = {}   # {cc_id: float}
        self.buttons_state = {} # {note_id: bool}
        self.initialized = False

    def activate(self, device_id, **kwargs):
        """
        Inicializa el dispositivo MIDI.
        device_id puede ser el índice del dispositivo en pygame.midi.
        """
        if not MIDI_AVAILABLE:
            print("[MIDI] Error: pygame.midi no está disponible.")
            return

        if not pygame.midi.get_init():
            pygame.midi.init()

        try:
            # Si device_id es "MIDI_AUTO", podríamos intentar buscar el primer input
            if device_id == "MIDI_AUTO":
                idx = pygame.midi.get_default_input_id()
                if idx == -1:
                    print("[MIDI] No se encontró dispositivo de entrada por defecto.")
                    return
                device_id = idx

            self.device_id = int(device_id)
            self.device = pygame.midi.Input(self.device_id)
            self.initialized = True
            print(f"[MIDI] Dispositivo activado (ID: {self.device_id})")
        except Exception as e:
            print(f"[MIDI] Error al abrir dispositivo {device_id}: {e}")
            self.initialized = False

    def deactivate(self):
        if self.device:
            self.device.close()
            self.device = None
        self.initialized = False

    def poll(self):
        """Lee todos los eventos MIDI pendientes en el buffer."""
        if not self.initialized or not self.device:
            return

        while self.device.poll():
            events = self.device.read(10) # Leer hasta 10 eventos
            for event in events:
                data, timestamp = event
                status, d1, d2, d3 = data
                
                msg_type = status & 0xF0
                channel = status & 0x0F

                # Control Change (CC) -> Ejes
                if msg_type == 0xB0:
                    val = (d2 / 127.0) * 2.0 - 1.0 # Normalizar a -1.0 a 1.0
                    self.axes_state[d1] = val
                    self.last_input = ("axis", d1)
                
                # Note On -> Botón Presionado
                elif msg_type == 0x90:
                    if d2 > 0: # Velocity > 0 es Presionado
                        self.buttons_state[d1] = True
                        self.last_input = ("button", d1)
                    else: # Velocity 0 es Soltado
                        self.buttons_state[d1] = False
                
                # Note Off -> Botón Soltado
                elif msg_type == 0x80:
                    self.buttons_state[d1] = False

    def read_bind(self, bind, deadzone=0.1):
        if not bind: return 0.0
        
        itype = bind.get("type")
        iid = bind.get("id")

        if itype == "axis":
            val = self.axes_state.get(iid, 0.0)
            return val if abs(val) > deadzone else 0.0
        
        elif itype == "button":
            return 1.0 if self.buttons_state.get(iid, False) else 0.0

        return 0.0

    def get_last_input(self):
        last = self.last_input
        self.last_input = None # Consumir
        return last

    def flush(self):
        if self.device:
            while self.device.poll():
                self.device.read(10)
        self.axes_state = {}
        self.buttons_state = {}
        self.last_input = None
