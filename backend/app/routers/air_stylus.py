from __future__ import annotations

from fastapi import APIRouter, Request

from app.services.air_stylus_service import start_air_stylus, stop_air_stylus
from app.services.auth_service import resolve_request_user


router = APIRouter(prefix="/air-stylus", tags=["Air Stylus"])


@router.post("/start")
def start(request: Request):
    user = resolve_request_user(request)
    return {
        "message": start_air_stylus(user.user_id),
        "user_id": user.user_id,
    }


@router.post("/stop")
def stop():
    return {"message": stop_air_stylus()}

