class ModelState:
    def __init__(self):
        self.gesture_process = None
        self.air_stylus_process = None
        self.gesture_thread = None
        self.air_stylus_thread = None
        self.gesture_stop_event = None
        self.air_stylus_stop_event = None
        self.gesture_running = False
        self.air_stylus_running = False
        self.active_mode = "none"
        self.active_user_id = None

model_state = ModelState()
