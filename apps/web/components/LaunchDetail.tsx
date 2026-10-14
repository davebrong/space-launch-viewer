import Link from 'next/link';
import {localTime, launchTime, routeLabel, type Launch, type Location, type Assessment, type Evidence, type FlightPlan} from '../lib/client';
import SkyBand from './SkyBand';
import PlanningSummary from './PlanningSummary';
import FlightPlanPanel from './FlightPlanPanel';

export type Weather = {intervals: {start:string; end:string; total:number|null; visibility_m:number|null; missing_flags:string[]; provenance:{fetched_at:string; issued_at:string|null}[]}[]; note:string};

const explanations:Record<string,string> = {
  mission_route_unavailable:'A verified path for this mission is missing.',
  compatible_profile_unavailable:'A compatible historical ascent profile is missing.',
  observer_weather_unavailable:'Weather for the viewing point is unavailable.',
  weather_stale_or_incomplete:'Weather is incomplete or outside its freshness limit.',
  schedule_refresh_failed:'The latest schedule refresh failed.',
  approximate_flight_profile:'Approximate historical profile',
  time_insufficient:'The launch time is not precise enough.',
  nonactionable_hold:'Launch on hold',
  nonactionable_scrubbed:'Launch scrubbed',
  nonactionable_cancelled:'Launch cancelled',
  nonactionable_awaiting_confirmation:'Waiting for launch confirmation',
};
const explain=(code:string)=>explanations[code]||code.replaceAll('_',' ');
const cloudRange=(low:number,high:number)=>Math.round(low)===Math.round(high)?`${Math.round(low)}%`:`${Math.round(low)}–${Math.round(high)}%`;

