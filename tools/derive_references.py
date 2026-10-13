"""Independent reference generation. Never imports application modules. Review changes, do not auto-bless."""
from pathlib import Path
import json,math,datetime,zoneinfo,hashlib,zipfile,io,csv
from pyproj import Transformer,__version__ as pyproj_version
P=Path('tests/fixtures'); (P/'v1').mkdir(parents=True,exist_ok=True)
cases=[]
def add(id,op,input,expected,reqs,stories=(),basis='Normative decision table in spec/rules.md; hand-specified boundary outcome.',kind='synthetic',tolerance=None):
 c=dict(id=id,version=1,kind=kind,operation=op,input=input,expected=expected,requirements=reqs,stories=list(stories),oracle=basis)
 if tolerance:c['tolerance']=tolerance
 cases.append(c)
def r(*ids):return list(ids)
# ZIP rows independently read from archived Census, no application adapter.
z=zipfile.ZipFile(P/'raw/census.zip'); rows=list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig')),delimiter='|'))
for zip in ['fixture-zip','00601']:
 row=next(x for x in rows if x['GEOID']==zip)
 add('zip-'+zip,'resolve_zip',{'zip':zip,'gazetteer':'tests/fixtures/raw/census.zip'},{'zip':zip,'latitude_deg':float(row['INTPTLAT']),'longitude_deg':float(row['INTPTLONG']),'confirmed':False},r('R002'),['US-01'],basis='Direct exact GEOID row lookup in archived Census 2025, not application output.',kind='real_reference')
add('zip-missing','resolve_zip',{'zip':'00000','gazetteer':'tests/fixtures/raw/census.zip'},{'status':'unavailable','fallback':['gps','manual']},r('R002'),['US-01'])
add('zip-numeric','resolve_zip',{'zip':601},{'error':'INVALID_INPUT'},r('R002'),['US-01'])
add('location-change','location_change',{'old_confirmed':True,'old_revision':1,'new_point':[39.5,-77.4]},{'confirmed':False,'revision':2,'invalidate_assessment':True},r('R002','R011'),['US-01'])
for id,utc in [('rollover','2026-10-14T00:30:00Z'),('dst-fold-edt','2026-11-01T05:30:00Z'),('dst-fold-est','2026-11-01T06:30:00Z'),('dst-spring-before','2026-03-08T06:59:00Z'),('dst-spring-after','2026-03-08T07:00:00Z')]:
 d=datetime.datetime.fromisoformat(utc.replace('Z','+00:00')).astimezone(zoneinfo.ZoneInfo('America/New_York'))
 add(id,'local_time',{'utc':utc,'timezone':'America/New_York','device_timezone':'America/Los_Angeles'},{'local':d.isoformat(),'abbreviation':d.tzname(),'fold':d.fold},r('R008'),['US-02','US-03'],basis='Python zoneinfo/IANA conversion, frozen UTC vectors; no app code.')
add('dst-nonexistent','parse_local',{'local':'2026-03-08T02:30:00','timezone':'America/New_York','offset':None},{'error':'INVALID_INPUT'},r('R008'),['US-03'])
add('dst-ambiguous','parse_local',{'local':'2026-11-01T01:30:00','timezone':'America/New_York','offset':None},{'error':'INVALID_INPUT'},r('R008'),['US-03'])
# Independent PROJ topocentric pipeline. Points are synthetic geometry, not mission track.
for id,observer,target in [('cape-md-pad',[39.0,-77.0,0],[28.608,-80.604,0]),('cape-md-high',[39.0,-77.0,0],[33,-76,200000]),('near-pad',[28.608,-80.604,0],[28.61,-80.60,10000]),('equator-east',[0,0,0],[0,1,100000])]:
 lat,lon,h=observer
 tr=Transformer.from_pipeline(f'+proj=pipeline +step +proj=cart +ellps=WGS84 +step +proj=topocentric +ellps=WGS84 +lat_0={lat} +lon_0={lon} +h_0={h}')
 e,n,u=tr.transform(target[1],target[0],target[2]);az=math.degrees(math.atan2(e,n))%360;el=math.degrees(math.atan2(u,math.hypot(e,n)))
 add(id,'geometry',{'observer_lat_lon_alt_m':observer,'target_lat_lon_alt_m':target},{'azimuth_deg':az,'elevation_deg':el,'range_m':math.sqrt(e*e+n*n+u*u)},r('R006','R018','R019'),['US-07'],basis=f'Independent PROJ topocentric pipeline via pyproj {pyproj_version}; WGS84. Synthetic target; no claimed flown route.',tolerance={'azimuth_deg':0.1,'elevation_deg':0.1,'range_m':1})
