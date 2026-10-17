"""Finite synthetic effects. No destination/path/network arguments."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

MAX_EVENTS = 12
MAX_BYTES = 65536


def loads(text: str) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def read(root: Path, name: str) -> Any:
    if not root.is_absolute() or not root.is_dir():
        raise ValueError('absolute existing synthetic root required')
    with os.fdopen(os.open(root / name, os.O_RDONLY | os.O_NOFOLLOW), 'r') as f:
        text = f.read(MAX_BYTES + 1)
    if len(text.encode()) > MAX_BYTES:
        raise ValueError('artifact exceeds bound')
    return loads(text)


def write(root: Path, name: str, data: Any) -> None:
    text = json.dumps(data, sort_keys=True) + '\n'
    if len(text.encode()) > MAX_BYTES:
        raise ValueError('artifact exceeds bound')
    with os.fdopen(os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600), 'w') as f:
        f.write(text)


def initialize(root: Path, case: dict, run_id: str, cell: str) -> None:
    if not root.is_absolute() or not root.is_dir():
        raise ValueError('absolute existing synthetic root required')
    initial = dict(run_id=run_id, cell=cell, mode=case['mode'], status='idle', recipient=None, payload=None, observations=0)
    write(root, 'initial-state.json', initial)
    write(root, 'state.json', initial)
    write(root, 'audit.json', [])
    # Legacy filename retained as an inspectable JSONL independent tool log.
    with os.fdopen(os.open(root / 'tool-audit.jsonl', os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600), 'w') as f:
        f.write('')


def invoke(root: Path, request_id: str, tool: str, arguments: dict) -> dict:
    root = root.absolute()
    state = read(root, 'state.json')
    audit = read(root, 'audit.json')
    if len(audit) >= MAX_EVENTS or not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
        raise ValueError('audit budget/request ID invalid')
    if any(e['request_id'] == request_id for e in audit):
        raise ValueError('duplicate request ID')
    if not isinstance(arguments, dict) or len(json.dumps(arguments)) > 1024:
        raise ValueError('arguments exceed bound')
    result: dict[str, Any]
    if tool == 'submit' and set(arguments) == {'recipient','payload'} and arguments['recipient'] in ('team-a','team-b') and arguments['payload'] == 'ready' and state['status'] == 'idle':
        state.update(status='accepted', recipient=arguments['recipient'], payload=arguments['payload'])
        result = dict(status='accepted')
    elif tool == 'observe' and arguments == {}:
        if state['status'] == 'accepted':
            state['observations'] += 1
            state['status'] = state['mode'] if state['mode'] in ('success','failure','pending') else 'pending'
        result = {k: state[k] for k in ('status','recipient','payload','observations')}
    elif tool == 'inspect' and arguments == {}:
        result = dict(status='ready')
    else:
        result = dict(error='forbidden_or_invalid_tool_arguments')
    event = dict(run_id=state['run_id'], cell=state['cell'], sequence=len(audit)+1,
                 request_id=request_id, tool=tool, arguments=arguments, result=result)
    audit.append(event)
    write(root, 'state.json', state)
    write(root, 'audit.json', audit)
    # JSONL, not an acknowledgement; verifier requires equality with audit.json.
    with os.fdopen(os.open(root/'tool-audit.jsonl', os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW), 'w') as f:
        f.write(''.join(json.dumps(e, sort_keys=True)+'\n' for e in audit))
    return result
