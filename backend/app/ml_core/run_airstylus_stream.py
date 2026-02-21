#!/usr/bin/env python3
"""
Direct entry point for Air Stylus (mouse control) with video streaming to frontend
"""
import os
import sys
import time
import threading

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the frame buffer
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'services'))
from app.services.frame_buffer import frame_buffer

# Get ml_core directory for path resolution
ML_CORE_DIR = os.path.dirname(os.path.abspath(__file__))

# Try multiple possible locations for hand_landmarker.task
possible_model_paths = [
    "/Users/mayankkumar/Desktop/send to mayank/hand_landmarker.task",
    os.path.join(ML_CORE_DIR, "hand_landmarker.task"),
    os.path.join(ML_CORE_DIR, "..", "hand_landmarker.task"),
    os.path.join(ML_CORE_DIR, "Mouse_Control", "hand_landmarker.task"),
]

HAND_LANDMARKER_MODEL_PATH = None
for path in possible_model_paths:
    if os.path.exists(path):
        HAND_LANDMARKER_MODEL_PATH = path
        break

if HAND_LANDMARKER_MODEL_PATH is None:
    print("[Air Stylus Stream] ERROR: Could not find hand_landmarker.task!")
    print(f"[Air Stylus Stream] Searched in: {possible_model_paths}")
    sys.exit(1)

print(f"[Air Stylus Stream] Using hand_landmarker.model: {HAND_LANDMARKER_MODEL_PATH}")

# Import required components from Mouse_Control
from Mouse_Control.mouse_control import (
    detector, cap, get_palm_center, get_distance, is_fist, is_open_palm,
    detect_scroll_gesture, draw_hand, draw_tip, draw_scroll_visual,
    SCR_W, SCR_H, SYSTEM, PINCH_THRESHOLD, RIGHT_CLICK_THRESHOLD,
    DOUBLE_TAP_TIME, DRAG_CONFIRM_FRAMES, DRAG_RELEASE_FRAMES,
    HAND_LOST_GRACE_TIME, SCROLL_SPEED, SCROLL_INTERVAL,
    move_mouse, mouse_down, mouse_up, left_click, double_click, right_click, scroll
)

# Also import cv2
import cv2
import numpy as np

# Check if we're in streaming mode
STREAMING_MODE = os.environ.get('FULL_CONTROL_STREAMING', 'false').lower() == 'true'


