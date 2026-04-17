# API Key Entry Reference

Use this file as a quick checklist of where API keys should be entered.

## `backend/`
- File: `backend/.env`
- Required key fields:
  - `GROQ_API_KEY="enter api key"`
- Also present (project config, not always API keys):
  - `FIREBASE_PROJECT_ID=`
  - `FIREBASE_SERVICE_ACCOUNT_PATH=`

## `frontend/`
- File: `frontend/.env` (create from `frontend/.env.example` if needed)
- Key/config fields to fill:
  - `VITE_FIREBASE_API_KEY=`
  - `VITE_FIREBASE_AUTH_DOMAIN=`
  - `VITE_FIREBASE_PROJECT_ID=`
  - `VITE_FIREBASE_STORAGE_BUCKET=`
  - `VITE_FIREBASE_MESSAGING_SENDER_ID=`
  - `VITE_FIREBASE_APP_ID=`
  - `VITE_FIREBASE_MEASUREMENT_ID=`
