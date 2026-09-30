from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any


def absolute_prompt_path(cell_dir: Path) -> Path:
    return cell_dir.resolve() / "prompt.txt"


def evaluation_toolsets() -> str:
    return "skills,herbert-fixture"


def isolated_environment(home: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    source = os.environ if base is None else base
    allowed = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP", "TZ")
    env = {key: source[key] for key in allowed if source.get(key)}
    env.update(
        {
            "HOME": str(home.resolve()),
            "HERMES_HOME": str(home.resolve()),
            "NO_COLOR": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env


def sanitize_log(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    text = re.sub(
        r'(?i)("(?:access_token|refresh_token|id_token|api[_-]?key|password|secret)"\s*:\s*)"(?:\\.|[^"\\])*"',
        lambda match: match.group(1) + '"[REDACTED]"', text,
    )
    text = re.sub(
        r"(?i)\b(api[_-]?key|secret|password|passwd|token)\s*[=:]\s*[^\s]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        text,
    )
    text = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", "bearer [REDACTED]", text)
    text = re.sub(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b", "[REDACTED]", text)
    return text


def mcp_command_ok(result: Any) -> bool:
    text = f"{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}".lower()
    failure_markers = ("✗", "failed to connect", "not found in config", "traceback")
    return getattr(result, "returncode", 1) == 0 and not any(marker in text for marker in failure_markers)


def _normalized_calls(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, ""):
        return []
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        raise ValueError("session tool_calls must be a list or JSON list")
    calls: list[dict[str, Any]] = []
    for call in raw:
        if not isinstance(call, dict):
            raise ValueError("session tool_calls entries must be objects")
        function = call.get("function")
        if isinstance(function, dict):
            calls.append({
                "name": function.get("name", ""),
                "arguments": function.get("arguments", ""),
                "id": call.get("id"),
            })
        else:
            calls.append({"name": call.get("name", ""), "arguments": call.get("arguments", {}), "id": call.get("id")})
    return calls


def parse_session_export(path: Path) -> dict[str, Any]:
    sessions = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(sessions) != 1:
        raise ValueError(f"expected exactly one exported session, observed {len(sessions)}")
    session = sessions[0]
    if not isinstance(session, dict):
        raise ValueError("exported session must be an object")
    messages = session.get("messages")
    if not isinstance(messages, list) or any(not isinstance(message, dict) for message in messages):
        raise ValueError("exported session messages must be a list of objects")
    end_reason = session.get("end_reason")
    if end_reason not in {"cli_close", "completed"}:
        raise ValueError(f"exported session did not end successfully: {end_reason}")
    final_assistant_messages = [
        message
        for message in messages
        if message.get("role") == "assistant" and message.get("content")
    ]
    if not final_assistant_messages:
        raise ValueError("exported session has no final assistant response")
    final_assistant = final_assistant_messages[-1]
    if final_assistant.get("finish_reason") != "stop":
        raise ValueError(f"final assistant response did not stop cleanly: {final_assistant.get('finish_reason')}")
    calls: list[dict[str, Any]] = []
    for message in messages:
        calls.extend(_normalized_calls(message.get("tool_calls")))
    usage_keys = (
        "model",
        "billing_provider",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "api_call_count",
        "estimated_cost_usd",
        "actual_cost_usd",
        "cost_status",
        "end_reason",
    )
    return {
        "session_id": session.get("id"),
        "user_prompts": [message.get("content") for message in messages if message.get("role") == "user"],
        "response": final_assistant["content"],
        "trace": {"session_id": session.get("id"), "tool_calls": calls},
        "usage": {key: session.get(key) for key in usage_keys},
    }


class HermesExecutor:
    def __init__(
        self,
        *,
        hermes_bin: str = "hermes",
        auth_path: Path | None = None,
        max_turns: int = 4,
    ) -> None:
        resolved = shutil.which(hermes_bin) if not Path(hermes_bin).is_absolute() else hermes_bin
        if not resolved:
            raise ValueError(f"Hermes executable not found: {hermes_bin}")
        self.hermes_bin = str(Path(resolved).resolve())
        self.hermes_python = str(Path(resolved).parent / "python")
        self.auth_path = (auth_path or (Path.home() / ".hermes" / "auth.json")).resolve()
        self.max_turns = max_turns
        self.fixture_server = Path(__file__).resolve().with_name("fixture_mcp.py")

    def _run(
        self,
        args: list[str],
        *,
        env: dict[str, str],
        cwd: Path,
        timeout: int = 180,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            env=env,
            cwd=cwd,
            text=True,
            input=input_text,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def configure_runtime(self, home: Path, cell_dir: Path, runtime: dict[str, Any]) -> dict[str, str]:
        env = isolated_environment(home)
        outputs: list[str] = []
        settings = (
            ("model.provider", runtime["provider"]),
            ("model.default", runtime["model"]),
            ("agent.reasoning_effort", runtime["reasoning"]),
        )
        for key, value in settings:
            result = self._run(
                [self.hermes_bin, "config", "set", key, str(value)],
                env=env,
                cwd=cell_dir,
            )
            outputs.append(sanitize_log(result.stdout + result.stderr))
            if result.returncode != 0:
                (cell_dir / "runtime-config.txt").write_text("\n".join(outputs))
                raise RuntimeError(f"failed to seed isolated Hermes setting: {key}")
        retained = "\n".join(outputs)
        (cell_dir / "runtime-config.txt").write_text(retained)
        return {"status": "passed", "output": retained}

    def register_mcp(self, home: Path, cell_dir: Path) -> dict[str, str]:
        env = isolated_environment(home)
        add = None
        add_output = ""
        for attempt in (1, 2):
            add = self._run(
                [
                    self.hermes_bin,
                    "mcp",
                    "add",
                    "herbert-fixture",
                    "--command",
                    self.hermes_python,
                    "--env",
                    f"HERBERT_FIXTURE_DIR={cell_dir.resolve()}",
                    "--args",
                    str(self.fixture_server),
                ],
                env=env,
                cwd=cell_dir,
                input_text="\n",
            )
            add_output = sanitize_log(add.stdout + add.stderr)
            (cell_dir / f"mcp-add-attempt-{attempt}.txt").write_text(add_output)
            if mcp_command_ok(add):
                break
        (cell_dir / "mcp-add.txt").write_text(add_output)
        if add is None or not mcp_command_ok(add):
            raise RuntimeError(f"failed to register synthetic MCP server after 2 attempts: {getattr(add, 'returncode', 'unknown')}")
        test = self._run(
            [self.hermes_bin, "mcp", "test", "herbert-fixture"],
            env=env,
            cwd=cell_dir,
        )
        test_output = sanitize_log(test.stdout + test.stderr)
        (cell_dir / "mcp-test.txt").write_text(test_output)
        if not mcp_command_ok(test):
            raise RuntimeError(f"synthetic MCP server preflight failed: {test.returncode}")
        return {"status": "passed", "add_output": add_output, "test_output": test_output}

    def __call__(self, home: Path, prompt: str, cell_dir: Path, runtime: dict[str, Any]) -> dict[str, Any]:
        cell_dir = cell_dir.resolve()
        if not self.auth_path.is_file():
            raise ValueError(f"Hermes authentication record unavailable: {self.auth_path}")
        auth_link = home / "auth.json"
        auth_link.symlink_to(self.auth_path)
        env = isolated_environment(home)
        source = f"herbert-canary-{uuid.uuid4().hex}"

        self.configure_runtime(home, cell_dir, runtime)
        self.register_mcp(home, cell_dir)

        prompt_path = absolute_prompt_path(cell_dir)
        if prompt_path.read_text() != prompt:
            raise ValueError("prompt artifact does not match executor input")
        chat = self._run(
            [
                self.hermes_bin,
                "chat",
                "--query-file",
                str(prompt_path),
                "-Q",
                "--source",
                source,
                "-m",
                runtime["model"],
                "--provider",
                runtime["provider"],
                "--reasoning",
                runtime["reasoning"],
                "-t",
                evaluation_toolsets(),
                "--max-turns",
                str(self.max_turns),
            ],
            env=env,
            cwd=cell_dir,
            timeout=300,
        )
        (cell_dir / "hermes-stdout.txt").write_text(sanitize_log(chat.stdout))
        (cell_dir / "hermes-stderr.txt").write_text(sanitize_log(chat.stderr))
        if chat.returncode != 0:
            raise RuntimeError(f"Hermes cell failed: {chat.returncode}")

        export_path = cell_dir / "session.jsonl"
        export = self._run(
            [
                self.hermes_bin,
                "sessions",
                "export",
                str(export_path),
                "--format",
                "jsonl",
                "--source",
                source,
                "--yes",
                "--redact",
            ],
            env=env,
            cwd=cell_dir,
        )
        (cell_dir / "export.txt").write_text(sanitize_log(export.stdout + export.stderr))
        if export.returncode != 0:
            raise RuntimeError(f"Hermes session export failed: {export.returncode}")
        parsed = parse_session_export(export_path)
        (cell_dir / "response.txt").write_text(parsed["response"] + ("" if parsed["response"].endswith("\n") else "\n"))
        (cell_dir / "trace.json").write_text(json.dumps(parsed["trace"], indent=2, sort_keys=True) + "\n")
        (cell_dir / "usage.json").write_text(json.dumps(parsed["usage"], indent=2, sort_keys=True) + "\n")
        return {
            "exit_code": chat.returncode,
            "session_id": parsed["session_id"],
            "source": source,
            "mcp_preflight": "passed",
        }
