from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token

from app.services.user_storage_service import sanitize_user_id


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    is_guest: bool
    email: Optional[str] = None
    display_name: Optional[str] = None
    id_token: Optional[str] = None


def _extract_bearer_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization", "").strip()
    if not auth_header:
        return None
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    return token or None


def _verify_firebase_token(token: str) -> dict:
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "").strip() or None
    google_request = GoogleAuthRequest()
    decoded = id_token.verify_firebase_token(
        token,
        google_request,
        audience=project_id,
    )
    if not decoded:
        raise ValueError("Decoded token payload was empty.")
    return decoded


def resolve_request_user(request: Request) -> AuthUser:
    """
    Resolves the caller identity using:
    1) Firebase bearer token (verified), if provided.
    2) `X-User-Id` header.
    3) `guest`.
    """

    token = _extract_bearer_token(request)
    if token:
        try:
            decoded = _verify_firebase_token(token)
        except Exception as exc:
            raise HTTPException(
                status_code=401,
                detail=f"Invalid Firebase token: {exc}",
            ) from exc

        uid = (
            decoded.get("user_id")
            or decoded.get("uid")
            or decoded.get("sub")
        )
        if not uid:
            raise HTTPException(status_code=401, detail="Firebase token missing user id.")

        return AuthUser(
            user_id=sanitize_user_id(str(uid)),
            is_guest=False,
            email=decoded.get("email"),
            display_name=decoded.get("name"),
            id_token=token,
        )

    header_user = request.headers.get("x-user-id", "").strip()
    if header_user:
        sanitized = sanitize_user_id(header_user)
        return AuthUser(
            user_id=sanitized,
            is_guest=sanitized.startswith("guest"),
        )

    return AuthUser(user_id="guest", is_guest=True)
