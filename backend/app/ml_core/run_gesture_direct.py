#!/usr/bin/env python3
"""
Direct entry point for gesture control - bypasses the interactive menu
Run this directly to start gesture recognition without user interaction
"""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
backend_dir_str = str(BACKEND_DIR)
if backend_dir_str not in sys.path:
    sys.path.insert(0, backend_dir_str)

from app.ml_core.path_utils import ML_CORE_DIR, ensure_runtime_import_paths

ensure_runtime_import_paths()

# Change to ml_core directory
os.chdir(str(ML_CORE_DIR))

# Import and run the gesture control directly
from gesture_control_api.main import run_gesture_control

if __name__ == "__main__":
    print("Starting Gesture Control directly...")
    print(f"Working directory: {os.getcwd()}")
    run_gesture_control()
