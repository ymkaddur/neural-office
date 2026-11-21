import test from 'node:test';
import assert from 'node:assert/strict';
import {acceptAttempt,approvalMatches,claimPending,mergeEvents,pendingKey,readPending,recordedDuration,releasePending,remainingLabel,terminal,writePending} from './model.ts';
import type {Approval,Attempt,EventWindow,Pending,Source} from './model.ts';
import {readReport} from './client.ts';
import type {Requester} from './client.ts';
const storage=()=>{const data=new Map<string,string>();return {getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>{data.set(key,value);},removeItem:(key:string)=>{data.delete(key);}};};
const pending:Pending={office_id:'office-a',project_id:'project-a',idempotency_key:'same-command'};
const source:Source={entry_token:'source',project_id:'project-a',filename:'sample.html',sha256:'a'.repeat(64),bytes:20,session_id:'session-a',expires_in_seconds:120};
const approval:Approval={session_id:'session-a',approval_token:'approved',expected_revision:10,expires_in_seconds:120,project_id:'project-a',source_sha256:source.sha256,objective:'Review this HTML safely.',roles:1,model:'local',model_digest:'b'.repeat(64),mode:'ollama-owned',attempts_consumed:0,attempts_remaining:3};
const attempt:Attempt={id:'attempt',project_id:'project-a',ordinal:1,state:'RUNNING',revision:3,source_sha256:source.sha256,model:'local',model_digest:approval.model_digest,roles:1,objective:approval.objective,mode:'ollama-owned',request_key:pending.idempotency_key};
const matches=(a=approval,s=source,o=approval.objective,m=approval.model_digest,r=1,end=200,now=100)=>approvalMatches(a,'session-a',s,o,m,r,end,now);

test('simultaneous starts dispatch once and a late terminal receipt leaves the new owner intact',async()=>{
  const disk=storage();
  const choices=[pending,{...pending,project_id:'project-b',idempotency_key:'another-command'}];
  const sends:Pending[]=[];
  const outcomes=await Promise.all(choices.map(async choice=>{
    const occupied=await claimPending(disk,choice);
    if(!occupied)sends.push(choice);
    return occupied;
  }));
  assert.equal(sends.length,1);
  const first=sends[0],second=choices.find(p=>p!==first)!;
  assert.deepEqual(outcomes.find(value=>value!==null),first);
  assert.deepEqual(readPending(disk,first.office_id),first);
  assert.equal(await releasePending(disk,first),null);
  assert.equal(await claimPending(disk,second),null);
  assert.deepEqual(await releasePending(disk,first),second);
  assert.deepEqual(readPending(disk,second.office_id),second);
});

test('legacy records are reconciled without overwriting, and altered identities cannot release them',async()=>{
  const disk=storage();
  disk.setItem('neural-office.v55.pending-command.office-a',JSON.stringify(pending));
  const other={...pending,project_id:'other-project'};
  assert.deepEqual(await claimPending(disk,other),pending);
  assert.deepEqual(await claimPending(disk,pending),pending);
  assert.deepEqual(await releasePending(disk,other),pending);
  assert.throws(()=>writePending(disk,other),/IDENTITY_CONFLICT/);
  assert.equal(await releasePending(disk,pending),null);
  assert.equal(readPending(disk,pending.office_id),null);
});

test('failed claim or removal keeps an explicit failure instead of granting the slot',async()=>{
  const disk=storage();
  await assert.rejects(claimPending({...disk,setItem:()=>{}},pending),/NOT_SAVED/);
  assert.equal(await claimPending(disk,pending),null);
  await assert.rejects(releasePending({...disk,removeItem:()=>{}},pending),/NOT_CLEARED/);
  assert.deepEqual(readPending(disk,pending.office_id),pending);
});

test('a call shows only the interval attested by its two endpoints',()=>{
  const call={seq:1,role:'director',state:'STARTED',started_ms:1000};
  assert.equal(recordedDuration(call,1500,true),'<1 s');
  assert.equal(recordedDuration(call,62_999,true),'1 min 1 s');
  assert.equal(recordedDuration(call,23_000,false),null);
  assert.equal(recordedDuration({...call,state:'INTERRUPTED'},23_000,true),null);
  assert.equal(recordedDuration({...call,state:'DONE',completed_ms:3000},50_000,false),'2 s');
  assert.equal(recordedDuration({...call,state:'DONE'},50_000,false),null);
  assert.equal(recordedDuration({...call,started_ms:undefined},50_000,true),null);
  assert.equal(recordedDuration(call,999,true),null);
});

