"""Fail-closed normalization of retained Hermes exports for the new suite only."""
from __future__ import annotations
from .boundary_tools import loads, MAX_BYTES
from .hermes_executor import _normalized_calls


def normalize_export(path, runtime):
    text=path.read_text()
    if len(text.encode())>MAX_BYTES:
        raise ValueError('session exceeds development bound')
    sessions=[loads(line) for line in text.splitlines() if line.strip()]
    if len(sessions)!=1:
        raise ValueError('one session required')
    raw=sessions[0]
    messages=[]
    pending={}
    for message in raw['messages']:
        m=dict(message)
        if m['role']=='assistant':
            raw_calls=m.get('tool_calls')
            if isinstance(raw_calls,str) and raw_calls:
                raw_calls=loads(raw_calls)
            calls=_normalized_calls(raw_calls)
            for c in calls:
                args=loads(c['arguments']) if isinstance(c['arguments'],str) else dict(c['arguments'])
                name=c['name']
                if name in ('mcp_herbert_fixture_submit','mcp_herbert_fixture_observe','mcp_herbert_fixture_inspect'):
                    c['name']=name.removeprefix('mcp_herbert_fixture_')
                    c['request_id']=args.pop('request_id')
                c['arguments']=args
                if not c.get('id') or c['id'] in pending:
                    raise ValueError('missing/duplicate outer request ID')
                pending[c['id']]=c
            m['tool_calls']=calls
        elif m['role']=='tool':
            id=m.get('tool_call_id')
            if id not in pending:
                raise ValueError('uncorrelated outer request')
            call=pending[id]
            result=loads(m['content']) if isinstance(m['content'],str) else m['content']
            if call['name'] in ('submit','observe','inspect'):
                if isinstance(result,dict) and set(result)=={'result'}:
                    result=loads(result['result']) if isinstance(result['result'],str) else result['result']
                if result.get('request_id')!=call.get('request_id'):
                    raise ValueError('synthetic request receipt mismatch')
                result=result['result']
            m['content']=__import__('json').dumps(result)
        messages.append(m)
    return dict(id=raw.get('id'),end_reason=raw.get('end_reason'),messages=messages,
                # Requested identity is retained separately from exported served identity.
                usage={f:raw.get(f) for f in ('input_tokens','output_tokens','api_call_count','actual_cost_usd','estimated_cost_usd','cost_status')},
                exported_model=raw.get('model'),exported_provider=raw.get('billing_provider'),
                **{f:runtime[f] for f in ('model','provider','reasoning')})
