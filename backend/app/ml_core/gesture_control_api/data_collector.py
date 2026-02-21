import os
import time
import csv
import math
from typing import Optional

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks_python
from mediapipe.tasks.python import vision as mp_vision


# ============================================================
# Model Path Resolution
# ============================================================

def _resolve_hand_landmarker_model_path(default_path: str = None) -> str:
    """Resolve the hand landmarker model path with multiple fallback options."""
    # Check environment variable first
    env_path = os.environ.get('HAND_LANDMARKER_MODEL_PATH')
    if env_path and os.path.exists(env_path):
        return env_path
    
    # Try multiple possible locations
    possible_paths = [
        "/Users/mayankkumar/Desktop/send to mayank/hand_landmarker.task",
        os.path.expanduser("~/Desktop/send to mayank/hand_landmarker.task"),
        "hand_landmarker.task",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hand_landmarker.task"),
    ]
    
    # Add default path if provided
    if default_path:
        possible_paths.insert(0, default_path)
    
    for path in possible_paths:
        if path and os.path.exists(path):
            return path
    
    # Return the default if nothing found
    return possible_paths[0]


# Default model path
DEFAULT_HAND_LANDMARKER_MODEL_PATH = _resolve_hand_landmarker_model_path()
UI_COLOR_BG_PANEL = (25, 25, 25)
UI_COLOR_PANEL_BORDER = (60, 60, 60)
UI_COLOR_TITLE = (255, 200, 50)
UI_COLOR_SUBTITLE = (200, 200, 200)
UI_COLOR_GESTURE_NAME = (0, 255, 120)
UI_COLOR_RECORDING = (0, 0, 255)
UI_COLOR_RECORDING_GLOW = (0, 0, 200)
UI_COLOR_READY = (0, 220, 255)
UI_COLOR_PROGRESS_BG = (50, 50, 50)
UI_COLOR_PROGRESS_FILL = (0, 220, 100)
UI_COLOR_PROGRESS_TEXT = (255, 255, 255)
UI_COLOR_HINT_START = (0, 255, 255)
UI_COLOR_HINT_ABORT = (100, 100, 255)
UI_COLOR_SEGMENT_INFO = (180, 180, 180)
UI_COLOR_SAMPLES = (0, 200, 200)
UI_COLOR_FRAME_BORDER_IDLE = (80, 80, 80)
UI_COLOR_FRAME_BORDER_REC = (0, 0, 255)
UI_COLOR_LANDMARK_DOT = (0, 80, 255)
UI_COLOR_LANDMARK_LINE = (0, 200, 100)
UI_COLOR_HAND_BBOX = (255, 200, 0)
UI_COLOR_ABORT_OVERLAY = (0, 0, 180)
UI_COLOR_COMPLETE_OVERLAY = (0, 180, 0)

# Landmark connections for drawing hand skeleton
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # Index
    (0, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (0, 13), (13, 14), (14, 15), (15, 16), # Ring
    (0, 17), (17, 18), (18, 19), (19, 20), # Pinky
    (5, 9), (9, 13), (13, 17),             # Palm
]


