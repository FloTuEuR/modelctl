"""Focused tests for stable JSON output envelopes."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class JsonOutputSchemasTests(unittest.TestCase):
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

    def make_fixture(self, td: str, monitor: str = "none"):
        root = Path(td)
        models = root / "models"
        models.mkdir()
        model = models / "sample.Q4_K_M.gguf"
        model.write_bytes(b"sample")
        router_ini = root / "router.ini"
        router_ini.write_text(f"[sample]\nmodel = {model}\nctx-size = 4096\n", encoding="utf-8")
        config = root / "config" / "modelctl.ini"
        config.parent.mkdir()
        config.write_text(
            f"[router]\nini = {router_ini}\n"
            f"[models]\ndownload_dir = {models}\n"
            f"[monitor]\nbackend = {monitor}\n",
            encoding="utf-8",
        )
        registry = root / "data" / "modelctl.yaml"
        setup = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
        return root, router_ini, config, registry

    def assert_envelope(self, payload, command, status="ok"):
        self.assertEqual(set(payload), {"status", "command", "data", "warnings", "error"})
        self.assertEqual(payload["status"], status)
        self.assertEqual(payload["command"], command)
        self.assertIsInstance(payload["data"], dict)
        self.assertIsInstance(payload["warnings"], list)

    def test_list_json_envelope_has_deterministic_core_fields(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "list", "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "list")
            self.assertIsNone(payload["error"])
            self.assertEqual(len(payload["data"]["models"]), 1)
            model = payload["data"]["models"][0]
            self.assertEqual(set(model), {"id", "path", "state", "location", "size_bytes", "aliases"})
            self.assertEqual(model["id"], 1)
            self.assertEqual(model["location"], "active")
            self.assertEqual(len(payload["data"]["aliases"]), 1)
            alias = payload["data"]["aliases"][0]
            self.assertEqual(set(alias), {"id", "section", "enabled", "model_path"})
            self.assertEqual(alias["id"], "a1")
            self.assertEqual(alias["section"], "sample")

    def test_doctor_json_envelope_reports_paths_and_checks(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "doctor", "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "doctor")
            self.assertIsNone(payload["error"])
            self.assertIn("checks", payload["data"])
            self.assertIn("paths", payload["data"])
            self.assertIn("safety", payload["data"])
            self.assertIn("recovery_dir", payload["data"]["paths"])
            self.assertIn("benchmark_dir", payload["data"]["paths"])

    def test_doctor_json_error_envelope_when_router_ini_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config" / "modelctl.ini"
            config.parent.mkdir()
            config.write_text(f"[router]\nini = {root / 'missing.ini'}\n[models]\ndownload_dir = {root / 'models'}\n", encoding="utf-8")
            result = self.run_modelctl("--config", str(config), "doctor", "--json")
            self.assertNotEqual(result.returncode, 0)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "doctor", status="error")
            self.assertEqual(payload["error"]["code"], "doctor_failed")

    def test_monitor_json_envelope_for_none_backend_error(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "monitor", "--json")
            self.assertNotEqual(result.returncode, 0)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "monitor", status="error")
            self.assertEqual(payload["error"]["code"], "monitor_failed")
            self.assertEqual(payload["data"]["backend"], "none")
            self.assertEqual(payload["data"]["target"], "router")

    def test_monitor_json_envelope_for_file_backend_lines(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            log_file = Path(td) / "router.log"
            log_file.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
            config.write_text(
                config.read_text(encoding="utf-8") + f"\n[monitor]\nbackend = file\nlog_file = {log_file}\n",
                encoding="utf-8",
            )
            result = self.run_modelctl("--config", str(config), "monitor", "router", "--json", "--lines", "2")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "monitor")
            self.assertIsNone(payload["error"])
            self.assertEqual(payload["data"]["backend"], "file")
            self.assertEqual(payload["data"]["target"], "router")
            self.assertEqual(payload["data"]["lines_requested"], 2)
            self.assertEqual(payload["data"]["lines"], ["beta", "gamma"])

    def test_human_list_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "list")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Models", result.stdout)
            self.assertIn("Aliases", result.stdout)
            self.assertNotIn('"status"', result.stdout)


if __name__ == "__main__":
    unittest.main()
