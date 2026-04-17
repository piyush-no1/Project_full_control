from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account


FIRESTORE_SCOPE = "https://www.googleapis.com/auth/datastore"


def _to_firestore_value(value: Any) -> Dict[str, Any]:
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_to_firestore_value(v) for v in value]}}
    if isinstance(value, dict):
        return {
            "mapValue": {
                "fields": {str(k): _to_firestore_value(v) for k, v in value.items()}
            }
        }
    return {"stringValue": json.dumps(value)}


def _to_firestore_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _to_firestore_value(value) for key, value in payload.items()}


@dataclass
class _TokenCache:
    value: Optional[str] = None
    expires_at: float = 0.0


class FirebaseDataService:
    """
    Firestore REST integration with service-account or user-token auth.

    Collection layout:
    - users/{uid}
    - users/{uid}/settings/default
    - users/{uid}/gestures/{gesture_name}
    """

    def __init__(self) -> None:
        self.project_id = os.environ.get("FIREBASE_PROJECT_ID", "").strip()
        self.service_account_path = (
            os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        )
        self._credentials = None
        self._token_cache = _TokenCache()

        if self.service_account_path and os.path.exists(self.service_account_path):
            self._credentials = service_account.Credentials.from_service_account_file(
                self.service_account_path,
                scopes=[FIRESTORE_SCOPE],
            )

    @property
    def enabled(self) -> bool:
        return bool(self.project_id)

    @property
    def _documents_base_url(self) -> str:
        return (
            f"https://firestore.googleapis.com/v1/projects/{self.project_id}"
            "/databases/(default)/documents"
        )

    def _get_service_account_token(self) -> Optional[str]:
        if not self._credentials:
            return None

        now = time.time()
        if self._token_cache.value and now < self._token_cache.expires_at - 60:
            return self._token_cache.value

        creds = self._credentials
        creds.refresh(GoogleAuthRequest())
        token = creds.token
        if not token:
            return None

        expires = creds.expiry.timestamp() if creds.expiry else now + 3000
        self._token_cache = _TokenCache(value=token, expires_at=expires)
        return token

    def _resolve_auth_token(self, user_token: Optional[str]) -> Optional[str]:
        token = self._get_service_account_token()
        if token:
            return token
        return user_token

    def _request(
        self,
        method: str,
        document_path: str,
        *,
        user_token: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        token = self._resolve_auth_token(user_token)
        if not token:
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{self._documents_base_url}/{document_path}"

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=payload,
                timeout=12,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json() if response.content else {}
        except Exception:
            return None

    def _upsert_document(
        self,
        document_path: str,
        fields: Dict[str, Any],
        *,
        user_token: Optional[str] = None,
    ) -> None:
        self._request(
            "PATCH",
            document_path,
            user_token=user_token,
            payload={"fields": _to_firestore_fields(fields)},
        )

    def _delete_document(self, document_path: str, *, user_token: Optional[str] = None) -> None:
        self._request("DELETE", document_path, user_token=user_token)

    def sync_user_profile(
        self,
        *,
        user_id: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        is_guest: bool = False,
        user_token: Optional[str] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "is_guest": is_guest,
            "updated_at": int(time.time()),
        }
        if email:
            payload["email"] = email
        if display_name:
            payload["display_name"] = display_name
        self._upsert_document(f"users/{user_id}", payload, user_token=user_token)

    def set_user_settings(
        self,
        *,
        user_id: str,
        settings: Dict[str, Any],
        user_token: Optional[str] = None,
    ) -> None:
        payload = dict(settings)
        payload["updated_at"] = int(time.time())
        self._upsert_document(
            f"users/{user_id}/settings/default",
            payload,
            user_token=user_token,
        )

    def get_user_settings(
        self,
        *,
        user_id: str,
        user_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        doc = self._request(
            "GET",
            f"users/{user_id}/settings/default",
            user_token=user_token,
        )
        if not doc:
            return None

        fields = doc.get("fields", {})
        parsed: Dict[str, Any] = {}
        for key, firestore_value in fields.items():
            parsed[key] = self._from_firestore_value(firestore_value)
        return parsed

    def set_gesture_metadata(
        self,
        *,
        user_id: str,
        gesture_name: str,
        metadata: Dict[str, Any],
        user_token: Optional[str] = None,
    ) -> None:
        payload = dict(metadata)
        payload["gesture_name"] = gesture_name
        payload["updated_at"] = int(time.time())
        self._upsert_document(
            f"users/{user_id}/gestures/{gesture_name}",
            payload,
            user_token=user_token,
        )

    def delete_gesture_metadata(
        self,
        *,
        user_id: str,
        gesture_name: str,
        user_token: Optional[str] = None,
    ) -> None:
        self._delete_document(
            f"users/{user_id}/gestures/{gesture_name}",
            user_token=user_token,
        )

    def _from_firestore_value(self, value: Dict[str, Any]) -> Any:
        if "nullValue" in value:
            return None
        if "booleanValue" in value:
            return value["booleanValue"]
        if "integerValue" in value:
            return int(value["integerValue"])
        if "doubleValue" in value:
            return float(value["doubleValue"])
        if "stringValue" in value:
            return value["stringValue"]
        if "arrayValue" in value:
            arr = value["arrayValue"].get("values", [])
            return [self._from_firestore_value(v) for v in arr]
        if "mapValue" in value:
            fields = value["mapValue"].get("fields", {})
            return {k: self._from_firestore_value(v) for k, v in fields.items()}
        return value


firebase_data_service = FirebaseDataService()

