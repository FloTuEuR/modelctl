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

    def test_show_json_envelope_for_model_target(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "show", "1", "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "show")
            self.assertIsNone(payload["error"])
            self.assertIn("target", payload["data"])
            self.assertIn("resolved_target", payload["data"])
            self.assertIn("model", payload["data"])
            model = payload["data"]["model"]
            self.assertIn("path", model)
            self.assertIn("state", model)
            self.assertIn("location", model)
            self.assertIn("aliases", model)
            self.assertIsInstance(model["aliases"], list)
            self.assertIn("guidance", model)

    def test_show_json_envelope_for_alias_target(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "show", "alias:sample", "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "show")
            self.assertIsNone(payload["error"])
            self.assertIn("target", payload["data"])
            self.assertIn("resolved_target", payload["data"])
            self.assertIn("alias", payload["data"])
            alias = payload["data"]["alias"]
            self.assertIn("section", alias)
            self.assertIn("state", alias)
            self.assertIn("enabled", alias)
            self.assertIn("model_path", alias)

    def test_show_json_error_envelope_for_unresolvable_target(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "show", "nonexistent", "--json")
            self.assertNotEqual(result.returncode, 0)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "show", status="error")
            self.assertEqual(payload["error"]["code"], "target_not_found")
            self.assertEqual(payload["data"], {})

    def test_aliases_json_envelope_for_model_target(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "aliases", "1", "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "aliases")
            self.assertIsNone(payload["error"])
            self.assertIn("target", payload["data"])
            self.assertIn("resolved_target", payload["data"])
            self.assertIn("model_path", payload["data"])
            self.assertIn("aliases", payload["data"])
            self.assertIsInstance(payload["data"]["aliases"], list)
            if payload["data"]["aliases"]:
                alias = payload["data"]["aliases"][0]
                self.assertIn("section", alias)
                self.assertIn("state", alias)
                self.assertIn("enabled", alias)

    def test_aliases_json_error_envelope_for_unresolvable_target(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "aliases", "nonexistent", "--json")
            self.assertNotEqual(result.returncode, 0)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "aliases", status="error")
            self.assertEqual(payload["error"]["code"], "target_not_found")
            self.assertEqual(payload["data"], {})

    def test_human_list_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "list")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Models", result.stdout)
            self.assertIn("Aliases", result.stdout)
            self.assertNotIn('"status"', result.stdout)

    def test_add_dry_run_json_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl(
                "--config", str(config),
                "add", "--alias", "my-model", "--model", "/some/path.gguf",
                "--dry-run", "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "add")
            self.assertIsNone(payload["error"])
            self.assertIn("target_path", payload["data"])
            self.assertIn("alias", payload["data"])
            self.assertIn("model_path", payload["data"])
            self.assertIs(payload["data"]["dry_run"], True)
            self.assertIs(payload["data"]["would_write_ini"], False)
            self.assertIsInstance(payload["data"]["planned_changes"], list)
            self.assertTrue(len(payload["data"]["planned_changes"]) > 0)

    def test_archive_dry_run_json_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl(
                "--config", str(config),
                "archive", "1",
                "--dry-run", "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "archive")
            self.assertIsNone(payload["error"])
            self.assertIn("targets", payload["data"])
            self.assertIs(payload["data"]["dry_run"], True)
            self.assertIs(payload["data"]["would_move_file"], False)
            self.assertIs(payload["data"]["would_update_ini"], False)
            self.assertIn("aliases_preserved", payload["data"])
            self.assertIn("disable_aliases", payload["data"])
            self.assertIn("affected_aliases", payload["data"])
            self.assertIsInstance(payload["data"]["affected_aliases"], list)
            self.assertIn("entries", payload["data"])
            self.assertIsInstance(payload["data"]["entries"], list)
            self.assertTrue(len(payload["data"]["entries"]) >= 1)
            entry = payload["data"]["entries"][0]
            self.assertIn("source_path", entry)
            self.assertIn("archive_path", entry)
            self.assertIn("aliases_impacted", entry)
            self.assertIsInstance(payload["data"]["planned_changes"], list)
            self.assertTrue(len(payload["data"]["planned_changes"]) > 0)
            self.assertIsNone(payload["data"]["metadata_path"])
            self.assertIn("warnings", payload)

    def _archive_model(self, config, target="1"):
        result = self.run_modelctl("--config", str(config), "archive", target)
        self.assertEqual(result.returncode, 0, f"archive apply failed: {result.stderr + result.stdout}")
        return result

    def test_restore_dry_run_json_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            self._archive_model(config, "1")
            result = self.run_modelctl("--config", str(config), "restore", "1", "--dry-run", "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "restore")
            self.assertIsNone(payload["error"])
            self.assertIs(payload["data"]["dry_run"], True)
            self.assertIs(payload["data"]["would_move_file"], False)
            self.assertIs(payload["data"]["would_update_ini"], False)
            self.assertIn("archive_path", payload["data"])
            self.assertIn("source_path", payload["data"])
            self.assertIn("active_path", payload["data"])
            self.assertIn("restore_path", payload["data"])
            self.assertIn("target", payload["data"])
            self.assertIsInstance(payload["data"]["planned_changes"], list)
            self.assertTrue(len(payload["data"]["planned_changes"]) > 0)

    def test_delete_dry_run_json_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "delete", "1", "--dry-run", "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "delete")
            self.assertIsNone(payload["error"])
            self.assertIn("target", payload["data"])
            self.assertIn("model_path", payload["data"])
            self.assertIs(payload["data"]["dry_run"], True)
            self.assertIs(payload["data"]["would_delete_file"], False)
            self.assertIs(payload["data"]["would_update_ini"], False)
            self.assertIs(payload["data"]["would_write_recovery_manifest"], False)
            self.assertIs(payload["data"]["delete_requires_apply"], True)
            self.assertIn("affected_aliases", payload["data"])
            self.assertIn("affected_sections", payload["data"])
            self.assertIn("planned_recovery_manifest_path", payload["data"])
            self.assertIsInstance(payload["data"]["planned_changes"], list)
            self.assertTrue(len(payload["data"]["planned_changes"]) > 0)

    def _state_env(self, config):
        state_dir = str(Path(config).parent / "state")
        return {"MODELCTL_STATE_DIR": state_dir}

    def _recovery_manifests(self, config):
        state_dir = Path(config).parent / "state"
        return sorted(state_dir.glob("recovery/delete-*.json"))

    def test_recover_dry_run_json_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            model_path = _root / "models" / "sample.Q4_K_M.gguf"
            env = self._state_env(config)
            delete_result = self.run_modelctl("--config", str(config), "delete", f"path:{model_path}", "--apply", env=env)
            self.assertEqual(delete_result.returncode, 0, delete_result.stderr + delete_result.stdout)
            manifests = self._recovery_manifests(config)
            self.assertEqual(len(manifests), 1, f"no manifests in {config.parent / 'state' / 'recovery'}")
            manifest = manifests[0]
            model_path.write_bytes(b"sample")
            result = self.run_modelctl("--config", str(config), "recover", str(manifest), "--dry-run", "--json", env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "recover")
            self.assertIsNone(payload["error"])
            self.assertIn("recovery_manifest_path", payload["data"])
            self.assertIs(payload["data"]["dry_run"], True)
            self.assertIs(payload["data"]["would_update_ini"], False)
            self.assertIn("model_path", payload["data"])
            self.assertIn("affected_aliases", payload["data"])
            self.assertIn("affected_sections", payload["data"])
            self.assertIn("conflict_status", payload["data"])
            self.assertIn("has_conflicts", payload["data"]["conflict_status"])
            self.assertIn("conflicting_sections", payload["data"]["conflict_status"])
            self.assertIsInstance(payload["data"]["planned_changes"], list)

    def test_human_restore_dry_run_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            self._archive_model(config, "1")
            result = self.run_modelctl("--config", str(config), "restore", "1", "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN", result.stdout)
            self.assertIn("No files or ini entries were changed", result.stdout)
            self.assertNotIn('"status"', result.stdout)

    def test_human_delete_dry_run_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "delete", "1", "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN", result.stdout)
            self.assertIn("No files or ini entries were changed", result.stdout)
            self.assertNotIn('"status"', result.stdout)

    def test_human_recover_dry_run_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            model_path = _root / "models" / "sample.Q4_K_M.gguf"
            env = self._state_env(config)
            delete_result = self.run_modelctl("--config", str(config), "delete", f"path:{model_path}", "--apply", env=env)
            self.assertEqual(delete_result.returncode, 0, delete_result.stderr + delete_result.stdout)
            manifests = self._recovery_manifests(config)
            self.assertEqual(len(manifests), 1)
            manifest = manifests[0]
            model_path.write_bytes(b"sample")
            result = self.run_modelctl("--config", str(config), "recover", str(manifest), "--dry-run", env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN", result.stdout)
            self.assertNotIn('"status"', result.stdout)

    def test_human_add_dry_run_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl(
                "--config", str(config),
                "add", "--alias", "my-model", "--model", "/some/path.gguf",
                "--dry-run",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Router ini entry plan", result.stdout)
            self.assertIn("No ini entries were changed", result.stdout)
            self.assertNotIn('"status"', result.stdout)

    def test_human_archive_dry_run_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl(
                "--config", str(config),
                "archive", "1",
                "--dry-run",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN", result.stdout)
            self.assertIn("No files or ini entries were changed", result.stdout)
            self.assertNotIn('"status"', result.stdout)

    def test_add_apply_json_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl(
                "--config", str(config),
                "add", "--alias", "my-model", "--model", "/some/path.gguf",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "add")
            self.assertIsNone(payload["error"])
            self.assertIs(payload["data"]["applied"], True)
            self.assertIs(payload["data"]["dry_run"], False)
            self.assertIn("alias", payload["data"])
            self.assertIn("model_path", payload["data"])
            self.assertIn("ini_path", payload["data"])

    def test_add_human_apply_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl(
                "--config", str(config),
                "add", "--alias", "my-model", "--model", "/some/path.gguf",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("APPLIED", result.stdout)
            self.assertNotIn('"status"', result.stdout)

    def test_archive_apply_json_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl(
                "--config", str(config),
                "archive", "1",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "archive")
            self.assertIsNone(payload["error"])
            self.assertIs(payload["data"]["applied"], True)
            self.assertIs(payload["data"]["dry_run"], False)
            self.assertIn("moved", payload["data"])
            self.assertIn("entries", payload["data"])
            self.assertIn("affected_aliases", payload["data"])
            self.assertIn("ini_path", payload["data"])
            self.assertIn("metadata_path", payload["data"])
            self.assertIsNotNone(payload["data"]["metadata_path"])

    def test_archive_human_apply_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl(
                "--config", str(config),
                "archive", "1",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("APPLIED", result.stdout)
            self.assertNotIn('"status"', result.stdout)

    def test_restore_apply_json_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            self._archive_model(config, "1")
            result = self.run_modelctl(
                "--config", str(config),
                "restore", "1",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "restore")
            self.assertIsNone(payload["error"])
            self.assertIs(payload["data"]["applied"], True)
            self.assertIs(payload["data"]["dry_run"], False)
            self.assertIn("restored", payload["data"])
            self.assertIn("affected_aliases", payload["data"])
            self.assertIn("ini_path", payload["data"])

    def test_restore_human_apply_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            self._archive_model(config, "1")
            result = self.run_modelctl(
                "--config", str(config),
                "restore", "1",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("APPLIED", result.stdout)
            self.assertNotIn('"status"', result.stdout)

    def test_recover_apply_json_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            model_path = _root / "models" / "sample.Q4_K_M.gguf"
            env = self._state_env(config)
            delete_result = self.run_modelctl("--config", str(config), "delete", f"path:{model_path}", "--apply", env=env)
            self.assertEqual(delete_result.returncode, 0, delete_result.stderr + delete_result.stdout)
            manifests = self._recovery_manifests(config)
            self.assertEqual(len(manifests), 1)
            manifest = manifests[0]
            model_path.write_bytes(b"sample")
            result = self.run_modelctl("--config", str(config), "recover", str(manifest), "--json", env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "recover")
            self.assertIsNone(payload["error"])
            self.assertIs(payload["data"]["applied"], True)
            self.assertIs(payload["data"]["dry_run"], False)
            self.assertIn("sections_restored", payload["data"])
            self.assertIn("affected_aliases", payload["data"])
            self.assertIn("ini_path", payload["data"])
            self.assertIn("conflict_status", payload["data"])
            self.assertIn("recovery_manifest_path", payload["data"])

    def test_recover_human_apply_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            model_path = _root / "models" / "sample.Q4_K_M.gguf"
            env = self._state_env(config)
            delete_result = self.run_modelctl("--config", str(config), "delete", f"path:{model_path}", "--apply", env=env)
            self.assertEqual(delete_result.returncode, 0, delete_result.stderr + delete_result.stdout)
            manifests = self._recovery_manifests(config)
            self.assertEqual(len(manifests), 1)
            manifest = manifests[0]
            model_path.write_bytes(b"sample")
            result = self.run_modelctl("--config", str(config), "recover", str(manifest), env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("APPLIED", result.stdout)
            self.assertNotIn('"status"', result.stdout)

    def test_archive_json_error_envelope_when_target_missing(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "archive", "--json")
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "archive", status="error")
            self.assertEqual(payload["error"]["code"], "target_not_found")

    def test_recover_json_error_envelope_when_manifest_missing(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "recover", "/nonexistent/manifest.json", "--json")
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "recover", status="error")
            self.assertEqual(payload["error"]["code"], "manifest_not_found")

    def test_delete_json_error_envelope_when_target_missing(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _router_ini, config, _registry = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "delete", "999", "--json")
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "delete", status="error")
            self.assertEqual(payload["error"]["code"], "target_not_found")

    def _make_two_model_fixture(self, td: str):
        root = Path(td)
        models = root / "models"
        models.mkdir()
        m1 = models / "alpha.Q4_K_M.gguf"
        m1.write_bytes(b"alpha")
        m2 = models / "beta.Q4_K_M.gguf"
        m2.write_bytes(b"beta")
        ini = root / "router.ini"
        ini.write_text(
            f"[alpha]\nmodel = {m1}\nctx-size = 4096\n"
            f"[beta]\nmodel = {m2}\nctx-size = 4096\n"
            f"#[beta-disabled]\n#model = {m2}\n#ctx-size = 4096\n",
            encoding="utf-8",
        )
        cfg = root / "config" / "modelctl.ini"
        cfg.parent.mkdir()
        cfg.write_text(
            f"[router]\nini = {ini}\n"
            f"[models]\ndownload_dir = {models}\n"
            f"[monitor]\nbackend = none\n",
            encoding="utf-8",
        )
        reg = root / "data" / "modelctl.yaml"
        setup = self.run_modelctl("setup", str(ini), "--config", str(cfg), "--registry", str(reg))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
        return root, ini, cfg, reg, m1, m2

    def test_list_json_active_filter_applied(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _ini, config, _reg, _m1, _m2 = self._make_two_model_fixture(td)
            result = self.run_modelctl("--config", str(config), "list", "--json", "--active")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "list")
            self.assertIn("filters_applied", payload["data"])
            self.assertEqual(payload["data"]["filters_applied"], {"active": True})
            self.assertEqual(len(payload["data"]["models"]), 2)

    def test_list_json_archived_filter_applied(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _ini, config, _reg, _m1, _m2 = self._make_two_model_fixture(td)
            result = self.run_modelctl("--config", str(config), "list", "--json", "--archived")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "list")
            self.assertIn("filters_applied", payload["data"])
            self.assertEqual(payload["data"]["filters_applied"], {"archived": True})
            self.assertEqual(len(payload["data"]["models"]), 0)

    def test_list_json_enabled_filter_applied(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _ini, config, _reg, _m1, _m2 = self._make_two_model_fixture(td)
            result = self.run_modelctl("--config", str(config), "list", "--json", "--enabled")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "list")
            self.assertIn("filters_applied", payload["data"])
            self.assertEqual(payload["data"]["filters_applied"], {"enabled": True})
            self.assertEqual(len(payload["data"]["aliases"]), 2)

    def test_list_json_disabled_filter_applied(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _ini, config, _reg, _m1, _m2 = self._make_two_model_fixture(td)
            result = self.run_modelctl("--config", str(config), "list", "--json", "--disabled")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assert_envelope(payload, "list")
            self.assertIn("filters_applied", payload["data"])
            self.assertEqual(payload["data"]["filters_applied"], {"disabled": True})
            self.assertEqual(len(payload["data"]["aliases"]), 1)

    def test_list_no_filters_no_filters_applied_key(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _ini, config, _reg, _m1, _m2 = self._make_two_model_fixture(td)
            result = self.run_modelctl("--config", str(config), "list", "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assertNotIn("filters_applied", payload["data"])

    def test_list_invalid_active_archived_combination(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _ini, config, _reg, _m1, _m2 = self._make_two_model_fixture(td)
            result = self.run_modelctl("--config", str(config), "list", "--active", "--archived")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Cannot combine", result.stderr)

    def test_list_invalid_enabled_disabled_combination(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _ini, config, _reg, _m1, _m2 = self._make_two_model_fixture(td)
            result = self.run_modelctl("--config", str(config), "list", "--enabled", "--disabled")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Cannot combine", result.stderr)


if __name__ == "__main__":
    unittest.main()
