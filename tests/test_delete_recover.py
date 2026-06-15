import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class DeleteRecoverTests(unittest.TestCase):
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

    def make_fixture(self, td: str):
        root = Path(td)
        models = root / "models"
        models.mkdir()
        doomed = models / "doomed-model.Q4_K_M.gguf"
        keeper = models / "keeper-model.Q4_K_M.gguf"
        doomed.write_bytes(b"doomed")
        keeper.write_bytes(b"keeper")
        router_ini = root / "router.ini"
        original = f"""
# production note
[delete-me]
model = {doomed}
ctx-size = 4096
n-gpu-layers = 99

[keep-me]
model = {keeper}
ctx-size = 8192
""".lstrip()
        router_ini.write_text(original, encoding="utf-8")
        config = root / "modelctl.ini"
        registry = root / "modelctl.yaml"
        setup = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
        return root, models, router_ini, original, config, doomed, keeper

    def recovery_manifests(self, config: Path):
        return sorted((config.parent / "recovery").glob("delete-*.json"))

    def test_delete_requires_confirmation_or_apply(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, router_ini, original, config, doomed, _keeper = self.make_fixture(td)

            result = self.run_modelctl("--config", str(config), "delete", f"path:{doomed}", input_text="delete wrong\n")

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(doomed.exists())
            self.assertEqual(router_ini.read_text(encoding="utf-8"), original)
            self.assertEqual(self.recovery_manifests(config), [])

    def test_delete_apply_writes_focused_recovery_manifest_before_removing_model(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, router_ini, _original, config, doomed, keeper = self.make_fixture(td)

            result = self.run_modelctl("--config", str(config), "delete", f"path:{doomed}", "--apply")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            manifests = self.recovery_manifests(config)
            self.assertEqual(len(manifests), 1)
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            self.assertEqual(manifest["action"], "recover_deleted_model")
            self.assertEqual(manifest["deleted_model_path"], str(doomed))
            self.assertEqual(manifest["model_filename"], doomed.name)
            self.assertEqual(manifest["model_size_bytes"], len(b"doomed"))
            self.assertIn("model_sha256", manifest)
            self.assertEqual([a["section"] for a in manifest["affected_aliases"]], ["delete-me"])
            self.assertEqual([s["section"] for s in manifest["affected_sections"]], ["delete-me"])
            combined_manifest_text = json.dumps(manifest)
            self.assertIn("delete-me", combined_manifest_text)
            self.assertNotIn("keep-me", combined_manifest_text)
            self.assertNotIn("production note", combined_manifest_text)
            self.assertNotIn("router_ini_backup", manifest)
            self.assertNotIn("original_ini_text", manifest)
            self.assertFalse(doomed.exists())
            self.assertTrue(keeper.exists())
            updated = router_ini.read_text(encoding="utf-8")
            self.assertNotIn("[delete-me]", updated)
            self.assertNotIn(str(doomed), updated)
            self.assertIn("[keep-me]", updated)
            self.assertIn(str(keeper), updated)

    def test_recover_refuses_while_model_file_is_missing(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, _router_ini, _original, config, doomed, _keeper = self.make_fixture(td)
            deleted = self.run_modelctl("--config", str(config), "delete", f"path:{doomed}", "--apply")
            self.assertEqual(deleted.returncode, 0, deleted.stderr + deleted.stdout)
            manifest = self.recovery_manifests(config)[0]

            result = self.run_modelctl("--config", str(config), "recover", str(manifest))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("model file is still missing", result.stderr)

    def test_recover_restores_only_affected_section_and_preserves_later_changes(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, router_ini, _original, config, doomed, _keeper = self.make_fixture(td)
            deleted = self.run_modelctl("--config", str(config), "delete", f"path:{doomed}", "--apply")
            self.assertEqual(deleted.returncode, 0, deleted.stderr + deleted.stdout)
            manifest = self.recovery_manifests(config)[0]
            doomed.write_bytes(b"doomed")
            router_ini.write_text(router_ini.read_text(encoding="utf-8") + "\n[later]\nmodel = /tmp/later.gguf\n", encoding="utf-8")

            result = self.run_modelctl("--config", str(config), "recover", str(manifest))

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            text = router_ini.read_text(encoding="utf-8")
            self.assertIn("[delete-me]", text)
            self.assertIn(f"model = {doomed}", text)
            self.assertIn("ctx-size = 4096", text)
            self.assertIn("[keep-me]", text)
            self.assertIn("[later]", text)
            self.assertIn("model = /tmp/later.gguf", text)

    def test_recover_fails_on_alias_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, router_ini, _original, config, doomed, _keeper = self.make_fixture(td)
            deleted = self.run_modelctl("--config", str(config), "delete", f"path:{doomed}", "--apply")
            self.assertEqual(deleted.returncode, 0, deleted.stderr + deleted.stdout)
            manifest = self.recovery_manifests(config)[0]
            doomed.write_bytes(b"doomed")
            router_ini.write_text(router_ini.read_text(encoding="utf-8") + f"\n[delete-me]\nmodel = {doomed}\nctx-size = 1\n", encoding="utf-8")

            result = self.run_modelctl("--config", str(config), "recover", str(manifest))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("alias conflict", result.stderr)
            self.assertEqual(router_ini.read_text(encoding="utf-8").count("[delete-me]"), 1)


if __name__ == "__main__":
    unittest.main()
