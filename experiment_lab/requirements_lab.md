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
- `pygame-ce`: **(Nuevo)** Necesario para la gestión de mandos y joysticks estándar.
- `requests`: **(Nuevo)** Necesario para la comunicación de red del laboratorio.
- `evdev`: **(Opcional, Linux)** Para lectura directa de hardware de entrada.
- `pysdl2` y `pysdl2-dll`: **(Opcional)** Para el backend de SDL2 directo.

## 🛠️ Hardware
- **Cámara USB**: Necesaria para el seguimiento de gestos (si se habilita).
- **Arduino**: Opcional. Permite el control del brazo físico.
- **Mando / Joystick**: Opcional. El laboratorio permite control directo mediante dispositivos compatibles con Pygame.

## 🤖 Inteligencia Artificial y Drivers - OPCIONAL
El sistema tiene un Agente de IA y múltiples backends de entrada integrados.
- **IA (Ollama)**: El sistema detectará si Ollama está disponible y usará respuestas "Mock" si no lo está.
- **Drivers de Entrada**: El sistema detectará automáticamente qué librerías están instaladas (`evdev`, `pysdl2`). Si fallan al instalarse, el laboratorio seguirá funcionando perfectamente usando el backend estándar de `pygame`.
