"""
dsu_handler.py — Handler para el protocolo DSU (Cemuhook).

Recibe datos de sensores (acelerómetro) vía UDP desde servidores
Cemuhook, Dolphin emulator, o apps de smartphone.
Completamente aislado: no usa el sistema de binds.
"""

import socket
import struct
import threading

from .base import BaseInputHandler


class DSUClient:
    """Implementación mínima del protocolo DSU (Cemuhook) para recibir datos de sensores."""

    def __init__(self, port=26760):
        self.port = port
        self.active = False
        self.data = {"accel": [0.0, 0.0, 0.0], "buttons": {}}
        self.sock = None
        self._thread = None

    def start(self):
        if self.active:
            return
        self.active = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind(('0.0.0.0', self.port))
            self.sock.settimeout(1.0)
            self._thread = threading.Thread(target=self._listen, daemon=True)
            self._thread.start()
            print(f"[Input/DSU] Listening on port {self.port}")
        except Exception as e:
            print(f"[Input/DSU] Error binding to port {self.port}: {e}")
            self.active = False

    def _listen(self):
        while self.active:
            try:
                data, addr = self.sock.recvfrom(1024)
                if len(data) < 16:
                    continue
                # Parsear cabecera mínima
                # Magic: data[0:4] == b'DSUS'
                # Type: data[16:20]
                msg_type = struct.unpack("<I", data[16:20])[0]
                if msg_type == 0x100002:  # Data message
                    # Mapeo crudo de acelerómetros (típico en byte 44 en adelante)
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
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None


class DSUHandler(BaseInputHandler):
    """Handler para entrada vía protocolo DSU/Cemuhook (UDP)."""

    def __init__(self):
        self.client = DSUClient()

    def activate(self, device_id=None, **kwargs):
        """Inicia el cliente DSU."""
        port = kwargs.get("port", 26760)
        self.client.port = port
        self.client.start()

    def deactivate(self):
        """Detiene el cliente DSU."""
        self.client.stop()

    def get_direct_inputs(self):
        """
        Retorna los datos del DSU mapeados directamente a ejes del brazo.
        
        El DSU NO usa el sistema de binds. Los acelerómetros se mapean
        directamente: X → Base, Y → Hombro.
        
        Returns:
            tuple: (joy_inputs, actions, camera_inputs)
        """
        if not self.client.active:
            self.client.start()

        accel = self.client.data["accel"]
        joy_inputs = [accel[0], accel[1], 0.0, 0.0, 0.0, 0.0, 0.0]

        return joy_inputs, {}, [0.0] * 7
