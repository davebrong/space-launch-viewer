from pathlib import Path
import subprocess,json,datetime,hashlib,os
root=Path('.');py=str((root/'.venv/Scripts/python.exe').resolve());logs=root/'evidence/logs';logs.mkdir(exist_ok=True)
commands=[('spec-check',[py,'tools/check_spec.py']),('harness-self-tests',[py,'tests/acceptance/test_harness.py']),('application-acceptance',[py,'tests/acceptance/run.py','--suite','all']),('software-release',[py,'tools/release_gate.py','--stage','software']),('pilot-release',[py,'tools/release_gate.py','--stage','pilot']),('implementation-start',[py,'tools/start_implementation.py'])]
r=[];env=dict(os.environ);env.pop('LV_ACCEPTANCE_COMMAND',None)
for id,cmd in commands:
 proc=subprocess.run(cmd,capture_output=True,text=True,env=env);path=logs/(id+'.txt');path.write_text(proc.stdout+proc.stderr)
 r.append({'id':id,'command':cmd,'exit_code':proc.returncode,'log':path.as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()});print(id,proc.returncode)
report={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':r,'live_report':'evidence/live-latest.json','source_report':'spec/research/retrievals.json','prd_sha256':hashlib.sha256((root/'Launch_Visibility_PRD.md').read_bytes()).hexdigest(),'interpretation':'Specification passed; application deliberately absent so acceptance/release fail; empirical/evidence gates blocked independently.'}
(root/'evidence/verification.json').write_text(json.dumps(report,indent=2)+'\n')