class HandLandmarkExtractor:
    """
    Wraps MediaPipe HandLandmarker (Tasks API) and returns a 63-dim feature vector
    [x0, y0, z0, x1, y1, z1, ..., x20, y20, z20] for the first detected hand.

    Additionally, stores the last detected hand landmarks in `self.last_landmarks`
    so they can be visualized (21 points) on the frame.
    """

    def __init__(
        self,
        model_path: str = "/Users/mayankkumar/Desktop/send to mayank/hand_landmarker.task",
        num_hands: int = 1,
        min_hand_detection_confidence: float = 0.5,
        min_hand_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Hand landmarker model not found at '{model_path}'. "
                "Download 'hand_landmarker.task' and place it there."
            )

        base_options = mp_tasks_python.BaseOptions(model_asset_path=model_path)
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            running_mode=mp_vision.RunningMode.IMAGE,
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(options)
        self._mp = mp

        self.last_landmarks = None

    def extract(self, frame_bgr: np.ndarray) -> Optional[np.ndarray]:
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=rgb_frame,
        )
        result = self._landmarker.detect(mp_image)

        if not result.hand_landmarks:
            self.last_landmarks = None
            return None

        hand_landmarks = result.hand_landmarks[0]
        self.last_landmarks = hand_landmarks

        coords = []
        for lm in hand_landmarks:
            coords.extend([lm.x, lm.y, lm.z])

        return np.array(coords, dtype=np.float32)

    def close(self):
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# ============================================================
# Professional Drawing Helpers
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

    # Clamp radius
    max_radius = min((x2 - x1) // 2, (y2 - y1) // 2)
    radius = min(radius, max_radius)

    if thickness == -1:
        # Filled rounded rect
        # Center rectangles
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, -1)
        # Corners
        cv2.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, -1)
        cv2.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, -1)
        cv2.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, -1)
        cv2.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, -1)
    else:
        # Outlined
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

    # Draw connections
    for start_idx, end_idx in HAND_CONNECTIONS:
        if start_idx < len(points) and end_idx < len(points):
            cv2.line(
                frame, points[start_idx], points[end_idx],
                line_color, line_thickness, cv2.LINE_AA,
            )

    # Draw dots on top of lines
    for i, (px, py) in enumerate(points):
        # Fingertips get slightly larger dots
        r = dot_radius + 2 if i in (4, 8, 12, 16, 20) else dot_radius
        cv2.circle(frame, (px, py), r, dot_color, -1, cv2.LINE_AA)
        cv2.circle(frame, (px, py), r, (255, 255, 255), 1, cv2.LINE_AA)


def _draw_hand_bounding_box(
    frame: np.ndarray,
    landmarks,
    color: tuple = UI_COLOR_HAND_BBOX,
    padding: int = 20,
) -> None:
    """Draw a bounding box around the detected hand."""
    if landmarks is None:
        return

    h, w = frame.shape[:2]
    xs = [int(lm.x * w) for lm in landmarks]
    ys = [int(lm.y * h) for lm in landmarks]

    x_min = max(0, min(xs) - padding)
    y_min = max(0, min(ys) - padding)
    x_max = min(w, max(xs) + padding)
    y_max = min(h, max(ys) + padding)

    # Draw corners instead of full rectangle for a modern look
    corner_len = 15
    t = 2
    # Top-left
    cv2.line(frame, (x_min, y_min), (x_min + corner_len, y_min), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_min, y_min), (x_min, y_min + corner_len), color, t, cv2.LINE_AA)
    # Top-right
    cv2.line(frame, (x_max, y_min), (x_max - corner_len, y_min), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_max, y_min), (x_max, y_min + corner_len), color, t, cv2.LINE_AA)
    # Bottom-left
    cv2.line(frame, (x_min, y_max), (x_min + corner_len, y_max), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_min, y_max), (x_min, y_max - corner_len), color, t, cv2.LINE_AA)
    # Bottom-right
    cv2.line(frame, (x_max, y_max), (x_max - corner_len, y_max), color, t, cv2.LINE_AA)
    cv2.line(frame, (x_max, y_max), (x_max, y_max - corner_len), color, t, cv2.LINE_AA)


