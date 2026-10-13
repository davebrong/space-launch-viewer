'use client';
import {useEffect,useState} from 'react';
import {api,localTime,type LaunchHistoryPage} from '../lib/client';

export default function PastLaunches({zone}:{zone:string}) {
  const [request,setRequest]=useState<{cursor:string|null;revision:number}>({cursor:null,revision:0});
  const [rows,setRows]=useState<LaunchHistoryPage['rows']>([]);
  const [page,setPage]=useState<LaunchHistoryPage|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();
    setBusy(true);setError('');
    if(!request.cursor){setRows([]);setPage(null);}
    void (async()=>{
      try {
        for(let attempt=0;attempt<24;attempt++){
          const result=await api<LaunchHistoryPage>('/launch-history'+(request.cursor?'?cursor='+encodeURIComponent(request.cursor):''),{signal:controller.signal});
          if(controller.signal.aborted)return;
          setPage(result);
          if(result.state==='ready'){
            setRows(previous=>Array.from(new Map([...(!request.cursor?[]:previous),...result.rows].map(row=>[row.id,row])).values()));
            if(result.error)setError('The latest refresh failed. Previously retrieved records are shown.');
            return;
          }
          if(result.state==='unavailable'){
            setError(result.error==='BUDGET_DEFERRED'?'The shared API request allowance is temporarily used up. Older launches remain available when it resets.':'The historical feed could not be retrieved.');
            return;
          }
          await new Promise(resolve=>setTimeout(resolve,2500));
          if(controller.signal.aborted)return;
        }
        setError('The worker is still retrieving this page. Retry shortly.');
      } catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Could not load past launches.');}
      finally{if(!controller.signal.aborted)setBusy(false);}
    })();
    return()=>controller.abort();
  },[request]);
  return <section aria-label="Past launches">
    <h2>Past launches</h2>
    <p>All past Cape Canaveral and Kennedy launches in the provider archive, newest first. This view is independent of your ZIP and viewing estimates.</p>
    <div className="notice-strip"><span>{page?.provider_count!==null&&page?.provider_count!==undefined?`Showing ${rows.length} of ${page.provider_count.toLocaleString()} historical records.`:'Checking the historical archive…'} {page?.fetched_at?`Page retrieved ${localTime(page.fetched_at,zone)}.`:''}</span></div>
    <p className="small muted">The upcoming feed and historical archive are separate. Dates below are published launch dates; each record also shows when the provider updated it.</p>
    <button className="secondary" disabled={busy} onClick={()=>setRequest(r=>({cursor:null,revision:r.revision+1}))}>Reload history</button>
    {error&&<div className="alert error" role="alert">{error} {page?.retry_at?`Retry after ${localTime(page.retry_at,zone)}.`:''} <button disabled={busy} onClick={()=>setRequest(r=>({...r,revision:r.revision+1}))}>Retry history page</button></div>}
    <div className="history-list">{rows.map(row=><article className="launch-card" key={row.id}>
      <div className="launch-main"><div className="small muted">{row.pad_name}</div><h3>{row.name}</h3>
        <p>{row.net?(row.time_known?localTime(row.net,zone):row.date_only?`${row.net.slice(0,10)} · date only (UTC)`:`${row.net.slice(0,10)} · recorded date; time precision unspecified (UTC)`):'Launch date unavailable'}</p>
        <p className="small muted">Record updated {row.updated_at?localTime(row.updated_at,zone):'at an unspecified time'}</p></div>
      <div className="launch-state"><span className="badge">{row.status}</span><a href={row.source_url} target="_blank" rel="noreferrer">View API record ↗</a></div>
    </article>)}</div>
    {busy&&<p role="status">Retrieving past launches…</p>}
    {!busy&&!error&&page?.state==='ready'&&rows.length===0&&<p>No historical records were returned.</p>}
    {!busy&&!error&&page?.next_cursor&&<button onClick={()=>setRequest(r=>({cursor:page.next_cursor!,revision:r.revision+1}))}>Load older launches</button>}
    {!busy&&!error&&page?.state==='ready'&&!page.next_cursor&&rows.length>0&&<p>End of the provider’s historical archive.</p>}
    {page&&<p className="small"><a className="history-source" href={page.source_url} target="_blank" rel="noreferrer">Historical source: The Space Devs Launch Library 2 ↗</a></p>}
  </section>;
}
