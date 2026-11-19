export type AttemptState='QUEUED'|'RUNNING'|'VERIFYING'|'STOPPING'|'RECOVERY_REQUIRED'|'ACCEPTED'|'REJECTED'|'FAILED'|'CANCELLED';
export type Project={id:string;active:boolean;approved:boolean;attempts_consumed:number;legacy_consumed:number;verified_versions:number;simulated_versions:number};
export type ModelCall={seq:number;role:string;state:string;started_ms?:number;completed_ms?:number};
export type Attempt={session_id?:string;cursor?:number;observed_ms?:number;source_name?:string|null;id:string;project_id:string;ordinal:number;state:AttemptState;revision:number;source_sha256:string;model:string;model_digest:string;roles:number;objective:string;mode:string;request_key:string;calls?:ModelCall[];report_available?:boolean;execution_error_code?:string|null;analysis_scope?:string;thread_id?:string;inspection_id?:string};
export type Snapshot={current_attempt?:Attempt|null;session_id:string;office_id:string;revision:number;cursor:number;projects:Project[];attempts:Attempt[];next:{project_after:number;attempt_after:number};has_more:{projects:boolean;attempts:boolean};lease:{attempt_id:string|null;generation:number}};
export type Model={model:string;model_digest:string;mode:string};
export type Source={entry_token:string;project_id:string;filename:string;sha256:string;bytes:number;session_id:string;expires_in_seconds:number};
export type Approval={session_id:string;approval_token:string;expected_revision:number;expires_in_seconds:number;project_id:string;source_sha256:string;objective:string;roles:number;model:string;model_digest:string;mode:string;attempts_consumed:number;attempts_remaining:number};
export type Pending={office_id:string;project_id:string;idempotency_key:string};
export type Event={seq:number;stamp_ns:string;kind:string;payload:Record<string,unknown>};
export type EventBatch={session_id:string;cursor:number;next_after:number;has_more:boolean;events:Event[]};
export type EventWindow={session_id:string;cursor:number;events:Event[]};
export const terminal=(state:AttemptState)=>['ACCEPTED','REJECTED','FAILED','CANCELLED'].includes(state);
export const stateLabels:Record<AttemptState,string>={QUEUED:'Encargo registrado',RUNNING:'Trabajando',VERIFYING:'Comprobando la entrega',STOPPING:'Confirmando la parada',RECOVERY_REQUIRED:'Necesita recuperación',ACCEPTED:'Entrega disponible',REJECTED:'Entrega no validada',FAILED:'El encargo falló',CANCELLED:'Encargo detenido'};
export function pendingKey(officeId:string){if(!id(officeId))throw Error('OFFICE_ID_INVALID');return `neural-office.v55.pending-command.${officeId}`;}
const id=(value:unknown):value is string=>typeof value==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(value);
const projectId=(value:unknown):value is string=>typeof value==='string'&&value.length>0&&[...value].length<=80&&!/[\uD800-\uDFFF]/u.test(value);
const counter=(value:unknown):value is number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0;
export function remainingLabel(consumed:number) {
  const left=Math.max(0,3-consumed);
  return left===1?'1 intento disponible':`${left} intentos disponibles`;
}
export function recordedDuration(call:ModelCall,observed:number|undefined,active:boolean) {
  const end=call.state==='DONE'?call.completed_ms:call.state==='STARTED'&&active?observed:undefined;
  if(!counter(call.started_ms)||!counter(end)||end<call.started_ms)return null;
  const seconds=Math.floor((end-call.started_ms)/1000);
  if(seconds<1)return '<1 s';
  if(seconds<60)return `${seconds} s`;
  return `${Math.floor(seconds/60)} min ${seconds%60} s`;
}
const record=(value:unknown):value is Record<string,unknown>=>value!==null&&typeof value==='object'&&!Array.isArray(value);
function samePending(a:Pending|null,b:Pending) {
  return a!==null&&a.office_id===b.office_id&&a.project_id===b.project_id&&a.idempotency_key===b.idempotency_key;
}
export function readPending(storage:Pick<Storage,'getItem'>,officeId:string):Pending|null {
  const raw=storage.getItem(pendingKey(officeId));
  if(raw===null) return null;
  const value:unknown=JSON.parse(raw);
  if(!record(value)||Object.keys(value).length!==3||value.office_id!==officeId||!projectId(value.project_id)||!id(value.idempotency_key)) throw Error('PENDING_IDENTITY_INVALID');
  return {office_id:officeId,project_id:value.project_id,idempotency_key:value.idempotency_key};
}
export function writePending(storage:Pick<Storage,'setItem'|'getItem'>,pending:Pending) {
  if(!projectId(pending.project_id)||!id(pending.idempotency_key))throw Error('PENDING_IDENTITY_INVALID');
  const existing=readPending(storage,pending.office_id);
  if(existing&&!samePending(existing,pending))throw Error('PENDING_IDENTITY_CONFLICT');
  if(existing)return;
  storage.setItem(pendingKey(pending.office_id),JSON.stringify(pending));
  const readback=readPending(storage,pending.office_id);
  if(!samePending(readback,pending))throw Error('PENDING_IDENTITY_NOT_SAVED');
}

