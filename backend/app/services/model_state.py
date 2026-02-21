class ModelState:
    def __init__(self):
        self.gesture_process = None
        self.air_stylus_process = None
        self.gesture_running = False
        self.air_stylus_running = False

model_state = ModelState()