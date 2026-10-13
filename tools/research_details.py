import requests,json,pathlib,hashlib,datetime,concurrent.futures,urllib.parse
root=pathlib.Path('.'); p=root/'tests/fixtures/raw'; records=json.loads((root/'spec/research/retrievals.json').read_text())
urls={}
selected={
'shahar603/Telemetry-Data':['LICENSE','README.md','Orbcomm OG2/README.md','Orbcomm OG2/JSON/analysed.json','Orbcomm OG2/JSON/events.json','Orbcomm OG2/JSON/stages.json'],
'shahar603/Launch-Dashboard-API':['LICENSE','src/models/v2/launch.js','src/helpers/v2/s3_helper.js','src/helpers/v2/telemetry_helper.js'],
'shahar603/SpaceXtract':['LICENSE','README.md','setup.py'],
'ravi4ram/NOTAM-Mapper':['LICENSE','notam-mapper.py','test/notam-pslv-c48.txt'],
'skyfielders/python-skyfield':['LICENSE','skyfield/toposlib.py','skyfield/almanac.py'],
'jannikmi/timezonefinder':['LICENSE','packages/timezonefinder-data/DATA_LICENSE','timezonefinder/timezonefinder.py']}
for repo,paths in selected.items():
 key=repo.split('/')[-1]; tree=json.loads((p/f'{key}-tree.json').read_text()); sha=tree['sha']
 for path in paths:
  urls[key+'--'+path.replace('/','--')]='https://raw.githubusercontent.com/'+repo+'/'+sha+'/'+urllib.parse.quote(path)
urls.update({'nws-grid.json':json.loads((p/'nws-point.json').read_text())['properties']['forecastGridData'], 'll2-schema.yml':'https://ll.thespacedevs.com/2.3.0/schema/?format=yaml','kf3.pdf':'https://www.patrick.spaceforce.mil/Portals/14/4_%20Eastern%20Range%20Airspace%20%20KF-3%20Consolidated%2010-19%20Oct%202025.pdf','census.zip':'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_zcta_national.zip'})
def fetch(pair):
 key,url=pair; rec={'id':key,'url':url,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')}
 try:
  r=requests.get(url,headers={'User-Agent':'launch-visibility-spec/1.0 (local research)'},timeout=35); path=p/key;path.write_bytes(r.content)
  rec.update(status=r.status_code,path=path.as_posix(),sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content))
 except Exception as e:rec['error']=str(e)
 return rec
new=list(concurrent.futures.ThreadPoolExecutor(8).map(fetch,urls.items()));records.extend(new)
(root/'spec/research/retrievals.json').write_text(json.dumps(records,indent=2)+'\n')
for r in new:print(r['id'],r.get('status'),r.get('bytes'))
