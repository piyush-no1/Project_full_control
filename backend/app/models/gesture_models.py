from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class GestureInfo(BaseModel):
    name: str
    isPredefined: bool
    hasScript: bool


class AddGestureRequest(BaseModel):
    gesture_name: str = Field(..., min_length=1)
    action_description: str = Field(..., min_length=1)
    cooldown: float = 2.0
    collection_mode: Literal["camera", "browser"] = "camera"


class AddGestureJobRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    cooldown: float = 2.0
    collection_mode: Literal["camera", "browser"] = "camera"


class JobCreatedResponse(BaseModel):
    status: Literal["queued", "rejected"]
    job_id: Optional[str] = None
    stage: Optional[str] = None
    message: str
    reason: Optional[str] = None
    active_job_id: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    user_id: str
    status: str
    stage: str
    message: str
    error: Optional[Any] = None
    result: Optional[Any] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


class ControlStatusResponse(BaseModel):
    active_mode: Literal["gesture", "air_stylus", "none"]
    gesture_running: bool
    air_stylus_running: bool
    active_user_id: Optional[str] = None


class UploadGestureFramesRequest(BaseModel):
    gesture_name: str = Field(..., min_length=1)
    frames: List[str]


class UploadGestureFramesResponse(BaseModel):
    status: str
    gesture_name: str
    total_frames: int
    added_samples: int
    csv_path: str


class UserSettingsRequest(BaseModel):
    settings: Dict[str, Any]
