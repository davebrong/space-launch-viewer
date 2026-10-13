import type {Assessment} from '../lib/client';
import SkyBand from './SkyBand';

export default function PlanningSummary({assessment,zone}:{assessment:Assessment;zone:string}) {
  const plan=assessment.planning_scenario;
  if(!plan)return null;
  const watch=plan.watch_interval;
  const nearby=plan.kind==='near_launch_site';
  const direction=plan.directions.join(' → ');
  const time=watch?new Intl.DateTimeFormat('en-US',{timeZone:zone,month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).formatRange(new Date(watch.start),new Date(watch.end)):null;
  return <>
    <div className="eyebrow">YOUR VIEWING PLAN</div>
    <h2>{watch||nearby?`Look ${direction}`:'No viewing window in this simulation'}</h2>
    {time&&<p className="plan-time">Around {time}</p>}
    {nearby&&!watch&&<p className="plan-time">Launch time to be announced</p>}
    <p>{nearby?`Find an open horizon toward the launch pad, about ${Math.round(plan.pad_distance_m!/1000)} km away. Watch for the rocket rising above the horizon after liftoff.`:watch?'Find an open horizon. Start low in the sky and scan along this direction.':'This assumed ascent stays below your horizon. A different flight path could change the result.'}</p>
    <span className="badge">{nearby?'Nearby launch estimate':'Simulated estimate'}</span>
    <p className="small muted">{nearby?(watch?'Be ready before liftoff. This is watch guidance; the rocket may be visible for only part of this time.':'Check back for a launch time before planning your watch.'):(watch?'Includes a few minutes of watch time around the modeled ascent. ':'')}{watch?' Timing shifts with liftoff.':''}</p>
    <details className="planning-details"><summary>{nearby?'How this estimate works':'See simulation & assumptions'}</summary>
      {!nearby&&<SkyBand assessment={{...assessment,windows:plan.windows,mode:'reconstructed'}}/>}
      <ul>{plan.assumptions.map(a=><li key={a}>{a}</li>)}</ul>
      <p className="small">Model {plan.model_version}. The direction and time are calculated from your location and these assumptions.</p>
      {plan.references.map(r=><p className="small" key={r.url}><a href={r.url} target="_blank" rel="noreferrer">{r.title} ↗</a><br/>{r.supports}</p>)}
    </details>
  </>;
}
