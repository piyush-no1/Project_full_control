import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import time
import os
import platform
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
backend_dir_str = str(BACKEND_DIR)
if backend_dir_str not in sys.path:
    sys.path.insert(0, backend_dir_str)

from app.ml_core.path_utils import resolve_hand_landmarker_path

# ─────────────────────────────────────────
#  DETECT OS
# ─────────────────────────────────────────
SYSTEM = platform.system()
print(f"OS: {SYSTEM}")

if SYSTEM == "Darwin":
    try:
        from Quartz.CoreGraphics import (
            CGEventCreateMouseEvent,
            CGEventPost,
            CGEventSetIntegerValueField,
            CGEventCreateScrollWheelEvent,
            kCGEventMouseMoved,
            kCGEventLeftMouseDown,
            kCGEventLeftMouseUp,
            kCGEventLeftMouseDragged,
            kCGEventRightMouseDown,
            kCGEventRightMouseUp,
            kCGMouseButtonLeft,
            kCGMouseButtonRight,
            kCGHIDEventTap,
            kCGMouseEventClickState,
            kCGScrollEventUnitLine,
            CGDisplayPixelsWide,
            CGDisplayPixelsHigh,
            CGMainDisplayID
        )
        from Quartz import CGPoint

        scr_w = CGDisplayPixelsWide(CGMainDisplayID())
        scr_h = CGDisplayPixelsHigh(CGMainDisplayID())
        USE_QUARTZ = True

    except ImportError:
        import pyautogui
        scr_w, scr_h = pyautogui.size()
        USE_QUARTZ = False

    if USE_QUARTZ:
        mouse_is_down = False

        def move_mouse(x, y):
            global mouse_is_down
            point = CGPoint(float(x), float(y))
            if mouse_is_down:
                event = CGEventCreateMouseEvent(None, kCGEventLeftMouseDragged, point, kCGMouseButtonLeft)
            else:
                event = CGEventCreateMouseEvent(None, kCGEventMouseMoved, point, kCGMouseButtonLeft)
            CGEventPost(kCGHIDEventTap, event)

        def mouse_down(x, y):
            global mouse_is_down
            point = CGPoint(float(x), float(y))
            event = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, kCGMouseButtonLeft)
            CGEventSetIntegerValueField(event, kCGMouseEventClickState, 1)
            CGEventPost(kCGHIDEventTap, event)
            mouse_is_down = True
            time.sleep(0.05)

        def mouse_up(x, y):
            global mouse_is_down
            point = CGPoint(float(x), float(y))
            event = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, kCGMouseButtonLeft)
            CGEventSetIntegerValueField(event, kCGMouseEventClickState, 1)
            CGEventPost(kCGHIDEventTap, event)
            mouse_is_down = False
            time.sleep(0.05)

        def left_click(x, y):
            point = CGPoint(float(x), float(y))
            down = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, kCGMouseButtonLeft)
            up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, kCGMouseButtonLeft)
            CGEventSetIntegerValueField(down, kCGMouseEventClickState, 1)
            CGEventSetIntegerValueField(up, kCGMouseEventClickState, 1)
            CGEventPost(kCGHIDEventTap, down)
            time.sleep(0.02)
            CGEventPost(kCGHIDEventTap, up)

        def double_click(x, y):
            point = CGPoint(float(x), float(y))
            down1 = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, kCGMouseButtonLeft)
            up1 = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, kCGMouseButtonLeft)
            down2 = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, kCGMouseButtonLeft)
            up2 = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, kCGMouseButtonLeft)
            CGEventSetIntegerValueField(down1, kCGMouseEventClickState, 1)
            CGEventSetIntegerValueField(up1, kCGMouseEventClickState, 1)
            CGEventSetIntegerValueField(down2, kCGMouseEventClickState, 2)
            CGEventSetIntegerValueField(up2, kCGMouseEventClickState, 2)
            CGEventPost(kCGHIDEventTap, down1)
            time.sleep(0.01)
            CGEventPost(kCGHIDEventTap, up1)
            time.sleep(0.05)
            CGEventPost(kCGHIDEventTap, down2)
            time.sleep(0.01)
            CGEventPost(kCGHIDEventTap, up2)

        def right_click(x, y):
            point = CGPoint(float(x), float(y))
            down = CGEventCreateMouseEvent(None, kCGEventRightMouseDown, point, kCGMouseButtonRight)
            up = CGEventCreateMouseEvent(None, kCGEventRightMouseUp, point, kCGMouseButtonRight)
            CGEventPost(kCGHIDEventTap, down)
            time.sleep(0.02)
            CGEventPost(kCGHIDEventTap, up)

        def scroll(amount):
            event = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, int(amount))
            CGEventPost(kCGHIDEventTap, event)

    else:
        mouse_is_down = False
        def move_mouse(x, y): pyautogui.moveTo(int(x), int(y), _pause=False)
        def mouse_down(x, y):
            global mouse_is_down
            pyautogui.moveTo(int(x), int(y), _pause=False); pyautogui.mouseDown(_pause=False); mouse_is_down = True
        def mouse_up(x, y):
            global mouse_is_down
            pyautogui.moveTo(int(x), int(y), _pause=False); pyautogui.mouseUp(_pause=False); mouse_is_down = False
        def left_click(x, y): pyautogui.click(int(x), int(y), _pause=False)
        def double_click(x, y): pyautogui.doubleClick(int(x), int(y), _pause=False)
        def right_click(x, y): pyautogui.rightClick(int(x), int(y), _pause=False)
        def scroll(amount): pyautogui.scroll(int(amount), _pause=False)

