import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class ArchiveMutationTests(unittest.TestCase):
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
        main = models / "main-model.Q4_K_M.gguf"
        lab = models / "gemma-4-12b-it-qat-q4_0.gguf"
        main.write_bytes(b"main")
        lab.write_bytes(b"lab")
        router_ini = root / "router.ini"
        original = f"""
# 1) PRODUCTION
[main]
model = {main}
ctx-size = 4096

# 3) OTHERS / OPENWEBUI / TESTING
[gemma-qat-12b]
model = {lab}
ctx-size = 8192
""".lstrip()
        router_ini.write_text(original, encoding="utf-8")
        config = root / "modelctl.ini"
        registry = root / "modelctl.yaml"
        setup = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
        return root, models, router_ini, original, config, registry, main, lab

    def test_archive_model_dry_run_does_not_move_or_edit_ini(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, router_ini, original, config, _registry, _main, lab = self.make_fixture(td)

            result = self.run_modelctl("--config", str(config), "archive", f"path:{lab}", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN: archive model impact preview", result.stdout)
            self.assertIn("gemma-qat-12b", result.stdout)
            self.assertIn("aliases policy: preserve", result.stdout)
            self.assertIn("archive destination", result.stdout)
            self.assertIn("google", result.stdout)
            self.assertTrue(lab.exists())
            self.assertEqual(router_ini.read_text(encoding="utf-8"), original)

    def test_archive_model_apply_moves_file_preserves_aliases_updates_model_path_and_writes_movement_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root, models, router_ini, original, config, _registry, main, lab = self.make_fixture(td)
            plan_path = root / "archive-plan.json"

            result = self.run_modelctl(
                "--config", str(config), "archive", f"path:{lab}", "--plan", str(plan_path)
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("APPLIED: archive model", result.stdout)
            dest = models / "archive" / "google" / "gemma-4-12b-it-qat" / lab.name
            self.assertFalse(lab.exists())
            self.assertTrue(dest.exists())
            self.assertTrue(main.exists())
            updated = router_ini.read_text(encoding="utf-8")
            self.assertIn("[gemma-qat-12b]", updated)
            self.assertIn(f"model = {dest}", updated)
            self.assertIn("ctx-size = 8192", updated)
            self.assertNotIn("# [gemma-qat-12b]", updated)
            self.assertIn("[main]", updated)
            self.assertIn(f"model = {main}", updated)
            self.assertNotEqual(updated, original)
            self.assertTrue(plan_path.exists())
            metadata = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["aliases_policy"], "preserve")
            self.assertEqual(metadata["entries"][0]["source"], str(lab))
            self.assertEqual(metadata["entries"][0]["destination"], str(dest))
            self.assertTrue((router_ini.with_suffix(router_ini.suffix + ".bak")).exists())

            listing = self.run_modelctl("--config", str(config), "list")
            self.assertEqual(listing.returncode, 0, listing.stderr + listing.stdout)
            self.assertIn("archived", listing.stdout)
            self.assertIn(str(dest), listing.stdout)

            imported = self.run_modelctl("--config", str(config), "import")
            self.assertEqual(imported.returncode, 0, imported.stderr + imported.stdout)
            self.assertFalse(lab.exists())
            self.assertTrue(dest.exists())
            self.assertNotEqual(router_ini.read_text(encoding="utf-8"), original)

    def test_archive_with_disable_aliases_disables_only_affected_aliases(self):
        with tempfile.TemporaryDirectory() as td:
            _root, models, router_ini, _original, config, _registry, main, lab = self.make_fixture(td)

            result = self.run_modelctl("--config", str(config), "archive", f"path:{lab}", "--disable-aliases")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            dest = models / "archive" / "google" / "gemma-4-12b-it-qat" / lab.name
            text = router_ini.read_text(encoding="utf-8")
            self.assertIn("[main]", text)
            self.assertIn(f"model = {main}", text)
            self.assertIn("# [gemma-qat-12b]", text)
            self.assertIn(f"# model = {dest}", text)
            self.assertIn("# ctx-size = 8192", text)

    def test_archive_group_lab_targets_only_testing_section(self):
        with tempfile.TemporaryDirectory() as td:
            root, models, router_ini, _original, config, _registry, main, lab = self.make_fixture(td)
            plan_path = root / "lab-plan.json"

            result = self.run_modelctl(
                "--config", str(config), "archive", "--group", "lab", "--plan", str(plan_path)
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(main.exists())
            self.assertFalse(lab.exists())
            dest = models / "archive" / "google" / "gemma-4-12b-it-qat" / lab.name
            self.assertTrue(dest.exists())
            text = router_ini.read_text(encoding="utf-8")
            self.assertIn("[main]", text)
            self.assertIn("[gemma-qat-12b]", text)
            self.assertIn(f"model = {dest}", text)

    def test_archive_accepts_multiple_explicit_targets_in_one_plan(self):
        with tempfile.TemporaryDirectory() as td:
            root, models, _router_ini, _original, config, _registry, main, lab = self.make_fixture(td)
            extra = models / "Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf"
            extra.write_bytes(b"qwen")
            plan_path = root / "multi-plan.json"

            result = self.run_modelctl(
                "--config", str(config), "archive", f"path:{lab}", f"path:{extra}", "--plan", str(plan_path)
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(main.exists())
            self.assertFalse(lab.exists())
            self.assertFalse(extra.exists())
            self.assertTrue((models / "archive" / "google" / "gemma-4-12b-it-qat" / lab.name).exists())
            self.assertTrue((models / "archive" / "qwen" / "Qwen3.6-35B-A3B" / extra.name).exists())

    def test_restore_moves_file_back_preserves_unrelated_ini_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root, models, router_ini, _original, config, _registry, main, lab = self.make_fixture(td)
            plan_path = root / "archive-plan.json"
            archived = self.run_modelctl("--config", str(config), "archive", f"path:{lab}", "--plan", str(plan_path))
            self.assertEqual(archived.returncode, 0, archived.stderr + archived.stdout)
            dest = models / "archive" / "google" / "gemma-4-12b-it-qat" / lab.name
            self.assertTrue(dest.exists())
            text = router_ini.read_text(encoding="utf-8")
            router_ini.write_text(text + "\n[unrelated]\nmodel = /tmp/keep-me.gguf\n", encoding="utf-8")

            result = self.run_modelctl("--config", str(config), "restore", f"path:{dest}")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(lab.exists())
            self.assertFalse(dest.exists())
            restored_text = router_ini.read_text(encoding="utf-8")
            self.assertIn("[unrelated]", restored_text)
            self.assertIn("model = /tmp/keep-me.gguf", restored_text)
            self.assertIn("[gemma-qat-12b]", restored_text)
            self.assertIn(f"model = {lab}", restored_text)
            self.assertIn(f"model = {main}", restored_text)

    def test_restore_reenables_only_aliases_disabled_by_archive_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            _root, models, router_ini, _original, config, _registry, _main, lab = self.make_fixture(td)
            archived = self.run_modelctl("--config", str(config), "archive", f"path:{lab}", "--disable-aliases")
            self.assertEqual(archived.returncode, 0, archived.stderr + archived.stdout)
            dest = models / "archive" / "google" / "gemma-4-12b-it-qat" / lab.name
            self.assertIn("# [gemma-qat-12b]", router_ini.read_text(encoding="utf-8"))

            result = self.run_modelctl("--config", str(config), "restore", f"path:{dest}")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            text = router_ini.read_text(encoding="utf-8")
            self.assertIn("[gemma-qat-12b]", text)
            self.assertIn(f"model = {lab}", text)
            self.assertNotIn("# [gemma-qat-12b]", text)

    def test_restore_fails_if_active_target_already_exists(self):
        with tempfile.TemporaryDirectory() as td:
            _root, models, _router_ini, _original, config, _registry, _main, lab = self.make_fixture(td)
            archived = self.run_modelctl("--config", str(config), "archive", f"path:{lab}")
            self.assertEqual(archived.returncode, 0, archived.stderr + archived.stdout)
            dest = models / "archive" / "google" / "gemma-4-12b-it-qat" / lab.name
            lab.write_bytes(b"conflict")

            result = self.run_modelctl("--config", str(config), "restore", f"path:{dest}")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("target active file already exists", result.stderr)
            self.assertTrue(dest.exists())
            self.assertEqual(lab.read_bytes(), b"conflict")


if __name__ == "__main__":
    unittest.main()
