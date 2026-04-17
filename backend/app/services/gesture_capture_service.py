from __future__ import annotations

import base64
import csv
from typing import List

import cv2
import numpy as np

from app.ml_core.gesture_control_api.data_collector import HandLandmarkExtractor
from app.services.user_storage_service import get_user_storage


def _decode_base64_frame(frame_data: str) -> np.ndarray | None:
    try:
        encoded = frame_data.split(",", 1)[1] if "," in frame_data else frame_data
        raw = base64.b64decode(encoded)
        np_buf = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(np_buf, cv2.IMREAD_COLOR)
        return frame
    except Exception:
        return None


def append_samples_from_browser_frames(
    *,
    user_id: str,
    gesture_name: str,
    frames: List[str],
) -> dict:
    storage = get_user_storage(user_id)
    csv_path = storage.dataset_dir / f"{gesture_name}.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    header = [f"f{i}" for i in range(63)] + ["label"]
    file_exists = csv_path.exists()
    added_samples = 0
    total_frames = len(frames)
    rows = []

    extractor = HandLandmarkExtractor(str(storage.hand_landmarker_path))
    try:
        for frame_data in frames:
            frame = _decode_base64_frame(frame_data)
            if frame is None:
                continue
            features = extractor.extract(frame)
            if features is None or features.shape[0] != 63:
                continue
            rows.append(list(features.astype(float)) + [gesture_name])
            added_samples += 1
    finally:
        extractor.close()

    if rows:
        with csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if not file_exists:
                writer.writerow(header)
            writer.writerows(rows)

    return {
        "status": "success",
        "gesture_name": gesture_name,
        "total_frames": total_frames,
        "added_samples": added_samples,
        "csv_path": str(csv_path),
    }
