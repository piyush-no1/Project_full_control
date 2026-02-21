from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.routers import gesture, air_stylus
import asyncio
import json
from app.services.frame_buffer import frame_buffer

app = FastAPI()

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "Backend running"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        print("Received:", data)
        await websocket.send_text(f"Echo: {data}")

@app.websocket("/ws/video")
async def video_stream(websocket: WebSocket):
    """WebSocket endpoint for streaming video frames to frontend"""
    await websocket.accept()
    print("[WebSocket] Video streaming client connected")
    
    try:
        while True:
            # Get frame from buffer
            frame_data = frame_buffer.get_frame()
            
            if frame_data[0] is not None:
                # frame_data = (frame_base64, gesture_name, confidence, status, is_active)
                message = json.dumps({
                    "type": "frame",
                    "frame": f"data:image/jpeg;base64,{frame_data[0]}",
                    "gesture": frame_data[1],
                    "confidence": frame_data[2],
                    "status": frame_data[3],
                    "is_active": frame_data[4]
                })
                await websocket.send_text(message)
            else:
                # Send idle message
                await websocket.send_text(json.dumps({
                    "type": "idle",
                    "status": "no_hand"
                }))
            
            # ~30 FPS
            await asyncio.sleep(0.033)
            
    except Exception as e:
        print(f"[WebSocket] Video stream error: {e}")
    finally:
        print("[WebSocket] Video streaming client disconnected")

# Include routers
app.include_router(gesture.router)
app.include_router(air_stylus.router)
