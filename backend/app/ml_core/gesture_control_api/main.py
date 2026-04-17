import os
import json
import time
import math
import subprocess
import sys
import platform
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from collections import deque

import cv2
import numpy as np
import tensorflow as tf
from tensorflow import keras

import pyautogui

BACKEND_DIR = Path(__file__).resolve().parents[3]
backend_dir_str = str(BACKEND_DIR)
if backend_dir_str not in sys.path:
    sys.path.insert(0, backend_dir_str)

from app.ml_core.path_utils import (
    DATA_DIR,
    MODELS_DIR,
    SCRIPTS_DIR as DEFAULT_SCRIPTS_DIR,
    resolve_hand_landmarker_path,
    resolve_runtime_path,
)

try:
    from .data_collector import HandLandmarkExtractor, collect_gesture_samples
    from .model_trainer import (
        train_model,
        engineer_hand_features,
        load_feature_stats,
    )
    from .slm_agent import SLMCodeAgent
except ImportError:
    from data_collector import HandLandmarkExtractor, collect_gesture_samples
    from model_trainer import (
        train_model,
        engineer_hand_features,
        load_feature_stats,
    )
    from slm_agent import SLMCodeAgent

pyautogui.FAILSAFE = False

# ============================================================
# Platform Detection
# ============================================================
CURRENT_PLATFORM = platform.system()
IS_MACOS = CURRENT_PLATFORM == "Darwin"
IS_WINDOWS = CURRENT_PLATFORM == "Windows"
IS_LINUX = CURRENT_PLATFORM == "Linux"

PLATFORM_NAME = "macOS" if IS_MACOS else ("Windows" if IS_WINDOWS else "Linux")
print(f"[Platform] Detected operating system: {PLATFORM_NAME} ({CURRENT_PLATFORM})")

# Paths / config
GESTURE_API_DIR = Path(__file__).resolve().parent
ML_CORE_DIR = GESTURE_API_DIR.parent
DATASET_DIR = str(resolve_runtime_path("GESTURE_DATASET_DIR", DATA_DIR))
MODEL_PATH = str(resolve_runtime_path("GESTURE_MODEL_PATH", MODELS_DIR / "gesture_ann.keras"))
LABEL_MAP_PATH = str(resolve_runtime_path("GESTURE_LABEL_MAP_PATH", MODELS_DIR / "label_map.json"))
FEATURE_STATS_PATH = str(resolve_runtime_path("GESTURE_FEATURE_STATS_PATH", MODELS_DIR / "feature_stats.json"))
GESTURE_CONFIG_PATH = str(resolve_runtime_path("GESTURE_CONFIG_PATH", MODELS_DIR / "gesture_config.json"))
SCRIPTS_DIR = str(resolve_runtime_path("GESTURE_SCRIPTS_DIR", DEFAULT_SCRIPTS_DIR))
HAND_LANDMARKER_MODEL_PATH = str(resolve_hand_landmarker_path())

TRIGGER_CONFIDENCE = 0.80
REQUIRED_STREAK = 5
SMOOTHING_WINDOW = 7
SCROLL_AMOUNT = 700
VOLUME_STEP_COUNT = 5

COOLDOWN_REPEATABLE = 0.01
COOLDOWN_MODERATE = 2.0
COOLDOWN_ONESHOT = 5.0

BASE_GESTURE_COOLDOWNS = {
    "scroll_up": COOLDOWN_REPEATABLE,
    "scroll_down": COOLDOWN_REPEATABLE,
    "swipe_right": COOLDOWN_MODERATE,
    "swipe_left": COOLDOWN_MODERATE,
    "zoom_in": COOLDOWN_REPEATABLE,
    "zoom_out": COOLDOWN_REPEATABLE,
    "volume_up": COOLDOWN_REPEATABLE,
    "volume_down": COOLDOWN_REPEATABLE,
    "play/pause": COOLDOWN_MODERATE,
    "play_pause": COOLDOWN_MODERATE,
    "play-pause": COOLDOWN_MODERATE,
}

PREDEFINED_GESTURES = set(BASE_GESTURE_COOLDOWNS.keys())

# ============================================================
# UI Color Palette (BGR) — Matching data_collector style
# ============================================================
UI_COLOR_BG_PANEL = (25, 25, 25)
UI_COLOR_PANEL_BORDER = (60, 60, 60)
UI_COLOR_TITLE = (255, 200, 50)
UI_COLOR_SUBTITLE = (200, 200, 200)
UI_COLOR_GESTURE_NAME = (0, 255, 120)
UI_COLOR_CONFIDENCE_HIGH = (0, 255, 0)
UI_COLOR_CONFIDENCE_MED = (0, 200, 255)
UI_COLOR_CONFIDENCE_LOW = (0, 100, 255)
UI_COLOR_NO_HAND = (100, 100, 100)
UI_COLOR_UNRECOGNIZED = (0, 120, 255)
UI_COLOR_ACTION_FLASH = (50, 255, 50)
UI_COLOR_COOLDOWN = (0, 165, 255)
UI_COLOR_QUIT_HINT = (120, 120, 120)
UI_COLOR_ERROR = (0, 0, 255)
UI_COLOR_PROGRESS_BG = (50, 50, 50)
UI_COLOR_PROGRESS_FILL = (0, 220, 100)
UI_COLOR_STREAK_BG = (40, 40, 40)
UI_COLOR_STREAK_FILL = (0, 180, 255)
UI_COLOR_LANDMARK_DOT = (0, 80, 255)
UI_COLOR_LANDMARK_LINE = (0, 200, 100)
UI_COLOR_HAND_BBOX = (255, 200, 0)
UI_COLOR_ACTIVE_GLOW = (0, 255, 0)
UI_COLOR_STATUS_ACTIVE = (0, 255, 100)
UI_COLOR_STATUS_IDLE = (80, 80, 80)
UI_COLOR_SAMPLES = (0, 200, 200)
UI_COLOR_FRAME_BORDER_IDLE = (80, 80, 80)
UI_COLOR_FRAME_BORDER_ACTIVE = (0, 220, 100)
UI_COLOR_FRAME_BORDER_ACTION = (0, 255, 50)

# Hand skeleton connections
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]

if IS_MACOS:
    MODIFIER_KEY = "command"
else:
    MODIFIER_KEY = "ctrl"

ProgressCallback = Optional[Callable[[str, str], None]]


# ============================================================
# UI Drawing Helpers (matching data_collector professional style)
# ============================================================

