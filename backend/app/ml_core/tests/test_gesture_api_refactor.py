import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock


ML_CORE_DIR = Path(__file__).resolve().parents[1]
if str(ML_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(ML_CORE_DIR))


def _load_main_with_stubs():
    fake_np = types.ModuleType("numpy")
    fake_np.ndarray = object
    fake_np.mean = lambda *args, **kwargs: 0
    fake_np.argmax = lambda *args, **kwargs: 0

    fake_cv2 = types.ModuleType("cv2")
    fake_cv2.VideoCapture = lambda *args, **kwargs: None
    fake_cv2.WINDOW_AUTOSIZE = 0

    fake_tf = types.ModuleType("tensorflow")
    fake_tf.keras = types.SimpleNamespace()
    fake_pg = types.ModuleType("pyautogui")
    fake_pg.FAILSAFE = False
    fake_pg.scroll = lambda *args, **kwargs: None
    fake_pg.hotkey = lambda *args, **kwargs: None
    fake_pg.press = lambda *args, **kwargs: None
    fake_pg.click = lambda *args, **kwargs: None

    fake_dc = types.ModuleType("data_collector")

    class _DummyExtractor:
        def __init__(self, *args, **kwargs):
            self.last_landmarks = None

        def extract(self, _frame):
            return None

        def close(self):
            return None

    fake_dc.HandLandmarkExtractor = _DummyExtractor
    fake_dc.collect_gesture_samples = lambda *args, **kwargs: None

    fake_mt = types.ModuleType("model_trainer")
    fake_mt.train_model = lambda *args, **kwargs: None
    fake_mt.engineer_hand_features = lambda x: x
    fake_mt.load_feature_stats = lambda *args, **kwargs: (None, None)

    fake_sa = types.ModuleType("slm_agent")

    class _DummyAgent:
        def __init__(self, *args, **kwargs):
            pass

        def generate_python_script(self, *args, **kwargs):
            return "print('ok')"

    fake_sa.SLMCodeAgent = _DummyAgent

    stubs = {
        "cv2": fake_cv2,
        "numpy": fake_np,
        "tensorflow": fake_tf,
        "pyautogui": fake_pg,
        "data_collector": fake_dc,
        "model_trainer": fake_mt,
        "slm_agent": fake_sa,
    }

    with mock.patch.dict(sys.modules, stubs):
        main_path = ML_CORE_DIR / "gesture_control_api" / "main.py"
        spec = importlib.util.spec_from_file_location("gesture_main_stub", main_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module


class SlmAgentTests(unittest.TestCase):
    def test_requires_env_var_key(self):
        from gesture_control_api.slm_agent import SLMCodeAgent

        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                SLMCodeAgent()

        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "test_key"}, clear=True):
            agent = SLMCodeAgent()
            self.assertEqual(agent.api_key, "test_key")

    def test_platform_hint_reaches_prompt_payload(self):
        from gesture_control_api.slm_agent import SLMCodeAgent

        captured = {}

        class _DummyResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "print('ok')"}}]}

        def _fake_post(url, json, headers, timeout):
            captured["url"] = url
            captured["payload"] = json
            captured["headers"] = headers
            captured["timeout"] = timeout
            return _DummyResponse()

        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "test_key"}, clear=True):
            with mock.patch("gesture_control_api.slm_agent.requests.post", side_effect=_fake_post):
                agent = SLMCodeAgent()
                code = agent.generate_python_script(
                    action_description="Open browser",
                    gesture_name="wave",
                    target_platform="Linux",
                )

        self.assertEqual(code, "print('ok')")
        self.assertIn("Linux", captured["payload"]["messages"][0]["content"])


