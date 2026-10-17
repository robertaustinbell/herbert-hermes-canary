import json
import os
import subprocess
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from herbert_canary.hermes_executor import (
    HermesExecutor,
    absolute_prompt_path,
    evaluation_toolsets,
    isolated_environment,
    mcp_command_ok,
    parse_session_export,
    sanitize_log,
)


def installed_executor(test):
    selected=os.environ.get('HERMES_CANARY_BIN','hermes')
    explicit=bool(os.environ.get('HERMES_CANARY_BIN') or os.environ.get('HERMES_CANARY_PYTHON'))
    try:
        return HermesExecutor(hermes_bin=selected,hermes_python=os.environ.get('HERMES_CANARY_PYTHON'))
    except ValueError as exc:
        if explicit:
            raise
        test.skipTest('Unavailable documented runtime shape: '+str(exc))


class TraceParsingTests(unittest.TestCase):
    def test_oauth_json_fields_are_redacted(self):
        raw = '{"access_token":"synthetic-not-real","refresh_token": "synthetic-not-real"}'
        self.assertNotIn("synthetic-not-real", sanitize_log(raw))

    def test_log_sanitizer_removes_common_secret_forms_and_ansi(self):
        raw = "\x1b[31mAPI_KEY=supersecretvalue\x1b[0m bearer abcdefghijklmnop sk-abcdefghijklmnopqrstuvwxyz"
        sanitized = sanitize_log(raw)
        self.assertNotIn("supersecretvalue", sanitized)
        self.assertNotIn("abcdefghijklmnop", sanitized)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", sanitized)
        self.assertNotIn("\x1b", sanitized)
        self.assertIn("[REDACTED]", sanitized)

    def test_isolated_environment_drops_evaluator_credentials_and_overrides_home(self):
        home = Path(tempfile.mkdtemp()).resolve()
        base = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "en_US.UTF-8",
            "OPENAI_API_KEY": "must-not-pass",
            "UNRELATED_SECRET": "must-not-pass",
            "HERMES_HOME": "/wrong",
            "HOME": "/wrong",
        }
        result = isolated_environment(home, base)
        self.assertEqual(result["HOME"], str(home))
        self.assertEqual(result["HERMES_HOME"], str(home))
        self.assertNotIn("OPENAI_API_KEY", result)
        self.assertNotIn("UNRELATED_SECRET", result)
        self.assertNotIn("must-not-pass", json.dumps(result))

    def test_model_toolsets_include_skills_and_the_synthetic_server(self):
        self.assertEqual(evaluation_toolsets(), "skills,herbert-fixture")

    @unittest.skipUnless(shutil.which("hermes"), "Optional installed-Hermes integration probe")
    def test_runtime_model_configuration_is_seeded_noninteractively(self):
        home = Path(tempfile.mkdtemp()).resolve()
        cell = Path(tempfile.mkdtemp()).resolve()
        executor = installed_executor(self)
        result = executor.configure_runtime(
            home,
            cell,
            {"model": "gpt-5.6-sol", "provider": "openai-codex", "reasoning": "low"},
        )
        self.assertEqual(result["status"], "passed")
        self.assertTrue((cell / "runtime-config.txt").is_file())

    def test_synthetic_server_retries_one_transient_connection_failure(self):
        class FlakyExecutor(HermesExecutor):
            def __init__(self):
                super().__init__(hermes_bin=sys.executable, hermes_python=sys.executable)
                self.calls = 0

            def _run(self, args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return subprocess.CompletedProcess(args, 0, "✗ Failed to connect: Connection closed", "")
                return subprocess.CompletedProcess(args, 0, "✓ Connected", "")

        home = Path(tempfile.mkdtemp()).resolve()
        cell = Path(tempfile.mkdtemp()).resolve()
        executor = FlakyExecutor()
        result = executor.register_mcp(home, cell)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(executor.calls, 3)
        self.assertTrue((cell / "mcp-add-attempt-1.txt").is_file())

    @unittest.skipUnless(shutil.which("hermes"), "Optional installed-Hermes integration probe")
    def test_synthetic_server_registers_noninteractively(self):
        home = Path(tempfile.mkdtemp()).resolve()
        cell = Path(tempfile.mkdtemp()).resolve()
        (home / ".no-bundled-skills").write_text("test\n")
        (home / "skills").mkdir()
        executor = installed_executor(self)
        result = executor.register_mcp(home, cell)
        self.assertEqual(result["status"], "passed")
        self.assertTrue((home / "config.yaml").is_file())
        self.assertIn("Connected", result["test_output"])
        self.assertTrue((cell / "mcp-add.txt").is_file())
        self.assertTrue((cell / "mcp-test.txt").is_file())

    def test_mcp_semantic_failure_is_not_hidden_by_zero_exit(self):
        class Result:
            returncode = 0
            stdout = "✗ Server not found in config"
            stderr = ""
        self.assertFalse(mcp_command_ok(Result()))

    def test_prompt_path_is_absolute_even_when_cell_directory_is_relative(self):
        path = absolute_prompt_path(Path("runs/example/control/UTC-BASELINE"))
        self.assertTrue(path.is_absolute())
        self.assertEqual(path.name, "prompt.txt")

    def test_export_parser_extracts_final_response_tool_calls_and_usage(self):
        path = Path(tempfile.mkdtemp()) / "export.jsonl"
        session = {
            "id": "session-1",
            "model": "model-a",
            "billing_provider": "provider-a",
            "input_tokens": 10,
            "output_tokens": 5,
            "api_call_count": 2,
            "end_reason": "completed",
            "messages": [
                {"role": "user", "content": "task", "tool_calls": None},
                {"role": "assistant", "content": "", "tool_calls": json.dumps([{"function": {"name": "skill_view", "arguments": "{}"}}])},
                {"role": "tool", "content": "source", "tool_name": "skill_view", "tool_calls": None},
                {"role": "assistant", "content": "Project code: ORCHID-17", "tool_calls": None, "finish_reason": "stop"},
            ],
        }
        path.write_text(json.dumps(session) + "\n")
        parsed = parse_session_export(path)
        self.assertEqual(parsed["session_id"], "session-1")
        self.assertEqual(parsed["response"], "Project code: ORCHID-17")
        self.assertEqual(parsed["trace"]["tool_calls"][0]["name"], "skill_view")
        self.assertEqual(parsed["usage"]["input_tokens"], 10)
        self.assertEqual(parsed["usage"]["api_call_count"], 2)

    def test_export_parser_rejects_zero_or_multiple_sessions(self):
        root = Path(tempfile.mkdtemp())
        empty = root / "empty.jsonl"
        empty.write_text("")
        with self.assertRaises(ValueError):
            parse_session_export(empty)
        multiple = root / "multiple.jsonl"
        multiple.write_text("{}\n{}\n")
        with self.assertRaises(ValueError):
            parse_session_export(multiple)

    def test_export_parser_rejects_unsuccessful_end_state(self):
        path = Path(tempfile.mkdtemp()) / "export.jsonl"
        path.write_text(json.dumps({
            "id": "s",
            "end_reason": "error",
            "messages": [{"role": "assistant", "content": "plausible", "finish_reason": "stop"}],
        }) + "\n")
        with self.assertRaises(ValueError):
            parse_session_export(path)

    def test_export_parser_rejects_missing_final_assistant_response(self):
        path = Path(tempfile.mkdtemp()) / "export.jsonl"
        path.write_text(json.dumps({"id": "s", "messages": [{"role": "user", "content": "x"}]}) + "\n")
        with self.assertRaises(ValueError):
            parse_session_export(path)


if __name__ == "__main__":
    unittest.main()
