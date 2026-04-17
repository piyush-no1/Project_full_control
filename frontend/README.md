# Frontend (Vite + React)

## Prerequisites
- Node.js 18+
- Backend running on port `8000` (default)

## Setup
1. Copy `.env.example` to `.env`.
2. Fill all `VITE_FIREBASE_*` values from your Firebase project.
3. Install dependencies:
   - `npm install`
4. Start frontend:
   - `npm run dev`

## Build
- `npm run build`
- `npm run preview`

## Integration Notes
- Video stream websocket: `/ws/video`
- Real-time job/training websocket: `/ws/events?user_id=<uid>`
- Custom gesture flow uploads browser-captured frames to `/api/gestures/upload-samples`,
  then queues finalize/training with `/api/gestures` (`collection_mode=browser`).
- Gesture APIs use Firebase bearer token when available and fallback to `X-User-Id`.
