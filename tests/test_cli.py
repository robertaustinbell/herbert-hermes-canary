import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_verifier_reports_incomplete_bundle_as_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/verify_run.py"), temp],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            report = json.loads(result.stdout)
            self.assertEqual(report["result"], "error")
            self.assertNotIn("Traceback", result.stderr)

    def test_new_suite_requires_explicit_executor_before_runtime_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            result=subprocess.run([
                sys.executable,str(ROOT/'scripts/run_canary.py'),
                '--suite','consequential-boundary-dev/v1',
                '--herbert-source',temp,'--output',str(Path(temp)/'run'),
                '--model','synthetic','--provider','synthetic',
                '--hermes-bin',str(Path(temp)/'must-not-run'),
            ],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('--executor',result.stderr)
            self.assertFalse((Path(temp)/'run').exists())
            self.assertNotIn('Traceback',result.stderr)

    def test_legacy_omitted_executor_preserves_hermes_default(self):
        import importlib.util
        from unittest.mock import patch, MagicMock
        spec=importlib.util.spec_from_file_location('canary_cli',ROOT/'scripts/run_canary.py')
        assert spec is not None and spec.loader is not None
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        executor=MagicMock()
        executor.preflight.return_value={'version':'test'}
        with patch.object(sys,'argv',['run_canary.py','--herbert-source','unused','--output','unused','--model','test','--provider','test']), patch.object(module,'load_source_pin',return_value={}), patch.object(module,'HermesExecutor',return_value=executor), patch.object(module,'run_canary',return_value={'terminal_state':'passed'}) as runner:
            self.assertEqual(module.main(),0)
            self.assertIs(runner.call_args.kwargs['executor'],executor)
            executor.preflight.assert_called_once()

    def test_runner_reports_missing_runtime_as_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/run_canary.py"),
                "--herbert-source", temp, "--output", str(Path(temp) / "run"),
                "--model", "synthetic", "--provider", "synthetic",
                "--hermes-bin", str(Path(temp) / "missing-hermes"),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["result"], "error")
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
