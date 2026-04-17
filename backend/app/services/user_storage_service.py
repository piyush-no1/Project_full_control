from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


APP_DIR = Path(__file__).resolve().parent.parent
ML_CORE_DIR = APP_DIR / "ml_core"
USER_ROOT_DIR = ML_CORE_DIR / "user_data"

DEFAULT_DATASET_DIR = ML_CORE_DIR / "data"
DEFAULT_MODELS_DIR = ML_CORE_DIR / "models"
DEFAULT_SCRIPTS_DIR = ML_CORE_DIR / "scripts"
DEFAULT_HAND_LANDMARKER = ML_CORE_DIR / "hand_landmarker.task"


def sanitize_user_id(raw_user_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", raw_user_id.strip())
    cleaned = cleaned.strip("._-")
    if not cleaned:
        return "guest"
    return cleaned[:128]


@dataclass(frozen=True)
class UserStoragePaths:
    user_id: str
    root_dir: Path
    dataset_dir: Path
    models_dir: Path
    scripts_dir: Path
    hand_landmarker_path: Path

    @property
    def model_path(self) -> Path:
        return self.models_dir / "gesture_ann.keras"

    @property
    def label_map_path(self) -> Path:
        return self.models_dir / "label_map.json"

    @property
    def feature_stats_path(self) -> Path:
        return self.models_dir / "feature_stats.json"

    @property
    def gesture_config_path(self) -> Path:
        return self.models_dir / "gesture_config.json"

    def as_runtime_overrides(self) -> Dict[str, str]:
        return {
            "dataset_dir": str(self.dataset_dir),
            "model_path": str(self.model_path),
            "label_map_path": str(self.label_map_path),
            "feature_stats_path": str(self.feature_stats_path),
            "gesture_config_path": str(self.gesture_config_path),
            "scripts_dir": str(self.scripts_dir),
            "hand_landmarker_model_path": str(self.hand_landmarker_path),
        }


def _copy_if_missing(source: Path, target: Path) -> None:
    if not source.exists():
        return
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _bootstrap_user_files(paths: UserStoragePaths) -> None:
    model_files = [
        "gesture_ann.keras",
        "label_map.json",
        "feature_stats.json",
        "gesture_config.json",
    ]
    for filename in model_files:
        _copy_if_missing(DEFAULT_MODELS_DIR / filename, paths.models_dir / filename)

    if DEFAULT_HAND_LANDMARKER.exists():
        _copy_if_missing(DEFAULT_HAND_LANDMARKER, paths.hand_landmarker_path)

    if DEFAULT_DATASET_DIR.exists():
        for csv_file in DEFAULT_DATASET_DIR.glob("*.csv"):
            _copy_if_missing(csv_file, paths.dataset_dir / csv_file.name)

    if DEFAULT_SCRIPTS_DIR.exists():
        for script_file in DEFAULT_SCRIPTS_DIR.glob("*.py"):
            _copy_if_missing(script_file, paths.scripts_dir / script_file.name)


def get_user_storage(user_id: str) -> UserStoragePaths:
    safe_user_id = sanitize_user_id(user_id)
    root = USER_ROOT_DIR / safe_user_id
    should_bootstrap = not root.exists()
    dataset_dir = root / "data"
    models_dir = root / "models"
    scripts_dir = root / "scripts"
    hand_landmarker_path = root / "hand_landmarker.task"

    dataset_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    paths = UserStoragePaths(
        user_id=safe_user_id,
        root_dir=root,
        dataset_dir=dataset_dir,
        models_dir=models_dir,
        scripts_dir=scripts_dir,
        hand_landmarker_path=hand_landmarker_path,
    )
    if should_bootstrap:
        _bootstrap_user_files(paths)
    return paths
