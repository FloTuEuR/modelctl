import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class StorageMonitorTests(unittest.TestCase):
    def run_modelctl(self, *args, env=None):
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=run_env,
        )

    def make_fixture(self, td: str):
        root = Path(td)
        models = root / "models"
        models.mkdir()
        doomed = models / "doomed.Q4_K_M.gguf"
        doomed.write_bytes(b"doomed")
        router_ini = root / "router.ini"
        router_ini.write_text(f"[doomed]\nmodel = {doomed}\nctx-size = 4096\n", encoding="utf-8")
        config = root / "config" / "modelctl.ini"
        registry = root / "data" / "modelctl.yaml"
        setup = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
        return root, router_ini, config, doomed

    def test_delete_uses_modelctl_state_recovery_directory_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root, _router_ini, config, doomed = self.make_fixture(td)
            state_dir = root / "xdg-state" / "modelctl"

            result = self.run_modelctl(
                "--config", str(config), "delete", f"path:{doomed}", "--apply", env={"MODELCTL_STATE_DIR": str(state_dir)}
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            manifests = sorted((state_dir / "recovery").glob("delete-*.json"))
            self.assertEqual(len(manifests), 1)
            self.assertIn(str(state_dir / "recovery"), result.stdout)
            self.assertFalse((config.parent / "recovery").exists())

    def test_doctor_exposes_modelctl_owned_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root, _router_ini, config, _doomed = self.make_fixture(td)
            state_dir = root / "state" / "modelctl"
            data_dir = root / "data" / "modelctl"
            cache_dir = root / "cache" / "modelctl"

            result = self.run_modelctl(
                "--config", str(config), "doctor",
                env={"MODELCTL_STATE_DIR": str(state_dir), "MODELCTL_DATA_DIR": str(data_dir), "MODELCTL_CACHE_DIR": str(cache_dir)},
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(f"state dir: {state_dir}", result.stdout)
            self.assertIn(f"data dir: {data_dir}", result.stdout)
            self.assertIn(f"cache dir: {cache_dir}", result.stdout)
            self.assertIn(f"recovery dir: {state_dir / 'recovery'}", result.stdout)
            self.assertIn(f"benchmark dir: {data_dir / 'benchmarks'}", result.stdout)

    def test_monitor_none_backend_fails_clearly_without_mutating_files(self):
        with tempfile.TemporaryDirectory() as td:
            root, router_ini, config, _doomed = self.make_fixture(td)
            before = router_ini.read_text(encoding="utf-8")

            result = self.run_modelctl("--config", str(config), "monitor", "router")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("monitor backend is not configured", result.stderr)
            self.assertIn("modelctl monitor discover", result.stderr)
            self.assertEqual(router_ini.read_text(encoding="utf-8"), before)
            self.assertEqual(sorted(root.glob("*")), sorted(root.glob("*")))

    def test_monitor_none_backend_json_includes_discovery_guidance(self):
        with tempfile.TemporaryDirectory() as td:
            root, router_ini, config, _doomed = self.make_fixture(td)
            before = router_ini.read_text(encoding="utf-8")

            result = self.run_modelctl("--config", str(config), "monitor", "router", "--json")

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["command"], "monitor")
            self.assertEqual(payload["error"]["code"], "monitor_failed")
            data = payload["data"]
            self.assertEqual(data["status"], "unconfigured")
            self.assertIn("modelctl monitor discover", data["suggested_commands"])
            self.assertTrue(any("endpoint/log details" in step for step in data["next_steps"]))
            self.assertEqual(router_ini.read_text(encoding="utf-8"), before)
            self.assertEqual(sorted(root.glob("*")), sorted(root.glob("*")))

    def test_monitor_file_backend_reads_configured_log_and_lines(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _doomed = self.make_fixture(td)
            log_file = Path(td) / "router.log"
            log_file.write_text("one\ntwo\nthree\n", encoding="utf-8")
            with config.open("a", encoding="utf-8") as fh:
                fh.write(f"\n[monitor]\nbackend = file\nlog_file = {log_file}\n")

            result = self.run_modelctl("--config", str(config), "monitor", "router", "--lines", "2")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("backend: file", result.stdout)
            self.assertNotIn("one", result.stdout)
            self.assertIn("two", result.stdout)
            self.assertIn("three", result.stdout)

    def test_monitor_json_output_reports_metadata_and_log_lines(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _doomed = self.make_fixture(td)
            log_file = Path(td) / "router.log"
            log_file.write_text("alpha\nbeta\n", encoding="utf-8")
            with config.open("a", encoding="utf-8") as fh:
                fh.write(f"\n[monitor]\nbackend = file\nlog_file = {log_file}\n")

            result = self.run_modelctl("--config", str(config), "monitor", "router", "--lines", "1", "--json")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["command"], "monitor")
            self.assertEqual(payload["warnings"], [])
            self.assertIsNone(payload["error"])
            data = payload["data"]
            self.assertEqual(data["backend"], "file")
            self.assertEqual(data["target"], "router")
            self.assertFalse(data["follow"])
            self.assertEqual(data["lines_requested"], 1)
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["lines"], ["beta"])


class _ModelsHandler:
    def __init__(self, model_ids):
        self.model_ids = model_ids
        self.requests = []

    def handler(self):
        import json
        from http.server import BaseHTTPRequestHandler
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests.append(self.path)
                if self.path == "/v1/models":
                    raw = json.dumps({"data": [{"id": m} for m in outer.model_ids]}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, _format, *args):
                return

        return Handler


class MonitorDiscoveryTests(StorageMonitorTests):
    def _server(self, model_ids):
        from http.server import ThreadingHTTPServer
        import threading
        handler = _ModelsHandler(model_ids)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler.handler())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return f"http://127.0.0.1:{server.server_port}/v1", handler

    def test_monitor_discover_json_reports_no_endpoint_reachable_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root, router_ini, config, _doomed = self.make_fixture(td)
            before = router_ini.read_text(encoding="utf-8")
            with config.open("a", encoding="utf-8") as fh:
                fh.write("\n[monitor]\ndiscovery_timeout = 0.05\ndiscover_defaults = false\nendpoints = http://127.0.0.1:9/v1\n")
            result = self.run_modelctl("--config", str(config), "monitor", "discover", "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["command"], "monitor discover")
            self.assertEqual(payload["data"]["found_count"], 0)
            self.assertIsNone(payload["data"]["selected"])
            self.assertFalse(payload["data"]["mutated"])
            self.assertTrue(payload["warnings"])
            self.assertEqual(router_ini.read_text(encoding="utf-8"), before)
            self.assertFalse((root / "plans").exists())

    def test_monitor_discover_json_reports_one_endpoint_selected(self):
        endpoint, handler = self._server(["alpha", "beta"])
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _doomed = self.make_fixture(td)
            with config.open("a", encoding="utf-8") as fh:
                fh.write(f"\n[monitor]\nendpoint = {endpoint}\ndiscovery_timeout = 0.2\ndiscover_defaults = false\n")
            result = self.run_modelctl("--config", str(config), "monitor", "discover", "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["data"]["found_count"], 1)
            self.assertEqual(payload["data"]["selected"], endpoint)
            candidate = next(c for c in payload["data"]["candidates"] if c["endpoint"] == endpoint)
            self.assertTrue(candidate["reachable"])
            self.assertEqual(candidate["models_endpoint"], f"{endpoint}/models")
            self.assertEqual(candidate["model_ids"], ["alpha", "beta"])
            self.assertEqual(candidate["source"], "configured")
            self.assertIn("/v1/models", handler.requests)

    def test_monitor_discover_human_reports_multiple_endpoints(self):
        endpoint1, _handler1 = self._server(["alpha"])
        endpoint2, _handler2 = self._server(["beta"])
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _doomed = self.make_fixture(td)
            with config.open("a", encoding="utf-8") as fh:
                fh.write(f"\n[monitor]\nendpoints = {endpoint1}, {endpoint2}\ndiscovery_timeout = 0.2\ndiscover_defaults = false\n")
            result = self.run_modelctl("--config", str(config), "monitor", "discover")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Monitor discovery (read-only)", result.stdout)
            self.assertIn("found count: 2", result.stdout)
            self.assertIn("multiple servers found", result.stdout)
            self.assertIn(endpoint1, result.stdout)
            self.assertIn(endpoint2, result.stdout)
            self.assertIn("model ids: alpha", result.stdout)
            self.assertIn("model ids: beta", result.stdout)

    def test_monitor_router_behavior_still_works_after_discovery_addition(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _doomed = self.make_fixture(td)
            log_file = Path(td) / "router.log"
            log_file.write_text("one\ntwo\n", encoding="utf-8")
            with config.open("a", encoding="utf-8") as fh:
                fh.write(f"\n[monitor]\nbackend = file\nlog_file = {log_file}\n")
            result = self.run_modelctl("--config", str(config), "monitor", "router", "--lines", "1")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("backend: file", result.stdout)
            self.assertIn("two", result.stdout)
            self.assertNotIn("one", result.stdout)


if __name__ == "__main__":
    unittest.main()