# Actual USNO expected values parsed independently from authoritative response.
usno=json.loads((P/'raw/usno-maryland.json').read_text())['properties']['data'];sun={x['phen']:x['time'] for x in usno['sundata']}
def ts(v):return '2026-10-13T'+v+':00-04:00'
add('sunrise-maryland','solar_events',{'latitude_deg':39.0,'longitude_deg':-77.0,'altitude_m':0,'local_date':'2026-10-13','timezone':'America/New_York','sunrise_center_deg':-0.833},{'sunrise':datetime.datetime.fromisoformat(ts(sun['Rise'])).astimezone(datetime.timezone.utc).isoformat().replace('+00:00','Z'),'sunset':datetime.datetime.fromisoformat(ts(sun['Set'])).astimezone(datetime.timezone.utc).isoformat().replace('+00:00','Z')},r('R008','R018'),['US-04'],basis='Archived USNO one-day API at same point, timezone explicitly -4 with dst=false to avoid double DST. Source minute rounding; tolerance120s.',kind='real_reference',tolerance={'sunrise':120,'sunset':120})
add('polar-no-rise','solar_events',{'latitude_deg':90,'longitude_deg':0,'altitude_m':0,'local_date':'2026-12-21','timezone':'Etc/UTC','sunrise_center_deg':-0.833},{'sunrise':None,'sunset':None,'rise_set_state':'no_rise_or_set'},r('R008'),['US-04'],basis='North pole December solstice Sun remains below horizon all day; exact event times intentionally null.')
for angle,label in [(-18,'astronomical'),(-12,'nautical'),(-6,'civil'),(-0.833,'daylight'),(-18.001,'night')]:add('twilight-'+str(angle),'twilight_label',{'sun_deg':angle},{'label':label},r('R008'),['US-04'])
add('sunrise-slip','slip',{'launch_local':'2026-10-13T06:58:00-04:00','view_offset_s':480,'slip_s':600,'synthetic_sunrise':'2026-10-13T07:10:00-04:00'},{'before_view':'2026-10-13T07:06:00-04:00','after_view':'2026-10-13T07:16:00-04:00','recompute':['solar','weather','rules'],'automatic_daylight_rejection':False},r('R008','R011'),['US-05'],basis='PRD synthetic arithmetic example; 07:10 is NOT a real Maryland sunrise.')
for id,target,expected in [('shadow-night',[-7000000,0,0],True),('shadow-day',[7000000,0,0],False),('shadow-offset',[-7000000,7000000,0],False)]:
 add(id,'earth_shadow',{'target_ecef_m':target,'sun_direction_ecef_unit':[1,0,0],'earth_a_m':6378137,'earth_b_m':6356752.314245},{'in_shadow':expected},r('R006','R008'),['US-06'],basis='Analytic ray/ellipsoid cases: ray toward+x intersects Earth only for antisolar point within Earth radius.')
for id,engine,plume,sunlit,expected in [('engine-in-shadow',True,False,False,True),('sunlit-inactive',False,False,True,False),('active-sunlit-plume',False,True,True,True)]:add(id,'emission',{'active_engine':engine,'active_plume':plume,'sunlit':sunlit},{'eligible':expected},r('R006','R008'),['US-06'])
for val,expect in [(19.999,False),(20,True),(20.001,True)]:add('duration-'+str(val),'duration',{'continuous_s':val,'elevation_deg':1,'active_engine':True},{'eligible':expect},r('R006'),['US-07'])
add('zero-horizon','duration',{'continuous_s':60,'elevation_deg':0,'active_engine':True},{'eligible':False},r('R006'),['US-07'])
for gap,expect in [(15,True),(15.001,False)]:add('gap-'+str(gap),'gap',{'sample_gap_s':gap,'same_stage':True},{'interpolate':expect},r('R006'),['US-07'])
add('stage-switch','gap',{'sample_gap_s':5,'same_stage':False},{'interpolate':False},r('R005','R006'),['US-08'])
add('north-wrap','bearing_sector',{'bearings_deg':[359,1]},{'start_deg':345,'end_deg':15,'wraps_north':True},r('R007'),['US-07'])
add('round-outward','round_window',{'start':'2026-10-13T11:06:01Z','end':'2026-10-13T11:06:59Z'},{'start':'2026-10-13T11:06:00Z','end':'2026-10-13T11:07:00Z'},r('R007'),['US-07'])
for sec,elev,sun,expected in [(60,5,-6,True),(59.999,5,-6,False),(60,4.999,-6,False),(60,5,-5.999,False)]:add('lighting-'+str(len(cases)),'lighting_flag',{'continuous_s':sec,'elevation_deg':elev,'observer_sun_deg':sun,'emission':True},{'flag':expected},r('R008','R010'),['US-06','US-10'])
# Weather table values are stipulated product semantics, not real forecast claims.
for id,total,vis,low,mid,high,fog,expected in [('cloud25',25,10000,None,None,None,False,'clear'),('cloud25plus',25.001,10000,None,None,None,False,'mixed'),('cloud75',75,None,None,None,None,False,'poor'),('vis5000',0,5000,None,None,None,False,'mixed'),('vis4999',0,4999,None,None,None,False,'poor'),('vis9999',0,9999,None,None,None,False,'mixed'),('vis10000',0,10000,None,None,None,False,'clear'),('visibility-missing',0,None,None,None,None,None,'clear'),('layers-clear',25,10000,20,40,60,False,'clear'),('layers-low60',0,10000,60,0,0,False,'poor'),('layers-mid41',0,10000,0,41,0,False,'mixed'),('fog',0,10000,None,None,None,True,'poor'),('total-missing',None,10000,0,0,0,False,'unavailable')]:
 add(id,'weather_tier',{'total':total,'visibility_m':vis,'low':low,'mid':mid,'high':high,'fog':fog},{'tier':expected,'visibility_unknown':vis is None},r('R009'),['US-09'])
