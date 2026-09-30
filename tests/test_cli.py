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
