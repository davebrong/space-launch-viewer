import requests,json,pathlib,hashlib,datetime
p=pathlib.Path('tests/fixtures/raw');records=json.loads(pathlib.Path('spec/research/retrievals.json').read_text());sha=json.loads((p/'Telemetry-Data-tree.json').read_text())['sha']
urls={'usno-maryland.json':'https://aa.usno.navy.mil/api/rstt/oneday?date=2026-10-13&coords=39.0,-77.0&tz=-4&dst=false','telemetry-index.json':f'https://raw.githubusercontent.com/shahar603/Telemetry-Data/{sha}/Laucnhes.json'}
for key,url in urls.items():
 r=requests.get(url,timeout=30);(p/key).write_bytes(r.content);records.append({'id':key,'url':url,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),'status':r.status_code,'path':(p/key).as_posix(),'sha256':hashlib.sha256(r.content).hexdigest(),'bytes':len(r.content)});print(key,r.status_code,r.text[:1200])
pathlib.Path('spec/research/retrievals.json').write_text(json.dumps(records,indent=2)+'\n')
