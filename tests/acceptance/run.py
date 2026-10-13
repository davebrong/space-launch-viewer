"""Run the future application adapter. Expected outputs are never sent to it."""
import argparse, datetime, json, math, os, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]

def compare(actual, expected, tolerances, path=''):
    if isinstance(expected, dict):
        if not isinstance(actual, dict): raise AssertionError(f'{path}: expected object')
        for k, v in expected.items():
            if k not in actual: raise AssertionError(f'{path}/{k}: missing')
            compare(actual[k], v, tolerances, path+'/'+k)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected): raise AssertionError(f'{path}: list mismatch')
        for i, (a, e) in enumerate(zip(actual, expected)): compare(a, e, tolerances, path+'/'+str(i))
    else:
        key = path.rsplit('/', 1)[-1]; tol = tolerances.get(key)
        if tol is not None and expected is not None:
            if isinstance(expected, str):
                delta = abs((datetime.datetime.fromisoformat(actual.replace('Z', '+00:00'))-datetime.datetime.fromisoformat(expected.replace('Z', '+00:00'))).total_seconds())
            else:
                if isinstance(actual, bool) or not isinstance(actual, (float, int)) or not math.isfinite(actual): raise AssertionError(f'{path}: invalid number')
                delta = abs(actual-expected)
                if key == 'azimuth_deg': delta = min(delta % 360, 360-delta % 360)
            if delta > tol: raise AssertionError(f'{path}: {actual!r} != {expected!r}, tolerance {tol}')
        elif type(actual) != type(expected) and not (type(actual) in (float,int) and type(expected) in (float,int)):
            raise AssertionError(f'{path}: type mismatch')
        elif actual != expected: raise AssertionError(f'{path}: {actual!r} != {expected!r}')

def main():
    p=argparse.ArgumentParser(); p.add_argument('--suite',default='all'); p.add_argument('--adapter'); args=p.parse_args()
    command=args.adapter or os.environ.get('LV_ACCEPTANCE_COMMAND')
    if not command:
        print('FAIL MISSING_IMPLEMENTATION: set LV_ACCEPTANCE_COMMAND to a JSON argv array for the real application adapter.'); return 1
    try:
        command=json.loads(command); assert isinstance(command,list) and command and all(isinstance(x,str) for x in command)
    except Exception:
        print('FAIL INVALID_ADAPTER_COMMAND: expected JSON argv array'); return 1
    cases=json.loads((ROOT/'tests/fixtures/v1/cases.json').read_text())
    cases+=json.loads((ROOT/'tests/acceptance/scenarios.json').read_text())
    cases=[c for c in cases if args.suite=='all' or c['id']==args.suite or c['operation']==args.suite or args.suite in c['requirements'] or args.suite in c['stories']]
    if not cases: print('FAIL EMPTY_SUITE'); return 1
    passed=[]; failed=[]
    for c in cases:
        try:
            request={'protocol_version':1,'operation':c['operation'],'input':c['input']}
            proc=subprocess.run(command,input=json.dumps(request)+'\n',text=True,capture_output=True,cwd=ROOT,timeout=900 if c['operation']=='scenario' else 90)
            if proc.returncode: raise AssertionError(f'adapter exit {proc.returncode}: {proc.stderr[:300]}')
            compare(json.loads(proc.stdout),c['expected'],c.get('tolerance',{})); passed.append(c['id'])
        except Exception as e: failed.append({'id':c['id'],'error':str(e)})
    report={'suite':args.suite,'passed':passed,'failed':failed,'blocked':[],'adapter_command':command,'run_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (ROOT/'evidence').mkdir(exist_ok=True); (ROOT/'evidence/acceptance-latest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Acceptance: {len(passed)} passed, {len(failed)} failed, 0 blocked')
    for f in failed: print('FAIL', f['id'], f['error'])
    return int(bool(failed))

if __name__=='__main__': sys.exit(main())
