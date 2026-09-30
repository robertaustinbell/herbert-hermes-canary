#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from herbert_canary.hermes_executor import HermesExecutor
from herbert_canary.pinning import load_source_pin
from herbert_canary.runner import run_canary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the six-cell Herbert/Hermes behavioral canary")
    parser.add_argument("--herbert-source", type=Path, required=True)
    parser.add_argument("--source-pin", type=Path, default=ROOT / "source-pin.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--hermes-bin", default="hermes")
    parser.add_argument("--auth-path", type=Path, default=Path.home() / ".hermes" / "auth.json")
    args = parser.parse_args()

    hermes_version = subprocess.check_output([args.hermes_bin, "--version"], text=True).strip()
    source_pin = load_source_pin(args.source_pin)
    executor = HermesExecutor(hermes_bin=args.hermes_bin, auth_path=args.auth_path)
    summary = run_canary(
        args.herbert_source,
        args.output,
        source_pin=source_pin,
        model=args.model,
        provider=args.provider,
        reasoning=args.reasoning,
        executor=executor,
        hermes_version=hermes_version,
    )
    result = {"passed": "pass", "failed": "fail"}.get(summary["terminal_state"], "error")
    print(json.dumps({"result": result, "output": str(args.output.resolve()), **summary}, indent=2, sort_keys=True))
    return {"pass": 0, "fail": 1, "error": 2}[result]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Exception messages may contain provider secrets. Retain only the type.
        print(json.dumps({"result": "error", "error_type": type(exc).__name__}))
        raise SystemExit(2)
