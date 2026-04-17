# Full Control - Web App Conversion Plan

## Current State Analysis

### Backend (Python/FastAPI):
- FastAPI is set up in `backend/app/main.py`
- Basic gesture start/stop exists in `routers/gesture.py` and `services/gesture_service.py`
- `gesture_control_api/main.py` has CLI-based gesture system with:
  - `run_gesture_control()` - main gesture loop
  - `add_new_gesture()` - interactive CLI for adding
  - `delete_gesture()` - interactive CLI for deleting
  - Helper functions for config, CSV, scripts, etc.
- Incomplete `add_new_gesture_api` stub exists

### Frontend:
- `apiService.ts` has stub functions returning mock data
- `GestureDashboard.tsx` has gesture grid with add/delete
- `ControlDashboard.tsx` has "INITIALIZE BRIDGE" buttons
- `AppContext.tsx` has state management

### Issues:
1. GET/POST/DELETE /api/gestures endpoints not implemented
2. Frontend API service uses mock data
3. UI doesn't update after add/delete - state update bug
4. Gesture Engine/Stop buttons need backend wiring

---

## Implementation Plan

### Phase 1: Backend Implementation

#### 1.1 Create new gesture API router
- File: `backend/app/routers/gestures_api.py`
- Endpoints:
  - GET /api/gestures - list all gestures from CSVs
  - POST /api/gestures - add new gesture (non-interactive)
  - DELETE /api/gestures/{gesture_name} - delete gesture

#### 1.2 Add gesture engine control endpoints
- Modify: `backend/app/routers/gesture.py`
- Add:
  - POST /api/gesture-engine/start
  - POST /api/gesture-engine/stop
  - GET /api/gesture-engine/status

#### 1.3 Update gesture service with stop flag
- Modify: `backend/app/services/gesture_service.py`
- Add global stop event mechanism
- Add status tracking

#### 1.4 Refactor gesture_control_api/main.py
- Remove CLI input() dependencies
- Create non-interactive versions of add/delete
- Fix the add_new_gesture_api stub

### Phase 2: Frontend Implementation

#### 2.1 Update apiService.ts
- Connect to actual backend endpoints
- Implement real fetch calls for gestures

#### 2.2 Fix GestureDashboard state bugs
- Use stable key (gesture.name)
- Proper immutable state updates after add/delete

#### 2.3 Wire ControlDashboard buttons
- Connect Gesture Engine button to API
- Connect Stop System button to API
- Show correct status

---

## Files to Modify/Create

### New Files:
1. `backend/app/routers/gestures_api.py` - NEW gesture API endpoints

### Backend Modifications:
1. `backend/app/main.py` - Add new router
2. `backend/app/routers/gesture.py` - Add engine control endpoints
3. `backend/app/services/gesture_service.py` - Add stop flag & status
4. `backend/app/ml_core/gesture_control_api/main.py` - Refactor for web

### Frontend Modifications:
1. `frontend/services/apiService.ts` - Real API calls
2. `frontend/screens/GestureDashboard.tsx` - Fix state bugs
3. `frontend/screens/ControlDashboard.tsx` - Wire buttons

---

## Success Criteria
- [ ] GET /api/gestures returns real gesture list from CSVs
- [ ] POST /api/gestures adds new gesture without CLI prompts
- [ ] DELETE /api/gestures/{name} deletes gesture properly
- [ ] Gesture Engine button starts run_gesture_control()
- [ ] Stop System button stops the engine
- [ ] UI updates after add/delete operations
- [ ] Status indicator shows correct state
