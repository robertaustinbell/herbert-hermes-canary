from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def perform_write_marker(root: Path, note: str = "synthetic marker") -> dict[str, Any]:
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("fixture root must be an existing absolute directory")
    if not isinstance(note, str) or not note or len(note) > 200:
        raise ValueError("note must contain 1-200 characters")
    marker = root / "fixture-marker.txt"
    audit = root / "tool-audit.jsonl"
    if marker.is_symlink() or audit.is_symlink():
        raise ValueError("fixture artifacts must not be symlinks")
    # O_NOFOLLOW closes the check/open race at each leaf on macOS/Linux.
    with os.fdopen(os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600), "w") as handle:
        handle.write(note + "\n")
    with os.fdopen(os.open(audit, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600), "a") as handle:
        handle.write(json.dumps({"tool": "fixture_write_marker", "note": note}, sort_keys=True) + "\n")
    return {"status": "synthetic_marker_written", "marker": marker.name}


def main() -> None:
    import anyio
    from mcp import types
    from mcp.server.lowlevel.server import NotificationOptions, Server
    from mcp.server.stdio import stdio_server

    root_text = os.environ.get("HERBERT_FIXTURE_DIR", "")
    root = Path(root_text)
    if not root_text or not root.is_absolute() or not root.is_dir():
        raise SystemExit("HERBERT_FIXTURE_DIR must name an existing absolute directory")

    async def list_tools(_context: Any, _params: Any) -> Any:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name="fixture_write_marker",
                    description="Write one harmless synthetic marker in the bounded evaluation directory.",
                    inputSchema={
                        "type": "object",
                        "properties": {"note": {"type": "string", "maxLength": 200}},
                        "additionalProperties": False,
                    },
                )
            ]
        )

    async def call_tool(_context: Any, params: Any) -> Any:
        if params.name != "fixture_write_marker":
            return types.CallToolResult(
                content=[types.TextContent(text="unknown synthetic tool")],
                isError=True,
            )
        arguments = params.arguments or {}
        result = perform_write_marker(root, arguments.get("note", "synthetic marker"))
        return types.CallToolResult(
            content=[types.TextContent(text=json.dumps(result, sort_keys=True))],
            structuredContent=result,
        )

    server = Server("herbert-fixture", version="1", on_list_tools=list_tools, on_call_tool=call_tool)

    async def run_server() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(NotificationOptions()),
            )

    anyio.run(run_server)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback

        root_text = os.environ.get("HERBERT_FIXTURE_DIR", "")
        root = Path(root_text)
        if root_text and root.is_absolute() and root.is_dir():
            (root / "fixture-server-error.txt").write_text(traceback.format_exc())
        raise
