import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class RouterCommandTests(unittest.TestCase):
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
        model = models / "demo.Q4_K_M.gguf"
        model.write_bytes(b"demo")
        router_ini = root / "router.ini"
        router_ini.write_text(f"[demo]\nmodel = {model}\nctx-size = 4096\n", encoding="utf-8")
        config = root / "modelctl.ini"
        registry = root / "modelctl.yaml"
        setup = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
        with config.open("a", encoding="utf-8") as fh:
            fh.write("\n[router.services]\n8080 = llama-cuda.service\ncuda = llama-cuda.service\nvulkan = llama-vulkan.service\ncpu = llama-cpu.service\n")
            fh.write("\n[monitor.ports]\n8080 = llama-cuda.service\n8081 = llama-vulkan.service\n8082 = llama-cpu.service\n")
        return root, router_ini, config

    def fake_bin(self, td: str):
        bin_dir = Path(td) / "bin"
        bin_dir.mkdir()
        log = Path(td) / "commands.log"
        for name in ("journalctl", "systemctl", "sudo"):
            if os.name == "nt":
                shim = bin_dir / f"{name}.bat"
                shim.write_text(
                    "@echo off\r\n"
                    f"echo {name}:%* >> \"{log}\"\r\n"
                    "if \"%1\"==\"is-active\" echo active& exit /b 0\r\n"
                    "echo output:%*\r\n",
                    encoding="utf-8",
                )
            else:
                shim = bin_dir / name
                shim.write_text(
                    "#!/bin/sh\n"
                    f"echo {name}:$@ >> {log}\n"
                    "if [ \"$1\" = \"is-active\" ]; then echo active; exit 0; fi\n"
                    "echo output:$@\n",
                    encoding="utf-8",
                )
                shim.chmod(0o755)
        return bin_dir, log

    def test_router_help_wraps_systemd_service_shortcuts(self):
        result = self.run_modelctl("router", "-h")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("router logs cuda", result.stdout)
        self.assertNotIn("router logs cuda --follow", result.stdout)
        self.assertIn("router restart vulkan", result.stdout)
        self.assertIn("router reset cuda", result.stdout)
        self.assertIn("router start cpu", result.stdout)
        self.assertNotIn("router reload", result.stdout)

    def test_router_status_and_command_are_config_driven_json_friendly(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config = self.make_fixture(td)
            bin_dir, _log = self.fake_bin(td)
            env = {"PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")}

            status = self.run_modelctl("--config", str(config), "router", "status", "cuda", "--json", env=env)
            self.assertEqual(status.returncode, 0, status.stderr + status.stdout)
            payload = json.loads(status.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["data"]["service"], "llama-cuda.service")
            self.assertEqual(payload["data"]["backend"], "systemd")
            self.assertEqual(payload["data"]["systemctl_state"], "active")

            command = self.run_modelctl("--config", str(config), "router", "command", "logs", "8080", "--json", env=env)
            self.assertEqual(command.returncode, 0, command.stderr + command.stdout)
            payload = json.loads(command.stdout)
            self.assertEqual(payload["data"]["command"], ["journalctl", "-u", "llama-cuda.service", "-f"])
            self.assertTrue(payload["data"]["read_only"])

            recent = self.run_modelctl("--config", str(config), "router", "logs", "cuda", "--no-follow", "--lines", "12", "--json", env=env)
            self.assertEqual(recent.returncode, 0, recent.stderr + recent.stdout)
            payload = json.loads(recent.stdout)
            self.assertEqual(payload["data"]["command"], ["journalctl", "-u", "llama-cuda.service", "-n", "12", "--no-pager", "-o", "cat"])
            self.assertFalse(payload["data"]["follow"])

    def test_router_logs_and_lifecycle_wrap_expected_commands(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config = self.make_fixture(td)
            bin_dir, log = self.fake_bin(td)
            env = {"PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")}

            logs = self.run_modelctl("--config", str(config), "router", "logs", "vulkan", env=env)
            self.assertEqual(logs.returncode, 0, logs.stderr + logs.stdout)
            self.assertIn("journalctl -u llama-vulkan.service -f", logs.stdout)

            restart = self.run_modelctl("--config", str(config), "router", "restart", "cpu", env=env)
            self.assertEqual(restart.returncode, 0, restart.stderr + restart.stdout)
            reset = self.run_modelctl("--config", str(config), "router", "reset-failed", "cuda", env=env)
            self.assertEqual(reset.returncode, 0, reset.stderr + reset.stdout)
            start = self.run_modelctl("--config", str(config), "router", "start", "8080", env=env)
            self.assertEqual(start.returncode, 0, start.stderr + start.stdout)

            recorded = log.read_text(encoding="utf-8")
            self.assertIn("journalctl:-u llama-vulkan.service -f", recorded)
            self.assertIn("sudo:systemctl restart llama-cpu.service", recorded)
            self.assertIn("sudo:systemctl reset-failed llama-cuda.service", recorded)
            self.assertIn("sudo:systemctl start llama-cuda.service", recorded)


    def test_router_reset_shorthand_aliases_reset_failed(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config = self.make_fixture(td)

            shorthand = self.run_modelctl("--config", str(config), "router", "reset", "cuda", "--dry-run", "--json")
            explicit = self.run_modelctl("--config", str(config), "router", "reset-failed", "cuda", "--dry-run", "--json")

            self.assertEqual(shorthand.returncode, 0, shorthand.stderr + shorthand.stdout)
            self.assertEqual(explicit.returncode, 0, explicit.stderr + explicit.stdout)
            shorthand_payload = json.loads(shorthand.stdout)
            explicit_payload = json.loads(explicit.stdout)
            self.assertEqual(shorthand_payload["data"]["action"], "reset-failed")
            self.assertEqual(shorthand_payload["data"]["command"], explicit_payload["data"]["command"])
            self.assertEqual(shorthand_payload["data"]["command"], ["sudo", "systemctl", "reset-failed", "llama-cuda.service"])

    def test_router_unknown_service_fails_actionably_without_guessing(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config = self.make_fixture(td)

            result = self.run_modelctl("--config", str(config), "router", "logs", "gpu9")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown router service target", result.stderr)
            self.assertIn("configured targets", result.stderr)
            self.assertIn("cuda", result.stderr)


if __name__ == "__main__":
    unittest.main()
