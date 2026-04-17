from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.firebase_data_service import firebase_data_service
from app.services.user_storage_service import UserStoragePaths, get_user_storage
from app.websocket.event_manager import event_manager


TERMINAL_STATES = {"completed", "failed", "rejected"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _csv_row_count(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0
    try:
        with csv_path.open("r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]
        if not lines:
            return 0
        if lines[0].lower().startswith("f0,"):
            return max(0, len(lines) - 1)
        return len(lines)
    except Exception:
        return 0


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


class GestureJobService:
    """
    In-process background worker for gesture data/training jobs.

    One training-related job is allowed at a time to avoid model file conflicts.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._active_job_id: Optional[str] = None

    def _emit(self, job: Dict[str, Any]) -> None:
        event_manager.emit_user_event_threadsafe(
            job["user_id"],
            {
                "type": "job_update",
                "job": dict(job),
            },
        )

    def _new_job(
        self,
        *,
        job_type: str,
        user_id: str,
        stage: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        job_id = str(uuid.uuid4())
        now = _utc_now_iso()
        payload: Dict[str, Any] = {
            "job_id": job_id,
            "job_type": job_type,
            "user_id": user_id,
            "status": "queued",
            "stage": stage,
            "message": message,
            "error": None,
            "result": None,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        if extra:
            payload.update(extra)
        return payload

    def _get_active_job_locked(self) -> Optional[Dict[str, Any]]:
        if self._active_job_id is None:
            return None
        return self._jobs.get(self._active_job_id)

    def _update_job(self, job_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            job.update(fields)
            job["updated_at"] = _utc_now_iso()
            if job.get("status") in TERMINAL_STATES and not job.get("completed_at"):
                job["completed_at"] = _utc_now_iso()
            snapshot = dict(job)
        self._emit(snapshot)
        return snapshot

    def _release_active_job(self, job_id: str) -> None:
        with self._lock:
            if self._active_job_id == job_id:
                self._active_job_id = None

    def _enqueue_job(
        self,
        *,
        job_type: str,
        user_id: str,
        message: str,
        worker,
        worker_args: tuple,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            active_job = self._get_active_job_locked()
            if active_job and active_job.get("status") in {"queued", "running"}:
                return {
                    "status": "rejected",
                    "reason": "job_in_progress",
                    "active_job_id": active_job["job_id"],
                    "message": "Another gesture training job is already running.",
                }

            job = self._new_job(
                job_type=job_type,
                user_id=user_id,
                stage="queued",
                message=message,
                extra=extra,
            )
            self._jobs[job["job_id"]] = job
            self._active_job_id = job["job_id"]

        self._emit(dict(job))

        thread = threading.Thread(
            target=worker,
            args=(job["job_id"], *worker_args),
            daemon=True,
        )
        thread.start()

        return {
            "status": "queued",
            "job_id": job["job_id"],
            "stage": "queued",
            "message": message,
        }

    def _apply_runtime_overrides(self, module, paths: UserStoragePaths) -> Dict[str, str]:
        overrides = {
            "DATASET_DIR": str(paths.dataset_dir),
            "MODEL_PATH": str(paths.model_path),
            "LABEL_MAP_PATH": str(paths.label_map_path),
            "FEATURE_STATS_PATH": str(paths.feature_stats_path),
            "GESTURE_CONFIG_PATH": str(paths.gesture_config_path),
            "SCRIPTS_DIR": str(paths.scripts_dir),
            "HAND_LANDMARKER_MODEL_PATH": str(paths.hand_landmarker_path),
        }
        original = {key: getattr(module, key) for key in overrides}
        for key, value in overrides.items():
            setattr(module, key, value)
        return original

    def _restore_runtime_overrides(self, module, original: Dict[str, str]) -> None:
        for key, value in original.items():
            setattr(module, key, value)

    def _set_cooldown(self, paths: UserStoragePaths, gesture_name: str, cooldown: float) -> None:
        config = _load_json(paths.gesture_config_path)
        config[gesture_name.lower()] = float(cooldown)
        _save_json(paths.gesture_config_path, config)

    def _run_add_job(
        self,
        job_id: str,
        user_id: str,
        gesture_name: str,
        action_description: str,
        cooldown: float,
        user_token: Optional[str],
    ) -> None:
        gesture_main = None
        original_paths: Dict[str, str] = {}
        paths = get_user_storage(user_id)

        try:
            from app.ml_core.gesture_control_api import main as gesture_main  # type: ignore

            original_paths = self._apply_runtime_overrides(gesture_main, paths)

            def progress_callback(stage: str, message: str) -> None:
                stage_value = stage if stage in {
                    "script_generation",
                    "data_collection",
                    "training",
                    "completed",
                    "failed",
                } else "training"
                self._update_job(
                    job_id,
                    status="running",
                    stage=stage_value,
                    message=message,
                )

            self._update_job(
                job_id,
                status="running",
                stage="script_generation",
                message=f"Generating automation script for '{gesture_name}'.",
            )
            result = gesture_main.add_new_gesture_api(
                gesture_name=gesture_name,
                action_description=action_description,
                progress_callback=progress_callback,
            )
            if result.get("status") == "success":
                self._set_cooldown(paths, gesture_name, cooldown)
                result["cooldown"] = float(cooldown)
                row_count = _csv_row_count(paths.dataset_dir / f"{gesture_name}.csv")
                self._update_job(
                    job_id,
                    status="completed",
                    stage="completed",
                    message=result.get("message", "Gesture added successfully."),
                    result=result,
                    error=None,
                )
                firebase_data_service.set_gesture_metadata(
                    user_id=user_id,
                    gesture_name=gesture_name,
                    metadata={
                        "samples": row_count,
                        "cooldown": float(cooldown),
                        "source": "camera",
                        "last_job_id": job_id,
                    },
                    user_token=user_token,
                )
            else:
                self._update_job(
                    job_id,
                    status="failed",
                    stage="failed",
                    message=result.get("message", "Failed to add gesture."),
                    result=result,
                    error=result,
                )
        except Exception as exc:
            self._update_job(
                job_id,
                status="failed",
                stage="failed",
                message=f"Unexpected error while adding '{gesture_name}'.",
                error=str(exc),
            )
        finally:
            if gesture_main is not None and original_paths:
                self._restore_runtime_overrides(gesture_main, original_paths)
            self._release_active_job(job_id)

    def _run_finalize_job(
        self,
        job_id: str,
        user_id: str,
        gesture_name: str,
        action_description: str,
        cooldown: float,
        user_token: Optional[str],
    ) -> None:
        gesture_main = None
        original_paths: Dict[str, str] = {}
        paths = get_user_storage(user_id)
        gesture_csv = paths.dataset_dir / f"{gesture_name}.csv"

        try:
            sample_count = _csv_row_count(gesture_csv)
            self._update_job(
                job_id,
                status="running",
                stage="data_collection",
                message=f"Validating uploaded samples for '{gesture_name}'.",
            )
            if sample_count <= 0:
                self._update_job(
                    job_id,
                    status="failed",
                    stage="failed",
                    message=(
                        "No uploaded samples found for this gesture. "
                        "Record gesture frames in browser first."
                    ),
                )
                return

            from app.ml_core.gesture_control_api import main as gesture_main  # type: ignore
            from app.ml_core.gesture_control_api.model_trainer import train_model

            original_paths = self._apply_runtime_overrides(gesture_main, paths)

            self._update_job(
                job_id,
                status="running",
                stage="script_generation",
                message=f"Generating automation script for '{gesture_name}'.",
            )
            script_ok, script_error = gesture_main._generate_script_via_groq(
                gesture_name, action_description
            )
            if not script_ok:
                self._update_job(
                    job_id,
                    status="failed",
                    stage="failed",
                    message=script_error or f"Failed to generate script for '{gesture_name}'.",
                )
                return

            self._set_cooldown(paths, gesture_name, cooldown)

            self._update_job(
                job_id,
                status="running",
                stage="training",
                message=f"Training model with uploaded samples for '{gesture_name}'.",
            )
            train_model(
                csv_path=str(paths.dataset_dir),
                model_output_path=str(paths.model_path),
                label_map_path=str(paths.label_map_path),
                feature_stats_path=str(paths.feature_stats_path),
            )

            result = {
                "status": "success",
                "gesture": gesture_name,
                "cooldown": float(cooldown),
                "samples": sample_count,
                "message": f"Gesture '{gesture_name}' ready from browser-captured samples.",
            }
            self._update_job(
                job_id,
                status="completed",
                stage="completed",
                message=result["message"],
                result=result,
                error=None,
            )
            firebase_data_service.set_gesture_metadata(
                user_id=user_id,
                gesture_name=gesture_name,
                metadata={
                    "samples": sample_count,
                    "cooldown": float(cooldown),
                    "source": "browser",
                    "last_job_id": job_id,
                },
                user_token=user_token,
            )
        except Exception as exc:
            self._update_job(
                job_id,
                status="failed",
                stage="failed",
                message=f"Failed to finalize browser gesture '{gesture_name}'.",
                error=str(exc),
            )
        finally:
            if gesture_main is not None and original_paths:
                self._restore_runtime_overrides(gesture_main, original_paths)
            self._release_active_job(job_id)

    def _count_remaining_with_data(self, paths: UserStoragePaths) -> int:
        count = 0
        if not paths.dataset_dir.exists():
            return 0
        for csv_file in paths.dataset_dir.glob("*.csv"):
            if _csv_row_count(csv_file) > 0:
                count += 1
        return count

    def _clear_model_artifacts(self, paths: UserStoragePaths) -> None:
        for path in (paths.model_path, paths.label_map_path, paths.feature_stats_path):
            _remove_if_exists(path)

    def _run_delete_job(
        self,
        job_id: str,
        user_id: str,
        gesture_name: str,
        user_token: Optional[str],
    ) -> None:
        paths = get_user_storage(user_id)
        gesture_clean = gesture_name.strip()
        if not gesture_clean:
            self._update_job(
                job_id,
                status="failed",
                stage="failed",
                message="Gesture name cannot be empty.",
            )
            self._release_active_job(job_id)
            return

        try:
            from app.ml_core.gesture_control_api.model_trainer import train_model

            matching_name: Optional[str] = None
            for csv_file in paths.dataset_dir.glob("*.csv"):
                if csv_file.stem.lower() == gesture_clean.lower():
                    matching_name = csv_file.stem
                    break

            if not matching_name:
                self._update_job(
                    job_id,
                    status="failed",
                    stage="failed",
                    message=f"Gesture '{gesture_clean}' not found.",
                )
                return

            self._update_job(
                job_id,
                status="running",
                stage="training",
                message=f"Deleting '{matching_name}' and retraining model.",
            )

            _remove_if_exists(paths.dataset_dir / f"{matching_name}.csv")
            _remove_if_exists(paths.scripts_dir / f"{matching_name}.py")

            config = _load_json(paths.gesture_config_path)
            config.pop(matching_name.lower(), None)
            _save_json(paths.gesture_config_path, config)

            remaining = self._count_remaining_with_data(paths)
            if remaining >= 2:
                train_model(
                    csv_path=str(paths.dataset_dir),
                    model_output_path=str(paths.model_path),
                    label_map_path=str(paths.label_map_path),
                    feature_stats_path=str(paths.feature_stats_path),
                )
                result = {
                    "status": "success",
                    "gesture": matching_name,
                    "message": f"Gesture '{matching_name}' deleted and model retrained.",
                    "remaining_gestures": remaining,
                }
            else:
                self._clear_model_artifacts(paths)
                result = {
                    "status": "success",
                    "gesture": matching_name,
                    "message": (
                        f"Gesture '{matching_name}' deleted. "
                        "Not enough gestures remain to train a model."
                    ),
                    "remaining_gestures": remaining,
                }

            self._update_job(
                job_id,
                status="completed",
                stage="completed",
                message=result["message"],
                result=result,
                error=None,
            )
            firebase_data_service.delete_gesture_metadata(
                user_id=user_id,
                gesture_name=matching_name,
                user_token=user_token,
            )
        except Exception as exc:
            self._update_job(
                job_id,
                status="failed",
                stage="failed",
                message=f"Failed to delete '{gesture_clean}'.",
                error=str(exc),
            )
        finally:
            self._release_active_job(job_id)

    def _run_retrain_job(
        self,
        job_id: str,
        user_id: str,
        user_token: Optional[str],
    ) -> None:
        paths = get_user_storage(user_id)
        try:
            from app.ml_core.gesture_control_api.model_trainer import train_model

            self._update_job(
                job_id,
                status="running",
                stage="training",
                message="Retraining model with current gesture dataset.",
            )
            remaining = self._count_remaining_with_data(paths)
            if remaining < 2:
                self._clear_model_artifacts(paths)
                self._update_job(
                    job_id,
                    status="completed",
                    stage="completed",
                    message="Not enough gesture classes to retrain (need at least 2).",
                    result={
                        "status": "insufficient_data",
                        "remaining_gestures": remaining,
                    },
                )
                return

            train_model(
                csv_path=str(paths.dataset_dir),
                model_output_path=str(paths.model_path),
                label_map_path=str(paths.label_map_path),
                feature_stats_path=str(paths.feature_stats_path),
            )
            self._update_job(
                job_id,
                status="completed",
                stage="completed",
                message="Training complete.",
                result={
                    "status": "success",
                    "remaining_gestures": remaining,
                },
            )
            firebase_data_service.set_user_settings(
                user_id=user_id,
                settings={
                    "last_training_status": "success",
                    "last_retrain_job_id": job_id,
                    "remaining_gestures": remaining,
                },
                user_token=user_token,
            )
        except Exception as exc:
            self._update_job(
                job_id,
                status="failed",
                stage="failed",
                message="Retraining failed.",
                error=str(exc),
            )
            firebase_data_service.set_user_settings(
                user_id=user_id,
                settings={
                    "last_training_status": "failed",
                    "last_retrain_job_id": job_id,
                },
                user_token=user_token,
            )
        finally:
            self._release_active_job(job_id)

    def submit_add_gesture(
        self,
        *,
        user_id: str,
        gesture_name: str,
        action_description: str,
        cooldown: float = 2.0,
        user_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._enqueue_job(
            job_type="add_gesture",
            user_id=user_id,
            message=f"Gesture '{gesture_name}' queued for creation.",
            worker=self._run_add_job,
            worker_args=(user_id, gesture_name, action_description, cooldown, user_token),
            extra={"gesture_name": gesture_name},
        )

    def submit_finalize_gesture(
        self,
        *,
        user_id: str,
        gesture_name: str,
        action_description: str,
        cooldown: float = 2.0,
        user_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._enqueue_job(
            job_type="finalize_gesture",
            user_id=user_id,
            message=f"Gesture '{gesture_name}' queued for browser finalization.",
            worker=self._run_finalize_job,
            worker_args=(user_id, gesture_name, action_description, cooldown, user_token),
            extra={"gesture_name": gesture_name},
        )

    def submit_delete_gesture(
        self,
        *,
        user_id: str,
        gesture_name: str,
        user_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._enqueue_job(
            job_type="delete_gesture",
            user_id=user_id,
            message=f"Gesture '{gesture_name}' queued for deletion.",
            worker=self._run_delete_job,
            worker_args=(user_id, gesture_name, user_token),
            extra={"gesture_name": gesture_name},
        )

    def submit_retrain(self, *, user_id: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        return self._enqueue_job(
            job_type="retrain_model",
            user_id=user_id,
            message="Model retraining queued.",
            worker=self._run_retrain_job,
            worker_args=(user_id, user_token),
        )

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None


gesture_job_service = GestureJobService()