// The v5.5 key and JSON shape stay readable after an update or a lost host
// response. Only V5.13 writers participate in the cross-window arbitration.
async function pendingLock<T>(officeId:string,mutate:()=>T):Promise<T> {
  const key=pendingKey(officeId);
  if(globalThis.navigator?.locks){
    const outcome=await navigator.locks.request(key,()=>{
      try{return {ok:true,value:mutate()} as const;}
      catch(error){return {ok:false,error} as const;}
    });
    if(!outcome.ok)throw outcome.error;
    return outcome.value;
  }
  if(!globalThis.indexedDB)throw Error('PENDING_COORDINATION_UNAVAILABLE');
  // A readwrite transaction grants exclusive access to the object store across
  // same-origin tabs. The short synchronous callback only touches localStorage.
  return new Promise<T>((resolve,reject)=>{
    const opening=indexedDB.open('neural-office.pending-coordination',1);
    let blocked=false;
    opening.onupgradeneeded=()=>opening.result.createObjectStore('offices');
    opening.onerror=()=>reject(Error('PENDING_COORDINATION_UNAVAILABLE'));
    opening.onblocked=()=>{blocked=true;reject(Error('PENDING_COORDINATION_UNAVAILABLE'));};
    opening.onsuccess=()=>{
      const db=opening.result;
      if(blocked){db.close();return;}
      db.onversionchange=()=>db.close();
      try{
        const transaction=db.transaction('offices','readwrite');
        let value:T;
        let failure:unknown;
        transaction.onabort=()=>{db.close();reject(failure??Error('PENDING_COORDINATION_UNAVAILABLE'));};
        transaction.oncomplete=()=>{db.close();resolve(value);};
        transaction.objectStore('offices').get(key).onsuccess=()=>{
          try{value=mutate();}catch(error){failure=error;transaction.abort();}
        };
      }catch(error){db.close();reject(error);}
    };
  });
}

/** Null grants the sender this slot. An existing identity must be reconciled. */
export function claimPending(storage:Pick<Storage,'setItem'|'getItem'>,pending:Pending):Promise<Pending|null> {
  return pendingLock(pending.office_id,()=>{
    const existing=readPending(storage,pending.office_id);
    if(existing)return existing;
    writePending(storage,pending);
    return null;
  });
}

/** A late terminal receipt must preserve a different window's pending command. */
export function releasePending(storage:Pick<Storage,'getItem'|'removeItem'>,pending:Pending):Promise<Pending|null> {
  return pendingLock(pending.office_id,()=>{
    const current=readPending(storage,pending.office_id);
    if(!samePending(current,pending))return current;
    storage.removeItem(pendingKey(pending.office_id));
    const remaining=readPending(storage,pending.office_id);
    if(samePending(remaining,pending))throw Error('PENDING_IDENTITY_NOT_CLEARED');
    return remaining;
  });
}
export function mergeEvents(current:EventWindow,batch:EventBatch):{window:EventWindow;resync:boolean} {
  if(!id(batch.session_id)||!counter(batch.cursor)||!counter(batch.next_after)||!Array.isArray(batch.events)||batch.events.length>200) throw Error('EVENT_CONTRACT');
  if(current.session_id!==batch.session_id) return {window:{session_id:batch.session_id,cursor:batch.cursor,events:[]},resync:true};
  let cursor=current.cursor;
  const added:Event[]=[];
  for(const event of batch.events) {
    if(!counter(event.seq)||event.seq<1||typeof event.kind!=='string'||!record(event.payload)) throw Error('EVENT_CONTRACT');
    if(event.seq<=cursor) continue;
    if(event.seq!==cursor+1) return {window:{...current,events:current.events.slice(-100)},resync:true};
    cursor=event.seq;added.push(event);
  }
  if(!added.length&&batch.next_after<=current.cursor)return {window:current,resync:false};
  if(batch.next_after!==cursor||batch.cursor<cursor) throw Error('EVENT_CURSOR_CONTRACT');
  return {window:{...current,cursor,events:[...current.events,...added].slice(-100)},resync:false};
}
export function acceptAttempt(current:Attempt|null,next:Attempt):Attempt {
  if(!id(next.id)||!projectId(next.project_id)||!counter(next.revision)||!(next.state in stateLabels)) throw Error('ATTEMPT_CONTRACT');
  if(current?.id!==next.id) return next;
  if(next.revision<current.revision) return current;
  if(terminal(current.state)&&next.state!==current.state) throw Error('TERMINAL_STATE_CHANGED');
  return next;
}
export function approvalMatches(approval:Approval,session:string,source:Source|null,objective:string,modelDigest:string,roles:number,expiresAt:number,now:number) {
  return approvalScopeMatches(approval,session,source,objective,modelDigest,roles,expiresAt,now)&&approval.attempts_remaining>0;
}
export function approvalScopeMatches(approval:Approval,session:string,source:Source|null,objective:string,modelDigest:string,roles:number,expiresAt:number,now:number) {
  return !!source&&approval.session_id===session&&source.session_id===session&&approval.project_id===source.project_id&&approval.source_sha256===source.sha256&&approval.objective===objective.trim()&&approval.model_digest===modelDigest&&approval.roles===roles&&Number.isFinite(expiresAt)&&now<expiresAt&&counter(approval.attempts_consumed)&&counter(approval.attempts_remaining)&&approval.attempts_remaining===Math.max(0,3-approval.attempts_consumed);
}
export function validateSnapshot(value:Snapshot) {
  if(!id(value.session_id)||!id(value.office_id)||!counter(value.cursor)||!counter(value.revision)||!Array.isArray(value.projects)||!Array.isArray(value.attempts)||value.projects.length>200||value.attempts.length>200) throw Error('SNAPSHOT_CONTRACT');
  for(const p of value.projects) if(!projectId(p.id)||!counter(p.attempts_consumed)) throw Error('PROJECT_CONTRACT');
  for(const a of value.attempts) acceptAttempt(null,a);
  if(value.current_attempt)acceptAttempt(null,value.current_attempt);
  if(!counter(value.next.project_after)||!counter(value.next.attempt_after)) throw Error('SNAPSHOT_CURSOR_CONTRACT');
  return value;
}