def run_air_stylus_streaming():
    """Run Air Stylus mouse control with frame streaming to frontend"""
    
    # State
    sx, sy = SCR_W//2, SCR_H//2
    prev_sx, prev_sy = sx, sy
    velocity_x, velocity_y = 0, 0
    
    was_left_pinched = False
    tap_count = 0
    first_tap_time = 0
    waiting_for_second = False
    
    was_right_pinched = False
    last_right_click = 0
    
    dragging = False
    fist_frame_count = 0
    open_frame_count = 0
    
    hand_lost_frames = 0
    hand_lost_time = 0
    last_hand_detected = True
    
    # Scroll
    scroll_mode = False
    last_scroll_time = 0
    scroll_direction = "NONE"
    
    flash_time = 0
    flash_text = ""
    flash_color = (0,0,0)
    
    fps_time = time.time()
    fps_count = 0
    fps_display = 0

    # Get camera properties
    cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    SPEED = 1.8
    SMOOTHING = 0.5
    
    # Create hidden window (only if not in streaming mode)
    if not STREAMING_MODE:
        window_name = "AirStylus"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.moveWindow(window_name, -10000, -10000)
    
    print("[Air Stylus Stream] Starting Air Stylus with video streaming...")
    
    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
    
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            import mediapipe as mp
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = detector.detect(mp_image)
    
            status_text = "Show your hand"
            status_color = (100, 100, 100)
            now = time.time()
    
            fps_count += 1
            if now - fps_time >= 1.0:
                fps_display = fps_count
                fps_count = 0
                fps_time = now
    
            hand_detected = len(result.hand_landmarks) > 0 if result.hand_landmarks else False
            gesture_name = ""
            confidence = 0.0
    
            if hand_detected:
                hand_lost_frames = 0
                hand_lost_time = 0
                last_hand_detected = True
    
                lm = result.hand_landmarks[0]
                draw_hand(frame, lm, cam_w, cam_h)
    
                fist_now = is_fist(lm)
                open_now = is_open_palm(lm)
    
                thumb = lm[4]  # THUMB_TIP
                index = lm[8]  # INDEX_TIP
                middle = lm[12]  # MIDDLE_TIP
                dist_ti = get_distance(thumb, index)
                dist_tm = get_distance(thumb, middle)
    
                # Detect scroll
                scroll_direction = detect_scroll_gesture(lm)
    
                if scroll_direction in ["UP", "DOWN", "NEUTRAL"]:
                    scroll_mode = True
                    gesture_name = f"SCROLL_{scroll_direction}" if scroll_direction != "NEUTRAL" else "SCROLL"
                    confidence = 0.9
    
                    # Draw peace sign fingers
                    i_px = draw_tip(frame, lm, 8, cam_w, cam_h, (255, 100, 0), 15)
                    m_px = draw_tip(frame, lm, 12, cam_w, cam_h, (255, 100, 0), 15)
                    cv2.line(frame, i_px, m_px, (255, 100, 0), 3)
    
                    # Continuous scroll
                    if scroll_direction == "UP" and now - last_scroll_time > SCROLL_INTERVAL:
                        scroll(SCROLL_SPEED)
                        last_scroll_time = now
                    elif scroll_direction == "DOWN" and now - last_scroll_time > SCROLL_INTERVAL:
                        scroll(-SCROLL_SPEED)
                        last_scroll_time = now
    
                    draw_scroll_visual(frame, scroll_direction, cam_w, cam_h)
                    
                    # Scroll mode border
                    border_color = (0,255,0) if scroll_direction == "UP" else (0,100,255) if scroll_direction == "DOWN" else (255,200,0)
                    cv2.rectangle(frame, (5,5), (cam_w-5, cam_h-55), border_color, 2)
    
                    if scroll_direction == "UP":
                        status_text = "SCROLLING UP ↑"
                        status_color = (0, 255, 0)
                    elif scroll_direction == "DOWN":
                        status_text = "SCROLLING DOWN ↓"
                        status_color = (0, 100, 255)
                    else:
                        status_text = "SCROLL MODE - Tilt hand"
                        status_color = (255, 200, 0)
    
                else:
                    scroll_mode = False
    
                    # Palm → Cursor
                    palm_x, palm_y = get_palm_center(lm)
                    offset_x = (palm_x - 0.5) * SPEED
                    offset_y = (palm_y - 0.5) * SPEED
                    norm_x = max(0, min(1, 0.5 + offset_x))
                    norm_y = max(0, min(1, 0.5 + offset_y))
                    tx = int(norm_x * SCR_W)
                    ty = int(norm_y * SCR_H)
    
                    prev_sx, prev_sy = sx, sy
                    sx = int(sx + (tx - sx) * SMOOTHING)
                    sy = int(sy + (ty - sy) * SMOOTHING)
                    velocity_x = sx - prev_sx
                    velocity_y = sy - prev_sy
                    move_mouse(sx, sy)
    
                    # Palm visual
                    pcx, pcy = int(palm_x*cam_w), int(palm_y*cam_h)
                    palm_col = (0,0,255) if dragging else (0,255,255)
                    cv2.circle(frame, (pcx,pcy), 20, palm_col, 3)
                    cv2.circle(frame, (pcx,pcy), 6, palm_col, -1)
    
                    # Drag
                    if fist_now:
                        fist_frame_count += 1
                        open_frame_count = 0
                    else:
                        if not dragging: fist_frame_count = 0
    
                    if open_now and dragging:
                        open_frame_count += 1
                    else:
                        open_frame_count = 0
    
                    if fist_frame_count >= DRAG_CONFIRM_FRAMES and not dragging:
                        mouse_down(sx, sy)
                        dragging = True
                        print(f">> DRAG START")
                        flash_time, flash_text, flash_color = now, "DRAGGING...", (0,0,255)
                        gesture_name = "DRAG"
                        confidence = 0.9
    
                    if dragging and open_frame_count >= DRAG_RELEASE_FRAMES:
                        mouse_up(sx, sy)
                        dragging = False
                        fist_frame_count = open_frame_count = 0
                        print(f">> DROPPED")
                        flash_time, flash_text, flash_color = now, "DROPPED!", (0,255,0)
                        gesture_name = "DROP"
                        confidence = 0.9
    
                    # Clicks
                    if not dragging and not fist_now:
                        is_lp = dist_ti < PINCH_THRESHOLD
    
                        if is_lp and not was_left_pinched:
                            tap_count += 1
                            if tap_count == 1:
                                first_tap_time = now
                                waiting_for_second = True
                            elif tap_count >= 2:
                                if now - first_tap_time <= DOUBLE_TAP_TIME:
                                    double_click(sx, sy)
                                    print(">> DOUBLE CLICK")
                                    flash_time, flash_text, flash_color = now, "DOUBLE CLICK!", (255,0,255)
                                    gesture_name = "DOUBLE CLICK"
                                    confidence = 0.9
                                tap_count = 0
                                waiting_for_second = False
    
                        was_left_pinched = is_lp
    
                        if waiting_for_second and (now - first_tap_time > DOUBLE_TAP_TIME):
                            left_click(sx, sy)
                            print(">> LEFT CLICK")
                            flash_time, flash_text, flash_color = now, "LEFT CLICK!", (0,255,0)
                            gesture_name = "LEFT CLICK"
                            confidence = 0.9
                            tap_count = 0
                            waiting_for_second = False
    
                        is_rp = dist_tm < RIGHT_CLICK_THRESHOLD
                        if is_rp and not was_right_pinched:
                            if now - last_right_click > 0.4:
                                right_click(sx, sy)
                                last_right_click = now
                                print(">> RIGHT CLICK")
                                flash_time, flash_text, flash_color = now, "RIGHT CLICK!", (0,100,255)
                                gesture_name = "RIGHT CLICK"
                                confidence = 0.9
                        was_right_pinched = is_rp
    
                    # Visuals
                    if not dragging and not fist_now:
                        is_lp = dist_ti < PINCH_THRESHOLD
                        is_rp = dist_tm < RIGHT_CLICK_THRESHOLD
                        t_px = draw_tip(frame, lm, 4, cam_w, cam_h, (255,150,0))
                        i_px = draw_tip(frame, lm, 8, cam_w, cam_h, (0,255,0) if is_lp else (0,200,255))
                        m_px = draw_tip(frame, lm, 12, cam_w, cam_h, (0,255,0) if is_rp else (0,255,255))
                        cv2.line(frame, t_px, i_px, (0,255,0) if is_lp else (150,150,150), 4 if is_lp else 1)
                        cv2.line(frame, t_px, m_px, (0,255,0) if is_rp else (150,150,150), 4 if is_rp else 1)
    
                    if dragging:
                        gesture_name = "DRAGGING"
                        confidence = 0.9
                        th = int(3 + 2*abs((now*3)%2-1))
                        cv2.rectangle(frame, (5,5), (cam_w-5,cam_h-55), (0,0,255), th)
                        cv2.putText(frame, "DRAGGING", (cam_w//2-60,35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
                        cv2.putText(frame, "Open hand to DROP", (cam_w//2-110,60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,255), 1)
    
                    if fist_now and not dragging:
                        status_text = f"HOLD FIST {fist_frame_count}/{DRAG_CONFIRM_FRAMES}"
                        status_color = (0,100,255)
                        gesture_name = "FIST"
                        confidence = 0.7
    
                    if waiting_for_second:
                        status_text, status_color = "TAP AGAIN...", (255,0,255)
                    
                    if not dragging and not fist_now and not waiting_for_second:
                        status_text, status_color = "TRACKING", (200,200,200)
    
            else:
                # Hand lost
                hand_lost_frames += 1
                scroll_mode = False
    
                if last_hand_detected:
                    hand_lost_time = now
                    last_hand_detected = False
    
                tsl = now - hand_lost_time if hand_lost_time > 0 else 0
    
                if dragging:
                    sx = int(sx + velocity_x*0.5)
                    sy = int(sy + velocity_y*0.5)
                    sx = max(0, min(SCR_W-1, sx))
                    sy = max(0, min(SCR_H-1, sy))
                    move_mouse(sx, sy)
                    velocity_x *= 0.9
                    velocity_y *= 0.9
    
                    cv2.putText(frame, "HAND LOST - STILL DRAGGING", (cam_w//2-170,cam_h//2-30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,165,255), 2)
    
                    if tsl >= HAND_LOST_GRACE_TIME:
                        mouse_up(sx, sy)
                        dragging = False
                        fist_frame_count = open_frame_count = 0
                        velocity_x = velocity_y = 0
    
                status_text = f"HAND LOST ({max(0,HAND_LOST_GRACE_TIME-tsl):.1f}s)"
                status_color = (0,165,255)
    
            # Status bar
            cv2.rectangle(frame, (0,cam_h-55), (cam_w,cam_h), (30,30,30), -1)
            cv2.putText(frame, status_text, (10,cam_h-20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)
            cv2.putText(frame, f"{SYSTEM} Air Stylus", (cam_w-150,cam_h-20), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150,150,150), 1)
    
            # Flash
            if now - flash_time < 0.5:
                cv2.putText(frame, flash_text, (cam_w//2-130,cam_h//2), cv2.FONT_HERSHEY_SIMPLEX, 1.2, flash_color, 3)
    
            # Show in window only if not in streaming mode
            if not STREAMING_MODE:
                cv2.imshow(window_name, frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                # In streaming mode, use a small delay to maintain ~30 FPS
                cv2.waitKey(33)
    
            # Update frame buffer for streaming
            is_active = hand_detected and (gesture_name != "")
            frame_buffer.update_frame(
                frame,
                gesture_name=gesture_name,
                confidence=confidence,
                status="detected" if gesture_name else "no_hand",
                is_active=is_active
            )
            
    finally:
        cap.release()
        if not STREAMING_MODE:
            cv2.destroyAllWindows()
        frame_buffer.clear()
        print("[Air Stylus Stream] Stopped")


if __name__ == "__main__":
    print("Starting Air Stylus with video streaming...")
    print(f"Working directory: {os.getcwd()}")
    run_air_stylus_streaming()

