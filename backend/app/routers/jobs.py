from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.gesture_models import (
    AddGestureJobRequest,
    JobCreatedResponse,
    JobStatusResponse,
)
from app.services.auth_service import resolve_request_user
from app.services.firebase_data_service import firebase_data_service
from app.services.gesture_job_service import gesture_job_service


router = APIRouter(tags=["Gesture Jobs"])


def _resolve_visible_job(request: Request, job_id: str) -> dict:
    user = resolve_request_user(request)
    job = gesture_job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Job is not accessible for this user.")
    return job


@router.post("/add-gesture", response_model=JobCreatedResponse)
def enqueue_add_gesture(payload: AddGestureJobRequest, request: Request):
    user = resolve_request_user(request)
    firebase_data_service.sync_user_profile(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        is_guest=user.is_guest,
        user_token=user.id_token,
    )

    gesture_name = payload.name.strip().replace(" ", "_")
    action_description = payload.description.strip()
    if payload.collection_mode == "browser":
        response = gesture_job_service.submit_finalize_gesture(
            user_id=user.user_id,
            gesture_name=gesture_name,
            action_description=action_description,
            cooldown=payload.cooldown,
            user_token=user.id_token,
        )
    else:
        response = gesture_job_service.submit_add_gesture(
            user_id=user.user_id,
            gesture_name=gesture_name,
            action_description=action_description,
            cooldown=payload.cooldown,
            user_token=user.id_token,
        )
    return response


@router.get("/add-gesture/{job_id}", response_model=JobStatusResponse)
def get_add_gesture_job(job_id: str, request: Request):
    return _resolve_visible_job(request, job_id)


@router.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, request: Request):
    return _resolve_visible_job(request, job_id)
