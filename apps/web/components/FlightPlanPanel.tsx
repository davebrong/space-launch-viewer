import {localTime, evidenceLabels, coverageLabels, type FlightPlan} from '../lib/client';

const compass=(deg:number)=>['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'][Math.round((deg%360)/22.5)%16];

export default function FlightPlanPanel({plan,zone,error,complete=false}:{plan:FlightPlan|null;zone:string;error?:string;complete?:boolean}) {
  return <section className="panel route-panel" aria-labelledby="route-title">
    <div className="eyebrow">MISSION ROUTE INFORMATION</div>
    <h2 id="route-title">{plan?coverageLabels[plan.state]:error?'Route information unavailable':'Checking route sources…'}</h2>
    {error&&!plan&&<p role="alert">{error}</p>}
    {plan&&<>
      <p>{plan.note}</p>
      {plan.evidence.map((e,i)=><div className="source" key={i}>
        <h3>{evidenceLabels[e.evidence_type]||e.evidence_type.replaceAll('_',' ')}{e.departure_direction?`: ${e.departure_direction} from the pad`:''}</h3>
        <p>{e.note}</p>
        {e.hazard_bearing_sector_deg&&e.hazard_distance_km&&<p>Published hazard areas lie toward compass bearings {e.hazard_bearing_sector_deg.start_deg}°–{e.hazard_bearing_sector_deg.end_deg}°{e.hazard_bearing_sector_deg.wraps_north?' across north':''} ({compass(e.hazard_bearing_sector_deg.start_deg)}–{compass(e.hazard_bearing_sector_deg.end_deg)}) from the pad, {e.hazard_distance_km.min}–{e.hazard_distance_km.max} km away{e.message_id?` (notice ${e.message_id})`:''}. Altitude and timed visibility are unresolved.</p>}
        <p><a href={e.chart_url||e.source_url} target="_blank" rel="noreferrer">{e.source_name} ↗</a> · retrieved {localTime(e.fetched_at,zone)}{e.stale?' · not recently refreshed':''}</p>
        {!e.trajectory_available&&<p className="small muted">Not a timed trajectory: no published altitude or position over time.</p>}
        <details><summary>Source data & hash</summary><p className="small"><a href={e.source_url} target="_blank" rel="noreferrer">Retrieved data ↗</a> · parser {e.parser_version}</p><code>{e.source_sha256}</code></details>
      </div>)}
      {plan.changes.length>0&&<details><summary>Source changes ({plan.changes.length})</summary>{plan.changes.map((c,i)=><p className="small" key={i}>{localTime(c.at,zone)}: {c.from||'none'} → {c.to||'none'}</p>)}</details>}
      <details><summary>Sources checked</summary>
        {plan.sources.length===0&&<p className="small">No source has been checked for this mission yet.</p>}
        {plan.sources.map(s=><div className="source" key={s.source}><p><strong>{s.name}</strong> · {coverageLabels[s.state]}</p><p className="small">{s.detail}</p><p className="small muted">Checked {localTime(s.checked_at,zone)}{s.next_check_at&&!complete?` · next check ${localTime(s.next_check_at,zone)}`:''}</p></div>)}
      </details>
    </>}
  </section>;
}
