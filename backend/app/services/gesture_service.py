from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from app.services.frame_buffer import frame_buffer
from app.services.model_state import model_state
from app.services.user_storage_service import get_user_storage


SERVICE_DIR = Path(__file__).resolve().parent
APP_DIR = SERVICE_DIR.parent
ML_CORE_DIR = APP_DIR / "ml_core"
GESTURE_STREAM_SCRIPT = ML_CORE_DIR / "run_gesture_stream.py"


def _build_environment(user_id: Optional[str]) -> Dict[str, str]:
    env: Dict[str, str] = {"FULL_CONTROL_STREAMING": "true"}
    if user_id:
        storage = get_user_storage(user_id)
        env["GESTURE_MODEL_PATH"] = str(storage.model_path)
        env["GESTURE_LABEL_MAP_PATH"] = str(storage.label_map_path)
        env["GESTURE_FEATURE_STATS_PATH"] = str(storage.feature_stats_path)
        env["GESTURE_DATASET_DIR"] = str(storage.dataset_dir)
        env["GESTURE_SCRIPTS_DIR"] = str(storage.scripts_dir)
        env["HAND_LANDMARKER_MODEL_PATH"] = str(storage.hand_landmarker_path)
    return env


def _stop_air_stylus_if_running() -> None:
    if not model_state.air_stylus_running:
        return
    from app.services.air_stylus_service import stop_air_stylus

    stop_air_stylus()


def _run_gesture_thread(
    user_id: Optional[str],
    env_overrides: Dict[str, str],
    stop_event: threading.Event,
) -> None:
    original_env: Dict[str, Optional[str]] = {}
    try:
        for key, value in env_overrides.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        from app.ml_core import run_gesture_stream

        run_gesture_stream.set_stop_event(stop_event)
        run_gesture_stream.run_gesture_control_streaming()
    except Exception as exc:
        print(f"[Gesture] Worker crashed: {exc}")
    finally:
        try:
            from app.ml_core import run_gesture_stream

            run_gesture_stream.set_stop_event(None)
        except Exception:
            pass

        for key, previous in original_env.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

        model_state.gesture_running = False
        model_state.gesture_thread = None
        model_state.gesture_stop_event = None
        model_state.gesture_process = None
        if model_state.active_mode == "gesture":
            model_state.active_mode = "none"
            model_state.active_user_id = None
        frame_buffer.clear()


def start_gesture(user_id: Optional[str] = None) -> str:
    if model_state.gesture_running:
        return "Gesture already running"

    _stop_air_stylus_if_running()

    if not GESTURE_STREAM_SCRIPT.exists():
        return f"Gesture stream script not found: {GESTURE_STREAM_SCRIPT}"

    env_overrides = _build_environment(user_id)
    requested_model = env_overrides.get("GESTURE_MODEL_PATH")
    if requested_model and not Path(requested_model).exists():
        return f"Model not found: {requested_model}"

    stop_event = threading.Event()
    thread = threading.Thread(
        target=_run_gesture_thread,
        args=(user_id, env_overrides, stop_event),
        daemon=True,
    )

    model_state.gesture_thread = thread
    model_state.gesture_stop_event = stop_event
    model_state.gesture_process = None
    model_state.gesture_running = True
    model_state.active_mode = "gesture"
    model_state.active_user_id = user_id

    thread.start()
    time.sleep(1.0)

    if not thread.is_alive():
        model_state.gesture_running = False
        model_state.gesture_thread = None
        model_state.gesture_stop_event = None
        model_state.active_mode = "none"
        model_state.active_user_id = None
        return "Gesture process exited unexpectedly."

    return "Gesture started"


def stop_gesture() -> str:
    if not model_state.gesture_running or not model_state.gesture_thread:
        return "Gesture not running"

    stop_event = model_state.gesture_stop_event
    if stop_event is not None:
        stop_event.set()

    worker = model_state.gesture_thread
    worker.join(timeout=4.0)
    if worker.is_alive():
        return "Gesture stop timed out"

    model_state.gesture_thread = None
    model_state.gesture_stop_event = None
    model_state.gesture_process = None
    model_state.gesture_running = False
    if model_state.active_mode == "gesture":
        model_state.active_mode = "none"
        model_state.active_user_id = None

    frame_buffer.clear()
    return "Gesture stopped"


def get_gesture_status() -> bool:
    return model_state.gesture_running


def start_gesture_engine(user_id: Optional[str] = None):
    result = start_gesture(user_id)
    if result == "Gesture started":
        return {"status": "started"}
    if result == "Gesture already running":
        return {"status": "already_running"}
    return {"status": "error", "message": result}


def stop_gesture_engine():
    result = stop_gesture()
    if result == "Gesture not running":
        return {"status": "not_running"}
    return {"status": "stopped"}


def get_engine_status():
    return {"running": get_gesture_status()}
