# Requisitos del Sistema - Experiment Lab

Este documento detalla los requisitos necesarios para ejecutar el Laboratorio de Experimentos del brazo robótico.

## 🐍 Entorno de Software
- **Python**: Versión 3.10 o superior.
- **Sistema Operativo**: Windows 10/11 o Linux.

## 📦 Dependencias de Python
El sistema utiliza un entorno virtual (`venv`). Las librerías necesarias son:
- `PySide6`: Para la interfaz gráfica avanzada.
- `ursina`: Para el motor de simulación 3D.
- `opencv-python`: Para el procesamiento de visión.
- `mediapipe`: Para el seguimiento de gestos.
- `pyserial`: Para la comunicación con el hardware Arduino.
- `pygame`: **(Nuevo)** Necesario para la gestión de mandos y joysticks en el laboratorio.
- `requests`: **(Nuevo)** Necesario para la comunicación de red del laboratorio.

## 🛠️ Hardware
- **Cámara USB**: Necesaria para el seguimiento de gestos (si se habilita).
- **Arduino**: Opcional. Permite el control del brazo físico.
- **Mando / Joystick**: Opcional. El laboratorio permite control directo mediante dispositivos compatibles con Pygame.

## 🤖 Inteligencia Artificial (Ollama) - OPCIONAL
El sistema tiene un Agente de IA integrado en `ai_agent.py`.
- **Estado Actual**: Omitido por limitaciones de hardware del usuario.
- **Comportamiento**: El sistema detectará que Ollama no está disponible y utilizará respuestas "Mock" (simuladas) para las interacciones del chat, permitiendo que la aplicación funcione sin errores.