def _draw_recording_indicator(
    frame: np.ndarray,
    is_recording: bool,
    elapsed: float = 0.0,
) -> None:
    """
    Draw a professional recording indicator at the top-left.
    Includes a pulsing red circle and 'REC' text when recording.
    """
    if not is_recording:
        return

    # Pulsing effect: circle radius oscillates
    pulse = 0.5 + 0.5 * math.sin(time.time() * 4.0)
    base_radius = 8
    pulse_radius = int(base_radius + 3 * pulse)

    # Glow circle (larger, semi-transparent feel via darker red)
    glow_alpha = int(100 + 80 * pulse)
    cv2.circle(frame, (30, 30), pulse_radius + 4, (0, 0, glow_alpha), -1, cv2.LINE_AA)

    # Main red circle
    cv2.circle(frame, (30, 30), pulse_radius, UI_COLOR_RECORDING, -1, cv2.LINE_AA)

    # White border on circle
    cv2.circle(frame, (30, 30), pulse_radius, (255, 255, 255), 1, cv2.LINE_AA)

    # REC text
    cv2.putText(
        frame, "REC",
        (50, 37),
        cv2.FONT_HERSHEY_SIMPLEX, 0.65,
        UI_COLOR_RECORDING, 2, cv2.LINE_AA,
    )

    # Elapsed time next to REC
    time_str = f"{elapsed:.1f}s"
    cv2.putText(
        frame, time_str,
        (100, 37),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
        (200, 200, 200), 1, cv2.LINE_AA,
    )


def _draw_progress_bar(
    frame: np.ndarray,
    progress: float,
    x: int,
    y: int,
    width: int,
    height: int = 8,
) -> None:
    """Draw a sleek progress bar with rounded ends."""
    # Background
    _draw_rounded_rect(frame, (x, y), (x + width, y + height), UI_COLOR_PROGRESS_BG, radius=4, thickness=-1)

    # Fill
    fill_width = int(width * min(1.0, max(0.0, progress)))
    if fill_width > 0:
        # Color gradient from green to yellow as it progresses
        r = int(0 + 220 * progress)
        g = int(220 - 100 * progress)
        fill_color = (0, g, r) if progress > 0.7 else UI_COLOR_PROGRESS_FILL
        _draw_rounded_rect(frame, (x, y), (x + fill_width, y + height), fill_color, radius=4, thickness=-1)

    # Border
    _draw_rounded_rect(frame, (x, y), (x + width, y + height), (100, 100, 100), radius=4, thickness=1)


