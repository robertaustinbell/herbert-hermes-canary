"""Typed development evidence checks, before replay or Python equality."""
from .boundary_tools import MAX_EVENTS


def obj(value, required=(), allowed=None):
    if type(value) is not dict or not set(required) <= set(value) or (allowed is not None and not set(value) <= set(allowed)):
        raise ValueError('invalid object shape')


def text(value, maximum=65536):
    if type(value) is not str or not 1 <= len(value) <= maximum:
        raise ValueError('invalid string scalar')


def integer(value, minimum=0, maximum=MAX_EVENTS):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('invalid bounded integer')


def nullable_text(value):
    if value is not None:
        text(value)


def state_shape(value):
    fields=('run_id','cell','mode','status','recipient','payload','observations')
    obj(value,fields,fields)
    for f in ('run_id','cell','mode','status'):
        text(value[f],100)
    for f in ('recipient','payload'):
        nullable_text(value[f])
    integer(value['observations'])


def result_shape(value, tool):
    obj(value)
    if tool=='skill_view':
        if 'success' in value and type(value['success']) is not bool:
            raise ValueError('invalid retrieval success')
        if 'content' in value and type(value['content']) is not str:
            raise ValueError('invalid retrieval content')
        return
    fields= {'error'} if 'error' in value else {'status','recipient','payload','observations'} if tool=='observe' else {'status'}
    obj(value,fields,fields)
    for f in ('error','status'):
        if f in value:
            text(value[f],100)
    if 'observations' in value:
        integer(value['observations'])
        nullable_text(value['recipient'])
        nullable_text(value['payload'])


def audit_shape(value):
    if type(value) is not list or len(value)>MAX_EVENTS:
        raise ValueError('audit bound/shape')
    fields=('run_id','cell','sequence','request_id','tool','arguments','result')
    for e in value:
        obj(e,fields,fields)
        for f in ('run_id','cell','request_id','tool'):
            text(e[f],100)
        integer(e['sequence'],1)
        obj(e['arguments'])
        result_shape(e['result'],e['tool'])


def session_shape(value):
    obj(value,('end_reason','messages','model','provider','reasoning'))
    for f in ('end_reason','model','provider','reasoning'):
        text(value[f])
    for f in ('id','exported_model','exported_provider'):
        if f in value:
            nullable_text(value[f])
    if type(value['messages']) is not list or not 1 <= len(value['messages']) <= 2*MAX_EVENTS+2:
        raise ValueError('invalid bounded messages')
    tools={}
    for m in value['messages']:
        obj(m,('role',))
        role=m['role']
        content=m.get('content')
        valid_content = (type(content) is str or (role=='assistant' and content is None) or (role=='tool' and type(content) is dict))
        if role not in ('user','assistant','tool') or not valid_content:
            raise ValueError('invalid message scalar')
        if 'finish_reason' in m:
            nullable_text(m['finish_reason'])
        calls=m.get('tool_calls')
        if calls is not None:
            if m['role']!='assistant' or type(calls) is not list or len(calls)>MAX_EVENTS:
                raise ValueError('invalid calls shape')
            for c in calls:
                obj(c,('id','name','arguments'),('id','name','arguments','request_id'))
                text(c['id'],100)
                text(c['name'],100)
                if 'request_id' in c:
                    text(c['request_id'],100)
                obj(c['arguments'])
                if c['name']=='skill_view':
                    for field in ('name','file_path'):
                        if field in c['arguments']:
                            text(c['arguments'][field])
                tools[c['id']]=c['name']
        if m['role']=='tool':
            text(m.get('tool_call_id'),100)
            from .boundary_tools import loads
            result_shape(loads(content) if type(content) is str else content,tools.get(m['tool_call_id']))
    if 'usage' in value:
        obj(value['usage'])


def response_shape(value):
    obj(value,('status','recipient'),('status','recipient'))
    text(value['status'],100)
    nullable_text(value['recipient'])


def runtime_shape(value):
    obj(value,('configuration','model','provider','reasoning','custom_skills'))
    for f in ('configuration','model','provider','reasoning'):
        text(value[f])
    integer(value['custom_skills'],0,1)
    for f in ('herbert_commit','source','hermes_version','suite','identity'):
        if f in value:
            text(value[f])
    if 'installed_hashes' in value:
        obj(value['installed_hashes'])
        for k,v in value['installed_hashes'].items():
            text(k)
            text(v,64)
