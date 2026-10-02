"""Installed-package probes that cannot succeed through repository-root imports."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class PackagingTests(unittest.TestCase):
    def test_isolated_installed_import_and_rules_resource(self):
        code = '''
import json, sys
from importlib.resources import files
import tetris_trainer
from tetris_trainer.environment import PlacementEnvironment
env = PlacementEnvironment(42)
assert env.legal_actions()
assert len(env.observe()) == 929
assert 'torch' not in sys.modules
assert 'tkinter' not in sys.modules
data = files('tetris_trainer').joinpath('data/srs_plus.json').read_text()
assert json.loads(data)
print(json.dumps({'module': tetris_trainer.__file__}))
'''
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-I', '-c', code], cwd=directory,
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        resolved = Path(json.loads(result.stdout)['module']).resolve()
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / 'tetris_trainer').exists())
        # Editable development resolves to src; a regular install may use site-packages.
        self.assertTrue(resolved.is_relative_to(root / 'src')
                        or 'site-packages' in resolved.parts, str(resolved))


if __name__ == '__main__':
    unittest.main()
