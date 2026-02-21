#!/usr/bin/env python3
"""
Direct entry point for gesture control with video streaming to frontend
Bypasses the interactive menu and streams frames via frame_buffer
"""
import os
import sys
import time
import threading

# Get the ml_core directory (absolute path)
ML_CORE_DIR = os.path.dirname(os.path.abspath(__file__))

# Add gesture_control_api to path
GESTURE_API_DIR = os.path.join(ML_CORE_DIR, 'gesture_control_api')
sys.path.insert(0, GESTURE_API_DIR)
sys.path.insert(0, ML_CORE_DIR)

# Import the frame buffer
SERVICES_DIR = os.path.join(ML_CORE_DIR, '..', 'services')
sys.path.insert(0, os.path.abspath(SERVICES_DIR))
from app.services.frame_buffer import frame_buffer

# Change to ml_core directory
os.chdir(ML_CORE_DIR)

# Check if we're in streaming mode
STREAMING_MODE = os.environ.get('FULL_CONTROL_STREAMING', 'false').lower() == 'true'

# Import required components
import cv2
import numpy as np
import tensorflow as tf
from tensorflow import keras
import pyautogui

from gesture_control_api.data_collector import HandLandmarkExtractor
from gesture_control_api.model_trainer import load_feature_stats


def run_gesture_control_streaming():
    """Run gesture control with frame streaming to frontend"""
    
    # Paths - use absolute paths based on ML_CORE_DIR
    MODEL_PATH = os.path.join(ML_CORE_DIR, "models", "gesture_ann.keras")
    LABEL_MAP_PATH = os.path.join(ML_CORE_DIR, "models", "label_map.json")
    FEATURE_STATS_PATH = os.path.join(ML_CORE_DIR, "models", "feature_stats.json")
    
    # Try multiple possible locations for hand_landmarker.task
    possible_model_paths = [
        "/Users/mayankkumar/Desktop/send to mayank/hand_landmarker.task",
        os.path.join(ML_CORE_DIR, "hand_landmarker.task"),
        os.path.join(ML_CORE_DIR, "..", "hand_landmarker.task"),
    ]
    
    HAND_LANDMARKER_MODEL_PATH = None
    for path in possible_model_paths:
        if os.path.exists(path):
            HAND_LANDMARKER_MODEL_PATH = path
            break
    
    if HAND_LANDMARKER_MODEL_PATH is None:
        print("[Gesture Stream] ERROR: Could not find hand_landmarker.task!")
        print(f"[Gesture Stream] Searched in: {possible_model_paths}")
        return
    
    print(f"[Gesture Stream] ML_CORE_DIR: {ML_CORE_DIR}")
    print(f"[Gesture Stream] MODEL_PATH: {MODEL_PATH}")
    print(f"[Gesture Stream] HAND_LANDMARKER_MODEL_PATH: {HAND_LANDMARKER_MODEL_PATH}")
    print(f"[Gesture Stream] Exists: {os.path.exists(MODEL_PATH)}")
    
    if not os.path.exists(MODEL_PATH):
        print("[Gesture Stream] ERROR: Model not found!")
        return
        
    # Load model
    import json
    with open(LABEL_MAP_PATH, 'r') as f:
        label_list = json.load(f)
    
    print(f"[Gesture Stream] Loaded {len(label_list)}-class model: {label_list}")
    
    model = keras.models.load_model(MODEL_PATH)
    print("[Gesture Stream] Model loaded successfully")
    extractor = HandLandmarkExtractor(HAND_LANDMARKER_MODEL_PATH)
    
    # Get expected feature dimension
    input_shape = model.input_shape
    if isinstance(input_shape, list):
        input_shape = input_shape[0]
    expected_dim = input_shape[-1]
    
    mean, std = load_feature_stats(FEATURE_STATS_PATH)
    
    # Camera
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # Gesture tracking
    current_gesture = None
    streak = 0
    TRIGGER_CONFIDENCE = 0.80
    REQUIRED_STREAK = 5
    SMOOTHING_WINDOW = 7
    SCROLL_AMOUNT = 700
    
    from collections import deque
    probs_buffer = deque(maxlen=SMOOTHING_WINDOW)
    
    # Cooldowns
    COOLDOWN_REPEATABLE = 0.01
    COOLDOWN_MODERATE = 2.0
    
    BASE_GESTURE_COOLDOWNS = {
        "scroll_up": COOLDOWN_REPEATABLE,
        "scroll_down": COOLDOWN_REPEATABLE,
        "swipe_right": COOLDOWN_MODERATE,
        "swipe_left": COOLDOWN_MODERATE,
        "zoom_in": COOLDOWN_REPEATABLE,
        "zoom_out": COOLDOWN_REPEATABLE,
        "volume_up": COOLDOWN_REPEATABLE,
        "volume_down": COOLDOWN_REPEATABLE,
        "play_pause": COOLDOWN_MODERATE,
        "ok": COOLDOWN_REPEATABLE,
    }
    
    gesture_last_trigger = {}
    
    # Create overlay window only if not in streaming mode
    if not STREAMING_MODE:
        window_name = "GestureControl"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.moveWindow(window_name, -10000, -10000)  # Move off screen
    
    print("[Gesture Stream] Starting gesture control with video streaming...")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame = cv2.flip(frame, 1)
            original_frame = frame.copy()
            
            features = extractor.extract(frame)
            
            ui_gesture = ""
            ui_confidence = 0.0
            ui_status = "no_hand"
            is_active = False
            
            if features is not None:
                try:
                    x_raw = features.reshape(1, -1).astype("float32")
                    from gesture_control_api.model_trainer import engineer_hand_features
                    x_eng = engineer_hand_features(x_raw)
                    
                    if x_eng.shape[1] != expected_dim:
                        ui_status = "error"
                        ui_gesture = "Feature dimension mismatch"
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
                            cooldown = BASE_GESTURE_COOLDOWNS.get(current_gesture, 2.0)
                            last_trigger = gesture_last_trigger.get(current_gesture, 0.0)
                            time_since_last = now - last_trigger
                            
                            if (current_gesture is not None and 
                                streak >= REQUIRED_STREAK and 
                                time_since_last >= cooldown):
                                
                                # Perform action
                                perform_action(current_gesture)
                                gesture_last_trigger[current_gesture] = now
                                streak = 0
                                
                except Exception as e:
                    ui_status = "error"
                    ui_gesture = str(e)[:30]
                    current_gesture = None
                    streak = 0
                    probs_buffer.clear()
            else:
                probs_buffer.clear()
                current_gesture = None
                streak = 0
            
            # Draw UI on frame
            frame = draw_ui(frame, ui_gesture, ui_confidence, ui_status, is_active, streak)
            
            # Update frame buffer for streaming
            frame_buffer.update_frame(
                frame, 
                gesture_name=ui_gesture, 
                confidence=ui_confidence, 
                status=ui_status,
                is_active=is_active
            )
            
            # Show in OpenCV window only if not in streaming mode
            if not STREAMING_MODE:
                cv2.imshow(window_name, frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                # In streaming mode, use a small delay to maintain ~30 FPS
                cv2.waitKey(33)
                
    finally:
        cap.release()
        if not STREAMING_MODE:
            cv2.destroyAllWindows()
        extractor.close()
        frame_buffer.clear()
        print("[Gesture Stream] Stopped")


def perform_action(gesture_name: str) -> None:
    """Perform the action for the recognized gesture"""
    import subprocess
    
    pyautogui.FAILSAFE = False
    
    # Scroll amount for scroll gestures
    SCROLL_AMOUNT = 700
    
    try:
        if gesture_name == "scroll_up":
            pyautogui.scroll(SCROLL_AMOUNT)
            print(f"[Action] Scroll UP")
        elif gesture_name == "scroll_down":
            pyautogui.scroll(-SCROLL_AMOUNT)
            print(f"[Action] Scroll DOWN")
        elif gesture_name == "swipe_right":
            pyautogui.hotkey("command", "shift", "]")
            print(f"[Action] Swipe RIGHT")
        elif gesture_name == "swipe_left":
            pyautogui.hotkey("command", "shift", "[")
            print(f"[Action] Swipe LEFT")
        elif gesture_name == "zoom_in":
            pyautogui.hotkey("command", "=")
            print(f"[Action] Zoom IN")
        elif gesture_name == "zoom_out":
            pyautogui.hotkey("command", "-")
            print(f"[Action] Zoom OUT")
        elif gesture_name == "volume_up":
            subprocess.run(["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) + 6)"], 
                         capture_output=True)
            print(f"[Action] Volume UP")
        elif gesture_name == "volume_down":
            subprocess.run(["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) - 6)"], 
                         capture_output=True)
            print(f"[Action] Volume DOWN")
        elif gesture_name == "play_pause":
            subprocess.run(['osascript', '-e', 'tell application "System Events" to key code 49'], 
                         capture_output=True)
            print(f"[Action] Play/Pause")
        elif gesture_name == "ok":
            # Left click on ok gesture
            pyautogui.click()
            print(f"[Action] OK - Left Click")
        else:
            print(f"[Action] Unknown gesture: {gesture_name}")
    except Exception as e:
        print(f"[Action] Error: {e}")


def draw_ui(frame, gesture_name, confidence, status, is_active, streak):
    """Draw professional UI overlay on frame"""
    h, w = frame.shape[:2]
    
    # Top bar background
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 50), (25, 25, 25), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    
    # Title
    cv2.putText(frame, "FULL CONTROL (macOS)", (w//2 - 100, 22), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 50), 2)
    
    # Status indicator
    if is_active:
        cv2.circle(frame, (w - 30, 25), 8, (0, 255, 0), -1)
        cv2.putText(frame, "ACTIVE", (w - 80, 29), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    else:
        cv2.circle(frame, (w - 30, 25), 8, (100, 100, 100), -1)
        cv2.putText(frame, "IDLE", (w - 65, 29), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
    
    # Bottom panel
    panel_height = 100
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - panel_height), (w, h), (25, 25, 25), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    
    # Gesture info
    if status == "detected":
        cv2.putText(frame, f"Gesture: {gesture_name}", (15, h - 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 120), 2)
        cv2.putText(frame, f"Confidence: {confidence*100:.1f}%", (15, h - 35), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        # Streak bar
        streak_progress = min(streak / 5, 1.0)
        cv2.rectangle(frame, (250, h - 50), (250 + int(150*streak_progress), h - 45), 
                      (0, 180, 255), -1)
        cv2.putText(frame, f"Streak: {streak}/5", (250, h - 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 180, 255), 1)
    elif status == "unrecognized":
        cv2.putText(frame, f"Unknown: {gesture_name} ({confidence*100:.1f}%)", (15, h - 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 100, 255), 1)
    else:
        cv2.putText(frame, "Show your hand to begin", (15, h - 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
    
    # Frame border
    border_color = (0, 220, 100) if is_active else (80, 80, 80)
    cv2.rectangle(frame, (0, 0), (w-1, h-1), border_color, 2)
    
    return frame


if __name__ == "__main__":
    print("Starting Gesture Control with video streaming...")
    print(f"Working directory: {os.getcwd()}")
    run_gesture_control_streaming()

