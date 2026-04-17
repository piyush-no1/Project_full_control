# Backend (FastAPI + WebSockets)

## Prerequisites
- Python 3.10+
- Install dependencies in your backend environment (FastAPI, OpenCV, TensorFlow, Mediapipe, etc.)

## Setup
1. Copy `.env.example` to `.env`.
2. Set at minimum:
   - `GROQ_API_KEY`
   - `FIREBASE_PROJECT_ID` (recommended for strict token verification)
   - Optional:
     - `FIREBASE_SERVICE_ACCOUNT_PATH` for backend Firestore writes
3. Start server:
   - PowerShell: `./run_backend.ps1`
   - Bash: `./run_backend.sh`
   - or directly: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

## API + WebSocket
- Video stream: `ws://localhost:8000/ws/video`
- Event stream: `ws://localhost:8000/ws/events?user_id=<uid>`
- Add gesture job: `POST /add-gesture` or `POST /api/gestures`
- Browser sample upload: `POST /api/gestures/upload-samples`
- Job status: `GET /add-gesture/{job_id}` or `GET /api/jobs/{job_id}`
- Delete gesture (auto retrain): `DELETE /api/gestures/{gesture_name}`
- User settings: `GET/PUT /api/user/settings`

## User Isolation
- Per-user gesture data/models/scripts are stored in:
  - `backend/app/ml_core/user_data/<user_id>/`
- Backend resolves user from:
  1. Firebase Bearer token
  2. `X-User-Id` header fallback