export default function LaunchDetail({launch,location,assessment,evidence,weather,flightPlan,flightPlanError,busy,error,onDownload}:{
  launch:Launch; location:Location; assessment:Assessment|null; evidence:Evidence[]; weather:Weather|null;
  flightPlan:FlightPlan|null; flightPlanError:string; busy:boolean; error:string; onDownload:()=>void;
}) {
  const zone=location.timezone;
  const review=launch.status==='completed';
  const launchAt=launch.actual_liftoff||launch.net;
  const timed=Boolean(launch.actual_liftoff)||['exact','window'].includes(launch.time_precision);
  const a=assessment?.launch_id===launch.id&&assessment.location_id===location.id?assessment:null;
  const plan=a?.planning_scenario;
  const missingModel=a?.mode==='unavailable'||a?.mode==='route_screening';
  const title=!a?(error?'Viewing details unavailable':'Loading viewing details…'):review?
    missingModel?'Viewing estimate unavailable':a.mode==='official_guidance'?'Published viewing guidance':
      a.windows.length?'Approximate viewing window':'No supported viewing window':a.advice;
  const intervals=a?.supported_intervals?.length?a.supported_intervals:
    a?.windows.map(w=>w.interval)||[];
  const weatherRows=timed?weather?.intervals.filter(w=>intervals.length?
    intervals.some(i=>Date.parse(w.start)<Date.parse(i.end)&&Date.parse(w.end)>Date.parse(i.start)):
    launchAt?Date.parse(w.start)<Date.parse(launchAt)+3600000&&Date.parse(w.end)>Date.parse(launchAt):false).slice(0,100)||[]:[];
  const weatherSources=Array.from(new Map(weatherRows.flatMap(w=>w.provenance).map(p=>[`${p.issued_at}:${p.fetched_at}`,p])).values());
  const issuedAfter=Boolean(launchAt&&weatherSources.some(p=>p.issued_at&&Date.parse(p.issued_at)>Date.parse(launchAt)));
  const sunrise=a?.solar_events.find(s=>s.sunrise&&launchAt&&Math.abs(Date.parse(s.sunrise)-Date.parse(launchAt))<12*3600000)?.sunrise;
  const sunriseMinutes=sunrise&&launchAt&&timed?Math.round((Date.parse(sunrise)-Date.parse(launchAt))/60000):null;
  return <>
    <Link className="back-link" href="/launches">← All launches</Link>
    <section className="page-heading"><div><div className="eyebrow">{launch.pad_name}</div>
      <h1>{launch.name.split(' | ').pop()}</h1><p>{launchTime(launch,zone)}</p>
      <span className="small muted">{launch.vehicle_variant} · {launch.actual_liftoff?'Confirmed liftoff':'Published launch time'} · {location.zip?'ZIP '+location.zip:'Your confirmed point'}</span>
    </div><span className="badge">{a?.display_status==='awaiting_confirmation'?'Awaiting launch confirmation':launch.status.replaceAll('_',' ')}</span></section>
    {review&&a&&<div className="notice-strip"><strong>{plan?'Launch-day plan':'Review this launch'}</strong><span>{plan?' This launch has happened. Here is the viewing plan based on its scheduled liftoff.':' This launch has happened. You can still review its viewing outlook.'}</span></div>}
    {a&&missingModel&&!plan&&<div className="notice-strip"><strong>No viewing estimate</strong><span> {flightPlan?`${routeLabel(flightPlan)}. `:''}Without a published route for this mission, the app does not guess its direction from the rocket or destination. Missing route information is not a sign it cannot be seen.</span></div>}
    <div className="detail-grid"><div>
      <section className="panel advice-panel">
        {plan&&a?<PlanningSummary assessment={a} zone={zone||'UTC'} review={review}/>:<><div className="eyebrow">{!a?'VIEWING DETAILS':review?'WHAT COULD HAVE BEEN VISIBLE':'YOUR VIEWING OUTLOOK'}</div><h2>{title}</h2></>}
        {a&&!plan&&<>
          <p>{missingModel?(review?
            'This app cannot reconstruct the viewing window, direction or elevation for this launch from the available evidence. It may still have been visible from your location.':
            'There is not enough supported mission evidence to estimate a viewing window from this point.'):
            a.mode==='official_guidance'?'Mission-specific official viewing guidance.':
            'Approximate historical-profile reconstruction, capped at Possible. This is an estimate of the viewing geometry, not a record of what anyone saw.'}</p>
          <div className="chips">{a.reason_codes.filter(r=>!review||!r.startsWith('nonactionable_')).map(r=><span key={r} className="badge">{explain(r)}</span>)}
            {!review&&!a.fresh&&<span className="badge">Essential data incomplete or stale</span>}</div>
          {review&&<p className="small muted">Reviewed {localTime(a.computed_at,zone)}. This page does not recreate a forecast saved before liftoff. Sightings and model estimates are separate evidence.</p>}
          {a.official_intervals?.map((w,i)=><p key={'official'+i}><strong>Official viewing interval:</strong> {localTime(w.start,zone)} – {localTime(w.end,zone)}</p>)}
          {a.supported_intervals?.map((w,i)=><p key={'supported'+i}><strong>{review?'Interval supported by the available forecast:':'Weather-supported interval:'}</strong> {localTime(w.start,zone)} – {localTime(w.end,zone)}</p>)}
          {a.alternatives&&a.alternatives.length>0&&<details><summary>Conditional launch-time alternatives ({a.alternatives.length})</summary><table><thead><tr><th>Assumed liftoff</th><th>Outlook</th></tr></thead><tbody>{a.alternatives.map((v,i)=><tr key={i}><td>{localTime(v.t0,zone)}</td><td>{String((v.result as {advice?:string}).advice||'Unavailable')}</td></tr>)}</tbody></table></details>}
          <SkyBand assessment={a} review={review}/>
          {!a.conditional&&a.windows.map((w,i)=><p key={i}>{localTime(w.interval.start,zone)} – {localTime(w.interval.end,zone)}</p>)}
          {a.all_tracks_agree===false&&<p className="alert">Modeled candidates disagree. The band includes their separate opportunities.</p>}
        </>}
        {!a&&error&&<p>We could not load the assessment. The error above has a reload action; missing details are not a visibility result.</p>}
      </section>
      <FlightPlanPanel plan={flightPlan} zone={zone||'UTC'} error={flightPlanError} complete={review}/>
      <details className="panel"><summary>Sources & technical details</summary>
        {plan&&<p>The viewing plan uses documented planning assumptions. The stricter mission-evidence checks below apply to verified forecasts.</p>}
        {a?.missing_flags.map(f=><p key={f}>{explain(f)}</p>)}
        {a?.limitations.map(l=><p className="small muted" key={l}>{l}</p>)}
        {a&&evidence.length===0&&<p>No approved mission-specific route or viewing guidance is registered.</p>}
        {evidence.map(e=><div key={e.id}><h3>{e.evidence_type.replaceAll('_',' ')}</h3><p>{e.admission} · {e.association} association</p></div>)}
        <details><summary>Source timestamps, hashes & calculation versions</summary><p>Schedule revision {launch.revision} · UTC {launchAt||'unavailable'}</p><p>{a?.ruleset} · {a?.astronomy_version}</p>{a?.provenance.map((p,i)=><div className="source" key={i}><a href={p.source_url} target="_blank" rel="noreferrer">{p.kind.replaceAll('_',' ')} ↗</a><p>Retrieved {localTime(p.fetched_at,zone)} · issued {p.issued_at?localTime(p.issued_at,zone):'unknown'}</p><code>{p.sha256}</code><p>{p.license} · {p.parser_version}</p></div>)}</details>
      </details>
    </div><aside>
      <section className="panel"><div className="eyebrow">AT YOUR VIEWING POINT</div><h2>Light & clouds</h2>
        {sunriseMinutes!==null&&<p>{launch.actual_liftoff?'Liftoff':'The published launch time'} {review?'was':'is'} {Math.abs(sunriseMinutes)} minutes {sunriseMinutes>=0?'before':'after'} local sunrise.</p>}
        {a?.solar_events.map(s=><div key={s.local_date}><h3>{s.local_date}</h3><div className="sun-row"><span>↑ Sunrise</span><strong>{s.sunrise?localTime(s.sunrise,zone):s.rise_set_state.replaceAll('_',' ')}</strong></div><div className="sun-row"><span>↓ Sunset</span><strong>{s.sunset?localTime(s.sunset,zone):s.rise_set_state.replaceAll('_',' ')}</strong></div><details><summary>Twilight transitions</summary>{s.transitions.map((t,i)=><p className="small" key={i}>{t.event.replaceAll('_',' ')} · {t.direction}<br/>{localTime(t.at,zone)}</p>)}</details></div>)}
        <hr/><h3>Cloud forecast</h3>
        {plan?<>
          {plan.cloud_cover_min_pct===null?<p>{review?'No prelaunch cloud forecast was saved for this viewing window.':'Cloud forecast is not available for this viewing window yet.'}</p>:<p><strong>{cloudRange(plan.cloud_cover_min_pct,plan.cloud_cover_max_pct!)} cloud cover</strong> forecast during the watch window. Clear-sky guidance above does not depend on it.{plan.cloud_cover_max_pct!>=75?' Clouds may obscure the view.':''}</p>}
          <p className="small muted">NWS forecast for your viewing point.</p>
        </>:<><p className="small">Weather alone cannot establish launch visibility. Haze and cloud layers may be unavailable.</p>
        {review&&<p className="small">These are forecast values, not measured cloud conditions or a sighting record.{issuedAfter?' This forecast was issued after the launch; it does not show what was predicted beforehand.':''}</p>}
        {!timed?<p>The launch time is too imprecise to select matching cloud intervals.</p>:!weather?<p role="status">Loading the forecast for your viewing point…</p>:!weather.intervals.length?<p>Observer forecast unavailable. It will be retried automatically within source limits.</p>:<>
          <div className="weather-bins">{weatherRows.map((w,i)=><div key={i}><span>{localTime(w.start,zone)}<br/><span className="small">to {localTime(w.end,zone)}</span></span><strong>{w.total===null?'Unknown':`${w.total}%`}</strong></div>)}</div>
          <p className="small muted">{weatherRows.length?'Forecast bins overlapping this launch or supported viewing interval.':'No available forecast bin covers this launch time. Historical conditions remain unavailable.'} No extrapolation beyond validity.</p>
          {weatherSources.map((p,i)=><p className="small muted" key={i}>Forecast issued {p.issued_at?localTime(p.issued_at,zone):'at an unknown time'}<br/>Retrieved {localTime(p.fetched_at,zone)}</p>)}
        </>}</>}
      </section>
      <section className="panel"><h2>{review?'Keep the launch record':'Plan a look outside'}</h2><p>{review?'The calendar download preserves the published launch time. Reminders apply to future opportunities.':'Calendar downloads are snapshots. Download again after a delay or scrub.'}</p>
        <button className="wide secondary" onClick={onDownload} disabled={busy||launch.time_precision==='unknown'}>{review?'Download launch record .ics':'Download calendar .ics'}</button>
        <Link className="button wide" href="/subscriptions">{review?'Reminders for future launches':'Set reminder preferences'}</Link>
      </section>
    </aside></div>
  </>;
}
