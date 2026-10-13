"""Release evidence audit. Software and empirical pilot are separate stages."""
import argparse,hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['software','pilot'],default='software');args=p.parse_args()
 gates=json.loads((ROOT/'evidence/gates.json').read_text());failed=[];blocked=[];passed=[]
 for gate in gates:
  id=gate['id']
  if id=='G-PILOT' and args.stage=='software':continue
  if id=='G-SPEC':
   path=ROOT/'evidence/spec-check.json'
   if not path.exists():failed.append(id);continue
   r=json.loads(path.read_text());ok=bool(r.get('checks')) and all(x['status']=='passed' for x in r['checks'])
   (passed if ok else failed).append(id);continue
  report=ROOT/'evidence/releases'/f'{id}.json'
  if not report.exists():(failed if gate['status']=='not_implemented' else blocked).append(id);continue
  data=json.loads(report.read_text());proof=data.get('checks',[]);manifest=data.get('reviewed_input_manifest')
  if not proof or not manifest or not (ROOT/manifest).is_file() or any(x.get('status')=='blocked' for x in proof):blocked.append(id);continue
  good=True
  for x in proof:
   file=ROOT/x.get('artifact_path','__missing__')
   if x.get('exit_code')!=0 or x.get('status')!='passed' or not x.get('command') or not file.is_file():good=False;continue
   if hashlib.sha256(file.read_bytes()).hexdigest()!=x.get('sha256'):good=False
  (passed if good else failed).append(id)
 print('PASSED:',', '.join(passed) or 'none');print('FAILED:',', '.join(failed) or 'none');print('BLOCKED:',', '.join(blocked) or 'none')
 if args.stage=='software':print('EMPIRICAL G-PILOT: separate; run --stage pilot. Software pass never proves sightings.')
 return 1 if failed else 2 if blocked else 0
if __name__=='__main__':sys.exit(main())
