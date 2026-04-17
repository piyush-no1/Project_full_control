from __future__ import annotations

from fastapi import APIRouter, Request

from app.services.auth_service import resolve_request_user
from app.services.gesture_service import get_gesture_status, start_gesture, stop_gesture
from app.services.model_state import model_state


router = APIRouter(prefix="/gesture", tags=["Gesture"])


@router.post("/start")
def start(request: Request):
    user = resolve_request_user(request)
    return {
        "message": start_gesture(user.user_id),
        "user_id": user.user_id,
    }


@router.post("/stop")
def stop():
    return {"message": stop_gesture()}


gesture_engine_router = APIRouter(prefix="/api/gesture-engine", tags=["Gesture Engine"])


@gesture_engine_router.post("/start")
def start_engine(request: Request):
    user = resolve_request_user(request)
    return {
        "message": start_gesture(user.user_id),
        "user_id": user.user_id,
    }


@gesture_engine_router.post("/stop")
def stop_engine():
    return {"message": stop_gesture()}


@gesture_engine_router.get("/status")
def engine_status():
    return {
        "running": get_gesture_status(),
        "active_mode": model_state.active_mode,
        "active_user_id": model_state.active_user_id,
    }

