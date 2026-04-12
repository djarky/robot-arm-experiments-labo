import socket
import json
import serial
import serial.tools.list_ports
import time
import sys

class LabCommunication:
    """
    Gestiona la comunicación UDP con Ursina y Serial con Arduino.
    """
    def __init__(self, sim_ip="127.0.0.1", sim_port=5005, feedback_port=5006):
        self.sim_addr = (sim_ip, sim_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.recv_sock.bind(("127.0.0.1", feedback_port))
            self.recv_sock.setblocking(False)
        except Exception as e:
            print(f"[Comm] Error bind feedback socket: {e}")

        self.ser = None

    def send_angles(self, angles):
        """Envía ángulos a la simulación y al Arduino."""
        # Ursina (UDP)
        msg = json.dumps({"type": "angles", "data": angles})
        self.sock.sendto(msg.encode(), self.sim_addr)

        # Arduino (Serial)
        if self.ser and self.ser.is_open:
            parts = [str(int(a + 90)) for a in angles]
            serial_msg = ",".join(parts) + ",0\n"
            try:
                self.ser.write(serial_msg.encode())
            except Exception as e:
                print(f"[Comm] Serial write error: {e}")

    def connect_arduino(self, port, baud=115200):
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            time.sleep(2.0) # Wait for reset
            print(f"[Comm] Arduino conectado en {port}")
            return True
        except Exception as e:
            print(f"[Comm] Error serial: {e}")
            return False

    def get_feedback(self):
        """
        Lee todos los paquetes de feedback pendientes y retorna el último.
        Esto evita latencia acumulada en el buffer UDP.
        """
        last_msg = None
        while True:
            try:
                data, _ = self.recv_sock.recvfrom(4096)
                last_msg = json.loads(data.decode())
            except (BlockingIOError, socket.error):
                break
            except Exception as e:
                print(f"[Comm] Feedback error: {e}")
                break
        return last_msg

    @staticmethod
    def list_ports(filter_arduino=True):
        all_ports = serial.tools.list_ports.comports()
        if not filter_arduino:
            return [p.device for p in all_ports]
            
        # Filtro similar a la GUI principal
        if sys.platform == "win32":
            return [p.device for p in all_ports if "COM" in p.device.upper()]
        else:
            return [p.device for p in all_ports if "ttyUSB" in p.device or "ttyACM" in p.device]
