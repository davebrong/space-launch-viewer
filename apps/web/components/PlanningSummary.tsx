import {localTime, minutesAfterLiftoff, type Assessment} from '../lib/client';
import SkyBand from './SkyBand';

export default function PlanningSummary({assessment,zone,historical=false,review=false}:{assessment:Assessment;zone:string;historical?:boolean;review?:boolean}) {
  const plan=assessment.planning_scenario;
  if(!plan)return null;
  const watch=plan.watch_interval;
  const nearby=plan.kind==='near_launch_site';
  const heading=plan.kind==='published_heading_model';
  const relative=plan.relative_window;
  const route=plan.route_basis;
  const direction=plan.directions.join(' → ');
  const sameAsDeparture=Boolean(route&&plan.directions.length===1&&plan.directions[0]===route.departure_direction);
  const time=watch?new Intl.DateTimeFormat('en-US',{timeZone:zone,...(historical?{year:'numeric' as const}:{}),month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).formatRange(new Date(watch.start),new Date(watch.end)):null;
  const visible=heading?Boolean(relative):Boolean(watch||nearby);
  const title=visible?`Look ${direction}${heading?' in clear skies':''}`:heading?(plan.horizon_grazing?'Only grazes your horizon':'Stays below your horizon'):'No viewing window in this simulation';
  return <>
    <div className="eyebrow">{review?'LAUNCH-DAY VIEWING PLAN':'YOUR VIEWING PLAN'}</div>
    <h2>{title}</h2>
    {time&&<p className="plan-time">Around {time}</p>}
    {heading&&relative&&!watch&&<p className="plan-time">About {minutesAfterLiftoff(relative)} · {historical?'launch time unspecified in the archive':'launch time to be announced'}</p>}
    {nearby&&!watch&&<p className="plan-time">{historical?'Launch time unspecified in the archive':'Launch time to be announced'}</p>}
    {heading&&route&&<p className="route-basis"><span className="small-label">FROM THE PAD</span>The rocket departs <strong>{route.departure_direction}</strong>, as published by <a href={route.source_url} target="_blank" rel="noreferrer">{route.source_name} ↗</a>{route.stale?' (not recently refreshed)':''}. {visible?(sameAsDeparture?`From your location you would also look ${direction}; that is calculated from your position, not copied from the departure direction.`:`From your location you would look ${direction}, calculated from your position.`):'From your location the rocket would not rise high enough to see in this model.'}</p>}
    <p>{nearby?`Find an open horizon toward the launch pad, about ${Math.round(plan.pad_distance_m!/1000)} km away. Watch for the rocket rising above the horizon after liftoff.`:
      heading?(visible?`Start with a clear view of the ${plan.directions[0]} horizon. Modeled peak height above your horizon: ${Math.floor(plan.max_elevation_deg!.min_deg)}°–${Math.ceil(plan.max_elevation_deg!.max_deg)}°, depending on the exact path.`:
        plan.horizon_grazing?'Across the published direction, the modeled ascent never rises 3° above your horizon. Haze and terrain usually hide paths that low.':'Across the published direction, the modeled ascent stays below your horizon. A different actual flight profile could change this.'):
      watch?'Find an open horizon. Start low in the sky and scan along this direction.':'This assumed ascent stays below your horizon. A different flight path could change the result.'}</p>
    <span className="badge">{nearby?'Nearby launch estimate':heading?'Clear-sky estimate':'Simulated estimate'}</span>
    {heading&&plan.candidates&&<span className="badge">{plan.candidates.with_view} of {plan.candidates.evaluated} modeled paths visible</span>}
    <p className="small muted">{nearby?(watch?'Be ready before liftoff. This is watch guidance; the rocket may be visible for only part of this time.':historical?'Direction and nearby viewing potential only; no timed watch window.':'Check back for a launch time before planning your watch.'):
      heading?(visible?'Assumes clear skies. Includes two minutes of watch time either side of the modeled ascent. Timing shifts with liftoff.':'Assumes clear skies; clouds are not the reason.'):
      (watch?'Includes a few minutes of watch time around the modeled ascent. ':'')}{!heading&&watch?' Timing shifts with liftoff.':''}</p>
    <details className="planning-details"><summary>{nearby?'How this estimate works':'See model & assumptions'}</summary>
      {!nearby&&plan.windows.length>0&&<SkyBand assessment={{...assessment,windows:plan.windows,mode:'reconstructed'}}/>}
      {heading&&plan.windows.length>0&&<p className="small">Each table row is one modeled departure heading (three heights each). Where to look depends on which heading the rocket actually flies.</p>}
      {heading&&route&&<p className="small">Published departure “{route.departure_direction}” is treated as bearings {route.departure_sector_deg.start_deg}°–{route.departure_sector_deg.end_deg}° from the pad{route.narrowed_by_hazard_areas?`, narrowed to ${route.swept_sector_deg.start_deg}°–${route.swept_sector_deg.end_deg}° where it overlaps the published hazard areas`:''}. Retrieved {localTime(route.fetched_at,zone)}.</p>}
      <ul>{plan.assumptions.map(a=><li key={a}>{a}</li>)}</ul>
      <p className="small">Model {plan.model_version}. The direction and time are calculated from your location and these assumptions.</p>
      {plan.references.map(r=><p className="small" key={r.url}><a href={r.url} target="_blank" rel="noreferrer">{r.title} ↗</a><br/>{r.supports}</p>)}
    </details>
  </>;
}
