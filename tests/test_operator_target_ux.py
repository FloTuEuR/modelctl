"""Tests for intuitive model target resolution in archive --dry-run."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class ArchiveTargetResolutionTests(unittest.TestCase):
    """Test intuitive model resolution: stem, path, absolute paths, case normalization."""

    def run_modelctl(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def run_modelctl_with_cwd(self, *args, cwd):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def _make_fixture(self, td: str):
        """Create temp model files with various naming patterns."""
        root = Path(td)
        models = root / "models"
        models.mkdir()

        # Canonical model for success tests (case-insensitive, separator variations)
        canonical_models = [
            "Llama-3.2-3B-Instruct-UD-Q8_K_XL.gguf",
            "llama-3.2-3b-instruct-ud-q8_k_xl.gguf",
            "Llama-3.2-3B-Instruct-UD-Q8_K_XL",
            "llama-3.2-3b-instruct-ud-q8_k_xl",
        ]
        for base in canonical_models:
            (models / base).write_bytes(b"model_data")

        # Separate models for ambiguity tests - hyphen and underscore variants
        ambiguity_models = [
            "my-model-q8_k_xl.gguf",
            "my_model_q8_k_xl.gguf",
        ]
        for base in ambiguity_models:
            (models / base).write_bytes(b"model_data")

        router_ini = root / "router.ini"
        router_ini.write_text(
            f"""[active]
model = {models / "Llama-3.2-3B-Instruct-UD-Q8_K_XL.gguf"}
ctx-size = 4096
""",
            encoding="utf-8",
        )


        config = root / "modelctl.ini"
        registry = root / "modelctl.yaml"

        setup = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)

        return root, models, router_ini, config, registry

    def test_archive_exact_gguf_filename_resolves(self):
        """Test that exact GGUF filename works as target."""
        with tempfile.TemporaryDirectory() as td:
            _root, models, router_ini, config, registry = self._make_fixture(td)

            result = self.run_modelctl("--config", str(config), "archive", "Llama-3.2-3B-Instruct-UD-Q8_K_XL.gguf", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN: archive model impact preview", result.stdout)
            self.assertIn("Llama-3.2-3B-Instruct-UD-Q8_K_XL", result.stdout)
            self.assertTrue((models / "Llama-3.2-3B-Instruct-UD-Q8_K_XL.gguf").exists())

    def test_archive_stem_without_gguf_resolves(self):
        """Test that stem without .gguf extension works."""
        with tempfile.TemporaryDirectory() as td:
            _root, models, router_ini, config, registry = self._make_fixture(td)

            result = self.run_modelctl("--config", str(config), "archive", "Llama-3.2-3B-Instruct-UD-Q8_K_XL", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN: archive model impact preview", result.stdout)
            self.assertIn("Llama-3.2-3B-Instruct-UD-Q8_K_XL", result.stdout)
            self.assertTrue((models / "Llama-3.2-3B-Instruct-UD-Q8_K_XL.gguf").exists())

    def test_archive_relative_path_resolves(self):
        """Test that relative path from cwd works."""
        with tempfile.TemporaryDirectory() as td:
            _root, models, router_ini, config, registry = self._make_fixture(td)

            result = self.run_modelctl("--config", str(config), "archive", "./Llama-3.2-3B-Instruct-UD-Q8_K_XL.gguf", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN: archive model impact preview", result.stdout)
            self.assertTrue((models / "Llama-3.2-3B-Instruct-UD-Q8_K_XL.gguf").exists())

    def test_archive_absolute_path_resolves(self):
        """Test that absolute path works."""
        with tempfile.TemporaryDirectory() as td:
            _root, models, router_ini, config, registry = self._make_fixture(td)

            model_path = str(models / "Llama-3.2-3B-Instruct-UD-Q8_K_XL.gguf")
            result = self.run_modelctl("--config", str(config), "archive", model_path, "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN: archive model impact preview", result.stdout)
            self.assertTrue((models / "Llama-3.2-3B-Instruct-UD-Q8_K_XL.gguf").exists())

    def test_archive_hyphen_underscore_dot_space_normalization(self):
        """Test that hyphen/underscore/dot/space variations resolve to same model."""
        with tempfile.TemporaryDirectory() as td:
            _root, models, router_ini, config, registry = self._make_fixture(td)

            result = self.run_modelctl("--config", str(config), "archive", "Llama-3.2-3B-Instruct-UD-Q8_K_XL-hyphen", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN: archive model impact preview", result.stdout)

            result = self.run_modelctl("--config", str(config), "archive", "Llama-3.2-3B-Instruct-UD-Q8_K_XL_underscore", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN: archive model impact preview", result.stdout)

            result = self.run_modelctl("--config", str(config), "archive", "Llama-3.2-3B-Instruct.UD.Q8.K.XL", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN: archive model impact preview", result.stdout)

    def test_archive_ambiguous_target_fails_clearly(self):
        """Test that ambiguous targets fail with clear error and candidates."""
        with tempfile.TemporaryDirectory() as td:
            _root, models, router_ini, config, registry = self._make_fixture(td)

            result = self.run_modelctl("--config", str(config), "archive", "my-model", "--dry-run")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ambiguous", result.stderr)
            self.assertIn("candidates", result.stderr)
            self.assertIn("my-model-q8_k_xl", result.stderr)
            self.assertIn("my_model_q8_k_xl", result.stderr)

    def test_archive_no_match_fails_with_useful_suggestions(self):
        """Test that no-match targets fail with useful suggestions."""
        with tempfile.TemporaryDirectory() as td:
            _root, models, router_ini, config, registry = self._make_fixture(td)

            result = self.run_modelctl("--config", str(config), "archive", "nonexistent-model.gguf", "--dry-run")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Could not resolve", result.stderr)
            self.assertIn("tried filename", result.stderr)
            self.assertIn("tried stem", result.stderr)
            self.assertIn("tried path", result.stderr)

    def test_archive_prefers_exact_matches_over_partial(self):
        """Test that exact matches are preferred over partial matches."""
        with tempfile.TemporaryDirectory() as td:
            _root, models, router_ini, config, registry = self._make_fixture(td)

            # Exact match should resolve to my-model-q8_k_xl.gguf
            result = self.run_modelctl("--config", str(config), "archive", "my-model-q8_k_xl", "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY RUN: archive model impact preview", result.stdout)
            self.assertIn("my-model-q8_k_xl", result.stdout)
