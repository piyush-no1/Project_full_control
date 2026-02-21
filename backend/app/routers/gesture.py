from fastapi import APIRouter
from app.services.gesture_service import start_gesture, stop_gesture

router = APIRouter(prefix="/gesture", tags=["Gesture"])

@router.post("/start")
def start():
    return {"message": start_gesture()}

@router.post("/stop")
def stop():
    return {"message": stop_gesture()}