class MainRefactorTests(unittest.TestCase):
    def test_add_new_gesture_api_uses_shared_pipeline(self):
        main = _load_main_with_stubs()
        captured = {}

        def _fake_pipeline(gesture_name, action_description, cooldown, progress_callback=None):
            captured["gesture_name"] = gesture_name
            captured["action_description"] = action_description
            captured["cooldown"] = cooldown
            captured["has_callback"] = progress_callback is not None
            return {"status": "success"}

        main._run_add_new_gesture_pipeline = _fake_pipeline
        result = main.add_new_gesture_api("ok", "open app", progress_callback=lambda _s, _m: None)

        self.assertEqual(result["status"], "success")
        self.assertEqual(captured["gesture_name"], "ok")
        self.assertEqual(captured["action_description"], "open app")
        self.assertEqual(captured["cooldown"], main.COOLDOWN_MODERATE)
        self.assertTrue(captured["has_callback"])

    def test_row_count_uses_real_row_deltas(self):
        main = _load_main_with_stubs()

        with tempfile.TemporaryDirectory() as tmpdir:
            main.DATASET_DIR = tmpdir
            csv_path = Path(tmpdir) / "demo.csv"
            csv_path.write_text("f0,f1,label\n1,2,a\n3,4,a\n", encoding="utf-8")
            self.assertEqual(main._gesture_csv_row_count("demo"), 2)
            self.assertTrue(main._gesture_csv_has_data("demo"))

            csv_path.write_text("1,2,a\n", encoding="utf-8")
            self.assertEqual(main._gesture_csv_row_count("demo"), 1)

    def test_data_collector_source_no_machine_specific_default(self):
        source = (ML_CORE_DIR / "gesture_control_api" / "data_collector.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("/Users/mayankkumar", source)


class ServerJobTests(unittest.TestCase):
    def setUp(self):
        import server

        self.server = server
        with self.server.add_gesture_lock:
            self.server.add_gesture_jobs.clear()
            self.server.active_add_gesture_job_id = None

    def test_background_job_success_and_status_endpoint(self):
        fake_main = types.ModuleType("gesture_control_api.main")

        def _fake_add_new_gesture_api(gesture_name, description, progress_callback=None):
            if progress_callback:
                progress_callback("script_generation", "Generating script")
                progress_callback("data_collection", "Collecting data")
                progress_callback("training", "Training model")
            return {"status": "success", "message": f"{gesture_name} ready"}

        fake_main.add_new_gesture_api = _fake_add_new_gesture_api

        with mock.patch.dict(sys.modules, {"gesture_control_api.main": fake_main}):
            req = self.server.GestureRequest(name="ok", description="left click")
            queued = self.server.add_gesture(req)
            self.assertEqual(queued["status"], "queued")
            job_id = queued["job_id"]

            deadline = time.time() + 5
            final = None
            while time.time() < deadline:
                final = self.server.get_add_gesture_status(job_id)
                if final["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.05)

            self.assertIsNotNone(final)
            self.assertEqual(final["status"], "completed")
            self.assertEqual(final["stage"], "completed")

    def test_rejects_concurrent_add_gesture_jobs(self):
        fake_main = types.ModuleType("gesture_control_api.main")
        started = threading.Event()
        release = threading.Event()

        def _blocking_add_new_gesture_api(gesture_name, description, progress_callback=None):
            if progress_callback:
                progress_callback("script_generation", "Generating script")
            started.set()
            release.wait(timeout=3)
            if progress_callback:
                progress_callback("training", "Training model")
            return {"status": "success", "message": "done"}

        fake_main.add_new_gesture_api = _blocking_add_new_gesture_api

        with mock.patch.dict(sys.modules, {"gesture_control_api.main": fake_main}):
            first = self.server.add_gesture(
                self.server.GestureRequest(name="gesture_1", description="action")
            )
            self.assertEqual(first["status"], "queued")
            self.assertTrue(started.wait(timeout=1))

            second = self.server.add_gesture(
                self.server.GestureRequest(name="gesture_2", description="action")
            )
            self.assertEqual(second["status"], "rejected")
            self.assertEqual(second["reason"], "job_in_progress")

            release.set()

            deadline = time.time() + 5
            final = None
            while time.time() < deadline:
                final = self.server.get_add_gesture_status(first["job_id"])
                if final["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.05)
            self.assertEqual(final["status"], "completed")


if __name__ == "__main__":
    unittest.main()
