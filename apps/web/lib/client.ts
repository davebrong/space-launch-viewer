import type { components } from './api.generated';
export type Location = components['schemas']['location'];
export type Launch = components['schemas']['launch'];
export type Assessment = components['schemas']['assessment'];
export type Subscription = components['schemas']['subscription'];
export type Notice = components['schemas']['notification'];
export type Evidence = components['schemas']['route-evidence'];
export type HistoricalLaunchDetail = components['schemas']['HistoricalLaunchDetail'];

export async function apiAll<T>(path: string): Promise<T[]> {
  const rows:T[]=[];
  const seen=new Set<string>();
  let cursor:string|null=null;
  do {
    const response:Response=await fetch('/api/v1'+path+'?limit=100'+(cursor?'&cursor='+encodeURIComponent(cursor):''),{cache:'no-store'});
    if(!response.ok)throw new Error('Could not load saved records. Retry when the service is available.');
    rows.push(...await response.json() as T[]);
    cursor=response.headers.get('X-Next-Cursor');
    if(cursor&&seen.has(cursor))throw new Error('The service returned an invalid page cursor.');
    if(cursor)seen.add(cursor);
  } while(cursor);
  return rows;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = document.cookie.split('; ').find(s => s.startsWith('lv_csrf='))?.split('=')[1] || '';
  const res = await fetch('/api/v1' + path, { ...options, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token, ...options.headers }, cache: 'no-store' });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: 'Connection unavailable. Try again.' }));
    throw new Error(`${error.message}${error.request_id ? ' · Request ' + error.request_id : ''}`);
  }
  return res.status === 204 ? undefined as T : res.json();
}
export function localTime(value: string | null, zone: string | null): string {
  if (!value) return 'Time not yet published';
  const date = new Date(value);
  const options: Intl.DateTimeFormatOptions = { timeZone: zone || 'UTC', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' };
  const offset = new Intl.DateTimeFormat('en-US', {timeZone:zone || 'UTC',timeZoneName:'longOffset'}).formatToParts(date).find(p=>p.type==='timeZoneName')?.value;
  return `${new Intl.DateTimeFormat('en-US', options).format(date)} · ${offset}`;
}
export function launchTime(launch: Launch, zone: string | null): string {
  if (launch.actual_liftoff) return localTime(launch.actual_liftoff,zone);
  if (launch.time_precision === 'date') return `${launch.date_label} · date only (${launch.date_basis_timezone})`;
  if (launch.time_precision === 'unknown') return 'Launch time not yet confirmed';
  if (launch.time_precision === 'window' && launch.window) return `${localTime(launch.window.start, zone)} – ${localTime(launch.window.end, zone)} · conditional window`;
  return localTime(launch.net, zone);
}

export function launchDay(launch:Launch,zone:string):string {
  if(!launch.actual_liftoff&&launch.time_precision==='unknown')return 'Date to be announced';
  if(!launch.actual_liftoff&&launch.time_precision==='date')return `${launch.date_label} · source date (${launch.date_basis_timezone})`;
  const at=launch.actual_liftoff||launch.net;
  return at?new Intl.DateTimeFormat('en-US',{timeZone:zone,weekday:'long',year:'numeric',month:'long',day:'numeric'}).format(new Date(at)):'Date to be announced';
}

export type ViewingOpportunity = components['schemas']['ViewingOpportunity'];

export type LaunchHistoryPage = components['schemas']['LaunchHistoryPage'];
