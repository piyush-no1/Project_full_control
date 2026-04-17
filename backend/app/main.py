from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.routers import air_stylus, gesture, gestures_api, jobs, user_data
from app.services.frame_buffer import frame_buffer
from app.services.model_state import model_state
from app.services.user_storage_service import sanitize_user_id
from app.websocket.event_manager import event_manager


app = FastAPI(title="Full Control Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    event_manager.set_loop(asyncio.get_running_loop())


@app.get("/")
def root():
    return {"status": "Backend running"}


@app.get("/api/control/status")
def control_status():
    return {
        "active_mode": model_state.active_mode,
        "gesture_running": model_state.gesture_running,
        "air_stylus_running": model_state.air_stylus_running,
        "active_user_id": model_state.active_user_id,
    }


@app.websocket("/ws/video")
async def video_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            frame_data = frame_buffer.get_frame()
            if frame_data[0] is not None:
                payload = {
                    "type": "frame",
                    "frame": f"data:image/jpeg;base64,{frame_data[0]}",
                    "gesture": frame_data[1],
                    "confidence": frame_data[2],
                    "status": frame_data[3],
                    "is_active": frame_data[4],
                }
            else:
                payload = {
                    "type": "idle",
                    "status": "no_hand",
                }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0.033)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.websocket("/ws/events")
async def events_stream(websocket: WebSocket):
    user_id = sanitize_user_id(websocket.query_params.get("user_id", "guest"))
    await event_manager.connect(websocket, user_id)
    await event_manager.emit_user_event(
        user_id,
        {
            "type": "connection",
            "status": "connected",
            "message": "Connected to backend event stream.",
        },
    )
    try:
        while True:
            # Keepalive channel: client may send ping frames/messages.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await event_manager.disconnect(websocket, user_id)
    except Exception:
        await event_manager.disconnect(websocket, user_id)


app.include_router(gesture.router)
app.include_router(gesture.gesture_engine_router)
app.include_router(air_stylus.router)
app.include_router(gestures_api.router)
app.include_router(gestures_api.legacy_router)
app.include_router(jobs.router)
app.include_router(user_data.router)
