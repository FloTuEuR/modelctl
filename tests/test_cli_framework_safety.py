import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class CliFrameworkSafetyTests(unittest.TestCase):
    def make_fixture(self, td: str):
        root = Path(td)
        models = root / "models"
        models.mkdir()
        shared = models / "shared-model.Q4_K_M.gguf"
        solo = models / "solo-model.Q8_0.gguf"
        shared.write_bytes(b"shared")
        solo.write_bytes(b"solo")
        router_ini = root / "router.ini"
        original_ini = f"""
[alpha]
model = {shared}
ctx-size = 4096

[models.beta]
model = {shared}
ctx-size = 8192

# [disabled.gamma]
# model = {solo}
# ctx-size = 2048
""".lstrip()
        router_ini.write_text(original_ini, encoding="utf-8")
        return root, router_ini, original_ini, shared, solo

    def run_modelctl(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=cwd or ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_setup_imports_existing_ini_to_minimal_config_and_registry_without_touching_ini(self):
        with tempfile.TemporaryDirectory() as td:
            root, router_ini, original_ini, shared, _solo = self.make_fixture(td)
            config = root / "modelctl.ini"
            registry = root / "modelctl.yaml"

            result = self.run_modelctl(
                "setup",
                "--ini",
                str(router_ini),
                "--config",
                str(config),
                "--registry",
                str(registry),
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("aliases: 3", result.stdout)
            self.assertTrue(config.exists())
            self.assertTrue(registry.exists())
            self.assertEqual(router_ini.read_text(encoding="utf-8"), original_ini)
            self.assertTrue(shared.exists())

            registry_text = registry.read_text(encoding="utf-8")
            self.assertIn(f"router_ini: {router_ini}", registry_text)
            self.assertIn("section: alpha", registry_text)
            self.assertIn("section: models.beta", registry_text)
            self.assertIn("section: disabled.gamma", registry_text)

    def test_list_and_delete_are_safe_by_default_and_do_not_modify_files(self):
        with tempfile.TemporaryDirectory() as td:
            root, router_ini, original_ini, shared, solo = self.make_fixture(td)
            config = root / "modelctl.ini"
            registry = root / "modelctl.yaml"
            setup = self.run_modelctl(
                "setup", "--ini", str(router_ini), "--config", str(config), "--registry", str(registry)
            )
            self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)

            listing = self.run_modelctl("--config", str(config), "list")
            self.assertEqual(listing.returncode, 0, listing.stderr + listing.stdout)
            self.assertIn("alpha", listing.stdout)
            self.assertIn("models.beta", listing.stdout)
            self.assertIn("disabled.gamma", listing.stdout)

            delete_plan = self.run_modelctl("--config", str(config), "delete", f"path:{shared}", "--dry-run")
            self.assertEqual(delete_plan.returncode, 0, delete_plan.stderr + delete_plan.stdout)
            self.assertIn("DRY RUN", delete_plan.stdout)
            self.assertIn("multiple aliases", delete_plan.stdout)
            self.assertIn("alpha", delete_plan.stdout)
            self.assertIn("models.beta", delete_plan.stdout)

            self.assertEqual(router_ini.read_text(encoding="utf-8"), original_ini)
            self.assertTrue(shared.exists())
            self.assertTrue(solo.exists())


if __name__ == "__main__":
    unittest.main()
