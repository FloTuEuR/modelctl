import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from modelctl_core import apply_delete_plan, detect_from_ini, plan_delete_model


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class UxDeleteAndRoadmapTests(unittest.TestCase):
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
[delete-me]
model = {doomed}
ctx-size = 4096

[keep-me]
model = {keeper}
ctx-size = 4096
""".lstrip()
        router_ini.write_text(original, encoding="utf-8")
        config = root / "modelctl.ini"
        registry = root / "modelctl.yaml"
        setup = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
        return root, models, router_ini, original, config, doomed, keeper

    def test_subcommand_help_explains_targets_and_examples(self):
        expected = {
            "aliases": ["TARGET", "1", "alias:my-model", "filename.gguf"],
            "show": ["TARGET", "1", "alias:my-model", "path:/models/model.gguf"],
            "delete": ["permanently deletes", "interactive confirmation", "--dry-run", "1"],
            "archive": ["dry-run", "alias:my-model", "--group lab", "recovery metadata"],
            "setup": ["/path/to/models.ini", "--registry", "writes config/registry"],
            "import": ["Refresh", "modelctl import", "Router ini is not modified"],
            "doctor": ["configured paths", "modelctl doctor", "delete requires interactive"],
            "list": ["Models", "Aliases", "modelctl list"],
        }
        for command, snippets in expected.items():
            with self.subTest(command=command):
                result = self.run_modelctl(command, "-h")
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                combined = result.stdout + result.stderr
                for snippet in snippets:
                    self.assertIn(snippet, combined)

    def test_delete_noninteractive_is_blocked_unless_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, router_ini, original, config, doomed, _keeper = self.make_fixture(td)

            result = self.run_modelctl("--config", str(config), "delete", f"path:{doomed}", input_text="DELETE\n")

            self.assertNotEqual(result.returncode, 0)
            combined = result.stdout + result.stderr
            self.assertIn("interactive TTY", combined)
            self.assertIn("Agents and scripts should use --dry-run", combined)
            self.assertTrue(doomed.exists())
            self.assertEqual(router_ini.read_text(encoding="utf-8"), original)

            dry_run = self.run_modelctl("--config", str(config), "delete", f"path:{doomed}", "--dry-run")
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr + dry_run.stdout)
            self.assertIn("DRY RUN: delete model impact preview", dry_run.stdout)
            self.assertTrue(doomed.exists())
            self.assertEqual(router_ini.read_text(encoding="utf-8"), original)

    def test_delete_alias_target_resolves_to_model_for_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, router_ini, original, config, doomed, _keeper = self.make_fixture(td)

            result = self.run_modelctl("--config", str(config), "delete", "alias:delete-me", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(str(doomed), result.stdout)
            self.assertIn("delete-me", result.stdout)
            self.assertTrue(doomed.exists())
            self.assertEqual(router_ini.read_text(encoding="utf-8"), original)

    def test_delete_core_removes_file_and_alias_section_with_backup(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, router_ini, _original, _config, doomed, keeper = self.make_fixture(td)
            imported = detect_from_ini(router_ini)
            plan = plan_delete_model(imported, str(doomed))

            result = apply_delete_plan(plan)

            self.assertEqual(result["deleted_files"], [str(doomed)])
            self.assertFalse(doomed.exists())
            self.assertTrue(keeper.exists())
            updated = router_ini.read_text(encoding="utf-8")
            self.assertNotIn("[delete-me]", updated)
            self.assertNotIn(str(doomed), updated)
            self.assertIn("[keep-me]", updated)
            self.assertIn(str(keeper), updated)
            self.assertTrue(Path(result["router_ini_backup"]).exists())
            self.assertIn("original_ini_sha256", result)

    def test_docs_name_hf_update_benchmark_and_settings_features_as_roadmap(self):
        docs = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        for snippet in (
            "Hugging Face download",
            "up-to-date check",
            "benchmark",
            "suggest settings",
            "hardware/config detection",
            "not implemented in v0.1",
        ):
            self.assertIn(snippet, docs)


if __name__ == "__main__":
    unittest.main()