def _build_top_bar(
    frame: np.ndarray,
    gesture_name: str,
    segment_idx: int,
    total_segments: int,
    is_recording: bool,
    elapsed: float,
    total_time: float,
    samples_count: int,
) -> None:
    """Draw a semi-transparent top info bar on the frame."""
    h, w = frame.shape[:2]
    bar_height = 50

    # Semi-transparent overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, bar_height), UI_COLOR_BG_PANEL, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    # Bottom border line
    cv2.line(frame, (0, bar_height), (w, bar_height), UI_COLOR_PANEL_BORDER, 1)

    # Recording indicator
    _draw_recording_indicator(frame, is_recording, elapsed)

    # Gesture name centered
    gesture_text = f"GESTURE: {gesture_name.upper()}"
    text_size = cv2.getTextSize(gesture_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    text_x = (w - text_size[0]) // 2
    cv2.putText(
        frame, gesture_text,
        (text_x, 22),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
        UI_COLOR_GESTURE_NAME, 2, cv2.LINE_AA,
    )

    # Segment info
    seg_text = f"Segment {segment_idx}/{total_segments}"
    cv2.putText(
        frame, seg_text,
        (text_x, 42),
        cv2.FONT_HERSHEY_SIMPLEX, 0.45,
        UI_COLOR_SEGMENT_INFO, 1, cv2.LINE_AA,
    )

    # Samples counter (top right)
    samples_text = f"Samples: {samples_count}"
    s_size = cv2.getTextSize(samples_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
    cv2.putText(
        frame, samples_text,
        (w - s_size[0] - 15, 22),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
        UI_COLOR_SAMPLES, 1, cv2.LINE_AA,
    )

    # FPS / status (top right, below samples)
    if is_recording:
        status_text = f"{elapsed:.1f}s / {total_time:.0f}s"
    else:
        status_text = "READY"
    st_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
    cv2.putText(
        frame, status_text,
        (w - st_size[0] - 15, 42),
        cv2.FONT_HERSHEY_SIMPLEX, 0.45,
        UI_COLOR_READY if not is_recording else (200, 200, 200), 1, cv2.LINE_AA,
    )


def _build_bottom_bar(
    frame: np.ndarray,
    is_recording: bool,
    progress: float,
    show_hints: bool = True,
) -> None:
    """Draw a bottom bar with progress and key hints."""
    h, w = frame.shape[:2]
    bar_height = 55

    # Semi-transparent overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - bar_height), (w, h), UI_COLOR_BG_PANEL, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    # Top border
    cv2.line(frame, (0, h - bar_height), (w, h - bar_height), UI_COLOR_PANEL_BORDER, 1)

    if is_recording:
        # Progress bar
        bar_margin = 20
        bar_y = h - bar_height + 12
        bar_w = w - 2 * bar_margin
        _draw_progress_bar(frame, progress, bar_margin, bar_y, bar_w, height=10)

        # Percentage text
        pct_text = f"{progress * 100:.0f}%"
        pct_size = cv2.getTextSize(pct_text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
        cv2.putText(
            frame, pct_text,
            ((w - pct_size[0]) // 2, bar_y + 10 + 18),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4,
            UI_COLOR_PROGRESS_TEXT, 1, cv2.LINE_AA,
        )

        # Abort hint
        if show_hints:
            hint = "Press [Q] to abort"
            hint_size = cv2.getTextSize(hint, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
            cv2.putText(
                frame, hint,
                ((w - hint_size[0]) // 2, h - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                UI_COLOR_HINT_ABORT, 1, cv2.LINE_AA,
            )
    else:
        if show_hints:
            # Start hint
            hint1 = "Press [S] to start recording"
            h1_size = cv2.getTextSize(hint1, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0]
            cv2.putText(
                frame, hint1,
                ((w - h1_size[0]) // 2, h - bar_height + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                UI_COLOR_HINT_START, 1, cv2.LINE_AA,
            )

            # Abort hint
            hint2 = "Press [Q] to abort and discard all data"
            h2_size = cv2.getTextSize(hint2, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
            cv2.putText(
                frame, hint2,
                ((w - h2_size[0]) // 2, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                UI_COLOR_HINT_ABORT, 1, cv2.LINE_AA,
            )


def _draw_frame_border(
    frame: np.ndarray,
    is_recording: bool,
) -> None:
    """Draw a colored border around the frame."""
    h, w = frame.shape[:2]
    color = UI_COLOR_FRAME_BORDER_REC if is_recording else UI_COLOR_FRAME_BORDER_IDLE
    thickness = 3 if is_recording else 2
    cv2.rectangle(frame, (0, 0), (w - 1, h - 1), color, thickness)


def _draw_countdown_overlay(
    frame: np.ndarray,
    text: str,
    sub_text: str = "",
    color: tuple = (255, 255, 255),
) -> None:
    """Draw a large centered text overlay (for segment transitions)."""
    h, w = frame.shape[:2]

    # Semi-transparent background
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)

    # Main text
    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)[0]
    text_x = (w - text_size[0]) // 2
    text_y = (h + text_size[1]) // 2 - 20
    cv2.putText(
        frame, text,
        (text_x, text_y),
        cv2.FONT_HERSHEY_SIMPLEX, 1.5,
        color, 3, cv2.LINE_AA,
    )

    # Sub text
    if sub_text:
        sub_size = cv2.getTextSize(sub_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1)[0]
        sub_x = (w - sub_size[0]) // 2
        cv2.putText(
            frame, sub_text,
            (sub_x, text_y + 45),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
            (200, 200, 200), 1, cv2.LINE_AA,
        )


def _draw_hand_detection_status(
    frame: np.ndarray,
    hand_detected: bool,
) -> None:
    """Show a small hand detection indicator."""
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


# ============================================================
# Main Collection Function
# ============================================================


def collect_gesture_samples(
    gesture_name: str,
    output_csv: str = "data/gestures.csv",
    hand_landmarker_model_path: str ="/Users/mayankkumar/Desktop/send to mayank/hand_landmarker.task",
    num_videos: int = 4,
    seconds_per_video: int = 20,
    camera_index: int = 0,
) -> None:
    """
    Opens the webcam and records num_videos x seconds_per_video segments
    for a given gesture with a professional camera UI.

    If the user presses 'q' at ANY point (preview or recording):
      - All collected samples from this session are DISCARDED.
      - If a NEW CSV was created during this session, it is DELETED.
      - If the CSV already existed before this session, it is LEFT UNCHANGED.
    """
    # Determine base directory from output_csv
    if os.path.isdir(output_csv):
        base_dir = output_csv
    else:
        base_dir = os.path.dirname(output_csv) or "data"

    os.makedirs(base_dir, exist_ok=True)

    # Actual CSV for this gesture
    gesture_csv = os.path.join(base_dir, f"{gesture_name}.csv")

    # Track whether the file existed BEFORE this session
    file_existed_before = os.path.exists(gesture_csv)

    extractor = HandLandmarkExtractor(hand_landmarker_model_path)
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {camera_index}")

    # Try to set camera resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print(
        f"[DataCollector] Starting collection for gesture '{gesture_name}' "
        f"({num_videos} x {seconds_per_video} seconds)."
    )
    print("Controls: 's' = start segment, 'q' = abort (discards ALL collected data).\n")
    print(f"[DataCollector] This gesture will be saved to: {gesture_csv}")

    collected_rows = []
    abort = False
    total_samples = 0

    feature_dim = 63
    header = [f"f{i}" for i in range(feature_dim)] + ["label"]

    # Window name
    window_name = "Gesture Data Collection"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    for vid_idx in range(num_videos):
        if abort:
            break

        segment_num = vid_idx + 1

        # ------------------- PREVIEW / READY PHASE -------------------
        print(
            f"[DataCollector] Segment {segment_num}/{num_videos}: Get ready. "
            "Press 's' to start recording, or 'q' to abort."
        )

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[DataCollector] Frame grab failed during preview; stopping.")
                abort = True
                break

            frame = cv2.flip(frame, 1)

            features = extractor.extract(frame)
            hand_detected = features is not None

            # Draw hand visualization
            _draw_hand_skeleton(frame, extractor.last_landmarks)
            _draw_hand_bounding_box(frame, extractor.last_landmarks)

            # Draw UI overlays
            _build_top_bar(
                frame,
                gesture_name=gesture_name,
                segment_idx=segment_num,
                total_segments=num_videos,
                is_recording=False,
                elapsed=0.0,
                total_time=float(seconds_per_video),
                samples_count=total_samples,
            )
            _draw_hand_detection_status(frame, hand_detected)
            _build_bottom_bar(frame, is_recording=False, progress=0.0)
            _draw_frame_border(frame, is_recording=False)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("s"):
                # Brief countdown before recording starts
                for countdown in range(3, 0, -1):
                    countdown_start = time.time()
                    while time.time() - countdown_start < 1.0:
                        ret, frame = cap.read()
                        if not ret:
                            break
                        frame = cv2.flip(frame, 1)
                        _ = extractor.extract(frame)
                        _draw_hand_skeleton(frame, extractor.last_landmarks)
                        _draw_hand_bounding_box(frame, extractor.last_landmarks)
                        _build_top_bar(
                            frame, gesture_name, segment_num, num_videos,
                            False, 0.0, float(seconds_per_video), total_samples,
                        )
                        _draw_countdown_overlay(
                            frame,
                            str(countdown),
                            f"Recording starts in {countdown}...",
                            UI_COLOR_READY,
                        )
                        _draw_frame_border(frame, False)
                        cv2.imshow(window_name, frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            abort = True
                            break
                    if abort:
                        break

                if abort:
                    break

                start_time = time.time()
                print(f"[DataCollector] Segment {segment_num}/{num_videos}: recording started.")
                break
            elif key == ord("q"):
                abort = True
                print("[DataCollector] Aborted by user during preview.")
                break

        if abort:
            break

        # ------------------- RECORDING PHASE -------------------
        segment_samples = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[DataCollector] Frame grab failed; stopping.")
                abort = True
                break

            frame = cv2.flip(frame, 1)

            elapsed = time.time() - start_time
            if elapsed >= seconds_per_video:
                print(
                    f"[DataCollector] Segment {segment_num}/{num_videos}: "
                    f"complete. ({segment_samples} samples)"
                )

                # Show completion flash
                for _ in range(8):
                    ret, frame = cap.read()
                    if ret:
                        frame = cv2.flip(frame, 1)
                        _ = extractor.extract(frame)
                        _draw_hand_skeleton(frame, extractor.last_landmarks)
                        _build_top_bar(
                            frame, gesture_name, segment_num, num_videos,
                            False, float(seconds_per_video), float(seconds_per_video),
                            total_samples,
                        )
                        _draw_countdown_overlay(
                            frame,
                            f"Segment {segment_num} Complete!",
                            f"{segment_samples} samples collected",
                            UI_COLOR_COMPLETE_OVERLAY,
                        )
                        _draw_frame_border(frame, False)
                        cv2.imshow(window_name, frame)
                        cv2.waitKey(60)
                break

            progress = elapsed / seconds_per_video

            features = extractor.extract(frame)
            hand_detected = features is not None

            # Draw hand visualization
            _draw_hand_skeleton(frame, extractor.last_landmarks)
            _draw_hand_bounding_box(frame, extractor.last_landmarks)

            if features is not None and features.shape[0] == feature_dim:
                row = list(features.astype(float)) + [gesture_name]
                collected_rows.append(row)
                segment_samples += 1
                total_samples += 1

            # Draw UI overlays
            _build_top_bar(
                frame,
                gesture_name=gesture_name,
                segment_idx=segment_num,
                total_segments=num_videos,
                is_recording=True,
                elapsed=elapsed,
                total_time=float(seconds_per_video),
                samples_count=total_samples,
            )
            _draw_hand_detection_status(frame, hand_detected)
            _build_bottom_bar(frame, is_recording=True, progress=progress)
            _draw_frame_border(frame, is_recording=True)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                abort = True
                print("[DataCollector] Aborted by user during recording.")
                break

    # ------------------- CLEANUP -------------------
    cap.release()
    cv2.destroyAllWindows()
    extractor.close()

    # ---------- HANDLE ABORT: DISCARD EVERYTHING ----------
    if abort:
        print(
            f"[DataCollector] ABORTED — discarding all {len(collected_rows)} "
            f"collected samples for gesture '{gesture_name}'."
        )
        collected_rows.clear()

        if not file_existed_before and os.path.exists(gesture_csv):
            os.remove(gesture_csv)
            print(f"[DataCollector] Deleted newly created file: {gesture_csv}")

        print("[DataCollector] No data was saved.")
        return

    # ---------- NORMAL COMPLETION: SAVE DATA ----------
    if not collected_rows:
        print("[DataCollector] No samples collected; CSV not updated.")
        return

    file_exists_now = os.path.exists(gesture_csv)
    with open(gesture_csv, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists_now:
            writer.writerow(header)
        writer.writerows(collected_rows)

    print(
        f"\n[DataCollector] ✓ Collection complete!"
    )
    print(
        f"[DataCollector]   Gesture: '{gesture_name}'"
    )
    print(
        f"[DataCollector]   Total samples saved: {len(collected_rows)}"
    )
    print(
        f"[DataCollector]   Saved to: {gesture_csv}"
    )


if __name__ == "__main__":
    gesture = input("Enter gesture name to record: ").strip()
    collect_gesture_samples(gesture_name=gesture)