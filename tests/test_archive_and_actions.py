import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class ArchiveAndActionListTests(unittest.TestCase):
    def run_modelctl(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_list_includes_archive_models_and_status_column(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            models = root / "models"
            archive = models / "archive"
            archive.mkdir(parents=True)
            active = models / "active.gguf"
            unused = models / "unused-old.gguf"
            archived = archive / "archived-old.gguf"
            active.write_bytes(b"active")
            unused.write_bytes(b"unused")
            archived.write_bytes(b"archived")
            router_ini = root / "router.ini"
            router_ini.write_text(
                f"""
[active-alias]
model = {active}
ctx-size = 4096
""".lstrip(),
                encoding="utf-8",
            )
            config = root / "modelctl.ini"
            registry = root / "modelctl.yaml"

            setup = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry), )
            self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)

            result = self.run_modelctl("--config", str(config), "list")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("STATUS", result.stdout)
            self.assertIn("active", result.stdout)
            self.assertIn("archived", result.stdout)
            self.assertIn(str(active), result.stdout)
            self.assertIn(str(unused), result.stdout)
            self.assertIn(str(archived), result.stdout)
            self.assertIn("archived", result.stdout)

    def test_show_archived_model_explains_it_is_not_active(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            models = root / "models"
            archive = models / "archive"
            archive.mkdir(parents=True)
            active = models / "active.gguf"
            archived = archive / "archived-old.gguf"
            active.write_bytes(b"active")
            archived.write_bytes(b"archived")
            router_ini = root / "router.ini"
            router_ini.write_text(f"[active]\nmodel = {active}\n", encoding="utf-8")
            config = root / "modelctl.ini"
            registry = root / "modelctl.yaml"
            setup = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry), )
            self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)

            result = self.run_modelctl("--config", str(config), "show", archived.name)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(str(archived), result.stdout)
            self.assertIn("location: archived", result.stdout)
            self.assertIn("status: archived/present", result.stdout)
            self.assertIn("aliases: 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