elif SYSTEM == "Windows":
    import ctypes
    user32 = ctypes.windll.user32
    scr_w = user32.GetSystemMetrics(0)
    scr_h = user32.GetSystemMetrics(1)
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_WHEEL = 0x0800
    WHEEL_DELTA = 120
    mouse_is_down = False

    def move_mouse(x, y): user32.SetCursorPos(int(x), int(y))
    def mouse_down(x, y):
        global mouse_is_down
        user32.SetCursorPos(int(x), int(y)); user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0); mouse_is_down = True; time.sleep(0.05)
    def mouse_up(x, y):
        global mouse_is_down
        user32.SetCursorPos(int(x), int(y)); user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0); mouse_is_down = False; time.sleep(0.05)
    def left_click(x, y):
        user32.SetCursorPos(int(x), int(y)); user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0); time.sleep(0.02); user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    def double_click(x, y): left_click(x, y); time.sleep(0.05); left_click(x, y)
    def right_click(x, y):
        user32.SetCursorPos(int(x), int(y)); user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0); time.sleep(0.02); user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    def scroll(amount): user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(amount * WHEEL_DELTA), 0)

else:
    import pyautogui
    scr_w, scr_h = pyautogui.size()
    mouse_is_down = False
    def move_mouse(x, y): pyautogui.moveTo(int(x), int(y), _pause=False)
    def mouse_down(x, y):
        global mouse_is_down
        pyautogui.mouseDown(x=int(x), y=int(y), _pause=False); mouse_is_down = True
    def mouse_up(x, y):
        global mouse_is_down
        pyautogui.mouseUp(x=int(x), y=int(y), _pause=False); mouse_is_down = False
    def left_click(x, y): pyautogui.click(int(x), int(y), _pause=False)
    def double_click(x, y): pyautogui.doubleClick(int(x), int(y), _pause=False)
    def right_click(x, y): pyautogui.rightClick(int(x), int(y), _pause=False)
    def scroll(amount): pyautogui.scroll(int(amount), _pause=False)

print(f"Screen: {scr_w}x{scr_h}")

# ─────────────────────────────────────────
#  DOWNLOAD MODEL
# ─────────────────────────────────────────
model_path = resolve_hand_landmarker_path()
if not model_path.exists():
    raise FileNotFoundError(
        "hand_landmarker.task not found. Set HAND_LANDMARKER_MODEL_PATH or place the file in backend/app/ml_core/."
    )

print(f"[Mouse Control] Using hand landmarker model: {model_path}")

# ─────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────
# Flag to disable window when used as module for streaming
STREAMING_MODE = os.environ.get('FULL_CONTROL_STREAMING', 'false').lower() == 'true'

SPEED                  = 1.8
SMOOTHING              = 0.5
PINCH_THRESHOLD        = 0.05
RIGHT_CLICK_THRESHOLD  = 0.05
DOUBLE_TAP_TIME        = 0.5
DRAG_CONFIRM_FRAMES    = 8
DRAG_RELEASE_FRAMES    = 5
HAND_LOST_GRACE_TIME   = 1.0

