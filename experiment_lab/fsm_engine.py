import time

class StateMachine:
    """
    Motor de Máquina de Estados para animaciones complejas.
    """
    def __init__(self):
        self.states = {}
        self.current_state = None
        self.active = False

    def add_state(self, name, target_angles, transition_time=1.0):
        self.states[name] = {
            "angles": target_angles,
            "time": transition_time,
            "next": None
        }

    def set_sequence(self, state_list):
        """Encadena una lista de estados en orden circular."""
        for i in range(len(state_list)):
            name = state_list[i]
            next_name = state_list[(i + 1) % len(state_list)]
            if name in self.states:
                self.states[name]["next"] = next_name

    def start(self, initial_state):
        if initial_state in self.states:
            self.current_state = initial_state
            self.active = True

    def update(self):
        if not self.active or not self.current_state:
            return None
        
        state = self.states[self.current_state]
        # En una versión real, aquí haríamos la interpolación
        # Por ahora devolvemos los ángulos objetivo del estado
        return state["angles"]

    def next(self):
        if self.current_state in self.states:
            self.current_state = self.states[self.current_state]["next"]
