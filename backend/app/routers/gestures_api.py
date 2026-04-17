"""
Gesture management API.

Endpoints:
- GET    /api/gestures
- POST   /api/gestures
- POST   /api/gestures/upload-samples
- DELETE /api/gestures/{gesture_name}
- POST   /api/gestures/retrain
- GET    /api/gestures/jobs/{job_id}
- POST   /retrain-model  (legacy alias)
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Request

from app.models.gesture_models import (
    AddGestureRequest,
    GestureInfo,
    JobCreatedResponse,
    JobStatusResponse,
    UploadGestureFramesRequest,
    UploadGestureFramesResponse,
)
from app.services.auth_service import resolve_request_user
from app.services.firebase_data_service import firebase_data_service
from app.services.gesture_capture_service import append_samples_from_browser_frames
from app.services.gesture_job_service import gesture_job_service
from app.services.user_storage_service import get_user_storage


PREDEFINED_GESTURES = {
    "scroll_up",
    "scroll_down",
    "swipe_right",
    "swipe_left",
    "zoom_in",
    "zoom_out",
    "volume_up",
    "volume_down",
    "play/pause",
    "play_pause",
    "play-pause",
    "ok",
}

router = APIRouter(prefix="/api/gestures", tags=["Gestures"])
legacy_router = APIRouter(tags=["Gestures"])


def _is_predefined(gesture_name: str) -> bool:
    return gesture_name.strip().lower() in PREDEFINED_GESTURES


def _list_registered_gestures(user_id: str) -> List[GestureInfo]:
    paths = get_user_storage(user_id)
    if not paths.dataset_dir.exists():
        return []

    gestures: list[GestureInfo] = []
    for csv_file in sorted(paths.dataset_dir.glob("*.csv")):
        name = csv_file.stem
        gestures.append(
            GestureInfo(
                name=name,
                isPredefined=_is_predefined(name),
                hasScript=(paths.scripts_dir / f"{name}.py").exists(),
            )
        )
    return gestures


def _resolve_visible_job(request: Request, job_id: str) -> dict:
    user = resolve_request_user(request)
    job = gesture_job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Job is not accessible for this user.")
    return job


@router.get("", response_model=List[GestureInfo])
def get_gestures(request: Request):
    user = resolve_request_user(request)
    firebase_data_service.sync_user_profile(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        is_guest=user.is_guest,
        user_token=user.id_token,
    )
    return _list_registered_gestures(user.user_id)


@router.post("", response_model=JobCreatedResponse)
def add_gesture(payload: AddGestureRequest, request: Request):
    user = resolve_request_user(request)
    firebase_data_service.sync_user_profile(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        is_guest=user.is_guest,
        user_token=user.id_token,
    )

    gesture_name = payload.gesture_name.strip().replace(" ", "_")
    if not gesture_name:
        raise HTTPException(status_code=400, detail="Gesture name cannot be empty.")

    action_description = payload.action_description.strip()
    if not action_description:
        raise HTTPException(status_code=400, detail="Action description cannot be empty.")

    existing = {item.name.lower() for item in _list_registered_gestures(user.user_id)}
    if payload.collection_mode == "camera" and gesture_name.lower() in existing:
        raise HTTPException(
            status_code=400,
            detail=f"Gesture '{gesture_name}' already exists.",
        )

    if payload.collection_mode == "browser":
        return gesture_job_service.submit_finalize_gesture(
            user_id=user.user_id,
            gesture_name=gesture_name,
            action_description=action_description,
            cooldown=payload.cooldown,
            user_token=user.id_token,
        )

    return gesture_job_service.submit_add_gesture(
        user_id=user.user_id,
        gesture_name=gesture_name,
        action_description=action_description,
        cooldown=payload.cooldown,
        user_token=user.id_token,
    )


@router.delete("/{gesture_name}", response_model=JobCreatedResponse)
def delete_gesture(gesture_name: str, request: Request):
    user = resolve_request_user(request)
    return gesture_job_service.submit_delete_gesture(
        user_id=user.user_id,
        gesture_name=gesture_name,
        user_token=user.id_token,
    )


@router.post("/retrain", response_model=JobCreatedResponse)
def retrain_model(request: Request):
    user = resolve_request_user(request)
    return gesture_job_service.submit_retrain(
        user_id=user.user_id,
        user_token=user.id_token,
    )


@router.post("/upload-samples", response_model=UploadGestureFramesResponse)
def upload_browser_samples(payload: UploadGestureFramesRequest, request: Request):
    user = resolve_request_user(request)
    firebase_data_service.sync_user_profile(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        is_guest=user.is_guest,
        user_token=user.id_token,
    )

    gesture_name = payload.gesture_name.strip().replace(" ", "_")
    if not gesture_name:
        raise HTTPException(status_code=400, detail="Gesture name cannot be empty.")
    if not payload.frames:
        raise HTTPException(status_code=400, detail="No frames were provided.")

    result = append_samples_from_browser_frames(
        user_id=user.user_id,
        gesture_name=gesture_name,
        frames=payload.frames,
    )
    firebase_data_service.set_gesture_metadata(
        user_id=user.user_id,
        gesture_name=gesture_name,
        metadata={
            "samples": result["added_samples"],
            "source": "browser_capture_upload",
        },
        user_token=user.id_token,
    )
    return result


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, request: Request):
    return _resolve_visible_job(request, job_id)


@legacy_router.post("/retrain-model", response_model=JobCreatedResponse)
def legacy_retrain_model(request: Request):
    user = resolve_request_user(request)
    return gesture_job_service.submit_retrain(
        user_id=user.user_id,
        user_token=user.id_token,
    )
