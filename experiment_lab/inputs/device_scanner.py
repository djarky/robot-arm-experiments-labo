"""
device_scanner.py — Detección y clasificación de dispositivos de entrada.

Escanea el sistema buscando dispositivos via evdev y pygame,
los clasifica por categoría visual (Xbox, PS5, Joycons, Wiimote, etc.).
"""

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

try:
    import evdev
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False


def get_categorized_devices(force_raw=False):
    """
    Retorna un diccionario de categorías con sus dispositivos detectados.
    
    Args:
        force_raw: Si True, lista todos los dispositivos como RAW evdev.
        
    Returns:
        dict: {"Categoría": [{"id": str, "name": str}, ...], ...}
    """
    categories = {
        "Teclado": [{"id": "KM", "name": "Teclado y Ratón Genérico"}],
        "Mando Xbox": [],
        "Mando PS5": [],
        "Nintendo Joycons": [],
        "Wiimote": [],
        "DSU": [{"id": "DSU", "name": "Servidor Cemuhook / Móvil"}],
        "Otros (Custom)": []
    }

    if force_raw:
        if EVDEV_AVAILABLE:
            try:
                for path in evdev.list_devices():
                    dev = evdev.InputDevice(path)
                    categories["Otros (Custom)"].append({
                        "id": path,
                        "name": f"RAW: {dev.name}"
                    })
            except Exception:
                pass
        return categories

    # 1. Evdev Scan (Más preciso para Hardware IDs)
    if EVDEV_AVAILABLE:
        try:
            for path in evdev.list_devices():
                dev = evdev.InputDevice(path)
                dinfo = {"id": path, "name": dev.name}

                # Clasificación por nombre/vendor
                lower_name = dev.name.lower()
                if "nintendo" in lower_name or "rvl" in lower_name:
                    # Mostrar solo el nodo principal (Nintendo Wii Remote) en la lista,
                    # los otros se conectarán automáticamente en el handler.
                    if "accelerometer" not in lower_name and "ir" not in lower_name and "motion plus" not in lower_name:
                        dinfo["id"] = "WIIMOTE_AUTO"
                        categories["Wiimote"].append(dinfo)
                elif "xbox" in lower_name or dev.info.vendor == 0x045e:
                    categories["Mando Xbox"].append(dinfo)
                elif "dualsense" in lower_name or "dualshock" in lower_name or dev.info.vendor == 0x054c:
                    categories["Mando PS5"].append(dinfo)
                elif "joy-con" in lower_name:
                    categories["Nintendo Joycons"].append(dinfo)
                else:
                    categories["Otros (Custom)"].append(dinfo)
        except Exception:
            pass

    # 2. Pygame fallback for gamepads not caught by evdev
    if PYGAME_AVAILABLE:
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(i)
            name = joy.get_name().lower()
            jid = f"JOY_{i}"
            dinfo = {"id": jid, "name": f"Gamepad {i}: {joy.get_name()}"}

            if "xbox" in name:
                categories["Mando Xbox"].append(dinfo)
            elif "ps5" in name or "sony" in name:
                categories["Mando PS5"].append(dinfo)
            elif "joy-con" in name:
                categories["Nintendo Joycons"].append(dinfo)
            else:
                # Solo añadir a custom si no lo vimos ya en evdev
                if not any(
                    d["name"] == joy.get_name()
                    for cat in categories.values()
                    for d in cat
                ):
                    categories["Otros (Custom)"].append(dinfo)

    return categories
