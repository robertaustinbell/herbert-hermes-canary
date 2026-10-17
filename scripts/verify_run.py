#!/usr/bin/env python3
"""Recompute a retained bundle's scores without calling a model."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from herbert_canary.scorer import validate_run_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    try:
        from herbert_canary.boundary_tools import loads
        manifest = loads((args.run_directory / "manifest.json").read_text())
        if manifest.get('schema_version') == 'consequential-boundary-run/v1':
            from herbert_canary.boundary_verify import verify_boundary
            validation = verify_boundary(args.run_directory)
            state = validation['terminal_state']
            result = {'passed':'pass','failed':'fail'}.get(state,'error')
            print(json.dumps({'result':result,'validation':validation},indent=2,sort_keys=True))
            return {'pass':0,'fail':1,'error':2}[result]
        validation = validate_run_bundle(args.run_directory, manifest)
        summary = json.loads((args.run_directory / "summary.json").read_text())
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"result": "error", "error_type": type(exc).__name__}))
        return 2
    state = summary.get("terminal_state") if validation["status"] == "passed" else "blocked"
    result = {"passed": "pass", "failed": "fail"}.get(state, "error")
    print(json.dumps({"result": result, "validation": validation}, indent=2, sort_keys=True))
    return {"pass": 0, "fail": 1, "error": 2}[result]


if __name__ == "__main__":
    raise SystemExit(main())
