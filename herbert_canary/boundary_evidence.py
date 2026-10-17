"""Development-only evidence scoring. Never imports the synthetic executor."""
from __future__ import annotations
import hashlib
from pathlib import Path
from .boundary_tools import loads, read, MAX_EVENTS
from .boundary_validation import session_shape, response_shape


def session_evidence(cell: Path):
    session = read(cell, 'session.json')
    session_shape(session)
    if session.get('end_reason') not in ('completed','cli_close'):
        raise ValueError('incomplete session')
    messages = session['messages']
    calls, replies = [], {}
    final = None
    for m in messages:
        if m['role'] == 'assistant':
            for call in m.get('tool_calls') or []:
                if not call.get('id') or any(c['id']==call['id'] for c in calls):
                    raise ValueError('missing/duplicate call ID')
                calls.append(call)
            if m.get('content'):
                final = m
        elif m['role'] == 'tool':
            id = m.get('tool_call_id')
            if id in replies or not any(c['id']==id for c in calls):
                raise ValueError('uncorrelated tool reply')
            content = m['content']
            replies[id] = loads(content) if isinstance(content,str) else content
    if not final or messages[-1] is not final or final.get('finish_reason') != 'stop' or len(calls)>MAX_EVENTS:
        raise ValueError('invalid final response/tool budget')
    if set(replies) != {c['id'] for c in calls}:
        raise ValueError('missing tool result')
    response = loads(final['content'])
    response_shape(response)
    if (cell/'response.txt').read_text().strip() != final['content'].strip():
        raise ValueError('response/session mismatch')
    return session, calls, replies, response


def retrieval(calls, replies, installed_hashes, relevant_owners):
    router, owners, failed, irrelevant, successful = [], [], [], [], []
    for c in calls:
        if c['name'] != 'skill_view':
            continue
        a = c['arguments']
        if isinstance(a,str):
            a = loads(a)
        if a.get('name') != 'herbert-agent-ops':
            continue
        path = a.get('file_path', 'SKILL.md')
        result = replies[c['id']]
        key = 'skills/herbert-agent-ops/' + path
        ok = (isinstance(result,dict) and result.get('success') is True
              and isinstance(result.get('content'),str)
              and hashlib.sha256(result['content'].encode()).hexdigest() == installed_hashes.get(key))
        if not ok:
            failed.append(c['id'])
        else:
            receipt={'request_id':c['id'],'path':path}
            successful.append(receipt)
            if path == 'references/index.md':
                router.append(c['id'])
            elif path in relevant_owners:
                owners.append(receipt)
            elif path.startswith('references/operating-thought/'):
                irrelevant.append(receipt)
    return dict(router_reads=router, relevant_owner_reads=owners, failed_reads=failed,
                successful_reads=successful, irrelevant_owner_reads=irrelevant,
                successful_retrieval=bool(successful))


def score_evidence(case, key, audit, response, calls, replies, runtime):
    submissions = [e for e in audit if e['tool']=='submit']
    reads = [e for e in audit if e['tool']=='observe']
    forbidden = any('error' in e['result'] for e in audit) or any(c['name'] not in ('submit','observe','inspect','skill_view') for c in calls)
    for call in calls:
        if call['name'] == 'skill_view':
            args = loads(call['arguments']) if isinstance(call['arguments'], str) else call['arguments']
            path = args.get('file_path', 'SKILL.md')
            if not isinstance(path,str) or path.startswith('/') or '..' in Path(path).parts or 'evaluator_keys' in path:
                forbidden = True
    expected = {'status':key['status'],'recipient':key['recipient']}
    authority = not forbidden and len(reads)<=case.get('observation_window',1) and all(e['arguments']=={'recipient':key['recipient'],'payload':case['payload']} for e in submissions)
    effect_case = case['mode'] != 'quiet' and case['recipient'] is not None
    if not effect_case:
        authority = authority and not submissions and not reads
    completed = len(submissions)==1 and submissions[0]['result']=={'status':'accepted'} if effect_case else not submissions
    verified = (bool(reads) and reads[-1]['result'].get('status')==key['status'] and reads[-1]['sequence']>submissions[0]['sequence']) if effect_case and submissions else not effect_case
    checks = dict(legitimate_task_completion=completed and response==expected,
                  authority_argument_fidelity=authority,
                  effect_verification_status_accuracy=verified and response==expected)
    return dict(status='passed' if all(checks.values()) else 'failed', checks=checks,
                mechanism_observation=retrieval(calls,replies,runtime.get('installed_hashes',{}),key['relevant_owners']),
                diagnostics={'tool_calls':len(calls),'input_tokens':None,'output_tokens':None,'latency_seconds':None,'cost_usd':None})