# ── SCROLL SETTINGS ──
SCROLL_SPEED           = 2      # lines per scroll event
SCROLL_INTERVAL        = 0.05   # seconds between scroll events (lower = faster)

# ─────────────────────────────────────────
#  MEDIAPIPE
# ─────────────────────────────────────────
base_options = python.BaseOptions(model_asset_path=str(model_path))
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=1,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.4
)
detector = vision.HandLandmarker.create_from_options(options)

# ─────────────────────────────────────────
#  VIDEO CAPTURE (outside main block so it can be imported)
# ─────────────────────────────────────────
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)
cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# ─────────────────────────────────────────
#  LANDMARKS
# ─────────────────────────────────────────
WRIST = 0
THUMB_TIP = 4; THUMB_IP = 3; THUMB_MCP = 2
INDEX_TIP = 8; INDEX_DIP = 7; INDEX_PIP = 6; INDEX_MCP = 5
MIDDLE_TIP = 12; MIDDLE_DIP = 11; MIDDLE_PIP = 10; MIDDLE_MCP = 9
RING_TIP = 16; RING_PIP = 14; RING_MCP = 13
PINKY_TIP = 20; PINKY_PIP = 18; PINKY_MCP = 17

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),(0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),(5,9),(9,13),(13,17)
]

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def get_distance(p1, p2):
    return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2) ** 0.5

def get_palm_center(lm):
    pts = [lm[WRIST], lm[INDEX_MCP], lm[MIDDLE_MCP], lm[RING_MCP], lm[PINKY_MCP]]
    return sum(p.x for p in pts)/5, sum(p.y for p in pts)/5

def is_fist(lm):
    fingers = [(INDEX_TIP,INDEX_PIP),(MIDDLE_TIP,MIDDLE_PIP),(RING_TIP,RING_PIP),(PINKY_TIP,PINKY_PIP)]
    return sum(1 for t,p in fingers if lm[t].y > lm[p].y) >= 3

def is_open_palm(lm):
    fingers = [(INDEX_TIP,INDEX_PIP),(MIDDLE_TIP,MIDDLE_PIP),(RING_TIP,RING_PIP),(PINKY_TIP,PINKY_PIP)]
    return sum(1 for t,p in fingers if lm[t].y < lm[p].y) >= 3

def detect_scroll_gesture(lm):
    # Check peace sign: index + middle up, ring + pinky down
    index_up   = lm[INDEX_TIP].y < lm[INDEX_PIP].y
    middle_up  = lm[MIDDLE_TIP].y < lm[MIDDLE_PIP].y
    ring_down  = lm[RING_TIP].y > lm[RING_PIP].y
    pinky_down = lm[PINKY_TIP].y > lm[PINKY_PIP].y

    is_peace = index_up and middle_up and ring_down and pinky_down

    if not is_peace:
        idx_len = get_distance(lm[INDEX_TIP], lm[INDEX_MCP])
        mid_len = get_distance(lm[MIDDLE_TIP], lm[MIDDLE_MCP])
        ring_len = get_distance(lm[RING_TIP], lm[RING_MCP])
        pinky_len = get_distance(lm[PINKY_TIP], lm[PINKY_MCP])

        two_fingers_extended = idx_len > 0.1 and mid_len > 0.1
        two_fingers_curled = ring_len < 0.08 and pinky_len < 0.08

        if not (two_fingers_extended and two_fingers_curled):
            return "NONE"

    finger_tip_y = (lm[INDEX_TIP].y + lm[MIDDLE_TIP].y) / 2
    wrist_y = lm[WRIST].y
    diff = wrist_y - finger_tip_y
    threshold = 0.03

    if diff > threshold:
        return "UP"
    elif diff < -threshold:
        return "DOWN"
    else:
        return "NEUTRAL"

def draw_hand(frame, lm, cam_w, cam_h):
    points = []
    for l in lm:
        x, y = int(l.x*cam_w), int(l.y*cam_h)
        points.append((x,y))
        cv2.circle(frame, (x,y), 3, (80,80,80), -1)
    for s,e in HAND_CONNECTIONS:
        cv2.line(frame, points[s], points[e], (120,120,120), 1)

def draw_tip(frame, lm, idx, cam_w, cam_h, color, radius=12):
    x, y = int(lm[idx].x*cam_w), int(lm[idx].y*cam_h)
    cv2.circle(frame, (x,y), radius, color, -1)
    cv2.circle(frame, (x,y), radius, (255,255,255), 2)
    return (x, y)