def _draw_rounded_rect(
    img: np.ndarray,
    pt1: tuple,
    pt2: tuple,
    color: tuple,
    radius: int = 10,
    thickness: int = -1,
) -> None:
    """Draw a rectangle with rounded corners."""
    x1, y1 = pt1
    x2, y2 = pt2
    max_radius = min((x2 - x1) // 2, (y2 - y1) // 2)
    radius = min(radius, max(max_radius, 0))

    if thickness == -1:
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, -1)
        cv2.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, -1)
        cv2.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, -1)
        cv2.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, -1)
        cv2.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, -1)
    else:
        cv2.line(img, (x1 + radius, y1), (x2 - radius, y1), color, thickness)
        cv2.line(img, (x1 + radius, y2), (x2 - radius, y2), color, thickness)
        cv2.line(img, (x1, y1 + radius), (x1, y2 - radius), color, thickness)
        cv2.line(img, (x2, y1 + radius), (x2, y2 - radius), color, thickness)
        cv2.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness)
        cv2.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness)
        cv2.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness)
        cv2.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness)


def _draw_hand_skeleton(
    frame: np.ndarray,
    landmarks,
    dot_color: tuple = UI_COLOR_LANDMARK_DOT,
    line_color: tuple = UI_COLOR_LANDMARK_LINE,
    dot_radius: int = 5,
    line_thickness: int = 2,
) -> None:
    """Draw hand skeleton with connections and landmark dots."""
    if landmarks is None:
        return

    h, w = frame.shape[:2]
    points = []
    for lm in landmarks:
        x_px = int(lm.x * w)
        y_px = int(lm.y * h)
        points.append((x_px, y_px))

    for start_idx, end_idx in HAND_CONNECTIONS:
        if start_idx < len(points) and end_idx < len(points):
            cv2.line(frame, points[start_idx], points[end_idx],
                     line_color, line_thickness, cv2.LINE_AA)

    for i, (px, py) in enumerate(points):
        r = dot_radius + 2 if i in (4, 8, 12, 16, 20) else dot_radius
        cv2.circle(frame, (px, py), r, dot_color, -1, cv2.LINE_AA)
        cv2.circle(frame, (px, py), r, (255, 255, 255), 1, cv2.LINE_AA)


def _draw_hand_bounding_box(
    frame: np.ndarray,
    landmarks,
    color: tuple = UI_COLOR_HAND_BBOX,
    padding: int = 20,
) -> None:
    """Draw corner-bracket bounding box around detected hand."""
    if landmarks is None:
        return

    h, w = frame.shape[:2]
    xs = [int(lm.x * w) for lm in landmarks]
    ys = [int(lm.y * h) for lm in landmarks]

    x_min = max(0, min(xs) - padding)
    y_min = max(0, min(ys) - padding)
    x_max = min(w, max(xs) + padding)
    y_max = min(h, max(ys) + padding)

    corner_len = 15
    t = 2
    cv2.line(frame, (x_min, y_min), (x_min + corner_len, y_min), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_min, y_min), (x_min, y_min + corner_len), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_max, y_min), (x_max - corner_len, y_min), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_max, y_min), (x_max, y_min + corner_len), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_min, y_max), (x_min + corner_len, y_max), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_min, y_max), (x_min, y_max - corner_len), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_max, y_max), (x_max - corner_len, y_max), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_max, y_max), (x_max, y_max - corner_len), color, t, cv2.LINE_AA)


def _draw_active_indicator(
    frame: np.ndarray,
    is_active: bool,
) -> None:
    """Draw a pulsing green dot when gesture is actively detected above threshold."""
    if not is_active:
        # Idle grey dot
        cv2.circle(frame, (30, 30), 8, UI_COLOR_STATUS_IDLE, -1, cv2.LINE_AA)
        cv2.circle(frame, (30, 30), 8, (100, 100, 100), 1, cv2.LINE_AA)
        cv2.putText(
            frame, "IDLE",
            (50, 37),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55,
            UI_COLOR_STATUS_IDLE, 1, cv2.LINE_AA,
        )
        return

    # Pulsing green effect
    pulse = 0.5 + 0.5 * math.sin(time.time() * 5.0)
    base_radius = 8
    pulse_radius = int(base_radius + 3 * pulse)

    # Glow
    glow_intensity = int(100 + 80 * pulse)
    cv2.circle(frame, (30, 30), pulse_radius + 4, (0, glow_intensity, 0), -1, cv2.LINE_AA)

    # Main dot
    cv2.circle(frame, (30, 30), pulse_radius, UI_COLOR_ACTIVE_GLOW, -1, cv2.LINE_AA)
    cv2.circle(frame, (30, 30), pulse_radius, (255, 255, 255), 1, cv2.LINE_AA)

    cv2.putText(
        frame, "ACTIVE",
        (50, 37),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
        UI_COLOR_STATUS_ACTIVE, 1, cv2.LINE_AA,
    )


