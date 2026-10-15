import requests,json,pathlib,hashlib,datetime,concurrent.futures
root=pathlib.Path('.')
urls={
'll2':'https://ll.thespacedevs.com/2.3.0/launches/upcoming/?limit=1',
'll2-throttle':'https://ll.thespacedevs.com/2.3.0/api-throttle/',
'nws-point':'https://api.weather.gov/points/39.295,-76.6223',
'nws-openapi':'https://api.weather.gov/openapi.json',
}
for repo in ['shahar603/Telemetry-Data','shahar603/Launch-Dashboard-API','shahar603/SpaceXtract','ravi4ram/NOTAM-Mapper','skyfielders/python-skyfield','jannikmi/timezonefinder']:
 key=repo.split('/')[-1]
 urls[key+'-meta']='https://api.github.com/repos/'+repo
 urls[key+'-tree']='https://api.github.com/repos/'+repo+'/git/trees/HEAD?recursive=1'
def fetch(pair):
 key,url=pair
 rec={'id':key,'url':url,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')}
 try:
  r=requests.get(url,headers={'User-Agent':'launch-visibility-spec/1.0 (local research)','Accept':'application/json'},timeout=25)
  body=r.content; p=root/'tests/fixtures/raw'/f'{key}.json'; p.write_bytes(body)
  rec.update(status=r.status_code,path=p.as_posix(),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),content_type=r.headers.get('Content-Type'))
 except Exception as e: rec['error']=str(e)
 return rec
records=list(concurrent.futures.ThreadPoolExecutor(8).map(fetch,urls.items()))
(root/'spec/research/retrievals.json').write_text(json.dumps(records,indent=2)+'\n')
for r in records: print(r['id'],r.get('status'),r.get('bytes'),r.get('error',''))
for key in ['Telemetry-Data','Launch-Dashboard-API','SpaceXtract','NOTAM-Mapper','python-skyfield','timezonefinder']:
 p=root/'tests/fixtures/raw'/f'{key}-tree.json'
 try:
  tree=json.loads(p.read_text()).get('tree',[])
  print(key,[x['path'] for x in tree if any(s in x['path'].lower() for s in ['license','orbcomm','index','schema','notam','storage','almanac.py','toposlib.py'])][:45])
 except Exception: pass
