import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'modelctl.py'


def _run(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, env=env)


class ModelRealFeaturesTests(unittest.TestCase):
    def make_fixture(self, td: str):
        root = Path(td)
        models = root / 'models'
        models.mkdir()
        active = models / 'gemma-4-12b-it-q4_0.gguf'
        active.write_bytes(b'GGUFstub')
        ini = root / 'models.ini'
        ini.write_text(textwrap.dedent(f'''
            [gemma12]
            model = {active}
            hf_repo = google/gemma-4-12b-it-gguf
            hf_file = gemma-4-12b-it-q4_0.gguf
        ''').strip() + '\n', encoding='utf-8')
        config = root / 'config.ini'
        config.write_text(textwrap.dedent(f'''
            [router]
            ini = {ini}
            [models]
            download_dir = {models}
            [registry]
            path = {root / 'modelctl.yaml'}
            [state]
            benchmark_dir = {root / 'benchmarks'}
        ''').strip() + '\n', encoding='utf-8')
        return active, ini, config, root

    def test_enable_disable_apply_and_dry_run_is_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            active, ini, config, _root = self.make_fixture(td)
            result = _run('--config', str(config), 'disable', 'gemma12')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('APPLIED', result.stdout)
            self.assertIn('# [gemma12]', ini.read_text(encoding='utf-8'))

            dry = _run('--config', str(config), 'enable', 'gemma12', '--dry-run')
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertIn('DRY RUN', dry.stdout)
            self.assertIn('# [gemma12]', ini.read_text(encoding='utf-8'))

            apply_enable = _run('--config', str(config), 'enable', 'gemma12')
            self.assertEqual(apply_enable.returncode, 0, apply_enable.stderr)
            self.assertIn('APPLIED', apply_enable.stdout)
            text = ini.read_text(encoding='utf-8')
            self.assertIn('[gemma12]', text)
            self.assertNotIn('# [gemma12]', text)

    def test_show_uses_persisted_benchmark_and_hf_state(self):
        with tempfile.TemporaryDirectory() as td:
            _active, _ini, config, root = self.make_fixture(td)
            bench_dir = root / 'benchmarks'
            bench_dir.mkdir()
            (bench_dir / 'gemma-4-12b-it-q4_0.gguf.json').write_text(json.dumps({
                'model_path': 'ignored',
                'prompt_tokens_per_second': 123.4,
                'generation_tokens_per_second': 45.6,
            }), encoding='utf-8')
            state_dir = root / '.modelctl'
            state_dir.mkdir()
            (state_dir / 'hf-status.json').write_text(json.dumps({
                'google/gemma-4-12b-it-gguf::gemma-4-12b-it-q4_0.gguf': {
                    'status': 'update-available',
                    'remote_size': 999,
                    'local_size': 8,
                }
            }), encoding='utf-8')
            env = dict(**__import__('os').environ)
            env['MODELCTL_STATE_DIR'] = str(state_dir)
            result = _run('--config', str(config), 'show', '1', '--gpu-vram-gib', '8', env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            out = result.stdout
            self.assertIn('45.6 tok/s', out)
            self.assertIn('123.4 tok/s', out)
            self.assertIn('update-available', out)
            self.assertIn('cache-type-k', out)

    def test_update_check_records_hf_status_from_mock_api(self):
        with tempfile.TemporaryDirectory() as td:
            _active, _ini, config, root = self.make_fixture(td)
            state_dir = root / '.modelctl'
            state_dir.mkdir()
            env = dict(**__import__('os').environ)
            env['MODELCTL_STATE_DIR'] = str(state_dir)
            env['MODELCTL_HF_TREE_JSON'] = json.dumps([
                {'path': 'gemma-4-12b-it-q4_0.gguf', 'size': 123456789, 'type': 'file'}
            ])
            result = _run('--config', str(config), 'update-check', '1', env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('update-available', result.stdout)
            saved = json.loads((state_dir / 'hf-status.json').read_text(encoding='utf-8'))
            key = 'google/gemma-4-12b-it-gguf::gemma-4-12b-it-q4_0.gguf'
            self.assertEqual(saved[key]['status'], 'update-available')

    def test_benchmark_parses_json_and_persists_results(self):
        with tempfile.TemporaryDirectory() as td:
            _active, _ini, config, root = self.make_fixture(td)
            bench = root / 'fake-llama-bench.py'
            bench.write_text(textwrap.dedent('''
                #!/usr/bin/env python3
                import json
                print(json.dumps([
                  {"n_prompt":256, "n_gen":0, "avg_ts":111.1},
                  {"n_prompt":0, "n_gen":64, "avg_ts":22.2}
                ]))
            '''), encoding='utf-8')
            bench.chmod(0o755)
            env = dict(**__import__('os').environ)
            env['MODELCTL_LLAMA_BENCH'] = str(bench)
            result = _run('--config', str(config), 'benchmark', '1', env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('generation_tokens_per_second: 22.2 tok/s', result.stdout)
            saved = json.loads((root / 'benchmarks' / 'gemma-4-12b-it-q4_0.gguf.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['generation_tokens_per_second'], 22.2)


if __name__ == '__main__':
    unittest.main()
