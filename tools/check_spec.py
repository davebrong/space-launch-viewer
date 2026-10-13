"""Offline specification integrity only. Does not certify unimplemented behavior."""
import copy,datetime,hashlib,json,pathlib,sys
from jsonschema import Draft202012Validator,FormatChecker
from openapi_spec_validator import validate_spec
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def main():
 checks=[]
 def check(name,fn):
  try:fn();checks.append({'id':name,'status':'passed'})
  except Exception as e:checks.append({'id':name,'status':'failed','reason':str(e)})
 def schemas():
  for p in (ROOT/'spec/contracts').rglob('*.schema.json'):Draft202012Validator.check_schema(json.loads(p.read_text()))
 check('json-schemas',schemas)
 def openapi():
  # Inline local schema refs for a wholly offline OpenAPI validator.
  api=load('spec/contracts/openapi.json')
  def resolve(x):
   if isinstance(x,list):return [resolve(v) for v in x]
   if isinstance(x,dict):
    if '$ref' in x and not x['$ref'].startswith('#'):
     s=load('spec/contracts/'+x['$ref']);s.pop('$id',None);return resolve(s)
    return {k:resolve(v) for k,v in x.items()}
   return x
  validate_spec(resolve(api))
 check('openapi-3.1',openapi)
 def examples():
  for x in load('tests/fixtures/v1/schema-examples.json'):
   v=Draft202012Validator(load('spec/contracts/'+x['schema']),format_checker=FormatChecker());valid=v.is_valid(x['value'])
   assert valid==x['valid'],x['id']+': '+str(list(v.iter_errors(x['value']))[:1])
 check('positive-negative-schema-examples',examples)
 def cases():
  data=load('tests/fixtures/v1/cases.json');Draft202012Validator(load('spec/contracts/fixture.schema.json')).validate(data)
  Draft202012Validator(load('spec/contracts/fixture.schema.json')).validate(load('tests/acceptance/scenarios.json'))
  assert len({x['id'] for x in data})==len(data),'Duplicate fixture ID'
  m=load('tests/fixtures/v1/reference-manifest.json');assert hashlib.sha256((ROOT/'tests/fixtures/v1/cases.json').read_bytes()).hexdigest()==m['cases_sha256'],'Reference cases modified without oracle review'
 check('fixture-shape-and-oracle-hash',cases)
 def raw():
  for r in load('spec/research/retrievals.json'):
   if 'path' in r:assert hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()==r['sha256'],r['id']
 check('raw-provenance-hashes',raw)
 def providers():
  for source,rawpath in [('ll2','ll2.json'),('nws-grid','nws-grid.json'),('historical-series','Telemetry-Data--Orbcomm OG2--JSON--analysed.json')]:
   Draft202012Validator(load('spec/contracts/external/'+source+'.schema.json'),format_checker=FormatChecker()).validate(load('tests/fixtures/raw/'+rawpath))
  s=load('tests/fixtures/raw/Telemetry-Data--Orbcomm OG2--JSON--analysed.json');assert len({len(v) for v in s.values()})==1
  assert all(a<b for a,b in zip(s['time'],s['time'][1:]))
 check('real-provider-snapshot-contracts',providers)
 def traceability():
  req={r['id'] for r in load('spec/requirements.json')};stories={f'US-{i:02}' for i in range(1,17)};cases=load('tests/fixtures/v1/cases.json');ids={c['id'] for c in cases};tasks=load('plans/tasks.json');tids={t['id'] for t in tasks};gids={g['id'] for g in load('evidence/gates.json')};mapping=load('spec/traceability.json')
  assert {x['id'] for x in mapping}==req|stories
  for x in mapping:
   assert x['tasks'] and set(x['tasks'])<=tids,x['id']
   assert set(x['fixtures'])<=ids,x['id'];assert x['tests'] and set(x['gates'])<=gids,x['id']
   if x['id'] in stories:assert x['fixtures'],x['id']
   assert set(x.get('scenarios',[])) <= {s['id'] for s in load('tests/acceptance/scenarios.json')}
  for c in cases:assert set(c['requirements'])<=req and set(c['stories'])<=stories,c['id']
  visited=set()
  def visit(t,stack):
   assert t['id'] not in stack,'Task cycle'
   for pre in t['prerequisites']:
    assert pre in tids,pre
    visit(next(x for x in tasks if x['id']==pre),stack|{t['id']})
   visited.add(t['id'])
  for t in tasks:
   assert set(t['requirements'])<=req and t['commands'] and t['evidence'] and t['acceptance']
   assert (ROOT/t['plan']).exists();visit(t,set())
 check('requirements-stories-task-graph-traceability',traceability)
 def links():
  import re
  for p in [ROOT/'IMPLEMENTATION_PLAN.md',ROOT/'AGENTS.md',*(ROOT/'spec').glob('*.md'),*(ROOT/'plans').glob('*.md')]:
   for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
    if target.startswith(('http:','https:','#')):continue
    assert (p.parent/target.split('#')[0]).exists(),f'{p}: missing {target}'
 check('local-document-links',links)
 def harness():
  import subprocess
  result=subprocess.run([sys.executable,str(ROOT/'tests/acceptance/test_harness.py')],capture_output=True,text=True,cwd=ROOT)
  assert result.returncode==0,result.stdout+result.stderr
 check('harness-fail-closed-self-tests',harness)
 report={'run_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Specification integrity only; application behavior is verified separately','checks':checks}
 (ROOT/'evidence').mkdir(exist_ok=True);(ROOT/'evidence/spec-check.json').write_text(json.dumps(report,indent=2)+'\n')
 for c in checks:print(c['status'].upper(),c['id'],c.get('reason',''))
 print(f'Specification: {sum(c["status"]=="passed" for c in checks)} passed, {sum(c["status"]=="failed" for c in checks)} failed')
 return int(any(c['status']=='failed' for c in checks))
if __name__=='__main__':sys.exit(main())
