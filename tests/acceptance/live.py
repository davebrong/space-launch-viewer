"""Read-only provider smoke gate; does not validate application route coverage."""
import datetime, json, pathlib, sys, time
import requests
ROOT=pathlib.Path(__file__).resolve().parents[2]

def main():
    results=[]; headers={'User-Agent':'launch-visibility-spec/1.0 (local read-only verification)','Accept':'application/json'}
    def fetch(name,url,required):
        try:
            r=requests.get(url,headers=headers,timeout=20)
            if r.status_code!=200:
                results.append({'id':name,'status':'blocked','reason':f'HTTP {r.status_code}'}); return None
            data=r.json()
            if not all(k in data for k in required):
                results.append({'id':name,'status':'failed','reason':'Provider schema drift'}); return None
            results.append({'id':name,'status':'passed','url':url}); return data
        except requests.RequestException as e:
            results.append({'id':name,'status':'blocked','reason':str(e)}); return None
        except ValueError as e:
            results.append({'id':name,'status':'failed','reason':'Invalid JSON '+str(e)}); return None
    ledger=ROOT/'evidence/live-ll2-budget.json'; ledger.parent.mkdir(exist_ok=True); now=time.time()
    hist=json.loads(ledger.read_text()) if ledger.exists() else []; hist=[t for t in hist if now-t<3600]
    if len(hist)>=12: results.append({'id':'LL2','status':'blocked','reason':'Local12/hour request budget exhausted'})
    else:
        hist.append(now); ledger.write_text(json.dumps(hist)); fetch('LL2','https://ll.thespacedevs.com/2.3.0/launches/upcoming/?limit=1',['count','results'])
    point=fetch('NWS-point','https://api.weather.gov/points/39.295,-76.6223',['properties'])
    if point:
        url=point['properties'].get('forecastGridData','')
        if url.startswith('https://api.weather.gov/gridpoints/'):
            grid=fetch('NWS-grid',url,['properties'])
            if grid and not all(k in grid['properties'] for k in ['skyCover','updateTime']): results.append({'id':'NWS-fields','status':'failed','reason':'Missing fields'})
        else: results.append({'id':'NWS-grid','status':'blocked','reason':'Missing or unapproved grid URL'})
    else: results.append({'id':'NWS-grid','status':'blocked','reason':'Point unavailable'})
    report={'run_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Live transport/schema smoke only','checks':results}
    (ROOT/'evidence/live-latest.json').write_text(json.dumps(report,indent=2)+'\n')
    for r in results: print(r['status'].upper(),r['id'],r.get('reason',''))
    return 1 if any(x['status']=='failed' for x in results) else 2 if any(x['status']=='blocked' for x in results) else 0

if __name__=='__main__': sys.exit(main())
