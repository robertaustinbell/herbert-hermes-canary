import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from herbert_canary.pinning import load_source_pin, validate_pinned_source


class SourcePinTests(unittest.TestCase):
    def make_source(self, fixture_ids=None):
        fixture_ids = fixture_ids or ["UTC-BASELINE", "UTC-POSITIVE-CONTROL", "UTC-ADVERSARIAL"]
        root = Path(tempfile.mkdtemp())
        (root / "SOUL.md").write_text("soul\n")
        (root / "index.md").write_text("index\n")
        page = root / "operating-thought" / "owner.md"
        page.parent.mkdir()
        page.write_text("owner\n")
        fixture = root / "evidence" / "fixtures" / "untrusted-content-v1.json"
        fixture.parent.mkdir(parents=True)
        fixture.write_text(json.dumps({
            "schema_version": "untrusted-content-fixture-set/v1",
            "authenticated_task": {"instruction": "task", "allowed_effects": ["return_text_response"]},
            "task_facts": {"project_code": "ORCHID-17", "review_date": "2042-05-06", "owner": "Morgan Vale"},
            "fixtures": [{"id": fixture_id, "source_content": "source", "expected_outcomes": ["useful_task_completion"]} for fixture_id in fixture_ids],
        }, sort_keys=True) + "\n")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Canary Test"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "source"], cwd=root, check=True)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        pin = {
            "schema_version": "herbert-hermes-canary-source-pin/v1",
            "herbert_commit": commit,
            "fixture_path": "evidence/fixtures/untrusted-content-v1.json",
            "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "canonical_cases": ["UTC-BASELINE", "UTC-POSITIVE-CONTROL", "UTC-ADVERSARIAL"],
        }
        return root, fixture, pin

    def test_canonical_fixture_symlink_is_rejected(self):
        source, fixture, pin = self.make_source()
        target = source / "other-fixture.json"
        fixture.rename(target)
        fixture.symlink_to(target)
        with self.assertRaises(ValueError):
            validate_pinned_source(source, pin)

    def test_matching_source_pin_passes(self):
        source, _, pin = self.make_source()
        result = validate_pinned_source(source, pin)
        self.assertEqual(result["fixture_ids"], pin["canonical_cases"])
        self.assertEqual(result["herbert_commit"], pin["herbert_commit"])

    def test_commit_hash_and_canonical_case_drift_are_rejected(self):
        source, _, pin = self.make_source(["UTC-BASELINE"])
        with self.assertRaises(ValueError):
            validate_pinned_source(source, pin)
        pin["canonical_cases"] = ["UTC-BASELINE"]
        pin["herbert_commit"] = "0" * 40
        with self.assertRaises(ValueError):
            validate_pinned_source(source, pin)

    def test_fixture_hash_drift_is_rejected(self):
        source, _, pin = self.make_source()
        pin["fixture_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            validate_pinned_source(source, pin)

    def test_path_unsafe_fixture_id_is_rejected(self):
        source, fixture, pin = self.make_source()
        data = json.loads(fixture.read_text())
        data["fixtures"][0]["id"] = "../../escaped-cell"
        fixture.write_text(json.dumps(data, sort_keys=True) + "\n")
        subprocess.run(["git", "add", str(fixture.relative_to(source))], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "unsafe fixture"], cwd=source, check=True)
        pin["herbert_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        pin["fixture_sha256"] = hashlib.sha256(fixture.read_bytes()).hexdigest()
        pin["canonical_cases"][0] = "../../escaped-cell"
        with self.assertRaises(ValueError):
            validate_pinned_source(source, pin)

    def test_load_source_pin_requires_exact_schema(self):
        path = Path(tempfile.mkdtemp()) / "pin.json"
        path.write_text('{"schema_version":"wrong"}\n')
        with self.assertRaises(ValueError):
            load_source_pin(path)


if __name__ == "__main__":
    unittest.main()
