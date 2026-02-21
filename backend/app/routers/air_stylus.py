from fastapi import APIRouter
from app.services.air_stylus_service import start_air_stylus, stop_air_stylus

router = APIRouter(prefix="/air-stylus", tags=["Air Stylus"])

@router.post("/start")
def start():
    return {"message": start_air_stylus()}

@router.post("/stop")
def stop():
    return {"message": stop_air_stylus()}