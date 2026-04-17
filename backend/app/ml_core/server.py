from datetime import datetime, timezone
import subprocess
import threading
from typing import Any, Dict, Optional
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

gesture_process = None
mouse_process = None

add_gesture_jobs: Dict[str, Dict[str, Any]] = {}
add_gesture_lock = threading.Lock()
active_add_gesture_job_id: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_job_copy(job_id: str) -> Optional[Dict[str, Any]]:
    with add_gesture_lock:
        job = add_gesture_jobs.get(job_id)
        if job is None:
            return None
        return dict(job)


def _update_job(job_id: str, **fields: Any) -> None:
    with add_gesture_lock:
        job = add_gesture_jobs.get(job_id)
        if job is None:
            return
        job.update(fields)
        job["updated_at"] = _utc_now_iso()


def _run_add_gesture_job(job_id: str, gesture_name: str, description: str) -> None:
    global active_add_gesture_job_id

    from gesture_control_api.main import add_new_gesture_api

    def progress_callback(stage: str, message: str) -> None:
        _update_job(job_id, status="running", stage=stage, message=message)

    try:
        _update_job(
            job_id,
            status="running",
            stage="script_generation",
            message=f"Starting add-gesture flow for '{gesture_name}'.",
        )

        result = add_new_gesture_api(
            gesture_name,
            description,
            progress_callback=progress_callback,
        )

        if result.get("status") == "success":
            _update_job(
                job_id,
                status="completed",
                stage="completed",
                message=result.get("message", "Gesture setup completed."),
                result=result,
                error=None,
                completed_at=_utc_now_iso(),
            )
        else:
            _update_job(
                job_id,
                status="failed",
                stage="failed",
                message=result.get("message", "Gesture setup failed."),
                result=result,
                error=result,
                completed_at=_utc_now_iso(),
            )
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            stage="failed",
            message=f"Unexpected error while adding gesture '{gesture_name}'.",
            error=str(exc),
            completed_at=_utc_now_iso(),
        )
    finally:
        with add_gesture_lock:
            if active_add_gesture_job_id == job_id:
                active_add_gesture_job_id = None


# ---------------------------
# Start Gesture Engine
# ---------------------------
@app.post("/start-gesture")
def start_gesture():
    global gesture_process

    if gesture_process is None:
        gesture_process = subprocess.Popen(
            ["python", "gesture_control_api/main.py"]
        )
        return {"status": "Gesture Engine Started"}

    return {"status": "Gesture Engine Already Running"}


# ---------------------------
# Start Air Stylus
# ---------------------------
@app.post("/start-air-stylus")
def start_air_stylus():
    global mouse_process

    if mouse_process is None:
        mouse_process = subprocess.Popen(
            ["python", "Mouse_Control/mouse_control.py"]
        )
        return {"status": "Air Stylus Started"}

    return {"status": "Air Stylus Already Running"}


# ---------------------------
# Add Custom Gesture
# ---------------------------
class GestureRequest(BaseModel):
    name: str
    description: str


@app.post("/add-gesture")
def add_gesture(request: GestureRequest):
    global active_add_gesture_job_id

    gesture_name = request.name.strip()
    description = request.description.strip()
    if not gesture_name:
        raise HTTPException(status_code=400, detail="Gesture name cannot be empty.")
    if not description:
        raise HTTPException(status_code=400, detail="Gesture description cannot be empty.")

    with add_gesture_lock:
        if active_add_gesture_job_id is not None:
            active_job = add_gesture_jobs.get(active_add_gesture_job_id, {})
            if active_job.get("status") in {"queued", "running"}:
                return {
                    "status": "rejected",
                    "reason": "job_in_progress",
                    "active_job_id": active_add_gesture_job_id,
                    "message": "Another add-gesture job is already running.",
                }

        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "status": "queued",
            "stage": "queued",
            "message": f"Gesture '{gesture_name}' queued.",
            "error": None,
            "result": None,
            "gesture_name": gesture_name,
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
            "completed_at": None,
        }
        add_gesture_jobs[job_id] = job
        active_add_gesture_job_id = job_id

    thread = threading.Thread(
        target=_run_add_gesture_job,
        args=(job_id, gesture_name, description),
        daemon=True,
    )
    thread.start()

    return {
        "status": "queued",
        "job_id": job_id,
        "stage": "queued",
        "message": f"Gesture '{gesture_name}' job queued.",
    }


@app.get("/add-gesture/{job_id}")
def get_add_gesture_status(job_id: str):
    job = _get_job_copy(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job
