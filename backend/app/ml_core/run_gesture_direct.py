#!/usr/bin/env python3
"""
Direct entry point for gesture control - bypasses the interactive menu
Run this directly to start gesture recognition without user interaction
"""
import os
import sys

# Get the ml_core directory
ML_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
# Add gesture_control_api to path
GESTURE_API_DIR = os.path.join(ML_CORE_DIR, 'gesture_control_api')
sys.path.insert(0, GESTURE_API_DIR)
sys.path.insert(0, ML_CORE_DIR)

# Change to ml_core directory
os.chdir(ML_CORE_DIR)

# Import and run the gesture control directly
from gesture_control_api.main import run_gesture_control

if __name__ == "__main__":
    print("Starting Gesture Control directly...")
    print(f"Working directory: {os.getcwd()}")
    print(f"Python path: {sys.path[:3]}")
    run_gesture_control()

