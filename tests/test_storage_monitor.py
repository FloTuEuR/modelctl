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


if __name__ == "__main__":
    unittest.main()
