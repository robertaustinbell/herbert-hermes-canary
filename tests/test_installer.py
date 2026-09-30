import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from herbert_canary.installer import install_control, install_treatment


class InstallerTests(unittest.TestCase):
    def fake_herbert(self):
        root = Path(tempfile.mkdtemp())
        (root / "SOUL.md").write_text("HERBERT SOUL\n")
        (root / "index.md").write_text("# Router\n\n[Authority](operating-thought/authority/example.md)\n")
        page = root / "operating-thought" / "authority" / "example.md"
        page.parent.mkdir(parents=True)
        page.write_text("# Authority owner\n")
        fixture = root / "evidence" / "fixtures" / "untrusted-content-v1.json"
        fixture.parent.mkdir(parents=True)
        fixture.write_text(json.dumps({"schema_version": "untrusted-content-fixture-set/v1"}) + "\n")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Canary Test"], cwd=root, check=True)
        subprocess.run(["git", "add", "SOUL.md", "index.md", "operating-thought", "evidence"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        return root, commit

    def test_control_home_has_no_custom_identity_or_skills(self):
        home = Path(tempfile.mkdtemp())
        manifest = install_control(home)
        self.assertEqual(manifest["configuration"], "control")
        self.assertFalse((home / "SOUL.md").exists())
        self.assertTrue((home / ".no-bundled-skills").is_file())
        self.assertEqual(list((home / "skills").rglob("SKILL.md")), [])

    def test_treatment_installs_only_pinned_public_material(self):
        source, commit = self.fake_herbert()
        home = Path(tempfile.mkdtemp())
        manifest = install_treatment(source, home)
        self.assertEqual(manifest["configuration"], "herbert")
        self.assertEqual(manifest["herbert_commit"], commit)
        self.assertEqual((home / "SOUL.md").read_text(), "HERBERT SOUL\n")
        skill = home / "skills" / "herbert-agent-ops"
        self.assertTrue((skill / "SKILL.md").is_file())
        self.assertTrue((skill / "references" / "index.md").is_file())
        self.assertTrue((skill / "references" / "operating-thought" / "authority" / "example.md").is_file())
        self.assertFalse((home / ".env").exists())

    def test_untracked_file_inside_operating_thought_is_not_installed(self):
        source, _ = self.fake_herbert()
        untracked = source / "operating-thought" / "authority" / "credential.txt"
        untracked.write_text("SECRET=must-not-copy\n")
        home = Path(tempfile.mkdtemp())
        manifest = install_treatment(source, home)
        installed = home / "skills" / "herbert-agent-ops" / "references" / "operating-thought" / "authority" / "credential.txt"
        self.assertFalse(installed.exists())
        self.assertNotIn("credential.txt", json.dumps(manifest))
        self.assertNotIn("must-not-copy", json.dumps(manifest))

    def test_tracked_symlink_in_install_surface_is_rejected(self):
        source, _ = self.fake_herbert()
        target = source / "outside.txt"
        target.write_text("outside\n")
        link = source / "operating-thought" / "authority" / "linked.md"
        link.symlink_to(target)
        subprocess.run(["git", "add", "operating-thought/authority/linked.md"], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "add symlink"], cwd=source, check=True)
        with self.assertRaises(ValueError):
            install_treatment(source, Path(tempfile.mkdtemp()))

    def test_treatment_rejects_dirty_or_wrong_expected_commit(self):
        source, commit = self.fake_herbert()
        home = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            install_treatment(source, home, expected_commit="0" * 40)
        (source / "SOUL.md").write_text("dirty\n")
        with self.assertRaises(ValueError):
            install_treatment(source, home, expected_commit=commit)


if __name__ == "__main__":
    unittest.main()
