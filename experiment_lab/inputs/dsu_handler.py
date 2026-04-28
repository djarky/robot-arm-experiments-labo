import socket
import struct
import threading
import time

from .base import BaseInputHandler

# Packet signature to request data from DSU server (Cemuhook protocol)
DSU_REQUEST_PACKET = b"DSUC\351\003\f\000\016\363\371\333\000\000\000\000\002\000\020\000\001\000\000\000\000\000\000\000"

class DSUClient:
    """Implementación del protocolo DSU (Cemuhook) como cliente (polling)."""

    def __init__(self, host='127.0.0.1', port=26760):
        self.host = host
        self.port = port
        self.active = False
        self.data = {
            "accel": [0.0, 0.0, 0.0],
            "gyro": [0.0, 0.0, 0.0],
            "sticks": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0},
            "buttons": {}
        }
        self.sock = None
        self._listen_thread = None
        self._poll_thread = None

    def start(self):
        if self.active:
            return
        self.active = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # En modo cliente no hacemos bind a un puerto fijo local necesariamente,
            # pero establecemos el timeout para recvfrom.
            self.sock.settimeout(1.0)
            
            self._listen_thread = threading.Thread(target=self._listen, daemon=True)
            self._listen_thread.start()
            
            self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._poll_thread.start()
            
            print(f"[Input/DSU] Polling {self.host}:{self.port}")
        except Exception as e:
            print(f"[Input/DSU] Error initializing DSU client: {e}")
            self.active = False

    def _poll_loop(self):
        """Envía el paquete de suscripción periódicamente."""
        while self.active:
            try:
                if self.sock:
                    self.sock.sendto(DSU_REQUEST_PACKET, (self.host, self.port))
            except Exception:
                pass
            time.sleep(1.0)

    def _listen(self):
        while self.active:
            try:
                data, addr = self.sock.recvfrom(1024)
                if len(data) < 20:
                    continue
                
                # Header: Magic(4), Version(2), Len(2), CRC(4), ServerID(4), MsgType(4)
                msg_type = struct.unpack("<I", data[16:20])[0]
                
                if msg_type == 0x100002:  # Data message
                    if len(data) < 100:
                        continue
                        
                    # 20: PadID(1), State(1), Model(1), Conn(1), MAC(6), Battery(1), Active(1), PacketCounter(4)
                    # 36: Digital1(1), Digital2(1), Home(1), Touch(1)
                    # 40: LX(1), LY(1), RX(1), RY(1)
                    # 44: DpadL, DpadD, DpadR, DpadU, Square, Cross, Circle, Triangle, R1, L1, R2, L2 (todo en 1 byte cada uno si es analógico o digital?)
                    
                    # Siguiendo estructura de Universal-Remote/udp_listener.py
                    # 40: LX, LY, RX, RY
                    lx, ly, rx, ry = struct.unpack("BBBB", data[40:44])
                    self.data["sticks"]["lx"] = (lx - 128) / 128.0
                    self.data["sticks"]["ly"] = (ly - 128) / 128.0
                    self.data["sticks"]["rx"] = (rx - 128) / 128.0
                    self.data["sticks"]["ry"] = (ry - 128) / 128.0
                    
                    # Botones (Offsets aproximados basados en el struct del addon)
                    # El addon usa campos individuales. Vamos a mapear los más importantes.
                    # 36: buttons1 (Digital 1)
                    # 37: buttons2 (Digital 2)
                    b1 = data[36]
                    b2 = data[37]
                    
                    # Mapear a códigos internos (pueden ser arbitrarios pero consistentes)
                    # Digital 1: Share, L3, R3, Options, Up, Right, Down, Left
                    # Digital 2: L2, R2, L1, R1, Triangle, Circle, Cross, Square
                    self.data["buttons"] = {
                        0: (b2 >> 0) & 1,  # Square / Cross? Depende del servidor
                        1: (b2 >> 1) & 1,  # Cross
                        2: (b2 >> 2) & 1,  # Circle
                        3: (b2 >> 3) & 1,  # Triangle
                        4: (b2 >> 4) & 1,  # L1
                        5: (b2 >> 5) & 1,  # R1
                        6: (b2 >> 6) & 1,  # L2 (Digital)
                        7: (b2 >> 7) & 1,  # R2 (Digital)
                        8: (b1 >> 0) & 1,  # Share
                        9: (b1 >> 3) & 1,  # Options
                    }
                    
                    # Sensores (70: Accel, 82: Gyro en microsegundos + floats)
                    # Accel X, Y, Z (Floats)
                    accel_x, accel_y, accel_z = struct.unpack("<fff", data[70:82])
                    self.data["accel"] = [accel_x, accel_y, accel_z]
                    
                    # Gyro Pitch, Yaw, Roll (Floats)
                    gyro_p, gyro_y, gyro_r = struct.unpack("<fff", data[82:94])
                    self.data["gyro"] = [gyro_p, gyro_y, gyro_r]

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
    """Handler para entrada vía protocolo DSU/Cemuhook (UDP Client)."""

    def __init__(self):
        self.client = DSUClient()

    def activate(self, device_id=None, **kwargs):
        """Inicia el cliente DSU con la IP y puerto especificados."""
        host = kwargs.get("host", "127.0.0.1")
        port = kwargs.get("port", 26760)
        
        # Si ya está activo con la misma config, no reiniciar
        if self.client.active and self.client.host == host and self.client.port == port:
            return
            
        self.client.stop()
        self.client.host = host
        self.client.port = port
        self.client.start()

    def deactivate(self):
        """Detiene el cliente DSU."""
        self.client.stop()

    def poll(self):
        """El cliente corre en hilos separados, no requiere polling manual aquí."""
        pass

    def get_direct_inputs(self):
        """
        Mapeo directo heredado (acelerómetros).
        Para usar botones/sticks del DSU, se debería usar el sistema de binds.
        """
        if not self.client.active:
            return None

        accel = self.client.data["accel"]
        # Mapeo crudo: X -> Base, Y -> Hombro
        joy_inputs = [accel[0], accel[1], 0.0, 0.0, 0.0, 0.0, 0.0]

        return joy_inputs, {}, [0.0] * 7

    def get_last_input(self):
        """Detecta sticks o botones para el mapper."""
        if not self.client.active:
            return None

        # 1. Detectar Botones
        for bid, val in self.client.data["buttons"].items():
            if val:
                return ("button", bid)

        # 2. Detectar Sticks (Umbral 0.5)
        for sid, val in self.client.data["sticks"].items():
            if abs(val) > 0.5:
                return ("axis", sid)

        # 3. Detectar Sensores (Opcional, pero útil)
        for i, val in enumerate(self.client.data["accel"]):
            if abs(val) > 0.6:
                return ("axis", f"accel_{i}")

        return None

    def read_bind(self, bind, deadzone=0.1):
        """Resuelve un bind usando el estado del cliente DSU."""
        if not self.client.active:
            return 0.0

        itype = bind.get("type")
        iid = bind.get("id")

        if itype == "button":
            return 1.0 if self.client.data["buttons"].get(iid, 0) else 0.0

        if itype == "axis":
            val = 0.0
            if iid in self.client.data["sticks"]:
                val = self.client.data["sticks"][iid]
            elif str(iid).startswith("accel_"):
                idx = int(iid.split("_")[1])
                val = self.client.data["accel"][idx]
            
            if abs(val) < deadzone:
                return 0.0
            return val

        return 0.0

    def flush(self):
        """No hay cola de eventos que vaciar, usamos estado instantáneo."""
        pass
