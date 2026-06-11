import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class CliUserExperienceTests(unittest.TestCase):
    def make_fixture(self, td: str):
        root = Path(td)
        models = root / "models"
        models.mkdir()
        shared = models / "shared-model.Q4_K_M.gguf"
        solo = models / "solo-model.Q8_0.gguf"
        shared.write_bytes(b"shared")
        solo.write_bytes(b"solo")
        router_ini = root / "router.ini"
        router_ini.write_text(
            f"""
[alpha]
model = {shared}
ctx-size = 4096

[models.beta]
model = {shared}
ctx-size = 8192

# [disabled.gamma]
# model = {solo}
# ctx-size = 2048
""".lstrip(),
            encoding="utf-8",
        )
        return root, router_ini, shared, solo

    def run_modelctl(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_setup_with_direct_path_writes_config_without_extra_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            root, router_ini, _shared, _solo = self.make_fixture(td)
            config = root / "modelctl.ini"

            registry = root / "modelctl.yaml"
            result = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry))

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("aliases: 3", result.stdout)
            self.assertIn("Next:", result.stdout)
            self.assertIn("Setup written safely", result.stdout)
            self.assertTrue(config.exists())
            self.assertTrue(registry.exists())

    def test_setup_without_path_runs_wizard_and_writes_config_after_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            root, router_ini, _shared, _solo = self.make_fixture(td)
            config = root / "modelctl.ini"
            registry = root / "modelctl.yaml"

            result = self.run_modelctl(
                "setup",
                "--config",
                str(config),
                "--registry",
                str(registry),
                input_text=f"{router_ini}\n\n",
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Path to llama.cpp router models.ini", result.stdout)
            self.assertIn("Setup written safely", result.stdout)
            self.assertIn("Next:", result.stdout)
            self.assertIn("modelctl doctor", result.stdout)
            self.assertIn("modelctl list", result.stdout)
            self.assertNotIn("--config", result.stdout)
            self.assertTrue(config.exists())
            self.assertTrue(registry.exists())

    def test_doctor_show_and_aliases_make_common_discovery_easy(self):
        with tempfile.TemporaryDirectory() as td:
            root, router_ini, shared, _solo = self.make_fixture(td)
            config = root / "modelctl.ini"
            registry = root / "modelctl.yaml"
            setup = self.run_modelctl(
                "setup", str(router_ini), "--config", str(config), "--registry", str(registry)
            )
            self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)

            doctor = self.run_modelctl("--config", str(config), "doctor")
            self.assertEqual(doctor.returncode, 0, doctor.stderr + doctor.stdout)
            self.assertIn("OK router ini readable", doctor.stdout)
            self.assertIn("OK aliases detected: 3", doctor.stdout)
            self.assertIn("OK registry writable", doctor.stdout)

            show = self.run_modelctl("--config", str(config), "show", "1")
            self.assertEqual(show.returncode, 0, show.stderr + show.stdout)
            self.assertIn(str(shared), show.stdout)
            self.assertIn("alpha", show.stdout)
            self.assertIn("models.beta", show.stdout)

            aliases = self.run_modelctl("--config", str(config), "aliases", "1")
            self.assertEqual(aliases.returncode, 0, aliases.stderr + aliases.stdout)
            self.assertIn("alpha", aliases.stdout)
            self.assertIn("models.beta", aliases.stdout)

    def test_missing_config_error_is_actionable(self):
        with tempfile.TemporaryDirectory() as td:
            missing_config = Path(td) / "missing.ini"
            result = self.run_modelctl("--config", str(missing_config), "list")

            self.assertNotEqual(result.returncode, 0)
            combined = result.stderr + result.stdout
            self.assertIn("Run:", combined)
            self.assertIn("modelctl setup", combined)


if __name__ == "__main__":
    unittest.main()
