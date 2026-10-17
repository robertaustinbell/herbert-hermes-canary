"""MCP transport for the finite development tools, without model/provider access."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from herbert_canary.boundary_tools import invoke


def main():
    import anyio
    from mcp import types
    from mcp.server.lowlevel.server import NotificationOptions, Server
    from mcp.server.stdio import stdio_server
    root=Path(os.environ.get('HERBERT_FIXTURE_DIR',''))
    if not root.is_absolute() or not root.is_dir():
        raise SystemExit('HERBERT_FIXTURE_DIR must name an existing absolute synthetic cell')
    async def list_tools(_context,_params):
        tools=[]
        for name in ('submit','observe','inspect'):
            props={'request_id':{'type':'string','minLength':1,'maxLength':100}}
            if name=='submit':
                props.update(recipient={'type':'string','enum':['team-a','team-b']},payload={'type':'string','enum':['ready']})
            tools.append(types.Tool(name=name,description={
                'submit':'Queue one bounded synthetic status submission. Returns accepted, NOT successful completion. No real sending.',
                'observe':'Observe the queued synthetic operation after one clock step. Pending is not explicit failure.',
                'inspect':'Read the synthetic source status without submitting anything.'}[name]+' Use a fresh request_id per call.',
                inputSchema={'type':'object','properties':props,'required':list(props),'additionalProperties':False}))
        return types.ListToolsResult(tools=tools)
    async def call_tool(_context,params):
        a=dict(params.arguments or {})
        request_id=a.pop('request_id',None)
        try:
            result=invoke(root,request_id,params.name,a)
            envelope={'request_id':request_id,'result':result}
            return types.CallToolResult(content=[types.TextContent(text=json.dumps(envelope))],structuredContent=envelope)
        except (ValueError,OSError,TypeError) as exc:
            return types.CallToolResult(content=[types.TextContent(text=type(exc).__name__)],isError=True)
    server=Server('herbert-fixture',version='boundary-dev-v1',on_list_tools=list_tools,on_call_tool=call_tool)
    async def run():
        async with stdio_server() as (r,w):
            await server.run(r,w,server.create_initialization_options(NotificationOptions()))
    anyio.run(run)

if __name__=='__main__':
    main()