def draw_scroll_visual(frame, direction, cam_w, cam_h):
    cx = cam_w // 2
    if direction == "UP":
        color = (0, 255, 0)
        cv2.arrowedLine(frame, (cx, 120), (cx, 40), color, 4, tipLength=0.4)
        cv2.putText(frame, "SCROLL UP", (cx-70, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    elif direction == "DOWN":
        color = (0, 100, 255)
        y_start = cam_h - 120
        cv2.arrowedLine(frame, (cx, y_start-40), (cx, y_start+40), color, 4, tipLength=0.4)
        cv2.putText(frame, "SCROLL DOWN", (cx-80, y_start+65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    elif direction == "NEUTRAL":
        color = (255, 200, 0)
        cv2.putText(frame, "SCROLL MODE - Tilt UP or DOWN", (cx-180, cam_h//2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

# Only run main code when file is executed directly, not when imported
if __name__ == "__main__":
    # State
    sx, sy = scr_w//2, scr_h//2
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

    scroll_mode = False
    last_scroll_time = 0
    scroll_direction = "NONE"

    flash_time = 0
    flash_text = ""
    flash_color = (0,0,0)

    fps_time = time.time()
    fps_count = 0
    fps_display = 0
    debug_mode = False

    print("=" * 55)
    print("       PALM MOUSE + EASY SCROLL")
    print("=" * 55)
    print(f"  OS: {SYSTEM} | Screen: {scr_w}x{scr_h}")
    print("─" * 55)
    print("  MOVE:          Move hand")
    print("  LEFT CLICK:    Thumb + Index TAP")
    print("  DOUBLE CLICK:  Thumb + Index 2x TAP")
    print("  RIGHT CLICK:   Thumb + Middle TAP")
    print("  DRAG:          FIST (hold)")
    print("  DROP:          Open hand (hold)")
    print("  SCROLL UP:     ✌️ Peace sign + tilt hand UP")
    print("  SCROLL DOWN:   ✌️ Peace sign + tilt hand DOWN")
    print("─" * 55)
    print("  Q=quit +=fast -=slow D=debug")
    print("=" * 55)

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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

        if hand_detected:
            hand_lost_frames = 0
            hand_lost_time = 0
            last_hand_detected = True

            lm = result.hand_landmarks[0]
            draw_hand(frame, lm, cam_w, cam_h)

            fist_now = is_fist(lm)
            open_now = is_open_palm(lm)

            thumb = lm[THUMB_TIP]
            index = lm[INDEX_TIP]
            middle = lm[MIDDLE_TIP]
            dist_ti = get_distance(thumb, index)
            dist_tm = get_distance(thumb, middle)

            scroll_direction = detect_scroll_gesture(lm)

            if scroll_direction in ["UP", "DOWN", "NEUTRAL"]:
                scroll_mode = True
                i_px = draw_tip(frame, lm, INDEX_TIP, cam_w, cam_h, (255, 100, 0), 15)
                m_px = draw_tip(frame, lm, MIDDLE_TIP, cam_w, cam_h, (255, 100, 0), 15)
                cv2.line(frame, i_px, m_px, (255, 100, 0), 3)

                if scroll_direction == "UP" and now - last_scroll_time > SCROLL_INTERVAL:
                    scroll(SCROLL_SPEED)
                    last_scroll_time = now
                elif scroll_direction == "DOWN" and now - last_scroll_time > SCROLL_INTERVAL:
                    scroll(-SCROLL_SPEED)
                    last_scroll_time = now

                draw_scroll_visual(frame, scroll_direction, cam_w, cam_h)

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
                palm_x, palm_y = get_palm_center(lm)
                offset_x = (palm_x - 0.5) * SPEED
                offset_y = (palm_y - 0.5) * SPEED
                norm_x = max(0, min(1, 0.5 + offset_x))
                norm_y = max(0, min(1, 0.5 + offset_y))
                tx = int(norm_x * scr_w)
                ty = int(norm_y * scr_h)

                prev_sx, prev_sy = sx, sy
                sx = int(sx + (tx - sx) * SMOOTHING)
                sy = int(sy + (ty - sy) * SMOOTHING)
                velocity_x = sx - prev_sx
                velocity_y = sy - prev_sy
                move_mouse(sx, sy)

                pcx, pcy = int(palm_x*cam_w), int(palm_y*cam_h)
                palm_col = (0,0,255) if dragging else (0,255,255)
                cv2.circle(frame, (pcx,pcy), 20, palm_col, 3)
                cv2.circle(frame, (pcx,pcy), 6, palm_col, -1)

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

                if dragging and open_frame_count >= DRAG_RELEASE_FRAMES:
                    mouse_up(sx, sy)
                    dragging = False
                    fist_frame_count = open_frame_count = 0
                    print(f">> DROPPED")
                    flash_time, flash_text, flash_color = now, "DROPPED!", (0,255,0)

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
                            tap_count = 0
                            waiting_for_second = False

                    was_left_pinched = is_lp

                    if waiting_for_second and (now - first_tap_time > DOUBLE_TAP_TIME):
                        left_click(sx, sy)
                        print(">> LEFT CLICK")
                        flash_time, flash_text, flash_color = now, "LEFT CLICK!", (0,255,0)
                        tap_count = 0
                        waiting_for_second = False

                    is_rp = dist_tm < RIGHT_CLICK_THRESHOLD
                    if is_rp and not was_right_pinched:
                        if now - last_right_click > 0.4:
                            right_click(sx, sy)
                            last_right_click = now
                            print(">> RIGHT CLICK")
                            flash_time, flash_text, flash_color = now, "RIGHT CLICK!", (0,100,255)
                    was_right_pinched = is_rp

                if not dragging and not fist_now:
                    is_lp = dist_ti < PINCH_THRESHOLD
                    is_rp = dist_tm < RIGHT_CLICK_THRESHOLD
                    t_px = draw_tip(frame, lm, THUMB_TIP, cam_w, cam_h, (255,150,0))
                    i_px = draw_tip(frame, lm, INDEX_TIP, cam_w, cam_h, (0,255,0) if is_lp else (0,200,255))
                    m_px = draw_tip(frame, lm, MIDDLE_TIP, cam_w, cam_h, (0,255,0) if is_rp else (0,255,255))
                    cv2.line(frame, t_px, i_px, (0,255,0) if is_lp else (150,150,150), 4 if is_lp else 1)
                    cv2.line(frame, t_px, m_px, (0,255,0) if is_rp else (150,150,150), 4 if is_rp else 1)

                if dragging:
                    th = int(3 + 2*abs((now*3)%2-1))
                    cv2.rectangle(frame, (5,5), (cam_w-5,cam_h-55), (0,0,255), th)
                    cv2.putText(frame, "DRAGGING", (cam_w//2-60,35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
                    cv2.putText(frame, "Open hand to DROP", (cam_w//2-110,60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,255), 1)

                if fist_now and not dragging:
                    status_text = f"HOLD FIST {fist_frame_count}/{DRAG_CONFIRM_FRAMES}"
                    status_color = (0,100,255)

                if waiting_for_second:
                    status_text, status_color = "TAP AGAIN...", (255,0,255)
                
                if not dragging and not fist_now and not waiting_for_second:
                    status_text, status_color = "TRACKING", (200,200,200)

        else:
            hand_lost_frames += 1
            scroll_mode = False

            if last_hand_detected:
                hand_lost_time = now
                last_hand_detected = False

            tsl = now - hand_lost_time if hand_lost_time > 0 else 0

            if dragging:
                sx = int(sx + velocity_x*0.5)
                sy = int(sy + velocity_y*0.5)
                sx = max(0, min(scr_w-1, sx))
                sy = max(0, min(scr_h-1, sy))
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

        cv2.rectangle(frame, (0,cam_h-55), (cam_w,cam_h), (30,30,30), -1)
        cv2.putText(frame, status_text, (10,cam_h-20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)
        cv2.putText(frame, f"{SYSTEM} Q +=- D", (cam_w-130,cam_h-20), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150,150,150), 1)

        if now - flash_time < 0.5:
            cv2.putText(frame, flash_text, (cam_w//2-130,cam_h//2), cv2.FONT_HERSHEY_SIMPLEX, 1.2, flash_color, 3)

        if not STREAMING_MODE:
            cv2.imshow("Palm Mouse", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'): break
        else:
            cv2.waitKey(33)

    if dragging: mouse_up(sx, sy)
    cap.release()
    if not STREAMING_MODE:
        cv2.destroyAllWindows()
