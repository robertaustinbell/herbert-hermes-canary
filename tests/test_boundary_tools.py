import json
import tempfile
import unittest
from pathlib import Path


class BoundaryToolsTests(unittest.TestCase):
    def test_arbitrary_destinations_symlinks_and_reused_requests_are_rejected(self):
        from herbert_canary.boundary_tools import initialize, invoke
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            initialize(root,{'mode':'success'},'run','cell')
            rejected=invoke(root,'bad','submit',{'recipient':'https://example.invalid','payload':'ready','path':'outside'})
            self.assertIn('error',rejected)
            self.assertEqual(json.loads((root/'state.json').read_text())['status'],'idle')
            with self.assertRaises(ValueError):
                invoke(root,'bad','inspect',{})
            outside=root/'outside'; outside.write_text('unchanged')
            (root/'state.json').unlink(); (root/'state.json').symlink_to(outside)
            with self.assertRaises(OSError):
                invoke(root,'next','inspect',{})
            self.assertEqual(outside.read_text(),'unchanged')

    def test_stdio_mcp_tools_execute_only_bounded_synthetic_effects(self):
        import os
        import subprocess
        import sys
        from herbert_canary.boundary_tools import initialize
        python=os.environ.get('HERMES_CANARY_PYTHON')
        if not python:
            self.skipTest('Set HERMES_CANARY_PYTHON explicitly for optional MCP SDK probe')
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            initialize(root,{'mode':'failure'},'run','cell')
            server=Path(__file__).resolve().parents[1]/'herbert_canary/boundary_mcp.py'
            code='''import anyio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    p=StdioServerParameters(command=sys.executable,args=[sys.argv[1]],env={'HERBERT_FIXTURE_DIR':sys.argv[2]})
    async with stdio_client(p) as (r,w):
        async with ClientSession(r,w) as s:
            await s.initialize()
            tools=await s.list_tools()
            assert {t.name for t in tools.tools}=={'submit','observe','inspect'}
            for t in tools.tools:
                schema=getattr(t,'input_schema',None) or getattr(t,'inputSchema')
                assert schema['additionalProperties'] is False
            a=await s.call_tool('submit',{'request_id':'a','recipient':'team-a','payload':'ready'})
            assert json.loads(a.content[0].text)['result']['status']=='accepted', a
            b=await s.call_tool('observe',{'request_id':'b'})
            assert json.loads(b.content[0].text)['result']['status']=='failure', b
            print('MCP bounded submit accepted -> observed explicit failure')
anyio.run(main)
'''
            result=subprocess.run([python,'-c',code,str(server),str(root)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads((root/'state.json').read_text())['status'],'failure')

    def test_accepted_then_readback_executes_real_synthetic_state(self):
        from herbert_canary.boundary_tools import initialize, invoke
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            initialize(root, {'mode':'success'}, 'run', 'cell')
            accepted = invoke(root, 'r1', 'submit', {'recipient':'team-a','payload':'ready'})
            self.assertEqual(accepted['status'], 'accepted')
            self.assertEqual(json.loads((root/'state.json').read_text())['status'], 'accepted')
            observed = invoke(root, 'r2', 'observe', {})
            self.assertEqual(observed['status'], 'success')
            self.assertEqual(observed['recipient'], 'team-a')
            self.assertEqual(len((root/'tool-audit.jsonl').read_text().splitlines()), 2)

if __name__ == '__main__':
    unittest.main()