test('available attempts is the balance, including exhaustion and its singular form',()=>{
  assert.deepEqual([0,1,2,3].map(remainingLabel),['3 intentos disponibles','2 intentos disponibles','1 intento disponible','0 intentos disponibles']);
});

test('a lost acknowledgement retains exactly the original durable key after remount',()=>{
  const disk=storage();writePending(disk,pending);
  // The simulated transport response disappears; reopening only reads the saved identity.
  const reopened=readPending(disk,'office-a');
  assert.deepEqual(reopened,pending);
  assert.equal(readPending(disk,'office-a')?.idempotency_key,'same-command');
});
test('pending identities are separated by durable office, not ephemeral session',()=>{
  const disk=storage();writePending(disk,pending);
  assert.equal(readPending(disk,'office-b'),null);
  writePending(disk,{...pending,office_id:'office-b',idempotency_key:'another-command'});
  assert.equal(readPending(disk,'office-a')?.idempotency_key,'same-command');
  assert.equal(readPending(disk,'office-b')?.idempotency_key,'another-command');
});
test('unreliable or corrupt storage cannot silently lose the request identity',()=>{
  assert.throws(()=>writePending({getItem:()=>null,setItem:()=>{}},pending),/NOT_SAVED/);
  assert.throws(()=>writePending({getItem:()=>null,setItem:()=>{throw Error('quota');}},pending),/quota/);
  const disk=storage();disk.setItem(pendingKey('office-a'),JSON.stringify({...pending,office_id:'office-b'}));
  assert.throws(()=>readPending(disk,'office-a'),/IDENTITY_INVALID/);
});
test('approval is invalidated at the expiry boundary and by every work-defining input',()=>{
  assert.equal(matches(),true);
  assert.equal(matches(approval,source,approval.objective,approval.model_digest,1,100,100),false);
  assert.equal(matches({...approval,session_id:'another-session'}),false);
  assert.equal(matches(approval,{...source,sha256:'c'.repeat(64)}),false);
  assert.equal(matches(approval,source,'Different objective for the same file.'),false);
  assert.equal(matches(approval,source,approval.objective,'c'.repeat(64)),false);
  assert.equal(matches(approval,source,approval.objective,approval.model_digest,3),false);
  assert.equal(matches({...approval,attempts_remaining:0}),false);
});
test('duplicate and late event pages never advance the cursor or duplicate rows',()=>{
  const initial:EventWindow={session_id:'session-a',cursor:0,events:[]};
  const batch={session_id:'session-a',cursor:2,next_after:2,has_more:false,events:[1,2].map(seq=>({seq,stamp_ns:'1',kind:'EVENT',payload:{}}))};
  const once=mergeEvents(initial,batch).window;
  assert.equal(once.cursor,2);assert.equal(once.events.length,2);
  assert.deepEqual(mergeEvents(once,batch).window,once);
  const late={...batch,cursor:1,next_after:1,events:batch.events.slice(0,1)};
  assert.deepEqual(mergeEvents(once,late).window,once);
});
test('a missing event or a new session demands resynchronization without inventing transitions',()=>{
  const initial:EventWindow={session_id:'session-a',cursor:4,events:[]};
  const gap={session_id:'session-a',cursor:6,next_after:6,has_more:false,events:[{seq:6,stamp_ns:'1',kind:'DONE',payload:{}}]};
  const result=mergeEvents(initial,gap);
  assert.equal(result.resync,true);assert.equal(result.window.cursor,4);assert.equal(result.window.events.length,0);
  assert.equal(mergeEvents(initial,{...gap,session_id:'new-session'}).resync,true);
});
test('ten thousand events keep a bounded render window without losing cursor order',()=>{
  let state:EventWindow={session_id:'session-a',cursor:0,events:[]};
  for(let start=1;start<=10000;start+=100){
    const events=Array.from({length:100},(_,i)=>({seq:start+i,stamp_ns:'1',kind:'EVENT',payload:{}}));
    state=mergeEvents(state,{session_id:'session-a',cursor:start+99,next_after:start+99,has_more:false,events}).window;
    assert.ok(state.events.length<=100);
  }
  assert.equal(state.cursor,10000);assert.equal(state.events[0].seq,9901);
});
test('late snapshots cannot undo progress, and a requested stop is not terminal',()=>{
  assert.equal(acceptAttempt(attempt,{...attempt,revision:2,state:'QUEUED'}),attempt);
  assert.equal(terminal('STOPPING'),false);
  const stopped={...attempt,revision:5,state:'CANCELLED' as const};
  assert.throws(()=>acceptAttempt(stopped,{...attempt,revision:6}),/TERMINAL_STATE_CHANGED/);
});
const hash=async(data:Uint8Array)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),b=>b.toString(16).padStart(2,'0')).join('');
async function reportFixture(change?:(chunk:Record<string,unknown>)=>void, overrides:Record<string,unknown>={}){
  const text=JSON.stringify({schema:1,scope:'static-html-checks-v1',source_sha256:source.sha256,findings:[],model_commentary_status:'UNVERIFIED_ASSISTANCE',role_outputs:[{role:'director',content:'é🙂<script>literal text</script>'}],...overrides});
  const bytes=new TextEncoder().encode(text),sha=await hash(bytes);let calls=0;
  const send:Requester=async<T>(method:string,params:Record<string,unknown>={})=>{
    calls++;
    if(method==='report.get')return {attempt_id:'attempt',state:'ACCEPTED',sha256:sha,bytes:bytes.length,encoding:'utf-8',media_type:'application/json',verdict:{passed:true},mode:'fixture'} as T;
    const offset=params.offset as number,part=bytes.slice(offset,offset+7);
    const chunk={attempt_id:'attempt',sha256:sha,offset,next_offset:offset+part.length,eof:offset+part.length===bytes.length,chunk_sha256:await hash(part),base64:Buffer.from(part).toString('base64')};
    change?.(chunk);return chunk as T;
  };
  return {send,text,calls:()=>calls};
}
test('report bytes are assembled before UTF8 decoding and preserve text as data',async()=>{
  const fixture=await reportFixture(),result=await readReport(fixture.send,'attempt');
  assert.equal(result.text,fixture.text);assert.equal(result.report.role_outputs[0].content,'é🙂<script>literal text</script>');
});
test('a text-only Director reply is bound to its turn and has no authorized file excerpts',async()=>{
  const text={scope:'local-director-text-v1',thread_id:'main',inspection_id:'turn',authorized_fragments:[]};
  const fixture=await reportFixture(undefined,text);
  const {report}=await readReport(fixture.send,'attempt');
  assert.equal(report.role_outputs[0].content,'é🙂<script>literal text</script>');
  for(const change of [{scope:'local-inspection-excerpts-v1'},{inspection_id:''},{authorized_fragments:[{quote:'unasked'}]},{role_outputs:[]}]){
    const bad=await reportFixture(undefined,{...text,...change});
    await assert.rejects(()=>readReport(bad.send,'attempt'),/REPORT_EXCERPTS_INVALID/);
  }
});
test('report corruption, a stalled chunk and wrong attempt identity fail closed',async()=>{
  for(const change of [
    (c:Record<string,unknown>)=>{c.chunk_sha256='a'.repeat(64);},
    (c:Record<string,unknown>)=>{c.base64='';c.next_offset=c.offset;},
    (c:Record<string,unknown>)=>{c.attempt_id='another-attempt';},
  ]){
    const fixture=await reportFixture(change);await assert.rejects(()=>readReport(fixture.send,'attempt'),/REPORT_CHUNK_CHANGED/);assert.equal(fixture.calls(),2);
  }
});
test('leaving a report view stops further chunk requests',async()=>{
  const fixture=await reportFixture();await assert.rejects(()=>readReport(fixture.send,'attempt',()=>false),/SUPERSEDED/);assert.equal(fixture.calls(),1);
});

test('delivery requires agreement between accepted state and a passing verdict before reading content',async()=>{
  for(const [state,passed] of [['REJECTED',true],['ACCEPTED',false]]){
    const fixture=await reportFixture();
    const send:Requester=async<T>(method,params={})=>{
      assert.equal(method,'report.get');
      const meta=await fixture.send<Record<string,unknown>>(method,params);
      return {...meta,state,verdict:{passed}} as T;
    };
    await assert.rejects(()=>readReport(send,'attempt'),/REPORT_NOT_ACCEPTED/);
    assert.equal(fixture.calls(),1);
  }
});
