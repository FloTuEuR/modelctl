import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class ModelUxRequirementsTests(unittest.TestCase):
    def run_modelctl(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def make_fixture(self, td: str):
        root = Path(td)
        models = root / "models"
        models.mkdir()
        active = models / "demo-7b.Q4_K_M.gguf"
        inactive = models / "inactive-7b.Q4_K_M.gguf"
        active.write_bytes(b"x" * 1024)
        inactive.write_bytes(b"y" * 2048)
        ini = root / "models.ini"
        ini.write_text(
            f"""
[demo]
model = {active}
ctx-size = 4096

# [inactive]
# model = {inactive}
# ctx-size = 2048
""".lstrip(),
            encoding="utf-8",
        )
        config = root / "modelctl.ini"
        registry = root / "modelctl.yaml"
        setup = self.run_modelctl("setup", str(ini), "--config", str(config), "--registry", str(registry))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
        return root, models, active, inactive, ini, config

    def test_list_uses_status_not_action_and_explains_present_enabled_state(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, active, inactive, _ini, config = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "list")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("STATUS", result.stdout)
            self.assertNotIn("ACTION", result.stdout)
            self.assertIn("active", result.stdout)
            self.assertIn("enabled", result.stdout)
            self.assertIn("present", result.stdout)
            self.assertIn(str(active), result.stdout)
            self.assertIn(str(inactive), result.stdout)

    def test_plain_numeric_model_id_works_for_show_aliases_and_delete_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, active, _inactive, _ini, config = self.make_fixture(td)
            show = self.run_modelctl("--config", str(config), "show", "1")
            aliases = self.run_modelctl("--config", str(config), "aliases", "1")
            delete = self.run_modelctl("--config", str(config), "delete", "1", "--dry-run")
            for result in [show, aliases, delete]:
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertIn(str(active), result.stdout)
            self.assertIn("demo", aliases.stdout)
            self.assertIn("No files or ini entries were changed", delete.stdout)

    def test_show_includes_capacity_speed_update_and_settings_guidance_placeholders(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, _active, _inactive, _ini, config = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "show", "1")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            for snippet in [
                "minimum vram",
                "average speed",
                "estimated max context",
                "estimated gpu layers",
                "hugging face update",
                "settings recommendation",
            ]:
                self.assertIn(snippet, result.stdout.lower())

    def test_new_operational_commands_are_discoverable(self):
        commands = {
            "update-check": ["Hugging Face", "update"],
            "enable": ["enable", "ini"],
            "disable": ["disable", "ini"],
            "add-entry": ["entry", "estimated"],
            "benchmark": ["llama.cpp", "settings"],
            "rules": ["outcomes", "20+ t/s", "128k"],
        }
        for command, snippets in commands.items():
            with self.subTest(command=command):
                result = self.run_modelctl(command, "-h")
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                combined = result.stdout + result.stderr
                for snippet in snippets:
                    self.assertIn(snippet, combined)


if __name__ == "__main__":
    unittest.main()
