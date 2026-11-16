export const screens = ['ready', 'running', 'result', 'error', 'stopping'] as const;
export type Screen = typeof screens[number];
export const screenLabels: Record<Screen, string> = { ready: 'Inicio', running: 'En curso', result: 'Resultado', error: 'Error', stopping: 'Parada' };
export const DRAFT_LIMIT = 2000;
export type Iteration = 1 | 2 | 3;
export type PreviewState = { screen: Screen; draft: string; objective: string; attempts: number; closed: boolean; revision: number; iteration: Iteration };
export type Action = {type:'DRAFT'; value:string} | {type:'START'} | {type:'STOP'} | {type:'FINISH'; revision:number}
  | {type:'ADVANCE'; revision:number; from:Iteration} | {type:'FAIL'; revision:number} | {type:'CONFIRM_STOP'; revision:number} | {type:'NEW'};
export function screenFrom(value: string | null): Screen { return screens.includes(value as Screen) ? value as Screen : 'ready'; }
export function fixture(screen: Screen, draft: string): PreviewState {
  const objective = draft.slice(0,DRAFT_LIMIT);
  return { screen, draft:screen==='ready'||screen==='error'?objective:'', objective, attempts:screen === 'ready' ? 0 : 1, closed:false, revision:1, iteration:screen==='result'?3:screen==='stopping'?2:1 };
}
export function isBusy(state: PreviewState) { return state.screen === 'running' || (state.screen === 'stopping' && !state.closed); }
export function transition(s: PreviewState, a: Action): PreviewState {
  if(a.type==='DRAFT') return isBusy(s) ? s : {...s,draft:a.value.slice(0,DRAFT_LIMIT)};
  if(a.type==='START') return isBusy(s) || s.attempts>=3 || !s.draft.trim() ? s : {...s,screen:'running',objective:s.draft.trim(),draft:'',attempts:s.attempts+1,closed:false,revision:s.revision+1,iteration:1};
  if(a.type==='STOP') return s.screen==='running' ? {...s,screen:'stopping'} : s;
  if(a.type==='NEW') return isBusy(s) ? s : {...s,screen:'ready',closed:false,iteration:1};
  if(a.revision!==s.revision) return s;
  if(a.type==='ADVANCE') return s.screen==='running' && s.iteration===a.from && s.iteration<3 ? {...s,iteration:(s.iteration+1) as Iteration} : s;
  if(a.type==='FINISH') return s.screen==='running' && s.iteration===3 ? {...s,screen:'result'} : s;
  if(a.type==='FAIL') return s.screen==='running' ? {...s,screen:'error',draft:s.objective} : s;
  if(a.type==='CONFIRM_STOP') return s.screen==='stopping' && !s.closed ? {...s,closed:true,draft:s.objective} : s;
  return s;
}
export function readDraft(storage: Pick<Storage,'getItem'> | null, fallback: string): string {
  try { const v=storage?.getItem('neural-office.v541.draft'); return typeof v==='string' && v.length<=DRAFT_LIMIT ? v : fallback; } catch { return fallback; }
}
export function pageWindow(total: number, page: number, size=50) {
  if(!Number.isSafeInteger(total) || total<0 || !Number.isSafeInteger(size) || size<1) throw new RangeError('Invalid pagination');
  const count=Math.max(1,Math.ceil(total/size));
  const selected=Number.isSafeInteger(page) ? Math.min(Math.max(0,page),count-1) : 0;
  return { page:selected, pages:count, start:selected*size, end:Math.min(total,(selected+1)*size) };
}
