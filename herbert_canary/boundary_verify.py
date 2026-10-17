"""Independent retained-bundle replay; never invokes subject tools or executor."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from .boundary_tools import loads, read, MAX_BYTES, MAX_EVENTS
from .boundary_evidence import session_evidence, score_evidence
from .boundary_validation import state_shape, audit_shape, runtime_shape, obj, integer, text

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = 'fixtures/consequential-boundary-dev-v1.json'
SCHEMA = 'schemas/consequential-boundary-dev-v1.json'
KEY = 'evaluator_keys/consequential-boundary-dev-v1.json'
SUITE = 'consequential-boundary-dev/v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identities():
    paths = [FIXTURE, SCHEMA, KEY, 'source-pin.json']
    paths += sorted(str(p.relative_to(ROOT)) for p in (ROOT/'herbert_canary').glob('*.py'))
    paths += sorted(str(p.relative_to(ROOT)) for p in (ROOT/'scripts').glob('*.py'))
    return {p:digest(ROOT/p) for p in paths}


def replay(initial, audit):
    """Independent transition implementation, bounded and data-only."""
    state_shape(initial)
    audit_shape(audit)
    state = dict(initial)
    seen = set()
    if not isinstance(audit,list) or len(audit)>MAX_EVENTS:
        raise ValueError('audit bound')
    for i, e in enumerate(audit,1):
        if e['run_id']!=state['run_id'] or e['cell']!=state['cell'] or e['sequence']!=i or e['request_id'] in seen:
            raise ValueError('stale/reordered/duplicate audit')
        seen.add(e['request_id'])
        tool, a = e['tool'],e['arguments']
        expected = {'error':'forbidden_or_invalid_tool_arguments'}
        if tool=='submit' and set(a)=={'recipient','payload'} and a['recipient'] in ('team-a','team-b') and a['payload']=='ready' and state['status']=='idle':
            state['recipient'], state['payload'], state['status'] = a['recipient'], a['payload'], 'accepted'
            expected = {'status':'accepted'}
        elif tool=='observe' and a=={}:
            if state['status']=='accepted':
                state['observations']+=1
                state['status']=state['mode'] if state['mode'] in ('success','failure','pending') else 'pending'
            expected={k:state[k] for k in ('status','recipient','payload','observations')}
        elif tool=='inspect' and a=={}:
            expected={'status':'ready'}
        if e['result'] != expected:
            raise ValueError('fabricated readback or transition')
    return state


def evaluate_cell(cell, case, key, run_id, cell_id, runtime_pin, execution_kind='deterministic', source_commit=None):
    # Root/leaf symlinks are not admissible evidence.
    allowed = {'initial-state.json','state.json','audit.json','tool-audit.jsonl','task.json','prompt.txt',
               'runtime.json','execution.json','score.json','session.json','session.jsonl','response.txt',
               'trace.json','usage.json','runtime-preflight.json','runtime-config.txt','mcp-add-attempt-1.txt',
               'mcp-add-attempt-2.txt','mcp-add.txt','mcp-test.txt','hermes-stdout.txt','hermes-stderr.txt','export.txt'}
    if cell.is_symlink() or any(p.is_symlink() or not p.is_file() or p.name not in allowed or p.stat().st_size>MAX_BYTES for p in cell.iterdir()):
        raise ValueError('unexpected/unbounded/symlink cell artifact')
    initial=read(cell,'initial-state.json')
    expected=dict(run_id=run_id,cell=cell_id,mode=case['mode'],status='idle',recipient=None,payload=None,observations=0)
    state_shape(initial)
    if initial!=expected:
        raise ValueError('stale initial state')
    audit=read(cell,'audit.json')
    final_state=read(cell,'state.json')
    state_shape(final_state)
    if replay(initial,audit)!=final_state:
        raise ValueError('state replay mismatch')
    log=(cell/'tool-audit.jsonl').read_text()
    logged=[loads(s) for s in log.splitlines() if s.strip()]
    audit_shape(logged)
    if len(log.encode())>MAX_BYTES or logged!=audit:
        raise ValueError('audit log mismatch')
    session,calls,replies,response=session_evidence(cell)
    if execution_kind == 'hermes':
        from .boundary_transport import normalize_export
        if normalize_export(cell/'session.jsonl',runtime_pin) != session:
            raise ValueError('raw export/normalized evidence mismatch')
        for exported,requested in [('exported_model','model'),('exported_provider','provider')]:
            if session.get(exported) is not None and session[exported] != runtime_pin[requested]:
                raise ValueError('served runtime identity mismatch')
    if [m['content'] for m in session['messages'] if m['role']=='user'] != [(cell/'prompt.txt').read_text()]:
        raise ValueError('session task mismatch')
    for field in ('model','provider','reasoning'):
        if session.get(field)!=runtime_pin[field]:
            raise ValueError('runtime mismatch')
    # Tool audit and exported request/reply stream must agree exactly and in order.
    actual=[]
    for c in calls:
        if c['name']=='skill_view':
            continue
        actual.append(dict(run_id=run_id,cell=cell_id,sequence=len(actual)+1,request_id=c.get('request_id',c['id']),tool=c['name'],arguments=c['arguments'],result=replies[c['id']]))
    if actual!=audit:
        raise ValueError('tool trace/audit mismatch')
    execution=read(cell,'execution.json')
    obj(execution,('exit_code',))
    integer(execution['exit_code'],0,255)
    if 'session_id' in execution:
        text(execution['session_id'],100)
    if 'elapsed_seconds' in execution:
        elapsed=execution['elapsed_seconds']
        if type(elapsed) not in (int,float) or not 0 <= elapsed < float('inf'):
            raise ValueError('invalid elapsed seconds')
    if execution['exit_code']!=0:
        raise ValueError('execution incomplete')
    runtime=read(cell,'runtime.json')
    runtime_shape(runtime)
    if cell_id.split('/')[0]!='control' and runtime.get('herbert_commit')!=source_commit:
        raise ValueError('treatment source commit mismatch')
    if runtime.get('installed_hashes',{}) != runtime_pin['configuration_hashes'][cell_id.split('/')[0]]:
        raise ValueError('installed content identity mismatch')
    if runtime['configuration']!=cell_id.split('/')[0] or any(runtime.get(f)!=runtime_pin[f] for f in ('model','provider','reasoning')):
        raise ValueError('runtime metadata mismatch')
    score = score_evidence(case,key,audit,response,calls,replies,runtime)
    usage=session.get('usage',{})
    score['diagnostics'].update({k:usage.get(k) for k in ('input_tokens','output_tokens','api_call_count','actual_cost_usd','estimated_cost_usd','cost_status')})
    score['diagnostics']['latency_seconds']=execution.get('elapsed_seconds')
    score['diagnostics']['quiet_policy_read_overhead']=case['mode']=='quiet' and score['mechanism_observation']['successful_retrieval']
    return score


def verify_boundary(output: Path, require_summary=True):
    output=output.resolve()
    try:
        manifest=read(output,'manifest.json')
        obj(manifest,('run_id','runtime','source_pin','pins'))
        text(manifest['run_id'],100)
        obj(manifest['runtime'])
        for f in ('model','provider','reasoning'):
            text(manifest['runtime'][f])
        if manifest['schema_version']!='consequential-boundary-run/v1' or manifest['suite']!=SUITE:
            raise ValueError('unsupported suite/bundle')
        if manifest['execution_kind'] not in ('hermes','deterministic','injected-test'):
            raise ValueError('unknown execution kind')
        from .pinning import load_source_pin, CANONICAL_CASES
        inputs=output/'inputs'
        if inputs.is_symlink() or any(p.is_symlink() or not p.is_file() or p.stat().st_size>MAX_BYTES for p in inputs.iterdir()):
            raise ValueError('invalid retained source inputs')
        retained=read(inputs,'source-pin.json')
        selected=load_source_pin(inputs/'source-pin.json')
        if retained != manifest['source_pin'] or digest(inputs/'source-pin.json') != manifest['source_pin_sha256']:
            raise ValueError('selected source pin identity mismatch')
        if selected['herbert_commit'] != manifest['herbert_commit']:
            raise ValueError('source identity mismatch')
        if digest(inputs/'untrusted-content-v1.json') != selected['fixture_sha256']:
            raise ValueError('retained source fixture digest mismatch')
        source_fixture=read(inputs,'untrusted-content-v1.json')
        if [c['id'] for c in source_fixture['fixtures']] != CANONICAL_CASES:
            raise ValueError('retained source fixture cases mismatch')
        hashes=manifest['runtime']['configuration_hashes']
        if set(hashes)!= {'control','identity-only','herbert'} or hashes['control']!={} or set(hashes['identity-only'])!={'SOUL.md'}:
            raise ValueError('configuration content invariant')
        if hashes['herbert'].get('SOUL.md')!=hashes['identity-only']['SOUL.md']:
            raise ValueError('configuration SOUL mismatch')
        for values in hashes.values():
            if not isinstance(values,dict) or any(not isinstance(k,str) or not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for k,v in values.items()):
                raise ValueError('invalid configuration hashes')
        # Development verifier is deliberately code/content pinned, not a migration tool.
        if manifest['pins']!=identities():
            raise ValueError('stale evaluator/fixture/schema identity')
        fixture=loads((ROOT/FIXTURE).read_text())
        schema=loads((ROOT/SCHEMA).read_text())
        key=loads((ROOT/KEY).read_text())
        cases=fixture['cases']
        planned=[f'{config}/{c["id"]}' for config in schema['configurations'] for c in cases]
        if schema['case_ids']!=[c['id'] for c in cases] or manifest['planned_cells']!=planned:
            raise ValueError('dropped/reordered planned cells')
        from .boundary import build_boundary_prompt
        scores=[]
        for cell_id in planned:
            config,id=cell_id.split('/')
            cell=output/config/id
            case=next(c for c in cases if c['id']==id)
            if (cell/'prompt.txt').read_text()!=build_boundary_prompt(case):
                raise ValueError('fixture task mismatch')
            result=evaluate_cell(cell,case,key['cases'][id],manifest['run_id'],cell_id,manifest['runtime'],manifest['execution_kind'],manifest['herbert_commit'])
            result['cell']=cell_id
            if require_summary and read(cell,'score.json')!=result:
                raise ValueError('stored score mismatch')
            scores.append(result)
        terminal='passed' if all(s['status']=='passed' for s in scores) else 'failed'
        summary=dict(schema_version='consequential-boundary-summary/v1',suite=SUITE,terminal_state=terminal,cells=scores)
        if require_summary and read(output,'summary.json')!=summary:
            raise ValueError('summary/coverage mismatch')
        return dict(status='passed',terminal_state=terminal,summary=summary,errors=[])
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, RecursionError) as exc:
        return dict(status='blocked',terminal_state='blocked',errors=[str(exc)])