add('bin-boundary','weather_overlap',{'view':[0,60],'bins':[{'interval':[0,60],'tier':'clear'},{'interval':[60,120],'tier':'poor'}]},{'tier':'clear'},r('R009'),['US-09'])
add('bin-poor-overlap','weather_overlap',{'view':[0,61],'bins':[{'interval':[0,60],'tier':'clear'},{'interval':[60,120],'tier':'poor'}]},{'tier':'poor'},r('R009'),['US-09'])
add('better-subinterval','weather_subinterval',{'view':[0,120],'bins':[{'interval':[0,40],'tier':'poor'},{'interval':[40,100],'tier':'clear'},{'interval':[100,120],'tier':'poor'}]},{'selected':[[40,100]],'tier':'clear'},r('R009'),['US-09'])
for id,fetch,issue,covered,expected in [('fresh-boundary',3600,43200,True,True),('fetch-stale',3600.001,100,True,False),('issue-stale',1,43200.001,True,False),('issue-unknown',1,None,True,False),('coverage-gap',1,1,False,False)]:add(id,'weather_fresh',{'fetch_age_s':fetch,'issue_age_s':issue,'covered':covered},{'fresh':expected},r('R009','R011'),['US-11'])
base={'status':'scheduled','mode':'reconstructed','route':'approved','profile':'compatible','complete':True,'fresh':True,'weather':'clear','luminous_seconds':60,'all_below_horizon':False,'official_member':False}
for id,change,advice in [('reconstruction-cap',{},'Possible'),('missing-route',{'route':'missing'},'Not enough data'),('hazard-only',{'mode':'route_screening'},'Not enough data'),('dogleg',{'route':'unsupported_dogleg'},'Not enough data'),('ambiguous-mission',{'route':'ambiguous'},'Not enough data'),('variant-mismatch',{'profile':'incompatible'},'Not enough data'),('missing-emission',{'luminous_seconds':None},'Not enough data'),('incomplete-negative',{'complete':False,'all_below_horizon':True},'Not enough data'),('complete-negative',{'all_below_horizon':True,'luminous_seconds':0},'Unlikely'),('poor-clouds',{'weather':'poor'},'Unlikely'),('stale-feed',{'fresh':False},'Not enough data'),('missing-weather',{'weather':'unavailable'},'Not enough data'),('official-clear',{'mode':'official_guidance','official_member':True},'Worth a look'),('official-mixed',{'mode':'official_guidance','official_member':True,'weather':'mixed'},'Possible'),('outside-map',{'mode':'official_guidance','official_member':False},'Not enough data'),('scrub',{'status':'scrubbed'},'Not enough data'),('hold',{'status':'hold'},'Not enough data'),('completed',{'status':'completed'},'Not enough data'),('cancelled',{'status':'cancelled'},'Not enough data')]:
 add(id,'advice',{**base,**change},{'advice':advice},r('R004','R005','R010','R011'),['US-08','US-10','US-11'])
