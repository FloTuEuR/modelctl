import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"


class ModelAdvancedUxTests(unittest.TestCase):
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
        active = models / "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
        manual = models / "Gemma-4-E4B-it-Q4_0.gguf"
        active.write_bytes(b"x" * 1024 * 1024)
        manual.write_bytes(b"y" * 2048)
        ini = root / "models.ini"
        ini.write_text(
            f"""
[qwen-fast]
model = {active}
ctx-size = 4096
""".lstrip(),
            encoding="utf-8",
        )
        config = root / "modelctl.ini"
        registry = root / "modelctl.yaml"
        setup = self.run_modelctl("setup", str(ini), "--config", str(config), "--registry", str(registry))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
        return root, models, active, manual, ini, config

    def test_show_explains_vram_formula_context_layers_and_settings(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, _active, _manual, _ini, config = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "show", "1", "--gpu-vram-gib", "8")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            low = result.stdout.lower()
            self.assertIn("minimum vram:", low)
            self.assertIn("model bytes × 1.20", low)
            self.assertIn("estimated max context:", low)
            self.assertIn("default kv cache", low)
            self.assertIn("estimated gpu layers:", low)
            self.assertIn("% of layers", low)
            self.assertIn("settings recommendation:", low)
            self.assertIn("cache-type-k", low)

    def test_benchmark_without_llama_bench_is_actionable_error(self):
        if shutil.which("llama-bench") or (Path.home() / "llama.cpp" / "build" / "bin" / "llama-bench").exists():
            self.skipTest("llama-bench is available in this environment")
        with tempfile.TemporaryDirectory() as td:
            _root, _models, _active, _manual, _ini, config = self.make_fixture(td)
            result = self.run_modelctl("--config", str(config), "benchmark", "1")
            self.assertNotEqual(result.returncode, 0)
            combined = result.stdout + result.stderr
            self.assertIn("llama-bench", combined)
            self.assertIn("not found", combined.lower())

    def test_opt_in_dry_run_help_and_scan_apply(self):
        with tempfile.TemporaryDirectory() as td:
            _root, _models, _active, manual, ini, config = self.make_fixture(td)
            scan_help = self.run_modelctl("scan", "-h")
            self.assertEqual(scan_help.returncode, 0, scan_help.stderr + scan_help.stdout)
            self.assertIn("--dry-run", scan_help.stdout)

            preview = self.run_modelctl("--config", str(config), "scan", "--dry-run")
            self.assertEqual(preview.returncode, 0, preview.stderr + preview.stdout)
            self.assertIn(str(manual), preview.stdout)
            self.assertIn("No ini entries were changed", preview.stdout)

            apply = self.run_modelctl("--config", str(config), "scan")
            self.assertEqual(apply.returncode, 0, apply.stderr + apply.stdout)
            text = ini.read_text(encoding="utf-8")
            self.assertIn(str(manual), text)
            self.assertIn("[gemma-4-e4b-it-q4-0]", text.lower())


if __name__ == "__main__":
    unittest.main()
