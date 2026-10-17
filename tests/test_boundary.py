import json
import tempfile
import unittest
from pathlib import Path


class BoundaryRunTests(unittest.TestCase):
    def test_successful_request_correlated_router_read_from_real_installed_file(self):
        from test_runner import RunnerTests
        from herbert_canary.boundary import run_boundary, deterministic_executor
        from herbert_canary.boundary_tools import read,write
        from herbert_canary.boundary_verify import verify_boundary
        source,_,pin=RunnerTests().fake_herbert()
        def executor(home,prompt,cell,runtime):
            execution=deterministic_executor(home,prompt,cell,runtime)
            if runtime['configuration']=='herbert':
                content=(home/'skills/herbert-agent-ops/references/index.md').read_text()
                session=read(cell,'session.json')
                session['messages'][1:1]=[
                    {'role':'assistant','content':'','tool_calls':[{'id':'router-request','name':'skill_view','arguments':{'name':'herbert-agent-ops','file_path':'references/index.md'}}]},
                    {'role':'tool','tool_call_id':'router-request','content':json.dumps({'success':True,'content':content})}]
                write(cell,'session.json',session)
            return execution
        with tempfile.TemporaryDirectory() as raw:
            output=Path(raw)/'run'
            result=run_boundary(source,output,source_pin=pin,model='deterministic',provider='local',reasoning='none',executor=executor,hermes_version='not-used')
            self.assertEqual(result['terminal_state'],'passed')
            observed=next(c for c in result['cells'] if c['cell']=='herbert/redirect')['mechanism_observation']
            self.assertEqual(observed['router_reads'],['router-request'])
            self.assertTrue(observed['successful_retrieval'])
            self.assertEqual(verify_boundary(output)['status'],'passed')

    def test_deterministic_cli_run_and_verify_new_suite(self):
        import subprocess
        import sys
        from test_runner import RunnerTests
        source,_,pin=RunnerTests().fake_herbert()
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            pinfile=root/'pin.json'
            pinfile.write_text(json.dumps(pin))
            repo=Path(__file__).resolve().parents[1]
            run=subprocess.run([sys.executable,str(repo/'scripts/run_canary.py'),'--suite','consequential-boundary-dev/v1','--executor','deterministic','--herbert-source',str(source),'--source-pin',str(pinfile),'--output',str(root/'run'),'--model','deterministic','--provider','local','--reasoning','none'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            verify=subprocess.run([sys.executable,str(repo/'scripts/verify_run.py'),str(root/'run')],capture_output=True,text=True)
            self.assertEqual(verify.returncode,0,verify.stdout+verify.stderr)

    def test_default_selected_pin_is_still_accepted(self):
        import subprocess
        import sys
        repo=Path(__file__).resolve().parents[1]
        source=repo/'.cache/herbert'
        if not (source/'.git').exists():
            self.skipTest('local pinned Herbert checkout unavailable; no network fetch')
        with tempfile.TemporaryDirectory() as raw:
            result=subprocess.run([sys.executable,str(repo/'scripts/run_canary.py'),'--suite','consequential-boundary-dev/v1','--executor','deterministic','--herbert-source',str(source),'--output',str(Path(raw)/'run'),'--model','deterministic','--provider','local','--reasoning','none'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            selected=json.loads((Path(raw)/'run/inputs/source-pin.json').read_text())
            self.assertEqual(selected,json.loads((repo/'source-pin.json').read_text()))

    def test_real_tools_end_to_end_three_configurations_and_independent_verify(self):
        from herbert_canary.boundary import run_boundary, deterministic_executor
        from herbert_canary.boundary_verify import verify_boundary
        from test_runner import RunnerTests
        source, _, pin = RunnerTests().fake_herbert()
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)/'run'
            result = run_boundary(source, output, source_pin=pin, model='deterministic', provider='local', reasoning='none', executor=deterministic_executor, hermes_version='not-used')
            self.assertEqual(result['terminal_state'], 'passed')
            self.assertEqual(len(result['cells']), 27)
            self.assertIsInstance(result['cells'][0]['diagnostics']['latency_seconds'],float)
            self.assertEqual(verify_boundary(output)['status'], 'passed')
            prompts = [(output/c/'redirect'/'prompt.txt').read_text() for c in ('control','identity-only','herbert')]
            self.assertEqual(len(set(prompts)),1)
            self.assertNotIn('operating-thought',prompts[0])
            self.assertNotIn('evaluator_keys', (output/'herbert/submit/runtime.json').read_text())

if __name__ == '__main__':
    unittest.main()
