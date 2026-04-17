from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable


ML_CORE_DIR = Path(__file__).resolve().parent
APP_DIR = ML_CORE_DIR.parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT_DIR = BACKEND_DIR.parent
GESTURE_API_DIR = ML_CORE_DIR / "gesture_control_api"
MOUSE_CONTROL_DIR = ML_CORE_DIR / "Mouse_Control"

MODELS_DIR = ML_CORE_DIR / "models"
DATA_DIR = ML_CORE_DIR / "data"
SCRIPTS_DIR = ML_CORE_DIR / "scripts"
DEFAULT_HAND_LANDMARKER_PATH = ML_CORE_DIR / "hand_landmarker.task"


def ensure_runtime_import_paths() -> None:
    """Make backend/ml_core imports independent of the current working directory."""
    desired_paths = (BACKEND_DIR, ML_CORE_DIR, GESTURE_API_DIR)
    desired_strings = {str(path) for path in desired_paths}
    current_strings = set(sys.path)

    for path in reversed(desired_paths):
        path_str = str(path)
        if path_str not in current_strings:
            sys.path.insert(0, path_str)

    # Keep duplicate path growth under control during repeated imports.
    deduped: list[str] = []
    seen: set[str] = set()
    for path in sys.path:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    sys.path[:] = deduped


def first_existing_path(candidates: Iterable[Path | str]) -> Path | None:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists():
            return path.resolve()
    return None


def resolve_hand_landmarker_path() -> Path:
    candidate = first_existing_path(
        [
            os.environ.get("HAND_LANDMARKER_MODEL_PATH", "").strip(),
            DEFAULT_HAND_LANDMARKER_PATH,
            GESTURE_API_DIR / "hand_landmarker.task",
            MOUSE_CONTROL_DIR / "hand_landmarker.task",
        ]
    )
    return candidate or DEFAULT_HAND_LANDMARKER_PATH


def resolve_runtime_path(env_var: str, default_path: Path | str) -> Path:
    override = os.environ.get(env_var, "").strip()
    candidate = first_existing_path([override, default_path])
    return candidate or Path(default_path)
