import json
import time
import random

class AIAgent:
    """
    Agente de IA para el Laboratorio.
    Maneja la lógica de LLM (Mock) y detección de objetos.
    """
    def __init__(self, console_output=None):
        self.console = console_output
        self.ollama_endpoint = "http://localhost:11434/api/generate"
        self.is_active = False

    def log(self, message):
        if self.console:
            self.console.append(f"[AI] {message}")
        else:
            print(f"[AI] {message}")

    def query_llm(self, prompt):
        """Mock de integración con Ollama/LLM"""
        self.log(f"Procesando comando: '{prompt}'")
        # Simulación de retardo
        time.sleep(1)
        responses = [
            "Moviendo brazo a posición de descanso.",
            "Detectando objetos en el espacio de trabajo...",
            "Comando aceptado: Realizando secuencia circular.",
            "IA: No puedo realizar esa acción por seguridad."
        ]
        response = random.choice(responses)
        self.log(f"Respuesta: {response}")
        return response

    def detect_objects(self):
        """Mock de visión artificial / detección en simulación"""
        # En una versión real, esto leería la cámara de Ursina o datos de la escena
        objects = [
            {"id": "cube_1", "pos": [1.5, 0.5, 0], "color": "red"},
            {"id": "sphere_A", "pos": [0, 0.5, 2], "color": "blue"}
        ]
        return objects

    def get_action_angles(self, current_angles):
        """Retorna ángulos sugeridos por la IA"""
        if not self.is_active:
            return None
        # Ejemplo: Mantener una posición o realizar un jitter
        return [a + random.uniform(-0.1, 0.1) for a in current_angles]
