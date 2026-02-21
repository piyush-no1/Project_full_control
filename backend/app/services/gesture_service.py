import subprocess
import sys
import os
import time
import threading
from app.services.model_state import model_state
from app.services.frame_buffer import frame_buffer

# Get the absolute path to the gesture streaming script
GESTURE_SCRIPT = os.path.join(
    os.path.dirname(__file__),  # backend/app/services/
    "..",                       # backend/app/
    "ml_core",                  # backend/app/ml_core/
    "run_gesture_stream.py"    # runs gesture with frame streaming
)
GESTURE_SCRIPT = os.path.abspath(GESTURE_SCRIPT)

# Also copy models to gesture_control_api/models if they don't exist
GESTURE_MODELS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "ml_core",
    "gesture_control_api",
    "models"
)
GESTURE_MODELS_DIR = os.path.abspath(GESTURE_MODELS_DIR)

MODELS_SOURCE_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "ml_core",
    "models"
)
MODELS_SOURCE_DIR = os.path.abspath(MODELS_SOURCE_DIR)

def copy_models_if_needed():
    """Copy model files to gesture_control_api/models if they don't exist"""
    os.makedirs(GESTURE_MODELS_DIR, exist_ok=True)
    
    model_files = ['gesture_ann.keras', 'label_map.json', 'feature_stats.json', 'gesture_config.json']
    
    for model_file in model_files:
        src = os.path.join(MODELS_SOURCE_DIR, model_file)
        dst = os.path.join(GESTURE_MODELS_DIR, model_file)
        
        if os.path.exists(src) and not os.path.exists(dst):
            import shutil
            shutil.copy2(src, dst)
            print(f"[Gesture Service] Copied {model_file} to gesture_control_api/models")
        elif os.path.exists(src):
            # Update existing file
            import shutil
            shutil.copy2(src, dst)
            print(f"[Gesture Service] Updated {model_file} in gesture_control_api/models")

# Thread to read subprocess output
def read_process_output(process, prefix):
    try:
        for line in process.stdout:
            print(f"[{prefix}] {line.strip()}")
        for line in process.stderr:
            print(f"[{prefix} ERROR] {line.strip()}")
    except:
        pass

def start_gesture():

    if model_state.gesture_running:
        return "Gesture already running"

    # Stop air stylus if running
    if model_state.air_stylus_running:
        model_state.air_stylus_process.terminate()
        try:
            model_state.air_stylus_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            model_state.air_stylus_process.kill()
        model_state.air_stylus_process = None
        model_state.air_stylus_running = False

    # Copy models if needed
    copy_models_if_needed()
    
    # Get the working directory
    work_dir = os.path.join(os.path.dirname(__file__), "..", "ml_core")
    work_dir = os.path.abspath(work_dir)
    
    print(f"[Gesture Service] Starting gesture control from: {GESTURE_SCRIPT}")
    print(f"[Gesture Service] Working directory: {work_dir}")
    
    # Check if script exists
    if not os.path.exists(GESTURE_SCRIPT):
        error_msg = f"[Gesture Service] ERROR: Script not found at {GESTURE_SCRIPT}"
        print(error_msg)
        return error_msg
    
    # Check if models exist
    model_path = os.path.join(MODELS_SOURCE_DIR, "gesture_ann.keras")
    if not os.path.exists(model_path):
        error_msg = f"[Gesture Service] ERROR: Model not found at {model_path}"
        print(error_msg)
        return error_msg
    
    # Get the python interpreter from the venv
    venv_python = os.path.join(os.path.dirname(__file__), "..", "..", "venv", "bin", "python")
    venv_python = os.path.abspath(venv_python)
    
    # Check if venv python exists
    if not os.path.exists(venv_python):
        # Try system python
        venv_python = sys.executable
        print(f"[Gesture Service] Using system Python: {venv_python}")
    else:
        print(f"[Gesture Service] Using venv Python: {venv_python}")
    
    # Set environment variable to enable streaming mode (no visible window)
    env = os.environ.copy()
    env['FULL_CONTROL_STREAMING'] = 'true'
    # Add backend directory to PYTHONPATH so it can find app.modules
    # The path needs to be the root directory (parent of backend)
    backend_root = os.path.join(os.path.dirname(__file__), "..", "..")
    backend_root = os.path.abspath(backend_root)
    # Also add the parent directory (Full control Final copy)
    project_root = os.path.dirname(backend_root)
    env['PYTHONPATH'] = backend_root + ':' + project_root + ':' + env.get('PYTHONPATH', '')
    
    print(f"[Gesture Service] PYTHONPATH: {env['PYTHONPATH']}")
    
    try:
        # Run the gesture streaming script (which updates frame buffer for frontend)
        process = subprocess.Popen(
            [venv_python, GESTURE_SCRIPT],
            cwd=work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
        
        # Start threads to read output
        output_thread = threading.Thread(target=read_process_output, args=(process, "Gesture"))
        output_thread.daemon = True
        output_thread.start()

        model_state.gesture_process = process
        model_state.gesture_running = True
        print("[Gesture Service] Gesture control started with video streaming")
        
        # Give it a moment to start and check for errors
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is not None:
            # Process has exited
            stdout, _ = process.communicate()
            error_msg = f"[Gesture Service] Gesture process exited unexpectedly. Output: {stdout}"
            print(error_msg)
            model_state.gesture_process = None
            model_state.gesture_running = False
            return f"Error starting gesture: {stdout[:200]}"
        
        return "Gesture started"
        
    except Exception as e:
        error_msg = f"[Gesture Service] ERROR starting gesture: {str(e)}"
        print(error_msg)
        return error_msg


def stop_gesture():

    if not model_state.gesture_running:
        return "Gesture not running"

    # Send termination signal
    try:
        model_state.gesture_process.terminate()
        # Give it a moment to terminate gracefully
        try:
            model_state.gesture_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            model_state.gesture_process.kill()
    except:
        pass
    
    model_state.gesture_process = None
    model_state.gesture_running = False
    
    # Clear the frame buffer
    frame_buffer.clear()
    print("[Gesture Service] Gesture control stopped")

    return "Gesture stopped"
