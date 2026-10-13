'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {api,type Location,type HistoricalLaunchDetail} from '../lib/client';
import PlanningSummary from './PlanningSummary';

export default function HistoricalDetail({id,location,onReturn}:{id:string;location:Location;onReturn:()=>void}) {
  const [record,setRecord]=useState<HistoricalLaunchDetail|null>(null);
  const [error,setError]=useState(''),[revision,setRevision]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();
    setRecord(null);setError('');
    void api<HistoricalLaunchDetail>(`/launch-history/${encodeURIComponent(id)}?location_id=${encodeURIComponent(location.id)}`,{signal:controller.signal})
      .then(result=>{if(!controller.signal.aborted)setRecord(result);})
      .catch(e=>{if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Could not load this launch.');});
    return()=>controller.abort();
  },[id,location.id,revision]);
  const zone=location.timezone||'UTC';
  const time=(value:string)=>new Intl.DateTimeFormat('en-US',{timeZone:zone,year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(value));
  const plan=record?.assessment.planning_scenario;
  const potential=Boolean(plan&&(plan.watch_interval||plan.kind==='near_launch_site'));
  const cloudy=plan?.cloud_cover_min_pct!==null&&plan?.cloud_cover_min_pct!==undefined&&plan.cloud_cover_min_pct>=75;
  const point=location.zip?`ZIP ${location.zip}`:'your viewing point';
  return <>
    <Link className="back-link" href="/launches" onClick={()=>{localStorage.setItem('lv_filter_v2','past');onReturn();}}>← Past launches</Link>
    {!record&&!error&&<p role="status">Checking what could have been visible from {point}…</p>}
    {error&&<section className="panel"><h1>Historical launch unavailable</h1><p role="alert">{error}</p><button onClick={()=>setRevision(r=>r+1)}>Retry launch</button></section>}
    {record&&<>
      <section className="page-heading"><div><div className="eyebrow">{record.launch.pad_name}</div><h1>{record.launch.name.split(' | ').pop()}</h1>
        <p>{record.launch.time_precision==='exact'&&record.launch.net?time(record.launch.net):record.launch.time_precision==='window'&&record.launch.window?`${time(record.launch.window.start)} – ${time(record.launch.window.end)}`:`${record.launch.net?.slice(0,10)||'Date unavailable'} · recorded date (UTC); launch time unspecified`}</p>
        <span className="small muted">{record.launch.vehicle_variant} · {point}</span></div><span className="badge">{record.source_status}</span></section>
      <div className="notice-strip"><strong>Historical viewing estimate.</strong><span> Calculated now from the archive’s published launch time and the same planning assumptions used for upcoming launches. This does not confirm a sighting or recreate a forecast saved before launch.</span></div>
      <div className="detail-grid"><div>
        <section className="panel advice-panel"><div className="eyebrow">COULD YOU HAVE SEEN IT?</div>
          <h2>{cloudy?'Clouds likely limited the view':potential?`Potentially visible from ${point}`:plan?'Outside this model’s viewing area':'Viewing potential unknown'}</h2>
          {plan?<PlanningSummary assessment={record.assessment} zone={zone} historical/>:<p>{record.launch.time_precision==='unknown'?'The archive does not specify enough launch timing to calculate a viewing plan.':'This location and mission are outside the current planning models. That does not mean the launch was invisible.'}</p>}
          {/fail/i.test(record.source_status)&&<p>The provider records a launch failure. This scenario assumes nominal ascent; the actual viewing opportunity may have been shorter or absent.</p>}
        </section>
        <details className="panel"><summary>Launch record & sources</summary><p><a href={record.source_url} target="_blank" rel="noreferrer">View original API record ↗</a></p>
          <p>Record updated {record.launch.source_updated_at?time(record.launch.source_updated_at):'at an unspecified time'}.</p>
          <p>Archive retrieved {time(record.launch.provenance[0].fetched_at)}.</p>
          {record.time_precision_unspecified&&<p>The archive supplies a recorded date without time-precision metadata. Its clock value is not used for a timed viewing estimate.</p>}
          <p>The archive may contain later corrections to the published launch time. No original prelaunch schedule snapshot is claimed.</p>
        </details>
      </div><aside><section className="panel"><h2>Light & clouds</h2>
        {record.assessment.solar_events.map(event=><div key={event.local_date}><h3>{event.local_date}</h3><p>Sunrise: {event.sunrise?time(event.sunrise):event.rise_set_state.replaceAll('_',' ')}</p><p>Sunset: {event.sunset?time(event.sunset):event.rise_set_state.replaceAll('_',' ')}</p></div>)}
        <h3>Prelaunch cloud forecast</h3>
        {plan&&plan.cloud_cover_min_pct!==null?<p>{Math.round(plan.cloud_cover_min_pct)}–{Math.round(plan.cloud_cover_max_pct!)}% cloud cover during the watch window.</p>:<p>No matching prelaunch cloud forecast is available. Viewing potential assumes a clear, unobstructed horizon.</p>}
        <p className="small muted">Current weather and later forecasts are excluded from this estimate.</p>
      </section></aside></div>
    </>}
  </>;
}
