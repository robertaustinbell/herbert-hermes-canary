import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from herbert_canary.fixture_mcp import perform_write_marker


class FixtureToolTests(unittest.TestCase):
    def test_marker_tool_writes_only_fixed_contained_artifacts(self):
        root = Path(tempfile.mkdtemp()).resolve()
        result = perform_write_marker(root, "synthetic request")
        self.assertEqual(result["status"], "synthetic_marker_written")
        self.assertEqual((root / "fixture-marker.txt").read_text(), "synthetic request\n")
        audit = [json.loads(line) for line in (root / "tool-audit.jsonl").read_text().splitlines()]
        self.assertEqual(audit[0]["tool"], "fixture_write_marker")
        self.assertNotIn(str(root.parent), json.dumps(audit))

    def test_marker_and_audit_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            outside = root / "outside.txt"
            outside.write_text("unchanged\n")
            for filename in ("fixture-marker.txt", "tool-audit.jsonl"):
                cell = root / filename.replace(".", "-")
                cell.mkdir()
                (cell / filename).symlink_to(outside)
                with self.subTest(filename=filename), self.assertRaises((ValueError, OSError)):
                    perform_write_marker(cell, "synthetic")
                self.assertEqual(outside.read_text(), "unchanged\n")

    def test_marker_tool_rejects_unbounded_note(self):
        root = Path(tempfile.mkdtemp()).resolve()
        with self.assertRaises(ValueError):
            perform_write_marker(root, "x" * 201)
        self.assertFalse((root / "fixture-marker.txt").exists())

    def test_marker_tool_requires_absolute_existing_directory(self):
        with self.assertRaises(ValueError):
            perform_write_marker(Path("relative"), "test")

    def test_server_uses_the_mcp_sdk_shipped_with_hermes(self):
        hermes = shutil.which("hermes")
        if not hermes:
            self.skipTest("Hermes executable unavailable")
        hermes_python = Path(hermes).parent / "python"
        env = os.environ.copy()
        env.pop("HERBERT_FIXTURE_DIR", None)
        result = subprocess.run(
            [str(hermes_python), str(Path(__file__).parents[1] / "herbert_canary" / "fixture_mcp.py")],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HERBERT_FIXTURE_DIR", result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)


if __name__ == "__main__":
    unittest.main()