add('date-only','time_presentation',{'precision':'date','date':'2026-10-13','actual_liftoff':None},{'countdown':False,'precise_reminder':False},r('R003','R011'),['US-12'])
add('window-only','time_presentation',{'precision':'window','start':'2026-10-13T11:00:00Z','end':'2026-10-13T12:00:00Z','actual_liftoff':None},{'conditional':True,'precise_reminder':False},r('R003','R011'),['US-12'])
add('awaiting-confirmation','time_presentation',{'precision':'exact','net':'2026-10-13T11:00:00Z','now':'2026-10-13T11:00:00Z','actual_liftoff':None},{'display_status':'awaiting_confirmation','countdown':False},r('R003','R011'),['US-12'])
for clock,quiet in [('21:59:59',False),('22:00:00',True),('06:59:59',True),('07:00:00',False)]:add('quiet-'+clock.replace(':',''),'quiet_hours',{'local_time':clock,'overnight_opt_in':False},{'suppressed':quiet},r('R012'),['US-13'])
add('overnight-opt-in','quiet_hours',{'local_time':'05:00:00','overnight_opt_in':True},{'suppressed':False},r('R012'),['US-13'])
for shift,correct in [(299,False),(300,True)]:add('correction-'+str(shift),'correction',{'shift_from_last_delivered_s':shift,'local_date_changed':False,'previously_notified':True},{'notify':correct},r('R013'),['US-14'])
add('date-correction','correction',{'shift_from_last_delivered_s':60,'local_date_changed':True,'previously_notified':True},{'notify':True},r('R013'),['US-14'])
for seconds,near,scrub,expected in [(599,False,False,False),(600,False,False,True),(0,True,False,True),(0,False,True,True)]:add('debounce-'+str(len(cases)),'downgrade',{'persistent_s':seconds,'inside_30m':near,'scrub':scrub},{'notify':expected},r('R013'),['US-14'])
add('no-past-milestone','enqueue',{'created_at':'2026-10-13T10:00:00Z','due_at':'2026-10-13T10:00:00Z'},{'enqueue':False},r('R012'),['US-13'])
add('expired-notice','delivery',{'now':'2026-10-13T11:30:00Z','expires_at':'2026-10-13T11:30:00Z','consent':True},{'deliver':False,'state':'expired'},r('R013'),['US-14'])
add('notification-race','notification_race',{'workers':2,'subscription':'sub1','attempt':'attempt1','type':'planning_24h','revision':1,'barrier':'before_claim'},{'logical_notices':1,'outbox_rows':1},r('R013'),['US-14'],basis='Database uniqueness requirement; real adapter must run2 concurrent transactions, not return canned counts.')
add('unsubscribe-race','unsubscribe_race',{'unsubscribe_commits_before_claim':True,'pending':1},{'enabled':False,'delivered':0,'pending':0},r('R013','R014'),['US-15'],basis='Transaction ordering: committed disable must be read under delivery lock.')
add('revision-race','revision_race',{'old_revision':1,'new_revision':2,'revision_commits_before_claim':True},{'old_deliveries':0,'current_revision':2},r('R013'),['US-14'])
add('delete-24h','privacy_delete',{'elapsed_s':86400,'subscription_deleted':True},{'subscription_exists':False,'pending':0},r('R014'),['US-15'])
for code in [403,429,503,'timeout']:add('provider-'+str(code),'provider_failure',{'status':code,'has_cache':True},{'paid_fallback':False,'positive_notices':False,'cached_data_retained':True},r('R001','R011','R015'),['US-11'])
add('ll2-budget','provider_budget',{'requests_in_last_3600s':12,'next_request_kind':'retry'},{'allowed':False},r('R015'),['US-11'])
add('reproducibility','assessment_key',{'baseline_hash':'a'*64,'changed_input':'weather_snapshot','changed_hash':'b'*64},{'same_key':False,'archive_original':True},r('R018'),['US-16'])
add('mission-disable','admin_disable',{'authenticated':True,'mission_enabled':True},{'mission_enabled':False,'positive_notices':False,'audit_created':True},r('R014','R018'),['US-16'])
# Real provider parser golden values obtained directly from raw file access.
a=json.loads((P/'raw/Telemetry-Data--Orbcomm OG2--JSON--analysed.json').read_text());e=json.loads((P/'raw/Telemetry-Data--Orbcomm OG2--JSON--events.json').read_text())
add('orbcomm-archive','parse_historical_archive',{'series_path':'tests/fixtures/raw/Telemetry-Data--Orbcomm OG2--JSON--analysed.json','events_path':'tests/fixtures/raw/Telemetry-Data--Orbcomm OG2--JSON--events.json'},{'sample_count':len(a['time']),'last_t_s':a['time'][-1],'last_altitude_m':a['altitude'][-1]*1000,'last_downrange_m':a['downrange_distance'][-1]*1000,'ses1_s':e['ses1'],'seco1_s':e['seco1'],'production_admitted':False},r('R005','R018','R019'),['US-08'],basis='Direct archived JSON fields; km->m dimensional conversion, metadata insufficient for production; no application code.',kind='real_reference')
(P/'v1/cases.json').write_text(json.dumps(cases,indent=2)+'\n')
(P/'v1/reference-manifest.json').write_text(json.dumps({'version':1,'generator':'tools/derive_references.py','pyproj_version':pyproj_version,'generated_for':'specification, not application validation','cases_sha256':hashlib.sha256((P/'v1/cases.json').read_bytes()).hexdigest(),'independence':'PROJ pipeline/USNO/Census/raw JSON/direct rule tables; no application imports'},indent=2)+'\n')
print(f'Wrote {len(cases)} reference cases')
