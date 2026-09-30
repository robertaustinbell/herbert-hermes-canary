from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

PIN_SCHEMA = "herbert-hermes-canary-source-pin/v1"
FIXTURE_PATH = "evidence/fixtures/untrusted-content-v1.json"
CANONICAL_CASES = ["UTC-BASELINE", "UTC-POSITIVE-CONTROL", "UTC-ADVERSARIAL"]
SAFE_FIXTURE_ID = re.compile(r"^UTC-[A-Z0-9-]+$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source_pin(path: Path) -> dict[str, Any]:
    try:
        pin = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid source pin: {exc}") from exc
    if not isinstance(pin, dict):
        raise ValueError("source pin must be an object")
    if pin.get("schema_version") != PIN_SCHEMA:
        raise ValueError("unsupported source-pin schema")
    required = {"herbert_commit", "fixture_path", "fixture_sha256", "canonical_cases"}
    missing = sorted(required - set(pin))
    if missing:
        raise ValueError(f"source pin missing fields: {missing}")
    if pin["fixture_path"] != FIXTURE_PATH:
        raise ValueError("source pin does not name the canonical fixture path")
    if pin["canonical_cases"] != CANONICAL_CASES:
        raise ValueError("source pin does not name the canonical fixture cases in order")
    if not isinstance(pin["herbert_commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", pin["herbert_commit"]):
        raise ValueError("source pin commit must be a full lowercase Git SHA")
    if not isinstance(pin["fixture_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", pin["fixture_sha256"]):
        raise ValueError("source pin fixture digest must be a lowercase SHA-256")
    return pin


def validate_pinned_source(source: Path, pin: dict[str, Any]) -> dict[str, Any]:
    source = source.resolve()
    if pin.get("schema_version") != PIN_SCHEMA:
        raise ValueError("unsupported source-pin schema")
    if pin.get("fixture_path") != FIXTURE_PATH:
        raise ValueError("noncanonical fixture path")
    if pin.get("canonical_cases") != CANONICAL_CASES:
        raise ValueError("noncanonical fixture case declaration")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if commit != pin.get("herbert_commit"):
        raise ValueError(f"Herbert commit mismatch: expected {pin.get('herbert_commit')}, observed {commit}")
    fixture_path = source / FIXTURE_PATH
    if any(path.is_symlink() for path in (fixture_path, fixture_path.parent, fixture_path.parent.parent)):
        raise ValueError("canonical fixture path must not contain symlinks")
    fixture_path = fixture_path.resolve()
    try:
        fixture_path.relative_to(source)
    except ValueError as exc:
        raise ValueError("fixture path escapes Herbert source") from exc
    if not fixture_path.is_file() or fixture_path.is_symlink():
        raise ValueError("canonical fixture is missing or symlinked")
    fixture_hash = _sha256(fixture_path)
    if fixture_hash != pin.get("fixture_sha256"):
        raise ValueError("canonical fixture hash mismatch")
    fixture = json.loads(fixture_path.read_text())
    rows = fixture.get("fixtures")
    if not isinstance(rows, list):
        raise ValueError("canonical fixture has no case list")
    fixture_ids = [row.get("id") for row in rows if isinstance(row, dict)]
    if fixture_ids != CANONICAL_CASES:
        raise ValueError("canonical fixture IDs or order changed")
    if any(not isinstance(case_id, str) or not SAFE_FIXTURE_ID.fullmatch(case_id) for case_id in fixture_ids):
        raise ValueError("fixture ID is unsafe as a path component")
    return {
        "herbert_commit": commit,
        "fixture_path": fixture_path,
        "fixture_sha256": fixture_hash,
        "fixture_ids": fixture_ids,
        "fixture": fixture,
    }
