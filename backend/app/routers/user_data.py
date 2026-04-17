from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, Request

from app.models.gesture_models import UserSettingsRequest
from app.services.auth_service import resolve_request_user
from app.services.firebase_data_service import firebase_data_service
from app.services.user_storage_service import get_user_storage


router = APIRouter(prefix="/api/user", tags=["User Data"])


def _settings_file_path(user_id: str):
    storage = get_user_storage(user_id)
    return storage.root_dir / "settings.json"


def _load_local_settings(user_id: str) -> Dict[str, Any]:
    settings_path = _settings_file_path(user_id)
    if not settings_path.exists():
        return {}
    try:
        with settings_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _save_local_settings(user_id: str, settings: Dict[str, Any]) -> None:
    settings_path = _settings_file_path(user_id)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with settings_path.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)


@router.get("/profile")
def get_profile(request: Request):
    user = resolve_request_user(request)
    firebase_data_service.sync_user_profile(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        is_guest=user.is_guest,
        user_token=user.id_token,
    )
    return {
        "user_id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "is_guest": user.is_guest,
        "firebase_enabled": firebase_data_service.enabled,
    }


@router.put("/profile")
def update_profile(request: Request):
    user = resolve_request_user(request)
    firebase_data_service.sync_user_profile(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        is_guest=user.is_guest,
        user_token=user.id_token,
    )
    return {"status": "success", "user_id": user.user_id}


@router.get("/settings")
def get_settings(request: Request):
    user = resolve_request_user(request)
    local_settings = _load_local_settings(user.user_id)
    remote_settings = firebase_data_service.get_user_settings(
        user_id=user.user_id,
        user_token=user.id_token,
    )
    merged = dict(local_settings)
    if remote_settings:
        merged.update(remote_settings)
    return {"status": "success", "settings": merged}


@router.put("/settings")
def update_settings(payload: UserSettingsRequest, request: Request):
    user = resolve_request_user(request)
    settings = payload.settings or {}

    existing = _load_local_settings(user.user_id)
    existing.update(settings)
    _save_local_settings(user.user_id, existing)

    firebase_data_service.set_user_settings(
        user_id=user.user_id,
        settings=existing,
        user_token=user.id_token,
    )
    return {"status": "success", "settings": existing}

