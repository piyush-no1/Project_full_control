"""
Shared frame buffer for video streaming between ML models and frontend
"""
import threading
import numpy as np
from typing import Optional
import cv2
import base64

class FrameBuffer:
    """Thread-safe frame buffer for video streaming"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._gesture_name: str = ""
        self._confidence: float = 0.0
        self._status: str = "no_hand"
        self._is_active: bool = False
        
    def update_frame(self, frame: np.ndarray, gesture_name: str = "", confidence: float = 0.0, status: str = "no_hand", is_active: bool = False):
        """Update the frame and gesture info (thread-safe)"""
        with self._lock:
            self._frame = frame.copy() if frame is not None else None
            self._gesture_name = gesture_name
            self._confidence = confidence
            self._status = status
            self._is_active = is_active
    
    def get_frame(self) -> tuple:
        """Get current frame as base64 (thread-safe)"""
        with self._lock:
            if self._frame is None:
                return None, "", 0.0, "no_hand", False
            
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', self._frame)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            return (
                frame_base64,
                self._gesture_name,
                self._confidence,
                self._status,
                self._is_active
            )
    
    def clear(self):
        """Clear the frame buffer"""
        with self._lock:
            self._frame = None
            self._gesture_name = ""
            self._confidence = 0.0
            self._status = "no_hand"
            self._is_active = False


# Global frame buffer instance
frame_buffer = FrameBuffer()

