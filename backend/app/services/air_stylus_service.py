import subprocess
import sys
import os
import time
import threading
from app.services.model_state import model_state
from app.services.frame_buffer import frame_buffer

# Get the absolute path to the air stylus streaming script
AIRSTYLUS_SCRIPT = os.path.join(
    os.path.dirname(__file__),  # backend/app/services/
    "..",                       # backend/app/
    "ml_core",                  # backend/app/ml_core/
    "run_airstylus_stream.py"   # runs air stylus with frame streaming
)
AIRSTYLUS_SCRIPT = os.path.abspath(AIRSTYLUS_SCRIPT)

# Thread to read subprocess output
def read_process_output(process, prefix):
    try:
        for line in process.stdout:
            print(f"[{prefix}] {line.strip()}")
        for line in process.stderr:
            print(f"[{prefix} ERROR] {line.strip()}")
    except:
        pass


def start_air_stylus():
    if model_state.air_stylus_running:
        return "Air Stylus already running"

    # Stop gesture if running
    if model_state.gesture_running:
        model_state.gesture_process.terminate()
        try:
            model_state.gesture_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            model_state.gesture_process.kill()
        model_state.gesture_process = None
        model_state.gesture_running = False

    # Get the working directory
    work_dir = os.path.join(os.path.dirname(__file__), "..", "ml_core")
    work_dir = os.path.abspath(work_dir)
    
    print(f"[Air Stylus Service] Starting Air Stylus from: {AIRSTYLUS_SCRIPT}")
    print(f"[Air Stylus Service] Working directory: {work_dir}")
    
    # Check if script exists
    if not os.path.exists(AIRSTYLUS_SCRIPT):
        error_msg = f"[Air Stylus Service] ERROR: Script not found at {AIRSTYLUS_SCRIPT}"
        print(error_msg)
        return error_msg
    
    # Get the python interpreter from the venv
    venv_python = os.path.join(os.path.dirname(__file__), "..", "..", "venv", "bin", "python")
    venv_python = os.path.abspath(venv_python)
    
    # Check if venv python exists
    if not os.path.exists(venv_python):
        # Try system python
        venv_python = sys.executable
        print(f"[Air Stylus Service] Using system Python: {venv_python}")
    else:
        print(f"[Air Stylus Service] Using venv Python: {venv_python}")
    
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
    
    print(f"[Air Stylus Service] PYTHONPATH: {env['PYTHONPATH']}")
    
    try:
        # Run the air stylus streaming script (which updates frame buffer for frontend)
        process = subprocess.Popen(
            [venv_python, AIRSTYLUS_SCRIPT],
            cwd=work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
        
        # Start threads to read output
        output_thread = threading.Thread(target=read_process_output, args=(process, "AirStylus"))
        output_thread.daemon = True
        output_thread.start()

        model_state.air_stylus_process = process
        model_state.air_stylus_running = True
        print("[Air Stylus Service] Air Stylus started with video streaming")
        
        # Give it a moment to start and check for errors
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is not None:
            # Process has exited
            stdout, _ = process.communicate()
            error_msg = f"[Air Stylus Service] Air Stylus process exited unexpectedly. Output: {stdout}"
            print(error_msg)
            model_state.air_stylus_process = None
            model_state.air_stylus_running = False
            return f"Error starting air stylus: {stdout[:200]}"
        
        return "Air Stylus started"
        
    except Exception as e:
        error_msg = f"[Air Stylus Service] ERROR starting air stylus: {str(e)}"
        print(error_msg)
        return error_msg


def stop_air_stylus():
    if not model_state.air_stylus_running:
        return "Air Stylus not running"

    # Send termination signal
    try:
        model_state.air_stylus_process.terminate()
        # Give it a moment to terminate gracefully
        try:
            model_state.air_stylus_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            model_state.air_stylus_process.kill()
    except:
        pass
    
    model_state.air_stylus_process = None
    model_state.air_stylus_running = False
    
    # Clear the frame buffer
    frame_buffer.clear()
    print("[Air Stylus Service] Air Stylus stopped")

    return "Air Stylus stopped"
