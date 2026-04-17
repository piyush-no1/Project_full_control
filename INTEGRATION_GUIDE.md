# Full Control Integration Guide

## 1. Firebase Setup
1. Create Firebase project.
2. Enable Google Authentication.
3. Copy Web App config into `frontend/.env`.
4. Set backend Firebase project id in `backend/.env`:
   - `FIREBASE_PROJECT_ID=<your-project-id>`

## 2. Backend Setup
1. `cd backend`
2. Create `.env` from `.env.example`
3. Set:
   - `GROQ_API_KEY=<your-groq-key>`
   - `FIREBASE_PROJECT_ID=<your-project-id>`
   - Optional for backend-managed Firestore writes:
     - `FIREBASE_SERVICE_ACCOUNT_PATH=<abs path to service-account.json>`
4. Run:
   - `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

## 3. Frontend Setup
1. `cd frontend`
2. Create `.env` from `.env.example`
3. Fill all `VITE_FIREBASE_*` keys
4. Run:
   - `npm install`
   - `npm run dev`

## 4. End-to-End Flow
1. Open frontend app.
2. Intro animation plays.
3. Click `Enter System` -> Login.
4. After login, open Gesture Dashboard.
5. Click `Initiate System Control` -> Control Dashboard.
6. Select mode:
   - `Air Stylus` (mouse control stream in browser)
   - `Gesture Engine` (gesture control stream in browser)
7. Add/Delete custom gestures from dashboard:
   - Browser captures frames, uploads samples, then runs finalize+training job.
   - No OpenCV data-collection window is used for custom gesture creation.
   - Jobs run in background.
   - Training progress appears via WebSocket events.

## 5. Important Endpoints
- `POST /add-gesture`
- `GET /add-gesture/{job_id}`
- `GET /api/gestures`
- `POST /api/gestures`
- `POST /api/gestures/upload-samples`
- `DELETE /api/gestures/{gesture_name}`
- `POST /api/gestures/retrain`
- `GET /api/jobs/{job_id}`
- `GET /api/user/settings`
- `PUT /api/user/settings`
- `WS /ws/video`
- `WS /ws/events?user_id=<uid>`
