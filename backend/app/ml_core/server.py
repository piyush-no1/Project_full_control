from fastapi import FastAPI
from pydantic import BaseModel
import subprocess

app = FastAPI()

gesture_process = None
mouse_process = None


# ---------------------------
# Start Gesture Engine
# ---------------------------
@app.post("/start-gesture")
def start_gesture():
    global gesture_process

    if gesture_process is None:
        gesture_process = subprocess.Popen(
            ["python", "gesture_control_api/main.py"]
        )
        return {"status": "Gesture Engine Started"}

    return {"status": "Gesture Engine Already Running"}


# ---------------------------
# Start Air Stylus
# ---------------------------
@app.post("/start-air-stylus")
def start_air_stylus():
    global mouse_process

    if mouse_process is None:
        mouse_process = subprocess.Popen(
            ["python", "Mouse_Control/mouse_control.py"]
        )
        return {"status": "Air Stylus Started"}

    return {"status": "Air Stylus Already Running"}


# ---------------------------
# Add Custom Gesture
# ---------------------------
class GestureRequest(BaseModel):
    name: str
    description: str


@app.post("/add-gesture")
def add_gesture(request: GestureRequest):
    from gesture_control_api.main import add_new_gesture_api

    result = add_new_gesture_api(
        request.name,
        request.description
    )

    return result
