import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from herbert_canary.hermes_executor import HermesExecutor


class RuntimeSelectionTests(unittest.TestCase):
    def test_explicit_interpreter_keeps_venv_symlink_location(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            launcher=root/'hermes'; launcher.write_text('')
            interpreter=root/'python'; interpreter.symlink_to(sys.executable)
            executor=HermesExecutor(hermes_bin=str(launcher),hermes_python=str(interpreter))
            self.assertEqual(executor.hermes_python,str(interpreter))

    def test_cli_preflight_diagnostic_mentions_explicit_interpreter(self):
        import subprocess
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            launcher=root/'hermes'; launcher.write_text(''); launcher.chmod(0o700)
            repo=Path(__file__).resolve().parents[1]
            result=subprocess.run([sys.executable,str(repo/'scripts/run_canary.py'),'--herbert-source',str(root),'--output',str(root/'out'),'--model','m','--provider','p','--hermes-bin',str(launcher)],text=True,capture_output=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('--hermes-python',result.stdout)
            self.assertFalse((root/'out').exists())

    def test_missing_sibling_is_actionable_before_authentication(self):
        with tempfile.TemporaryDirectory() as raw:
            launcher = Path(raw) / 'hermes'
            launcher.write_text('')
            with self.assertRaisesRegex(ValueError, 'hermes-python'):
                HermesExecutor(hermes_bin=str(launcher))

    def test_explicit_interpreter_and_incompatible_preflight(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            launcher = root / 'hermes'
            launcher.write_text('#!/bin/sh\necho incompatible\n')
            launcher.chmod(0o700)
            executor = HermesExecutor(hermes_bin=str(launcher), hermes_python=sys.executable)
            self.assertEqual(executor.hermes_python, str(Path(sys.executable).absolute()))
            with self.assertRaisesRegex(ValueError, 'preflight'):
                executor.preflight(root)

    def test_supported_sibling_and_explicit_runtime_are_recorded(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            launcher = root / 'hermes'
            launcher.write_text('#!/bin/sh\necho "Hermes test chat --query-file --source --max-turns sessions export --redact mcp add test"\n')
            launcher.chmod(0o700)
            interpreter = root / 'python'
            interpreter.write_text('#!/bin/sh\necho \'{"python":"test", "mcp":"test"}\'\n')
            interpreter.chmod(0o700)
            result = HermesExecutor(hermes_bin=str(launcher)).preflight(root)
            self.assertEqual(result['status'], 'passed')
            self.assertIn('interpreter_sha256', result)
            self.assertIn('launcher_sha256', result)


if __name__ == '__main__':
    unittest.main()
