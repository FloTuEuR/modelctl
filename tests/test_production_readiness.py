import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modelctl.py"
PRIVATE_MARKERS = [
    "/home/",
    "C:\\Users\\",
    "192.168.",
    "10.",
    "172.16.",
    "localai",
    "private-hostname",
    "private-username",
    "private-mount",
]


class ProductionReadinessTests(unittest.TestCase):
    def run_modelctl(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def run_private_marker_scan(self):
        scan_code = textwrap.dedent(
            """
            from pathlib import Path
            import sys

            ROOT = Path(sys.argv[1])
            PRIVATE_MARKERS = sys.argv[2:]
            SKIP_DIRS = {'.git', '.github', '__pycache__', '.pytest_cache', '.venv', 'venv', 'private'}
            SCAN_SUFFIXES = {'.py', '.md', '.txt', '.toml', '.yml', '.yaml', '.ini', ''}
            SKIP_FILES = {Path('tests/test_production_readiness.py')}

            def should_scan(path: Path) -> bool:
                rel = path.relative_to(ROOT)
                if rel in SKIP_FILES:
                    return False
                if any(part in SKIP_DIRS for part in rel.parts):
                    return False
                return path.is_file() and path.suffix in SCAN_SUFFIXES

            hits = []
            for path in ROOT.rglob('*'):
                if not should_scan(path):
                    continue
                try:
                    text = path.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    continue
                for lineno, line in enumerate(text.splitlines(), start=1):
                    for marker in PRIVATE_MARKERS:
                        if marker in line:
                            hits.append(f'{path.relative_to(ROOT)}:{lineno}: contains private marker {marker!r}')
            if hits:
                print('Private marker scan failed:', file=sys.stderr)
                print('\\n'.join(hits), file=sys.stderr)
                raise SystemExit(1)
            print('Private marker scan passed.')
            """
        )
        return subprocess.run(
            [sys.executable, "-c", scan_code, str(ROOT), *PRIVATE_MARKERS],
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
        model = models / "publish-test-model.Q4_K_M.gguf"
        model.write_bytes(b"publishable")
        router_ini = root / "router.ini"
        original = f"""
[publish-test]
model = {model}
ctx-size = 4096
""".lstrip()
        router_ini.write_text(original, encoding="utf-8")
        config = root / "modelctl.ini"
        registry = root / "modelctl.yaml"
        setup = self.run_modelctl("setup", str(router_ini), "--config", str(config), "--registry", str(registry))
        self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
        return root, models, router_ini, original, config, model

    def test_help_and_errors_use_generic_paths_not_private_paths(self):
        help_result = self.run_modelctl("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr + help_result.stdout)
        combined = help_result.stdout + help_result.stderr
        self.assertIn("/path/to/models.ini", combined)
        for marker in ("/home/", "C:\\Users\\", "192.168.", "localai", "private-hostname"):
            self.assertNotIn(marker, combined)

        missing = self.run_modelctl("setup", "/definitely/missing/models.ini")
        self.assertNotEqual(missing.returncode, 0)
        combined = missing.stdout + missing.stderr
        self.assertIn("/path/to/models.ini", combined)
        self.assertNotIn("/home/", combined)

    def test_shell_launcher_is_portable_and_has_no_user_specific_default(self):
        launcher = (ROOT / "modelctl").read_text(encoding="utf-8")
        self.assertIn("SCRIPT_DIR", launcher)
        self.assertNotIn("/home/", launcher)
        self.assertNotIn("C:\\Users\\", launcher)

    def test_applied_archive_plan_does_not_embed_full_original_ini_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root, models, router_ini, original, config, model = self.make_fixture(td)
            plan_path = root / "archive-plan.json"

            result = self.run_modelctl("--config", str(config), "archive", f"path:{model}", "--plan", str(plan_path))

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertNotIn("original_ini_text", plan)
            self.assertIn("router_ini_backup", plan)
            self.assertIn("original_ini_sha256", plan)

            restored = router_ini.with_suffix(router_ini.suffix + ".bak").read_text(encoding="utf-8")
            self.assertEqual(restored, original)

    def test_publishable_tree_has_no_private_markers(self):
        result = self.run_private_marker_scan()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
