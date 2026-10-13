import type { Assessment } from '../lib/client';
export default function SkyBand({ assessment, review=false }: { assessment: Assessment; review?:boolean }) {
  if (!assessment.windows.length) {
    const official=assessment.mode==='official_guidance', reconstructed=assessment.mode==='reconstructed';
    return <div className="sky-empty"><span aria-hidden="true">↗</span><h3>{official?'Regional guidance only':reconstructed?'No modeled viewing window':'No supported sky path'}</h3><p>{official?'The official source supplies viewing guidance; exact directions and elevations are not estimated here.':reconstructed?'The admitted model candidates did not produce a supported viewing interval. Check the source limitations below.':assessment.mode === 'route_screening' ? 'Altitude and timed visibility unresolved.' : review?'A verified mission path and compatible ascent profile are needed to reconstruct where it could have appeared.':'A mission-specific route and compatible ascent profile are needed before we can tell you where to look.'}</p></div>;
  }
  return <section aria-labelledby="sky-title"><h3 id="sky-title">Approximate sky band</h3><p>Candidate spread, not a measured trajectory or confidence interval.</p>
    <svg viewBox="0 0 720 210" role="img" aria-labelledby="band-title"><title id="band-title">Approximate direction sectors; exact values are in the table below</title>
      {[0,30,60,90].map(e=><g key={e}><line x1="35" x2="700" y1={185-e*1.7} y2={185-e*1.7} stroke="#35444e"/><text x="0" y={190-e*1.7} fill="#b7c3cb" fontSize="12">{e}°</text></g>)}
      {assessment.windows.flatMap((w,i)=>w.bearing_sectors.flatMap((s,j)=>{
        const parts=s.wraps_north?[[s.start_deg,360],[0,s.end_deg]]:[[s.start_deg,s.end_deg]];
        return parts.map(([a,b],k)=><rect key={`${i}-${j}-${k}`} x={35+a/360*665} y={185-w.max_elevation_max_deg*1.7} width={Math.max(4,(b-a)/360*665)} height={Math.max(6,(w.max_elevation_max_deg-w.max_elevation_min_deg)*1.7)} fill="#a9e8ca" opacity=".65"/>);
      }))}
      {['N','E','S','W','N'].map((d,i)=><text key={i} x={35+i*166} y="207" fill="#b7c3cb" fontSize="12">{d}</text>)}
    </svg><div className="table-wrap"><table><caption>Viewing envelope across candidate tracks</caption><thead><tr><th>After liftoff</th><th>True-north direction</th><th>Maximum elevation</th><th>Movement</th></tr></thead><tbody>{assessment.windows.map((w,i)=><tr key={i}><td>T+{Math.floor(w.t_start_s/60)}–{Math.ceil(w.t_end_s/60)} min</td><td>{w.bearing_sectors.map(s=>`${s.start_deg}°–${s.end_deg}°${s.wraps_north?' across north':''}`).join(', ') || 'Bearing undefined at zenith'}</td><td>{Math.floor(w.max_elevation_min_deg)}°–{Math.ceil(w.max_elevation_max_deg)}°</td><td>{w.movement}</td></tr>)}</tbody></table></div>
  </section>;
}