def _draw_action_flash(
    frame: np.ndarray,
    action_name: str,
    action_age: float,
    max_age: float = 1.5,
) -> None:
    """Draw a brief flash overlay when an action is triggered."""
    if not action_name or action_age >= max_age:
        return

    h, w = frame.shape[:2]

    # Fade out effect
    alpha = max(0.0, 1.0 - (action_age / max_age))
    border_alpha = alpha * 0.6

    # Green border flash
    overlay = frame.copy()
    thickness = max(2, int(6 * alpha))
    cv2.rectangle(overlay, (0, 0), (w - 1, h - 1), UI_COLOR_FRAME_BORDER_ACTION, thickness)
    cv2.addWeighted(overlay, border_alpha, frame, 1.0 - border_alpha, 0, frame)

    # Action badge at top center
    badge_text = f"ACTION: {action_name.upper()}"
    text_size = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
    badge_w = text_size[0] + 30
    badge_h = text_size[1] + 20
    badge_x = (w - badge_w) // 2
    badge_y = 55

    overlay2 = frame.copy()
    _draw_rounded_rect(overlay2, (badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h),
                       (0, 80, 0), radius=8, thickness=-1)
    cv2.addWeighted(overlay2, alpha * 0.8, frame, 1.0 - alpha * 0.8, 0, frame)

    _draw_rounded_rect(frame, (badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h),
                       UI_COLOR_ACTION_FLASH, radius=8, thickness=2)

    cv2.putText(
        frame, badge_text,
        (badge_x + 15, badge_y + badge_h - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7,
        UI_COLOR_ACTION_FLASH, 2, cv2.LINE_AA,
    )


def _draw_confidence_bar(
    frame: np.ndarray,
    confidence: float,
    x: int,
    y: int,
    width: int,
    height: int = 10,
    threshold: float = TRIGGER_CONFIDENCE,
) -> None:
    """Draw a confidence bar with threshold marker."""
    # Background
    _draw_rounded_rect(frame, (x, y), (x + width, y + height), UI_COLOR_PROGRESS_BG,
                       radius=5, thickness=-1)

    # Fill
    fill_w = int(width * min(1.0, max(0.0, confidence)))
    if fill_w > 0:
        if confidence >= threshold:
            fill_color = UI_COLOR_CONFIDENCE_HIGH
        elif confidence >= threshold * 0.7:
            fill_color = UI_COLOR_CONFIDENCE_MED
        else:
            fill_color = UI_COLOR_CONFIDENCE_LOW
        _draw_rounded_rect(frame, (x, y), (x + fill_w, y + height), fill_color,
                           radius=5, thickness=-1)

    # Threshold marker
    thresh_x = x + int(width * threshold)
    cv2.line(frame, (thresh_x, y - 2), (thresh_x, y + height + 2),
             (255, 255, 255), 1, cv2.LINE_AA)

    # Border
    _draw_rounded_rect(frame, (x, y), (x + width, y + height), (100, 100, 100),
                       radius=5, thickness=1)


def _draw_streak_bar(
    frame: np.ndarray,
    streak: int,
    required: int,
    x: int,
    y: int,
    width: int,
    height: int = 6,
) -> None:
    """Draw a small streak progress bar."""
    progress = min(1.0, streak / max(1, required))

    _draw_rounded_rect(frame, (x, y), (x + width, y + height), UI_COLOR_STREAK_BG,
                       radius=3, thickness=-1)

    fill_w = int(width * progress)
    if fill_w > 0:
        color = UI_COLOR_CONFIDENCE_HIGH if progress >= 1.0 else UI_COLOR_STREAK_FILL
        _draw_rounded_rect(frame, (x, y), (x + fill_w, y + height), color,
                           radius=3, thickness=-1)

    _draw_rounded_rect(frame, (x, y), (x + width, y + height), (80, 80, 80),
                       radius=3, thickness=1)


def _draw_hand_detection_status(
    frame: np.ndarray,
    hand_detected: bool,
) -> None:
    """Show hand detection indicator in top-right area."""
    h, w = frame.shape[:2]
    indicator_y = 65

    if hand_detected:
        cv2.circle(frame, (w - 20, indicator_y), 6, (0, 255, 0), -1, cv2.LINE_AA)
        cv2.putText(
            frame, "Hand OK",
            (w - 90, indicator_y + 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4,
            (0, 255, 0), 1, cv2.LINE_AA,
        )
    else:
        cv2.circle(frame, (w - 20, indicator_y), 6, (0, 0, 200), -1, cv2.LINE_AA)
        cv2.putText(
            frame, "No Hand",
            (w - 90, indicator_y + 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4,
            (0, 0, 200), 1, cv2.LINE_AA,
        )


def _draw_cooldown_arc(
    frame: np.ndarray,
    cooldown_remaining: float,
    cooldown_total: float,
    center: tuple,
    radius: int = 18,
) -> None:
    """Draw a circular cooldown indicator."""
    if cooldown_remaining <= 0.05 or cooldown_total <= 0:
        return

    progress = cooldown_remaining / cooldown_total
    angle = int(360 * progress)

    # Background circle
    cv2.circle(frame, center, radius, (40, 40, 40), -1, cv2.LINE_AA)
    cv2.circle(frame, center, radius, (80, 80, 80), 1, cv2.LINE_AA)

    # Arc
    cv2.ellipse(frame, center, (radius, radius), -90, 0, angle,
                UI_COLOR_COOLDOWN, 3, cv2.LINE_AA)

    # Time text
    time_text = f"{cooldown_remaining:.1f}"
    t_size = cv2.getTextSize(time_text, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)[0]
    cv2.putText(
        frame, time_text,
        (center[0] - t_size[0] // 2, center[1] + t_size[1] // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 0.35,
        UI_COLOR_COOLDOWN, 1, cv2.LINE_AA,
    )


def _build_top_bar(
    frame: np.ndarray,
    gesture_name: str,
    status: str,
    is_active: bool,
) -> None:
    """Draw semi-transparent top info bar."""
    h, w = frame.shape[:2]
    bar_height = 50

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, bar_height), UI_COLOR_BG_PANEL, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    cv2.line(frame, (0, bar_height), (w, bar_height), UI_COLOR_PANEL_BORDER, 1)

    # Active / idle indicator
    _draw_active_indicator(frame, is_active)

    # Title centered
    title_text = f"FULL CONTROL ({PLATFORM_NAME})"
    title_size = cv2.getTextSize(title_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    title_x = (w - title_size[0]) // 2
    cv2.putText(
        frame, title_text,
        (title_x, 22),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
        UI_COLOR_TITLE, 2, cv2.LINE_AA,
    )

    # Subtitle
    sub_text = "Real-Time Gesture Recognition"
    sub_size = cv2.getTextSize(sub_text, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)[0]
    cv2.putText(
        frame, sub_text,
        ((w - sub_size[0]) // 2, 42),
        cv2.FONT_HERSHEY_SIMPLEX, 0.38,
        UI_COLOR_SUBTITLE, 1, cv2.LINE_AA,
    )

    # Quit hint top right
    cv2.putText(
        frame, "[Q] Quit",
        (w - 90, 22),
        cv2.FONT_HERSHEY_SIMPLEX, 0.4,
        UI_COLOR_QUIT_HINT, 1, cv2.LINE_AA,
    )


def _build_bottom_panel(
    frame: np.ndarray,
    gesture_name: str,
    confidence: float,
    status: str,
    streak: int,
    required_streak: int,
    action_triggered: str,
    cooldown_remaining: float,
    cooldown_total: float,
) -> np.ndarray:
    """Build a professional bottom info panel and stack below the frame."""
    h, w = frame.shape[:2]
    panel_height = 130

    panel = np.full((panel_height, w, 3), UI_COLOR_BG_PANEL, dtype=np.uint8)

    # Top border accent
    cv2.line(panel, (0, 0), (w, 0), UI_COLOR_TITLE, 2)

    y_cursor = 28

    if status == "detected":
        # Gesture name
        cv2.putText(
            panel, "Gesture:",
            (15, y_cursor),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5,
            UI_COLOR_SUBTITLE, 1, cv2.LINE_AA,
        )
        cv2.putText(
            panel, f"  {gesture_name}",
            (100, y_cursor),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6,
            UI_COLOR_GESTURE_NAME, 2, cv2.LINE_AA,
        )

        # Confidence percentage on the right
        conf_text = f"{confidence * 100:.1f}%"
        conf_color = UI_COLOR_CONFIDENCE_HIGH if confidence >= TRIGGER_CONFIDENCE else UI_COLOR_CONFIDENCE_MED
        conf_size = cv2.getTextSize(conf_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        cv2.putText(
            panel, conf_text,
            (w - conf_size[0] - 15, y_cursor),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
            conf_color, 2, cv2.LINE_AA,
        )

        # Confidence bar
        bar_y = y_cursor + 10
        _draw_confidence_bar(panel, confidence, 15, bar_y, w - 30, height=12)

        # Streak bar
        streak_y = bar_y + 22
        cv2.putText(
            panel, "Streak:",
            (15, streak_y + 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38,
            UI_COLOR_SUBTITLE, 1, cv2.LINE_AA,
        )
        _draw_streak_bar(panel, streak, required_streak, 80, streak_y + 3, 150, height=8)
        cv2.putText(
            panel, f"{min(streak, required_streak)}/{required_streak}",
            (238, streak_y + 11),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35,
            UI_COLOR_STREAK_FILL, 1, cv2.LINE_AA,
        )

        # Cooldown arc (right side of streak area)
        if cooldown_remaining > 0.05:
            _draw_cooldown_arc(
                panel, cooldown_remaining, cooldown_total,
                center=(w - 40, streak_y + 6), radius=16,
            )

        # Action display
        action_y = streak_y + 28
        if action_triggered:
            cv2.putText(
                panel, f"Last Action:  {action_triggered}",
                (15, action_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                UI_COLOR_ACTION_FLASH, 1, cv2.LINE_AA,
            )
        elif cooldown_remaining > 0.1:
            cv2.putText(
                panel, f"Cooldown:  {cooldown_remaining:.1f}s remaining",
                (15, action_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                UI_COLOR_COOLDOWN, 1, cv2.LINE_AA,
            )

    elif status == "unrecognized":
        cv2.putText(
            panel, "Gesture:",
            (15, y_cursor),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5,
            UI_COLOR_SUBTITLE, 1, cv2.LINE_AA,
        )
        cv2.putText(
            panel, f"  Unrecognized",
            (100, y_cursor),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6,
            UI_COLOR_UNRECOGNIZED, 1, cv2.LINE_AA,
        )

        # Show best guess
        if gesture_name:
            cv2.putText(
                panel, f"Best guess: {gesture_name} ({confidence * 100:.1f}%)",
                (15, y_cursor + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                UI_COLOR_CONFIDENCE_LOW, 1, cv2.LINE_AA,
            )

        # Low confidence bar
        bar_y = y_cursor + 38
        _draw_confidence_bar(panel, confidence, 15, bar_y, w - 30, height=10)

        cv2.putText(
            panel, f"Confidence below {TRIGGER_CONFIDENCE * 100:.0f}% threshold",
            (15, bar_y + 26),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4,
            UI_COLOR_SUBTITLE, 1, cv2.LINE_AA,
        )

    elif status == "no_hand":
        # Centered message
        msg = "No hand detected"
        msg_size = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1)[0]
        cv2.putText(
            panel, msg,
            ((w - msg_size[0]) // 2, 45),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
            UI_COLOR_NO_HAND, 1, cv2.LINE_AA,
        )

        hint = "Show your hand to the camera to begin"
        hint_size = cv2.getTextSize(hint, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
        cv2.putText(
            panel, hint,
            ((w - hint_size[0]) // 2, 75),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45,
            UI_COLOR_SUBTITLE, 1, cv2.LINE_AA,
        )

    elif status == "error":
        cv2.putText(
            panel, "ERROR",
            (15, y_cursor),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6,
            UI_COLOR_ERROR, 2, cv2.LINE_AA,
        )
        error_msg = gesture_name[:60] if gesture_name else "Unknown error"
        cv2.putText(
            panel, error_msg,
            (15, y_cursor + 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45,
            (180, 180, 180), 1, cv2.LINE_AA,
        )

    # Bottom separator and platform info
    cv2.line(panel, (0, panel_height - 20), (w, panel_height - 20), UI_COLOR_PANEL_BORDER, 1)
    platform_info = f"{PLATFORM_NAME} | Threshold: {TRIGGER_CONFIDENCE * 100:.0f}% | Streak: {REQUIRED_STREAK}"
    pi_size = cv2.getTextSize(platform_info, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)[0]
    cv2.putText(
        panel, platform_info,
        ((w - pi_size[0]) // 2, panel_height - 5),
        cv2.FONT_HERSHEY_SIMPLEX, 0.35,
        UI_COLOR_QUIT_HINT, 1, cv2.LINE_AA,
    )

    composite = np.vstack([frame, panel])
    return composite


def _draw_frame_border(
    frame: np.ndarray,
    status: str,
    has_action: bool,
) -> None:
    """Draw context-aware frame border."""
    h, w = frame.shape[:2]
    if has_action:
        color = UI_COLOR_FRAME_BORDER_ACTION
        thickness = 3
    elif status == "detected":
        color = UI_COLOR_FRAME_BORDER_ACTIVE
        thickness = 2
    else:
        color = UI_COLOR_FRAME_BORDER_IDLE
        thickness = 1
    cv2.rectangle(frame, (0, 0), (w - 1, h - 1), color, thickness)


# ============================================================
# Platform-specific volume/media helpers
# ============================================================

def _adjust_volume_up() -> None:
    if IS_MACOS:
        try:
            subprocess.run(
                ["osascript", "-e",
                 "set volume output volume ((output volume of (get volume settings)) + 6)"],
                capture_output=True, timeout=3,
            )
        except Exception:
            try:
                pyautogui.press("volumeup", presses=VOLUME_STEP_COUNT, interval=0.02)
            except Exception:
                pass
    elif IS_WINDOWS:
        try:
            pyautogui.press("volumeup", presses=VOLUME_STEP_COUNT, interval=0.02)
        except Exception:
            for _ in range(VOLUME_STEP_COUNT):
                pyautogui.hotkey("ctrl", "up")
    else:
        try:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"],
                           capture_output=True, timeout=3)
        except Exception:
            try:
                subprocess.run(["amixer", "set", "Master", "5%+"],
                               capture_output=True, timeout=3)
            except Exception:
                pyautogui.press("volumeup", presses=VOLUME_STEP_COUNT, interval=0.02)


def _adjust_volume_down() -> None:
    if IS_MACOS:
        try:
            subprocess.run(
                ["osascript", "-e",
                 "set volume output volume ((output volume of (get volume settings)) - 6)"],
                capture_output=True, timeout=3,
            )
        except Exception:
            try:
                pyautogui.press("volumedown", presses=VOLUME_STEP_COUNT, interval=0.02)
            except Exception:
                pass
    elif IS_WINDOWS:
        try:
            pyautogui.press("volumedown", presses=VOLUME_STEP_COUNT, interval=0.02)
        except Exception:
            for _ in range(VOLUME_STEP_COUNT):
                pyautogui.hotkey("ctrl", "down")
    else:
        try:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"],
                           capture_output=True, timeout=3)
        except Exception:
            try:
                subprocess.run(["amixer", "set", "Master", "5%-"],
                               capture_output=True, timeout=3)
            except Exception:
                pyautogui.press("volumedown", presses=VOLUME_STEP_COUNT, interval=0.02)


def _play_pause_media() -> None:
    if IS_MACOS:
        try:
            subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to key code 49'],
                capture_output=True, timeout=3,
            )
        except Exception:
            try:
                pyautogui.press("space")
            except Exception:
                pass
    elif IS_WINDOWS:
        try:
            pyautogui.press("playpause")
        except Exception:
            pyautogui.press("space")
    else:
        try:
            subprocess.run(["playerctl", "play-pause"],
                           capture_output=True, timeout=3)
        except Exception:
            try:
                pyautogui.press("space")
            except Exception:
                pass


# ============================================================
# Gesture config
# ============================================================

def _load_gesture_config() -> dict:
    if not os.path.exists(GESTURE_CONFIG_PATH):
        return {}
    try:
        with open(GESTURE_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_gesture_config(config: dict) -> None:
    os.makedirs(os.path.dirname(GESTURE_CONFIG_PATH), exist_ok=True)
    with open(GESTURE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _get_cooldown_for_gesture(gesture_name: str) -> float:
    name = gesture_name.strip().lower()
    config = _load_gesture_config()
    if name in config:
        return float(config[name])
    if name in BASE_GESTURE_COOLDOWNS:
        return BASE_GESTURE_COOLDOWNS[name]
    return COOLDOWN_ONESHOT


def _ask_cooldown_preference(gesture_name: str) -> float:
    print(f"\n[Main] Choose cooldown type for gesture '{gesture_name}':")
    print()
    print("  1) Repeatable  (0.01s) — Fires rapidly while holding gesture")
    print("     Best for: scrolling, volume, continuous actions")
    print()
    print("  2) Moderate    (2.0s)  — Fires once every 2 seconds")
    print("     Best for: play/pause, toggle actions")
    print()
    print("  3) One-shot    (5.0s)  — Fires once, then long wait")
    print("     Best for: opening apps, launching scripts")
    print()
    print("  4) Custom      — Enter your own cooldown time")
    print()

    while True:
        choice = input("  Select cooldown type [1-4]: ").strip()
        if choice == "1":
            print(f"  -> Repeatable cooldown (0.01s) selected for '{gesture_name}'")
            return COOLDOWN_REPEATABLE
        elif choice == "2":
            print(f"  -> Moderate cooldown (2.0s) selected for '{gesture_name}'")
            return COOLDOWN_MODERATE
        elif choice == "3":
            print(f"  -> One-shot cooldown (5.0s) selected for '{gesture_name}'")
            return COOLDOWN_ONESHOT
        elif choice == "4":
            while True:
                try:
                    custom = input("  Enter cooldown in seconds (e.g. 3.5): ").strip()
                    custom_val = float(custom)
                    if custom_val < 0:
                        print("  Cooldown cannot be negative. Try again.")
                        continue
                    print(f"  -> Custom cooldown ({custom_val}s) selected for '{gesture_name}'")
                    return custom_val
                except ValueError:
                    print("  Invalid number. Try again.")
        else:
            print("  Invalid choice. Please select 1-4.")


# ============================================================
# Core functions
# ============================================================

def _load_label_list(label_map_path: str) -> List[str]:
    if not os.path.exists(label_map_path):
        raise FileNotFoundError(
            f"Label map file '{label_map_path}' not found. "
            "You need to train a model first."
        )
    with open(label_map_path, "r", encoding="utf-8") as f:
        label_list = json.load(f)
    return label_list


def _execute_script_for_gesture(gesture_name: str) -> None:
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    script_path = os.path.join(SCRIPTS_DIR, f"{gesture_name}.py")
    if not os.path.exists(script_path):
        print(f"[Main] No script found for gesture '{gesture_name}' at {script_path}.")
        return
    print(f"[Main] Executing script for gesture '{gesture_name}': {script_path}")
    try:
        subprocess.Popen([sys.executable, script_path])
    except Exception as e:
        print(f"[Main] Failed to execute script: {e}")


def perform_gesture_action(gesture_name: str) -> bool:
    name = gesture_name.strip().lower()
    try:
        if name == "scroll_up":
            pyautogui.scroll(SCROLL_AMOUNT)
            return True
        elif name == "scroll_down":
            pyautogui.scroll(-SCROLL_AMOUNT)
            return True
        elif name == "swipe_right":
            if IS_MACOS:
                pyautogui.hotkey("command", "shift", "]")
            else:
                pyautogui.hotkey("ctrl", "pgdn")
            return True
        elif name == "swipe_left":
            if IS_MACOS:
                pyautogui.hotkey("command", "shift", "[")
            else:
                pyautogui.hotkey("ctrl", "pgup")
            return True
        elif name == "zoom_in":
            pyautogui.hotkey(MODIFIER_KEY, "=")
            return True
        elif name == "zoom_out":
            pyautogui.hotkey(MODIFIER_KEY, "-")
            return True
        elif name == "volume_up":
            _adjust_volume_up()
            return True
        elif name == "volume_down":
            _adjust_volume_down()
            return True
        elif name in ("play/pause", "play_pause", "play-pause"):
            _play_pause_media()
            return True
        else:
            return False
    except Exception as e:
        print(f"[Main] Error performing action for '{gesture_name}': {e}")
        return False


def handle_gesture_trigger(gesture_name: str) -> None:
    if perform_gesture_action(gesture_name):
        return
    _execute_script_for_gesture(gesture_name)


def _gesture_csv_row_count(gesture_name: str) -> int:
    gesture_csv = os.path.join(DATASET_DIR, f"{gesture_name}.csv")
    if not os.path.exists(gesture_csv):
        return 0
    try:
        with open(gesture_csv, "r", encoding="utf-8") as f:
            non_empty_lines = [line.strip() for line in f if line.strip()]
            if not non_empty_lines:
                return 0

            first_line = non_empty_lines[0].lower()
            if first_line.startswith("f0,"):
                return max(0, len(non_empty_lines) - 1)
            return len(non_empty_lines)
    except Exception:
        return 0


def _gesture_csv_has_data(gesture_name: str) -> bool:
    return _gesture_csv_row_count(gesture_name) > 0


def _safe_progress_update(
    progress_callback: ProgressCallback,
    stage: str,
    message: str,
) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(stage, message)
    except Exception:
        # Progress updates should not break the gesture pipeline.
        pass


def _get_platform_prompt_context() -> str:
    if IS_MACOS:
        return (
            "The target machine is running macOS (Apple Mac).\n"
            "Use macOS-specific approaches:\n"
            "  - Use 'subprocess' with 'open' command to launch applications.\n"
            "  - Use 'osascript' for AppleScript commands when needed.\n"
            "  - For keyboard shortcuts use pyautogui with 'command' key instead of 'ctrl'.\n"
            "  - For volume control use osascript.\n"
            "  - For opening URLs use: subprocess.run(['open', 'https://...']).\n"
            "  - Use '/Applications/' paths for app references.\n"
            "  - Do NOT use Windows-specific APIs.\n"
        )
    elif IS_WINDOWS:
        return (
            "The target machine is running Windows.\n"
            "Use Windows-specific approaches:\n"
            "  - Use 'os.startfile()' or 'subprocess.Popen' with Windows paths.\n"
            "  - For keyboard shortcuts use pyautogui with 'ctrl' key.\n"
            "  - For volume control use pyautogui.press('volumeup').\n"
            "  - Use Windows file paths.\n"
            "  - Do NOT use macOS commands.\n"
        )
    else:
        return (
            "The target machine is running Linux.\n"
            "Use Linux-specific approaches:\n"
            "  - Use 'subprocess.Popen' with Linux commands.\n"
            "  - Use 'xdg-open' to open URLs and files.\n"
            "  - For volume control use 'pactl' or 'amixer'.\n"
            "  - For media control use 'playerctl'.\n"
            "  - Do NOT use Windows or macOS specific APIs.\n"
        )


def _generate_script_via_groq(gesture_name: str, action_description: str) -> tuple[bool, str]:
    print(f"[Main] Generating {PLATFORM_NAME}-specific automation script...")
    print("[Main] Contacting Groq API...")
    print("[Main] This usually takes 2-5 seconds...\n")
    try:
        agent = SLMCodeAgent()
        platform_context = _get_platform_prompt_context()
        enhanced_description = (
            f"{action_description}\n\n"
            f"IMPORTANT PLATFORM INSTRUCTIONS:\n"
            f"{platform_context}"
        )
        script_code = agent.generate_python_script(
            action_description=enhanced_description,
            gesture_name=gesture_name,
            target_platform=PLATFORM_NAME,
        )
        if not script_code or len(script_code.strip()) < 10:
            print("[Main] Groq returned empty or invalid response.")
            return False, "Groq returned an empty or invalid script."
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        script_path = os.path.join(SCRIPTS_DIR, f"{gesture_name}.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_code)
        print(f"[Main] {PLATFORM_NAME} automation script saved to {script_path}")
        print("[Main] Script preview (first 5 lines):")
        for line in script_code.strip().split("\n")[:5]:
            print(f"  {line}")
        print()
        return True, ""
    except ValueError as e:
        print(f"[Main] Configuration error: {e}")
        return False, str(e).strip()
    except Exception as e:
        print(f"[Main] Script generation failed: {e}")
        return False, str(e).strip() or "Unexpected script generation error."


def _run_add_new_gesture_pipeline(
    gesture_name: str,
    action_description: str,
    cooldown: float,
    progress_callback: ProgressCallback = None,
) -> Dict[str, Any]:
    gesture_name = gesture_name.strip()
    if not gesture_name:
        return {"status": "invalid_input", "message": "Gesture name cannot be empty."}

    action_description = action_description.strip()
    if not action_description:
        return {"status": "invalid_input", "message": "Action description cannot be empty."}

    _safe_progress_update(
        progress_callback,
        "script_generation",
        f"Generating automation script for '{gesture_name}'.",
    )
    slm_success, script_error = _generate_script_via_groq(gesture_name, action_description)
    if not slm_success:
        failure_message = script_error or "Script generation failed."
        _safe_progress_update(progress_callback, "failed", failure_message)
        return {
            "status": "script_failed",
            "message": failure_message,
            "gesture": gesture_name,
        }

    script_path = os.path.join(SCRIPTS_DIR, f"{gesture_name}.py")
    before_count = _gesture_csv_row_count(gesture_name)

    _safe_progress_update(
        progress_callback,
        "data_collection",
        f"Collecting gesture samples for '{gesture_name}'.",
    )
    try:
        collect_gesture_samples(
            gesture_name=gesture_name,
            output_csv=DATASET_DIR,
            hand_landmarker_model_path=HAND_LANDMARKER_MODEL_PATH,
        )
    except Exception as exc:
        _safe_progress_update(progress_callback, "failed", "Data collection failed.")
        return {
            "status": "data_collection_failed",
            "message": f"Data collection failed: {exc}",
            "gesture": gesture_name,
        }

    after_count = _gesture_csv_row_count(gesture_name)
    added_samples = max(0, after_count - before_count)

    if after_count <= 0:
        if os.path.exists(script_path):
            os.remove(script_path)
        _safe_progress_update(
            progress_callback,
            "failed",
            f"No data collected for '{gesture_name}'.",
        )
        return {
            "status": "no_data",
            "message": f"No data collected for '{gesture_name}'.",
            "gesture": gesture_name,
            "added_samples": 0,
        }

    if added_samples <= 0:
        _safe_progress_update(
            progress_callback,
            "failed",
            f"No new samples added for '{gesture_name}'.",
        )
        return {
            "status": "no_new_data",
            "message": f"No new samples were added for '{gesture_name}'.",
            "gesture": gesture_name,
            "added_samples": 0,
        }

    config = _load_gesture_config()
    config[gesture_name.lower()] = float(cooldown)
    _save_gesture_config(config)

    _safe_progress_update(
        progress_callback,
        "training",
        f"Retraining model with new samples for '{gesture_name}'.",
    )
    try:
        train_model(
            csv_path=DATASET_DIR,
            model_output_path=MODEL_PATH,
            label_map_path=LABEL_MAP_PATH,
            feature_stats_path=FEATURE_STATS_PATH,
        )
    except Exception as exc:
        _safe_progress_update(progress_callback, "failed", "Model retraining failed.")
        return {
            "status": "training_failed",
            "message": f"Model retraining failed: {exc}",
            "gesture": gesture_name,
            "cooldown": float(cooldown),
            "added_samples": added_samples,
        }

    _safe_progress_update(
        progress_callback,
        "completed",
        f"Gesture '{gesture_name}' is ready.",
    )
    return {
        "status": "success",
        "message": f"Gesture '{gesture_name}' is ready to use.",
        "gesture": gesture_name,
        "cooldown": float(cooldown),
        "added_samples": added_samples,
    }


def add_new_gesture(gesture_name: str, action_description: str) -> None:
    print(f"\n[Main] Adding new gesture '{gesture_name}'...")
    print(f"[Main] Action: {action_description}")
    print(f"[Main] Target platform: {PLATFORM_NAME}\n")

    cooldown = _ask_cooldown_preference(gesture_name)
    result = _run_add_new_gesture_pipeline(
        gesture_name=gesture_name,
        action_description=action_description,
        cooldown=cooldown,
    )

    if result["status"] == "success":
        print(f"[Main] Cooldown for '{gesture_name}' set to {cooldown}s")
        print(f"[Main] Added samples: {result['added_samples']}")
        print("[Main] Retraining complete.")
        print(f"[Main] New gesture '{gesture_name}' is ready to use!")
        return

    print(f"[Main] {result.get('message', 'Gesture setup failed.')}")
    print("[Main] Returning to main menu.")


# ============================================================
# Delete gesture
# ============================================================

def _get_all_registered_gestures() -> List[str]:
    gestures = []
    if not os.path.exists(DATASET_DIR):
        return gestures
    for filename in os.listdir(DATASET_DIR):
        if filename.endswith(".csv"):
            gesture_name = filename[:-4]
            if gesture_name:
                gestures.append(gesture_name)
    return sorted(gestures)


def _is_predefined_gesture(gesture_name: str) -> bool:
    return gesture_name.strip().lower() in PREDEFINED_GESTURES


def _count_remaining_gestures_after_deletion(gesture_to_delete: str) -> int:
    all_gestures = _get_all_registered_gestures()
    remaining = [g for g in all_gestures if g.lower() != gesture_to_delete.lower()]
    return len(remaining)


def delete_gesture() -> None:
    all_gestures = _get_all_registered_gestures()
    if not all_gestures:
        print("\n[Main] No gestures found to delete.")
        return

    print("\n=== Delete Gesture ===")
    print("Available gestures:\n")
    for i, g in enumerate(all_gestures, 1):
        marker = " (predefined)" if _is_predefined_gesture(g) else ""
        has_script = os.path.exists(os.path.join(SCRIPTS_DIR, f"{g}.py"))
        script_marker = " [has script]" if has_script else ""
        print(f"  {i}) {g}{marker}{script_marker}")
    print(f"\n  0) Cancel and return to main menu")

    while True:
        selection = input(f"\nSelect gesture to delete [0-{len(all_gestures)}]: ").strip()
        try:
            sel_idx = int(selection)
        except ValueError:
            print("  Invalid input. Please enter a number.")
            continue
        if sel_idx == 0:
            print("[Main] Deletion cancelled.")
            return
        if sel_idx < 1 or sel_idx > len(all_gestures):
            print(f"  Invalid selection. Please enter 0-{len(all_gestures)}.")
            continue
        break

    gesture_name = all_gestures[sel_idx - 1]
    gesture_lower = gesture_name.strip().lower()

    if _is_predefined_gesture(gesture_name):
        print(f"\n[Main] WARNING: '{gesture_name}' is a predefined/built-in gesture.")
        print("[Main] Deleting removes training data; built-in mapping stays but won't trigger.")
        confirm = input(f"  Delete predefined gesture '{gesture_name}'? (yes/no): ").strip().lower()
        if confirm not in ("yes", "y"):
            print("[Main] Cancelled.")
            return
    else:
        confirm = input(f"  Delete gesture '{gesture_name}'? (yes/no): ").strip().lower()
        if confirm not in ("yes", "y"):
            print("[Main] Cancelled.")
            return

    remaining_count = _count_remaining_gestures_after_deletion(gesture_name)
    if remaining_count < 2:
        print(f"\n[Main] WARNING: Only {remaining_count} gesture(s) would remain.")
        print("[Main] Model requires at least 2 gestures. Model files will be removed.")
        confirm2 = input("  Proceed? (yes/no): ").strip().lower()
        if confirm2 not in ("yes", "y"):
            print("[Main] Cancelled.")
            return

    print(f"\n[Main] Deleting gesture '{gesture_name}'...")

    csv_path = os.path.join(DATASET_DIR, f"{gesture_name}.csv")
    if os.path.exists(csv_path):
        os.remove(csv_path)
        print(f"[Main] Deleted data: {csv_path}")

    script_path = os.path.join(SCRIPTS_DIR, f"{gesture_name}.py")
    if os.path.exists(script_path):
        os.remove(script_path)
        print(f"[Main] Deleted script: {script_path}")

    config = _load_gesture_config()
    if gesture_lower in config:
        del config[gesture_lower]
        _save_gesture_config(config)
        print(f"[Main] Removed config for '{gesture_name}'")

    remaining_gestures = _get_all_registered_gestures()
    remaining_with_data = [g for g in remaining_gestures if _gesture_csv_has_data(g)]

    if len(remaining_with_data) >= 2:
        print(f"\n[Main] {len(remaining_with_data)} gestures remaining. Retraining...")
        try:
            train_model(
                csv_path=DATASET_DIR,
                model_output_path=MODEL_PATH,
                label_map_path=LABEL_MAP_PATH,
                feature_stats_path=FEATURE_STATS_PATH,
            )
            print("[Main] Model retrained successfully.")
        except Exception as e:
            print(f"[Main] Retraining error: {e}")
    else:
        print("[Main] Too few gestures for training. Removing model files...")
        for path in [MODEL_PATH, LABEL_MAP_PATH, FEATURE_STATS_PATH]:
            if os.path.exists(path):
                os.remove(path)
                print(f"[Main] Removed: {path}")

    print(f"\n[Main] Gesture '{gesture_name}' deleted successfully.")


# ============================================================
# Model validation
# ============================================================

def _validate_model_feature_dim(model: keras.Model) -> int:
    input_shape = model.input_shape
    if isinstance(input_shape, list):
        input_shape = input_shape[0]
    return input_shape[-1]


# ============================================================
# Main gesture control loop with professional UI
# ============================================================

def run_gesture_control() -> None:
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model file '{MODEL_PATH}' not found. Train the model first."
        )

    label_list = _load_label_list(LABEL_MAP_PATH)
    num_classes = len(label_list)
    print(f"[Main] Loaded {num_classes}-class model with labels: {label_list}")
    print(f"[Main] Running on {PLATFORM_NAME} — using platform-specific controls")

    model = keras.models.load_model(MODEL_PATH)
    extractor = HandLandmarkExtractor(HAND_LANDMARKER_MODEL_PATH)

    expected_dim = _validate_model_feature_dim(model)
    print(f"[Main] Model expects {expected_dim}-dim input features.")

    mean, std = load_feature_stats(FEATURE_STATS_PATH)
    if mean is not None and len(mean) != expected_dim:
        print("[Main] WARNING: Feature stats dimension mismatch. Skipping standardization.")
        mean, std = None, None

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open default camera (index 0).")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    current_gesture = None
    streak = 0
    last_action_name = ""
    last_action_time = 0.0
    ACTION_DISPLAY_SEC = 1.5
    gesture_last_trigger: dict = {}
    probs_buffer = deque(maxlen=SMOOTHING_WINDOW)

    window_name = "Full Control"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    print("[Main] Starting real-time gesture control. Press 'q' to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            features = extractor.extract(frame)

            ui_gesture = ""
            ui_confidence = 0.0
            ui_status = "no_hand"
            action_display = ""
            cooldown_remaining = 0.0
            cooldown_total = 0.0
            hand_detected = features is not None
            is_active = False

            if features is not None:
                try:
                    x_raw = features.reshape(1, -1).astype("float32")
                    x_eng = engineer_hand_features(x_raw)

                    if x_eng.shape[1] != expected_dim:
                        ui_status = "error"
                        ui_gesture = "Feature dimension mismatch"
                        current_gesture = None
                        streak = 0
                        probs_buffer.clear()
                    else:
                        if mean is not None and std is not None:
                            x_input = (x_eng - mean) / std
                        else:
                            x_input = x_eng

                        probs = model.predict(x_input, verbose=0)[0]
                        probs_buffer.append(probs)

                        smoothed_probs = np.mean(probs_buffer, axis=0)
                        max_idx = int(np.argmax(smoothed_probs))
                        confidence = float(smoothed_probs[max_idx])
                        predicted_gesture = label_list[max_idx]

                        if confidence < TRIGGER_CONFIDENCE:
                            ui_status = "unrecognized"
                            ui_gesture = predicted_gesture
                            ui_confidence = confidence
                            current_gesture = None
                            streak = 0
                        else:
                            ui_status = "detected"
                            ui_gesture = predicted_gesture
                            ui_confidence = confidence
                            is_active = True

                            if predicted_gesture == current_gesture:
                                streak += 1
                            else:
                                current_gesture = predicted_gesture
                                streak = 1

                            now = time.time()
                            cooldown = _get_cooldown_for_gesture(current_gesture)
                            cooldown_total = cooldown
                            last_trigger = gesture_last_trigger.get(current_gesture, 0.0)
                            time_since_last = now - last_trigger
                            cooldown_remaining = max(0.0, cooldown - time_since_last)

                            if (
                                current_gesture is not None
                                and streak >= REQUIRED_STREAK
                                and time_since_last >= cooldown
                            ):
                                handle_gesture_trigger(current_gesture)
                                gesture_last_trigger[current_gesture] = now
                                last_action_name = current_gesture
                                last_action_time = now
                                streak = 0

                except Exception as e:
                    ui_status = "error"
                    ui_gesture = str(e)[:50]
                    current_gesture = None
                    streak = 0
                    probs_buffer.clear()
            else:
                probs_buffer.clear()
                current_gesture = None
                streak = 0

            now = time.time()
            action_age = now - last_action_time if last_action_name else ACTION_DISPLAY_SEC + 1
            if last_action_name and action_age < ACTION_DISPLAY_SEC:
                action_display = last_action_name
            else:
                last_action_name = ""

            # ---- Draw professional UI ----

            # Hand skeleton and bounding box
            _draw_hand_skeleton(frame, extractor.last_landmarks)
            _draw_hand_bounding_box(frame, extractor.last_landmarks)

            # Top bar
            _build_top_bar(frame, ui_gesture, ui_status, is_active)

            # Hand detection indicator
            _draw_hand_detection_status(frame, hand_detected)

            # Action flash overlay
            if action_display:
                _draw_action_flash(frame, action_display, action_age, ACTION_DISPLAY_SEC)

            # Frame border
            _draw_frame_border(frame, ui_status, bool(action_display))

            # Bottom panel
            composite = _build_bottom_panel(
                frame=frame,
                gesture_name=ui_gesture,
                confidence=ui_confidence,
                status=ui_status,
                streak=streak,
                required_streak=REQUIRED_STREAK,
                action_triggered=action_display,
                cooldown_remaining=cooldown_remaining,
                cooldown_total=cooldown_total,
            )

            cv2.imshow(window_name, composite)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        extractor.close()
        print("[Main] Gesture control stopped.")


def main():
    os.makedirs(DATASET_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    os.makedirs(ML_CORE_DIR / "mediapipe", exist_ok=True)

    print(f"\n[Main] System initialized for {PLATFORM_NAME}")

    while True:
        print(f"\n=== AI Hand Gesture Automation System ({PLATFORM_NAME}) ===")
        print("1) Run gesture control")
        print("2) Add new gesture (record data + generate script + retrain)")
        print("3) Delete gesture")
        print("4) Exit")
        choice = input("Select an option [1-4]: ").strip()

        if choice == "1":
            try:
                run_gesture_control()
            except Exception as e:
                print(f"[Main] Error during gesture control: {e}")

        elif choice == "2":
            gesture_name = input("Enter new gesture name (no spaces): ").strip()
            if not gesture_name:
                print("Gesture name cannot be empty.")
                continue
            print(
                "Describe the action you want this gesture to automate.\n"
                "Example: 'Open Spotify and start playing my liked songs.'"
            )
            action_description = input("Action description: ").strip()
            if not action_description:
                print("Action description cannot be empty.")
                continue
            try:
                add_new_gesture(gesture_name, action_description)
            except Exception as e:
                print(f"[Main] Error while adding new gesture: {e}")

        elif choice == "3":
            try:
                delete_gesture()
            except Exception as e:
                print(f"[Main] Error while deleting gesture: {e}")

        elif choice == "4":
            print("Exiting.")
            break
        else:
            print("Invalid choice, please select 1-4.")

def add_new_gesture_api(
    gesture_name: str,
    action_description: str,
    progress_callback: ProgressCallback = None,
) -> Dict[str, Any]:
    cooldown = COOLDOWN_MODERATE
    return _run_add_new_gesture_pipeline(
        gesture_name=gesture_name,
        action_description=action_description,
        cooldown=cooldown,
        progress_callback=progress_callback,
    )


if __name__ == "__main__":
    main()
