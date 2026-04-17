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
AIRSTYLUS_STREAM_SCRIPT = ML_CORE_DIR / "run_airstylus_stream.py"


def _build_environment(user_id: Optional[str]) -> Dict[str, str]:
    env: Dict[str, str] = {"FULL_CONTROL_STREAMING": "true"}
    if user_id:
        storage = get_user_storage(user_id)
        env["HAND_LANDMARKER_MODEL_PATH"] = str(storage.hand_landmarker_path)
    return env


def _stop_gesture_if_running() -> None:
    if not model_state.gesture_running:
        return
    from app.services.gesture_service import stop_gesture

    stop_gesture()


def _run_air_stylus_thread(
    user_id: Optional[str],
    env_overrides: Dict[str, str],
    stop_event: threading.Event,
) -> None:
    original_env: Dict[str, Optional[str]] = {}
    try:
        for key, value in env_overrides.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        from app.ml_core import run_airstylus_stream

        run_airstylus_stream.set_stop_event(stop_event)
        run_airstylus_stream.run_air_stylus_streaming()
    except Exception as exc:
        print(f"[AirStylus] Worker crashed: {exc}")
    finally:
        try:
            from app.ml_core import run_airstylus_stream

            run_airstylus_stream.set_stop_event(None)
        except Exception:
            pass

        for key, previous in original_env.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

        model_state.air_stylus_running = False
        model_state.air_stylus_thread = None
        model_state.air_stylus_stop_event = None
        model_state.air_stylus_process = None
        if model_state.active_mode == "air_stylus":
            model_state.active_mode = "none"
            model_state.active_user_id = None
        frame_buffer.clear()


def start_air_stylus(user_id: Optional[str] = None) -> str:
    if model_state.air_stylus_running:
        return "Air Stylus already running"

    _stop_gesture_if_running()

    if not AIRSTYLUS_STREAM_SCRIPT.exists():
        return f"Air Stylus stream script not found: {AIRSTYLUS_STREAM_SCRIPT}"

    env_overrides = _build_environment(user_id)

    stop_event = threading.Event()
    thread = threading.Thread(
        target=_run_air_stylus_thread,
        args=(user_id, env_overrides, stop_event),
        daemon=True,
    )

    model_state.air_stylus_thread = thread
    model_state.air_stylus_stop_event = stop_event
    model_state.air_stylus_process = None
    model_state.air_stylus_running = True
    model_state.active_mode = "air_stylus"
    model_state.active_user_id = user_id

    thread.start()
    time.sleep(1.0)

    if not thread.is_alive():
        model_state.air_stylus_running = False
        model_state.air_stylus_thread = None
        model_state.air_stylus_stop_event = None
        model_state.active_mode = "none"
        model_state.active_user_id = None
        return "Air Stylus process exited unexpectedly."

    return "Air Stylus started"


def stop_air_stylus() -> str:
    if not model_state.air_stylus_running or not model_state.air_stylus_thread:
        return "Air Stylus not running"

    stop_event = model_state.air_stylus_stop_event
    if stop_event is not None:
        stop_event.set()

    worker = model_state.air_stylus_thread
    worker.join(timeout=4.0)
    if worker.is_alive():
        return "Air Stylus stop timed out"

    model_state.air_stylus_thread = None
    model_state.air_stylus_stop_event = None
    model_state.air_stylus_process = None
    model_state.air_stylus_running = False
    if model_state.active_mode == "air_stylus":
        model_state.active_mode = "none"
        model_state.active_user_id = None

    frame_buffer.clear()
    return "Air Stylus stopped"
