import json
import tempfile
import unittest
from pathlib import Path


class BoundaryTransportTests(unittest.TestCase):
    def test_nested_tool_call_json_duplicate_keys_are_rejected(self):
        from herbert_canary.boundary_transport import normalize_export
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/'session.jsonl'
            path.write_text(json.dumps({'messages':[{'role':'assistant','tool_calls':'[{"id":"a","id":"b","name":"skill_view","arguments":{}}]'}]})+'\n')
            with self.assertRaisesRegex(ValueError,'duplicate'):
                normalize_export(path,{'model':'m','provider':'p','reasoning':'low'})

    def test_hermes_adapter_routes_development_server_and_retains_raw_export(self):
        import subprocess
        import sys
        from herbert_canary.hermes_executor import HermesExecutor
        from herbert_canary.boundary_tools import initialize, write
        from herbert_canary.boundary import deterministic_executor
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            home=root/'home'; home.mkdir()
            cell=root/'cell'; cell.mkdir()
            auth=root/'synthetic-auth.json'; auth.write_text('{}')
            case={'mode':'success','recipient':'team-a','payload':'ready'}
            runtime={'suite':'consequential-boundary-dev/v1','model':'m','provider':'p','reasoning':'low'}
            initialize(cell,case,'run','cell')
            write(cell,'task.json',case)
            (cell/'prompt.txt').write_text('task')
            class LocalAdapter(HermesExecutor):
                server=None
                def preflight(self,home):
                    return {'status':'passed'}
                def _run(self,args,**kwargs):
                    if 'add' in args:
                        self.server=args[-1]
                    if 'chat' in args:
                        deterministic_executor(home,'task',cell,runtime)
                    if 'export' in args:
                        data=json.loads((cell/'session.json').read_text())
                        data.update(id='local',model='m',billing_provider='p')
                        for msg in data['messages']:
                            for c in msg.get('tool_calls',[]):
                                c['arguments']['request_id']=c['id']
                                c['name']='mcp_herbert_fixture_'+c['name']
                            if msg['role']=='tool':
                                msg['content']=json.dumps({'result':json.dumps({'request_id':msg['tool_call_id'],'result':json.loads(msg['content'])})})
                        (cell/'session.jsonl').write_text(json.dumps(data)+'\n')
                        (cell/'session.json').unlink()
                    return subprocess.CompletedProcess(args,0,'Connected','')
            executor=LocalAdapter(hermes_bin=sys.executable,hermes_python=sys.executable,auth_path=auth)
            executor(home,'task',cell,runtime)
            self.assertEqual(Path(executor.server).name,'boundary_mcp.py')
            self.assertTrue((cell/'session.json').is_file())
            self.assertTrue((cell/'session.jsonl').is_file())

    def test_export_retains_outer_id_and_correlates_synthetic_receipt(self):
        from herbert_canary.boundary_transport import normalize_export
        session={'id':'s','end_reason':'completed','input_tokens':17,'output_tokens':5,'actual_cost_usd':None,'messages':[
            {'role':'user','content':'task'},
            {'role':'assistant','tool_calls':[{'id':'outer-1','function':{'name':'mcp_herbert_fixture_submit','arguments':json.dumps({'request_id':'local-1','recipient':'team-a','payload':'ready'})}}]},
            {'role':'tool','tool_call_id':'outer-1','content':json.dumps({'result':json.dumps({'request_id':'local-1','result':{'status':'accepted'}})})},
            {'role':'assistant','content':'{"status":"pending","recipient":"team-a"}','finish_reason':'stop'}]}
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/'session.jsonl'
            path.write_text(json.dumps(session)+'\n')
            normalized=normalize_export(path,{'model':'m','provider':'p','reasoning':'low'})
            self.assertEqual(normalized['usage']['input_tokens'],17)
            self.assertIsNone(normalized['usage']['actual_cost_usd'])
            call=normalized['messages'][1]['tool_calls'][0]
            self.assertEqual(call['id'],'outer-1')
            self.assertEqual(call['request_id'],'local-1')
            self.assertEqual(call['name'],'submit')
            self.assertEqual(json.loads(normalized['messages'][2]['content']),{'status':'accepted'})
            session['messages'][2]['content']=json.dumps({'result':json.dumps({'request_id':'stale','result':{'status':'accepted'}})})
            path.write_text(json.dumps(session)+'\n')
            with self.assertRaisesRegex(ValueError,'request'):
                normalize_export(path,{'model':'m','provider':'p','reasoning':'low'})

if __name__ == '__main__':
    unittest.main()
