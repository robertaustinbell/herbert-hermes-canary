"""Synthetic evidence tampering probes; no model or credential access."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import test_runner
from herbert_canary.hermes_executor import parse_session_export
from herbert_canary.runner import build_prompt, run_canary
from herbert_canary.scorer import validate_run_bundle


def dump(path, value):
    path.write_text(json.dumps(value) + "\n")


def make_bundle():
    source, _, pin = test_runner.RunnerTests().fake_herbert()
    output = Path(tempfile.mkdtemp()) / "run"

    def executor(home, prompt, cell, runtime):
        response = json.dumps({"project_code": "ORCHID-17", "review_date": "2042-05-06", "owner": "Morgan Vale"})
        session = {
            "id": str(cell.relative_to(output)), "end_reason": "completed",
            "model": "synthetic", "billing_provider": "synthetic", "input_tokens": 10,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response, "finish_reason": "stop"},
            ],
        }
        dump(cell / "session.jsonl", session)
        parsed = parse_session_export(cell / "session.jsonl")
        (cell / "response.txt").write_text(response + "\n")
        dump(cell / "trace.json", parsed["trace"])
        dump(cell / "usage.json", parsed["usage"])
        for name, text in {"mcp-test.txt": "Connected\n", "runtime-config.txt": "configured\n", "hermes-stdout.txt": "", "hermes-stderr.txt": ""}.items():
            (cell / name).write_text(text)
        return {"exit_code": 0, "session_id": session["id"]}

    summary = run_canary(source, output, source_pin=pin, model="synthetic", provider="synthetic", reasoning="low", executor=executor, hermes_version="synthetic")
    if summary["terminal_state"] != "passed":
        raise AssertionError(summary["bundle_validation"])
    return output, json.loads((output / "manifest.json").read_text())


class EvidenceIntegrityTests(unittest.TestCase):
    def test_empty_or_partial_suite_is_blocked(self):
        root, manifest = make_bundle()
        for cells in ([], ["control/UTC-BASELINE"], ["../../escape"]):
            with self.subTest(cells=cells):
                changed = {**manifest, "planned_cells": cells}
                dump(root / "manifest.json", changed)
                result = validate_run_bundle(root, changed, require_summary=False)
                self.assertEqual(result["status"], "blocked")
                self.assertIn("noncanonical_planned_cells", result["errors"])

    def test_retained_pin_schema_and_fixture_correlation_are_checked(self):
        root, manifest = make_bundle()
        pin_path = root / manifest["source_pin_path"]
        pin = json.loads(pin_path.read_text())
        for field, value in (("schema_version", "wrong"), ("fixture_sha256", "0" * 64), ("herbert_commit", "0" * 40), ("herbert_commit", []), ("fixture_sha256", {})):
            with self.subTest(field=field, value=value):
                dump(pin_path, {**pin, field: value})
                changed = {**manifest, "source_pin_sha256": hashlib.sha256(pin_path.read_bytes()).hexdigest()}
                dump(root / "manifest.json", changed)
                self.assertEqual(validate_run_bundle(root, changed)["status"], "blocked")

    def test_malformed_tool_calls_block_instead_of_becoming_empty(self):
        from herbert_canary.scorer import score_cell
        root, manifest = make_bundle()
        cell = root / "control/UTC-BASELINE"
        fixture_set = json.loads((root / manifest["fixture_path"]).read_text())
        for payload in ({"tool_calls": [None, 42]}, {"tool_calls": ["skill_manage"]}, []):
            with self.subTest(payload=payload):
                dump(cell / "trace.json", payload)
                self.assertEqual(score_cell(cell, fixture_set["fixtures"][0], fixture_set["task_facts"])["status"], "blocked")
        session_path = cell / "session.jsonl"
        session = json.loads(session_path.read_text())
        session["messages"][-1]["tool_calls"] = ["skill_manage"]
        for payload in (session, [], {**session, "messages": [None]}):
            with self.subTest(session=payload):
                dump(session_path, payload)
                with self.assertRaises(ValueError):
                    parse_session_export(session_path)

    def test_canonical_prompt_and_nonempty_outcomes_are_required(self):
        root, manifest = make_bundle()
        cell = root / "control/UTC-BASELINE"
        session_path = cell / "session.jsonl"
        session = json.loads(session_path.read_text())
        session["messages"][0]["content"] = "different task"
        dump(session_path, session)
        (cell / "prompt.txt").write_text("different task")
        self.assertIn("fixture_prompt_mismatch:control/UTC-BASELINE", validate_run_bundle(root, manifest)["errors"])
        from herbert_canary.scorer import score_cell
        self.assertEqual(score_cell(cell, {"id": "UTC-BASELINE", "expected_outcomes": []}, {"project_code": "ORCHID-17", "review_date": "2042-05-06", "owner": "Morgan Vale"})["status"], "blocked")

    def test_malformed_bundle_shapes_return_blocked(self):
        root, manifest = make_bundle()
        for name, payload in (("runtime.json", []), ("usage.json", None), ("execution.json", []), ("trace.json", [])):
            cell = root / "control/UTC-BASELINE"
            path = cell / name
            original = path.read_text()
            with self.subTest(name=name):
                dump(path, payload)
                self.assertEqual(validate_run_bundle(root, manifest)["status"], "blocked")
            path.write_text(original)

    def test_session_response_trace_prompt_and_usage_are_bound(self):
        root, manifest = make_bundle()
        cell = root / "herbert/UTC-ADVERSARIAL"
        original = json.loads((cell / "session.jsonl").read_text())
        mutations = [
            ("session_response_mismatch", lambda s: s["messages"][-1].update(content="SYNTHETIC-CANARY-NOT-A-SECRET")),
            ("session_trace_mismatch", lambda s: s["messages"][-1].update(tool_calls=[{"name": "skill_manage", "arguments": {}}])),
            ("session_prompt_mismatch", lambda s: s["messages"][0].update(content="different task")),
            ("session_usage_mismatch", lambda s: s.update(input_tokens=9000)),
        ]
        for error, mutate in mutations:
            with self.subTest(error=error):
                changed = json.loads(json.dumps(original))
                mutate(changed)
                dump(cell / "session.jsonl", changed)
                result = validate_run_bundle(root, manifest)
                self.assertEqual(result["status"], "blocked")
                self.assertIn(error + ":herbert/UTC-ADVERSARIAL", result["errors"])
        dump(cell / "session.jsonl", original)
        self.assertEqual(validate_run_bundle(root, manifest)["status"], "passed")


if __name__ == "__main__":
    unittest.main()
