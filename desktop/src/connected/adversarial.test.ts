import test from 'node:test';
import assert from 'node:assert/strict';
import {dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {build} from 'esbuild';
import {Window} from 'happy-dom';
import {acceptAttempt,readPending,validateSnapshot,writePending} from './model.ts';

// Execute the actual React component with a synthetic DOM and RPC peer.
// This exercises effect timing, not native rendering or assistive technology.
const bundle=build({stdin:{contents:`
  import React from 'react';
  import {createRoot} from 'react-dom/client';
  import {ConnectedWorkspace} from './ConnectedWorkspace.tsx';
  const root=createRoot(document.getElementById('root'));
  globalThis.disposeWorkspace=()=>root.unmount();
  root.render(<ConnectedWorkspace/>);`,resolveDir:dirname(fileURLToPath(import.meta.url)),sourcefile:'adversarial-entry.tsx',loader:'tsx'},
  write:false,bundle:true,format:'iife',platform:'browser',jsx:'automatic',
  define:{'process.env.NODE_ENV':'"production"','import.meta.env.DEV':'false'},loader:{'.css':'empty'}}).then(result=>result.outputFiles[0].text);
const wait=(ms:number)=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(condition:()=>boolean){
  const deadline=performance.now()+3000;
  while(!condition()){
    if(performance.now()>deadline)throw Error('Synthetic DOM condition timed out');
    await wait(10);
  }
}
const baseAttempt={id:'attempt',project_id:'project',ordinal:1,state:'RUNNING' as const,revision:1,source_sha256:'a'.repeat(64),model:'synthetic',model_digest:'b'.repeat(64),roles:1,objective:'Synthetic controlled task only.',mode:'fixture',request_key:'request-key',calls:[],report_available:false};
const project=(id:string,consumed=1)=>({id,active:false,approved:true,attempts_consumed:consumed,legacy_consumed:0,verified_versions:0,simulated_versions:0});
const snapshot=(attempts:any[]=[baseAttempt],projects=[project('project')])=>({session_id:'session',office_id:'office',revision:2,cursor:2,projects,attempts,next:{project_after:projects.length,attempt_after:attempts.length},has_more:{projects:false,attempts:false},lease:{attempt_id:null,generation:1}});
async function mount(send:(method:string,params:Record<string,unknown>)=>Promise<unknown>){
  const window=new Window({url:'http://tauri.localhost',width:1320,height:860});
  const later=window.setTimeout.bind(window),clear=window.clearTimeout.bind(window);
  let pollTimer:unknown, pollCleaned=false;
  // Observe the cleanup boundary instead of releasing the RPC after a guessed sleep.
  window.setTimeout=((callback:any,delay?:number,...args:any[])=>{const timer=later(callback,delay,...args);if(delay===250)pollTimer=timer;return timer;}) as any;
  window.clearTimeout=((timer:any)=>{if(timer===pollTimer)pollCleaned=true;return clear(timer);}) as any;
  window.document.body.innerHTML='<div id="root"></div>';
  Object.assign(window,{isTauri:true,__TAURI_INTERNALS__:{invoke:async(_command:string,{message}:any)=>({version:1,id:message.id,ok:true,result:await send(message.method,message.params),error:null})}});
  window.eval(await bundle);
  return {window,document:window.document,pollCleaned:()=>pollCleaned,close:async()=>{(window as any).disposeWorkspace();await window.happyDOM.close();}};
}

test('while a call runs, only its own history row adopts the newer receipt',async()=>{
  const queued={...baseAttempt,state:'QUEUED',revision:1,ordinal:2};
  const archived={...baseAttempt,id:'old',state:'CANCELLED',ordinal:1,objective:'Anterior'};
  const app=await mount(async method=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return {...snapshot([queued,archived],[project('project',2)]),current_attempt:queued};
    if(method==='attempt.get')return {...baseAttempt,session_id:'session',ordinal:2,revision:2,calls:[{seq:5,state:'STARTED',role:'director'}]};
    throw Error('Unexpected operation');
  });
  try{
    await until(()=>!!app.document.querySelector('.connected-call-list li'));
    const names=Array.from(app.document.querySelectorAll('.connected-history small'),el=>el.textContent);
    assert.deepEqual(names,['Trabajando · intento 2','Encargo detenido · intento 1']);
  }finally{await app.close();}
});

for(const delayed of [false,true])test(`terminal polling reconciles saved history even when event delivery is ${delayed?'delayed':'immediate'}`,async()=>{
  let gets=0,snapshots=0,release:(()=>void)|undefined;
  const app=await mount(async method=>{
    if(method==='describe')return {session_id:'session',office_id:'office',inference:'injected-test-backend'};
    if(method==='snapshot.get'){snapshots++;return snapshot([{...baseAttempt,state:gets>1?'CANCELLED':'RUNNING',revision:gets>1?2:1}]);}
    if(method==='attempt.get'){gets++;return {...baseAttempt,state:gets>1?'CANCELLED':'RUNNING',revision:gets>1?2:1};}
    if(method==='models.list')return {models:[],session_id:'session'};
    if(method==='events.read'){
      if(delayed)await new Promise<void>(resolve=>{release=resolve;});
      return {session_id:'session',cursor:3,next_after:3,has_more:false,events:[{seq:3,stamp_ns:'1',kind:'CANCELLED',payload:{attempt:'attempt'}}]};
    }
    throw Error('Unexpected synthetic RPC');
  });
  try{
    await until(()=>app.document.body.textContent.includes('Encargo detenido'));
    if(delayed)await until(app.pollCleaned);
    release?.();await wait(50);
    assert.equal(snapshots,2,'A terminal render must not cancel its own history refresh');
    assert.match(app.document.querySelector('.connected-history')?.textContent||'',/Encargo detenido/);
  }finally{release?.();await app.close();}
});

test('a confirmed terminal state survives a failed balance refresh',async()=>{
  let snapshots=0,reads=0;
  const app=await mount(async method=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get'){if(++snapshots>1)throw 'HOST_RESPONSE_TIMEOUT';return snapshot();}
    if(method==='attempt.get')return {...baseAttempt,state:++reads>1?'CANCELLED':'RUNNING',revision:reads};
    throw Error('unexpected operation');
  });
  try{
    await until(()=>app.document.body.textContent.includes('HOST_RESPONSE_TIMEOUT'));
    assert.match(app.document.querySelector('.connected-director-heading [role="status"]')!.textContent,/Encargo detenido/);
    assert.match(app.document.querySelector('.connected-quota')!.textContent,/Cuota pendiente/);
    assert.equal(app.document.querySelector('.active-work'),null);
    assert.equal(snapshots,2);
  }finally{await app.close();}
});

test('Stop submits one active identity during an unfinished archive read',async()=>{
  const archive={...baseAttempt,id:'archive',state:'FAILED',objective:'Consulta anterior'};
  let open:(()=>void)|undefined,finish:(()=>void)|undefined;
  const cancelled:unknown[]=[];
  const app=await mount(async(method,params)=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return {...snapshot([archive]),current_attempt:baseAttempt};
    if(method==='attempt.get'&&params.attempt_id==='archive'){
      await new Promise<void>(r=>open=r);return archive;
    }
    if(method==='attempt.get')return baseAttempt;
    if(method==='attempt.cancel'){
      cancelled.push(params.attempt_id);await new Promise<void>(r=>finish=r);
      return {...baseAttempt,state:'CANCELLED',revision:3,session_id:'session'};
    }
    throw Error('unexpected operation');
  });
  try{
    await until(()=>!!app.document.querySelector('.connected-history button:not(:disabled)'));
    app.document.querySelector<HTMLButtonElement>('.connected-history button')!.click();
    await until(()=>!!open);
    const stop=app.document.querySelector<HTMLButtonElement>('.active-work button')!;
    assert.equal(stop.disabled,false);stop.click();stop.click();
    await until(()=>!!finish);
    assert.deepEqual(cancelled,['attempt']);finish!();open!();
    await until(()=>app.document.querySelector('.active-work')===null);
    assert.equal(cancelled.length,1);
  }finally{finish?.();open?.();await app.close();}
});

for(const remaining of [0,1])test(`approval with ${remaining} remaining distinguishes exhaustion and expiry without starting`,async()=>{
  let previews=0,starts=0;
  const app=await mount(async(method,params)=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return snapshot([],[project('project',previews?3-remaining:2)]);
    if(method==='models.list')return {session_id:'session',models:[{model:'synthetic',model_digest:'b'.repeat(64),mode:'fixture'}]};
    if(method==='source.pick')return {session_id:'session',project_id:'project',filename:'ejemplo.html',entry_token:'grant',bytes:60,sha256:'a'.repeat(64)};
    if(method==='attempt.preview'){previews++;return {session_id:'session',approval_token:'ok',project_id:'project',objective:params.objective,roles:1,model_digest:'b'.repeat(64),source_sha256:'a'.repeat(64),attempts_consumed:3-remaining,attempts_remaining:remaining,expires_in_seconds:1};}
    if(method==='attempt.start')starts++;
    throw Error('unexpected operation');
  });
  try{
    await until(()=>!!app.document.querySelector('.connected-projects button:not(:disabled)'));
    await enterDraft(app,'Revisar el documento seleccionado.');
    app.document.querySelector<HTMLButtonElement>('.source-picker')!.click();
    const submit=()=>app.document.querySelector<HTMLButtonElement>('button[type="submit"]');
    await until(()=>submit()?.disabled===false);submit()!.click();
    if(remaining){
      await until(()=>!!app.document.querySelector('dialog[open]'));
      assert.match(app.document.querySelector('dialog')!.textContent,/el saldo pasará a 0 de 3/);
    }
    await until(()=>app.document.body.textContent.includes(remaining?'APPROVAL_INVALID_OR_EXPIRED':'ATTEMPT_BUDGET_EXHAUSTED'));
    assert.equal(app.document.querySelector('.connected-quota span:last-child')!.textContent,(remaining===1?'1 intento disponible':'0 intentos disponibles'));
    assert.equal(submit()!.disabled,remaining===0);
    assert.ok(!app.document.body.textContent.includes('APPROVAL_CHANGED'));
    assert.ok(!app.document.querySelector('dialog[open]'));
    assert.deepEqual([previews,starts],[1,0]);
  }finally{await app.close();}
});

test('selected project history includes all three attempts across the global page boundary',async()=>{
  const projects=Array.from({length:50},(_,i)=>project(`p${i}`,3));
  const attempts=Array.from({length:150},(_,i)=>({...baseAttempt,id:`a${i}`,project_id:`p${Math.floor(i/3)}`,ordinal:i%3+1,state:'CANCELLED',request_key:`k${i}`,objective:`Encargo ${i}`}));
  let pages=0;
  let release:(()=>void)|undefined;
  const app=await mount(async(method,params)=>{
    if(method==='describe')return {session_id:'session',office_id:'office',inference:'injected-test-backend'};
    if(method==='snapshot.get'){
      pages++;
      const after=params.attempt_after as number;
      const result=snapshot(attempts.slice(after,after+100),(params.project_after as number)>0?[]:projects);
      result.next={project_after:50,attempt_after:Math.min(after+100,150)};
      result.has_more.attempts=after===0;return result;
    }
    if(method==='project.history'){
      const id=params.project_id;
      if(id==='p33')await new Promise<void>(resolve=>{release=resolve;});
      return {office_id:'office',session_id:'session',revision:3,project_id:id,attempts:attempts.filter(a=>a.project_id===id).reverse()};
    }
    if(method==='models.list')return {models:[],session_id:'session'};
    throw Error('Unexpected synthetic RPC');
  });
  try{
    await until(()=>app.document.querySelectorAll('.connected-projects button').length===50);
    const select=(id:string)=>app.document.querySelector<HTMLButtonElement>(`.connected-projects button[title="${id}"]`)!.click();
    select('p33');await until(()=>!!release);
    assert.match(app.document.querySelector('.connected-history')!.textContent,/Leyendo historial/);
    select('p49');await until(()=>app.document.querySelectorAll('.connected-history button').length===3);
    release!();await wait(30);
    assert.deepEqual(Array.from(app.document.querySelectorAll('.connected-history strong'),r=>r.textContent),['Encargo 149','Encargo 148','Encargo 147']);
    assert.equal(pages,1);
    assert.equal(app.document.querySelectorAll('.connected-projects button').length,50);
    assert.match(app.document.querySelector('.connected-quota')?.textContent||'',/0 intentos disponibles/);
  }finally{release?.();await app.close();}
});

test('browsing a second project page retains the selected balance only within its revision',async()=>{
  const app=await mount(async(method,params)=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get'){
      const after=Number(params.project_after);
      const result=snapshot([],[project(after?'other':'project',after?0:2)]);
      result.next.project_after=after?101:100;result.has_more.projects=after===0;
      return result;
    }
    throw Error('unexpected operation');
  });
  try{
    await until(()=>app.document.querySelector('.connected-quota span:last-child')?.textContent==='1 intento disponible');
    Array.from(app.document.querySelectorAll('button')).find(b=>b.textContent.includes('Siguientes proyectos'))!.click();
    await until(()=>!!app.document.querySelector('.connected-projects [title="other"]'));
    assert.equal(app.document.querySelector('.connected-quota span:last-child')!.textContent,'1 intento disponible');
    assert.match(app.document.querySelector('.connected-new-project')!.textContent,/1 intento disponible/);
    app.document.querySelector<HTMLButtonElement>('.connected-projects [title="other"]')!.click();
    await until(()=>app.document.querySelector('.connected-quota span:last-child')?.textContent==='3 intentos disponibles');
  }finally{await app.close();}
});

test('drafting during live work preserves the next objective without submitting it',async()=>{
  let finished=false;
  const methods:string[]=[];
  const row=()=>({...baseAttempt,state:finished?'CANCELLED':'RUNNING',revision:finished?3:1,calls:[{seq:27,role:'director',state:'DONE'}]});
  const app=await mount(async method=>{
    methods.push(method);
    if(method==='describe')return {office_id:'office',session_id:'session'};
    if(method==='snapshot.get')return snapshot([row()]);
    if(method==='attempt.get')return row();
    if(method==='events.read')return {session_id:'session',cursor:2,next_after:2,has_more:false,events:[]};
    if(method==='models.list')return {session_id:'session',models:[]};
    throw Error('Unexpected RPC');
  });
  try{
    await until(()=>app.document.querySelector('.connected-call-list li')?.textContent.includes('Respuesta registrada')===true);
    assert.equal(app.document.querySelector('.call-order')?.textContent,'1');
    const field=app.document.querySelector('#next-objective') as any;
    field.closest('details').open=true;field.focus();
    field.value='Revisar el segundo documento';
    field.dispatchEvent(new app.window.Event('input',{bubbles:true}));
    field.dispatchEvent(new app.window.KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,bubbles:true}));
    finished=true;
    const reopen=()=>Array.from(app.document.querySelectorAll('button')).find(b=>b.textContent==='Volver al borrador');
    await until(()=>!!reopen());
    assert.equal(app.document.activeElement,field);
    reopen()!.click();
    await until(()=>(app.document.querySelector('#connected-objective') as any)?.value===field.value);
    assert.match(app.document.querySelector('.connected-quota')!.textContent,/2 intentos disponibles/);
    assert.ok(!methods.some(m=>['attempt.preview','attempt.start','attempt.cancel','attempt.recover'].includes(m)));
  }finally{await app.close();}
});

test('legacy project identifiers roundtrip without weakening opaque request identities',()=>{
  const disk=new Map<string,string>();
  const storage={getItem:(key:string)=>disk.get(key)??null,setItem:(key:string,value:string)=>{disk.set(key,value);}};
  for(const projectId of ['Área de revisión','x'.repeat(65),'x'.repeat(80),'🙂'.repeat(80),' ','nul\0project']){
    const pending={office_id:'office',project_id:projectId,idempotency_key:'command'};
    writePending(storage,pending);assert.deepEqual(readPending(storage,'office'),pending);
    const row={...baseAttempt,project_id:projectId};
    assert.equal(acceptAttempt(null,row).project_id,projectId);
    assert.equal(validateSnapshot(snapshot([row],[project(projectId)])).projects[0].id,projectId);
  }
  for(const invalid of ['','x'.repeat(81),'🙂'.repeat(81),'bad\ud800']){
    assert.throws(()=>acceptAttempt(null,{...baseAttempt,project_id:invalid}),/CONTRACT/);
  }
  assert.throws(()=>acceptAttempt(null,{...baseAttempt,id:'opaque id with spaces'}),/CONTRACT/);
});

async function openSavedAttempt(app:Awaited<ReturnType<typeof mount>>){
  await until(()=>!!app.document.querySelector('.connected-history button:not(:disabled)'));
  (app.document.querySelector('.connected-history button') as any).click();
  await until(()=>!!app.document.querySelector('.connected-user-request'));
}
function validReport(scope='static-html-checks-v1',findings:{code:string;line:number;column:number}[]=[]){
  const text=JSON.stringify({schema:1,scope,source_sha256:baseAttempt.source_sha256,findings,model_commentary_status:'UNVERIFIED_ASSISTANCE',role_outputs:[{role:'director',content:'Synthetic report for component verification.'}]});
  const bytes=Buffer.from(text),sha=createHash('sha256').update(bytes).digest('hex');
  return {
    meta:{attempt_id:baseAttempt.id,state:'ACCEPTED',sha256:sha,bytes:bytes.length,encoding:'utf-8',media_type:'application/json',verdict:{passed:true,coverage:'synthetic'},mode:'fixture'},
    chunk:{attempt_id:baseAttempt.id,sha256:sha,offset:0,next_offset:bytes.length,eof:true,chunk_sha256:sha,base64:bytes.toString('base64')},
  };
}
function savedAttemptPeer(attempt:any,reportReply?:(method:string,params:Record<string,unknown>)=>Promise<unknown>){
  const calls:{method:string;params:Record<string,unknown>}[]=[];
  return {calls,send:async(method:string,params:Record<string,unknown>)=>{
    calls.push({method,params});
    if(method==='describe')return {session_id:'session',office_id:'office',inference:'injected-test-backend'};
    if(method==='snapshot.get')return snapshot([attempt]);
    if(method==='attempt.get')return {...attempt};
    if(method==='models.list')return {models:[],session_id:'session'};
    if(method==='report.get'||method==='report.read'){
      assert.equal(params.attempt_id,attempt.id,'Report reads must stay bound to the saved attempt');
      if(reportReply)return reportReply(method,params);
    }
    throw Error(`Unexpected synthetic RPC: ${method}`);
  }};
}

test('a rejected attempt cannot present retained bytes as a delivery',async()=>{
  const fixture=validReport();
  const peer=savedAttemptPeer({...baseAttempt,state:'REJECTED',report_available:true},async method=>
    method==='report.get'?{...fixture.meta,state:'REJECTED',verdict:{passed:false}}:fixture.chunk);
  const app=await mount(peer.send);
  try{
    await openSavedAttempt(app);
    await until(()=>!!app.document.querySelector('.delivery-state'));
    assert.equal(app.document.querySelector('.delivery-state')?.textContent,'Sin informe validado');
    assert.equal(peer.calls.filter(call=>call.method.startsWith('report.')).length,0);
  }finally{await app.close();}
});

for(const state of ['CANCELLED','FAILED'] as const)test(`terminal ${state} delivery does not promise a future report`,async()=>{
  const peer=savedAttemptPeer({...baseAttempt,state,report_available:false});
  const app=await mount(peer.send);
  try{
    await openSavedAttempt(app);
    assert.match(app.document.querySelector('.delivery-empty')?.textContent||'',/No hay informe validado/);
    const status=app.document.querySelector('.delivery-state');
    assert.ok(status?.textContent.trim(),'The delivery must retain an explicit state');
    assert.doesNotMatch(status.textContent,/Esperando informe/,
      'A terminal attempt without a report cannot advertise that its report is still coming');
    assert.equal(peer.calls.filter(call=>call.method==='report.get'||call.method==='attempt.start').length,0);
  }finally{await app.close();}
});

for(const outcome of ['deferred','failed'] as const)test(`accepted report ${outcome} read is not reported as an absent validated report`,async()=>{
  const fixture=validReport();let release:(()=>void)|undefined;
  const peer=savedAttemptPeer({...baseAttempt,state:'ACCEPTED',report_available:true},async method=>{
    if(method==='report.read')return fixture.chunk;
    if(outcome==='failed')throw 'REPORT_TEMPORARILY_UNAVAILABLE';
    await new Promise<void>(resolve=>{release=resolve;});
    return fixture.meta;
  });
  const app=await mount(peer.send);
  try{
    await openSavedAttempt(app);
    await until(()=>peer.calls.some(call=>call.method==='report.get'));
    if(outcome==='failed')await until(()=>!!app.document.querySelector('[role="alert"]'));
    const delivery=app.document.querySelector('.connected-delivery-body');
    assert.ok(delivery?.textContent.trim(),'The existing report needs a visible read state');
    assert.doesNotMatch(delivery.textContent,/No hay informe validado/,
      'The ledger says the report exists; its read state must not overwrite that fact');
    assert.equal(peer.calls.filter(call=>call.method==='attempt.start').length,0);
  }finally{release?.();await app.close();}
});

for(const scope of ['static-html-checks-v1','static-html-checks-v2','static-html-checks-v3','static-html-checks-v4'])test(`${scope} accepted report renders the verified bytes without another attempt`,async()=>{
  const fixture=validReport(scope);
  const peer=savedAttemptPeer({...baseAttempt,state:'ACCEPTED',report_available:true},async method=>method==='report.get'?fixture.meta:fixture.chunk);
  const app=await mount(peer.send);
  try{
    await openSavedAttempt(app);
    await until(()=>!!app.document.querySelector('.connected-report'));
    assert.match(app.document.querySelector('.connected-report')?.textContent||'',/Synthetic report for component verification\./);
    assert.equal(app.document.querySelector('.delivery-state')?.textContent,'Informe recibido');
    assert.equal(peer.calls.filter(call=>call.method==='attempt.start').length,0);
  }finally{await app.close();}
});

test('a delayed verified report preserves the selected evidence tab and its focus',async()=>{
  const fixture=validReport('static-html-checks-v4');let release:(()=>void)|undefined;
  const peer=savedAttemptPeer({...baseAttempt,state:'ACCEPTED',report_available:true},async method=>{
    if(method==='report.get')return fixture.meta;
    await new Promise<void>(r=>release=r);return fixture.chunk;
  });
  const app=await mount(peer.send);
  try{
    await openSavedAttempt(app);await until(()=>!!release);
    const tab=app.document.querySelector<HTMLButtonElement>('#tab-evidence')!;
    tab.focus();tab.click();await until(()=>tab.getAttribute('aria-selected')==='true');
    release!();await until(()=>app.document.querySelector('.delivery-state')?.textContent==='Informe recibido');
    assert.equal(tab.getAttribute('aria-selected'),'true');assert.equal(app.document.activeElement,tab);
    assert.match(app.document.querySelector('#panel-evidence')!.textContent,new RegExp(fixture.meta.sha256));
  }finally{release?.();await app.close();}
});

test('Actualizar retries a transient report read for the unchanged accepted attempt without starting work',async()=>{
  const fixture=validReport();let reads=0;
  const peer=savedAttemptPeer({...baseAttempt,state:'ACCEPTED',report_available:true},async method=>{
    if(method==='report.read')return fixture.chunk;
    if(++reads===1)throw 'REPORT_TEMPORARILY_UNAVAILABLE';
    return fixture.meta;
  });
  const app=await mount(peer.send);
  try{
    await openSavedAttempt(app);
    await until(()=>!!app.document.querySelector('[role="alert"]'));
    assert.equal(reads,1,'A failed report read must not start an uncontrolled retry loop');
    const refresh=Array.from(app.document.querySelectorAll('button')).find(button=>button.textContent==='Actualizar');
    assert.ok(refresh);assert.equal(refresh.disabled,false);refresh.click();
    await until(()=>peer.calls.filter(call=>call.method==='attempt.get').length===2&&!refresh.disabled);
    assert.equal(peer.calls.filter(call=>call.method==='attempt.start').length,0);
    await assert.doesNotReject(()=>until(()=>reads===2),
      'Explicit refresh must retry the report even when attempt ID, revision and availability are unchanged');
    await until(()=>!!app.document.querySelector('.connected-report'));
    assert.equal(peer.calls.filter(call=>call.method==='report.get').length,2);
    assert.equal(peer.calls.filter(call=>call.method==='report.read').length,1);
    assert.equal(peer.calls.filter(call=>call.method==='attempt.start').length,0);
    assert.match(app.document.querySelector('.connected-quota')?.textContent||'',/2 intentos disponibles/);
  }finally{await app.close();}
});

test('an unverified terminal delivery is never described as waiting for its first call',async()=>{
  const peer=savedAttemptPeer({...baseAttempt,state:'REJECTED',report_available:false});
  const app=await mount(peer.send);
  try{
    await openSavedAttempt(app);
    const note=app.document.querySelector('.connected-work-status')!.textContent;
    assert.match(note,/no superó la verificación/);
    assert.doesNotMatch(note,/Esperando/);
  }finally{await app.close();}
});

async function enterDraft(app:Awaited<ReturnType<typeof mount>>,text:string){
  if(!app.document.querySelector('#connected-model')){
    const action=Array.from(app.document.querySelectorAll('button')).find(b=>b.textContent==='Consultar al Director');
    assert.ok(action);action.click();await until(()=>!!app.document.querySelector('#connected-model'));
  }
  writeObjective(app,text);
}
function writeObjective(app:Awaited<ReturnType<typeof mount>>,text:string){
  const field=app.document.querySelector('#connected-objective') as any;
  assert.ok(field);
  const setter=Object.getOwnPropertyDescriptor(app.window.HTMLTextAreaElement.prototype,'value')!.set!;
  setter.call(field,text);
  field.dispatchEvent(new app.window.Event('input',{bubbles:true}));
}

test('reading history returns to the unsent draft without reserving work',async()=>{
  const peer=savedAttemptPeer({...baseAttempt,state:'CANCELLED',report_available:false});
  const app=await mount(peer.send);
  try{
    await until(()=>!!app.document.querySelector('.connected-history button:not(:disabled)'));
    await enterDraft(app,'Revisar el formulario antes de publicarlo.');
    await until(()=>app.document.querySelector('.brief-writing')?.textContent.includes('42/2000')===true);
    await openSavedAttempt(app);
    const back=Array.from(app.document.querySelectorAll('button')).find(button=>button.textContent.includes('Volver al borrador'));
    assert.ok(back,'History is a read operation: the composer needs a return path');
    back.click();
    await until(()=>!!app.document.querySelector('#connected-objective'));
    assert.equal((app.document.querySelector('#connected-objective') as any).value,'Revisar el formulario antes de publicarlo.');
    assert.equal(peer.calls.filter(call=>call.method==='attempt.start'||call.method==='attempt.preview').length,0);
  }finally{await app.close();}
});

test('switching projects retains separate bounded in-memory drafts',async()=>{
  const calls:string[]=[];
  const app=await mount(async method=>{
    calls.push(method);
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return snapshot([],[project('alpha',0),project('beta',0)]);
    if(method==='models.list')return {models:[],session_id:'session'};
    throw Error('Unexpected RPC while navigating drafts');
  });
  const choose=(id:string)=>(app.document.querySelector(`.connected-projects button[title="${id}"]`) as any).click();
  try{
    await until(()=>app.document.querySelectorAll('.connected-projects button').length===2);
    writeObjective(app,'Alpha: revisar los campos.');await wait(20);
    choose('beta');await wait(20);
    assert.equal((app.document.querySelector('#connected-objective') as any).value,'');
    writeObjective(app,'Beta: revisar las imágenes.');await wait(20);
    choose('alpha');await wait(20);
    assert.equal((app.document.querySelector('#connected-objective') as any).value,'Alpha: revisar los campos.');
    choose('beta');await wait(20);
    assert.equal((app.document.querySelector('#connected-objective') as any).value,'Beta: revisar las imágenes.');
    assert.equal(calls.filter(method=>method.startsWith('attempt.')).length,0);
  }finally{await app.close();}
});

test('bootstrap cannot expose another project while its active attempt is still loading',async()=>{
  let release:(()=>void)|undefined,requested=false;
  const app=await mount(async method=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return snapshot([baseAttempt],[project('project',1),project('other',0)]);
    if(method==='attempt.get'){
      requested=true;await new Promise<void>(resolve=>{release=resolve;});return {...baseAttempt};
    }
    if(method==='models.list')return {models:[],session_id:'session'};
    if(method==='events.read')return {session_id:'session',cursor:2,next_after:2,has_more:false,events:[]};
    throw Error('Unexpected RPC');
  });
  try{
    await until(()=>requested&&!!app.document.querySelector('[title="other"]'));
    assert.equal((app.document.querySelector('[title="other"]') as any).disabled,true,
      'Bootstrap must reconcile the active identity before enabling project changes');
    const composer=app.document.querySelector('#connected-objective') as any;
    assert.ok(!composer||composer.disabled,'No editable composer before active identity reconciliation');
    release?.();await until(()=>!!app.document.querySelector('.connected-user-request'));
    assert.equal(app.document.querySelector('.connected-projects .selected')?.getAttribute('title'),'project');
    assert.match(app.document.querySelector('.connected-quota')?.textContent||'',/2 intentos disponibles/);
  }finally{release?.();await app.close();}
});

test('a failed bootstrap detail read keeps the authoritative active identity and can be refreshed',async()=>{
  let reads=0;
  const app=await mount(async method=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return snapshot([baseAttempt],[project('project',1),project('other',0)]);
    if(method==='attempt.get'){if(++reads===1)throw 'TRANSIENT_READ_FAILURE';return {...baseAttempt};}
    if(method==='events.read')return {session_id:'session',cursor:2,next_after:2,has_more:false,events:[]};
    if(method==='models.list')return {models:[],session_id:'session'};
    throw Error('Unexpected RPC');
  });
  try{
    await until(()=>!!app.document.querySelector('[role="alert"]'));
    assert.ok(!app.document.querySelector('#connected-objective'),'A failed detail read cannot erase the active snapshot');
    assert.equal((app.document.querySelector('[title="other"]') as any).disabled,true);
    assert.equal(app.document.querySelector('.connected-projects .selected')?.getAttribute('title'),'project');
    const refresh=Array.from(app.document.querySelectorAll('button')).find(button=>button.textContent==='Actualizar');
    assert.ok(refresh);await until(()=>!refresh.disabled);refresh.click();
    await until(()=>reads>=2&&!refresh.disabled);
    assert.match(app.document.querySelector('.connected-quota')?.textContent||'',/2 intentos disponibles/);
    assert.ok(!app.document.querySelector('[role="alert"]'),app.document.querySelector('[role="alert"]')?.textContent);
  }finally{await app.close();}
});

for(const transport of ['HOST_REQUEST_TIMEOUT','HOST_DISCONNECTED'])for(const found of [true,false])test(`lost start acknowledgement with ${transport} and durable receipt=${found}`,async()=>{
  let starts=0,key='',lookups=0,session='session';
  const app=await mount(async(method,params)=>{
    if(method==='describe'){if(starts>0&&transport==='HOST_DISCONNECTED')session='replacement';return {session_id:session,office_id:'office'};}
    if(method==='snapshot.get')return {...snapshot([],[project('project',found&&starts?1:0),project('other',0)]),session_id:session};
    if(method==='models.list')return {session_id:session,models:[{model:'synthetic',model_digest:'b'.repeat(64),mode:'fixture'}]};
    if(method==='source.pick')return {entry_token:'source',project_id:'project',filename:'synthetic.html',sha256:'a'.repeat(64),bytes:60,session_id:'session',expires_in_seconds:120};
    if(method==='attempt.preview')return {session_id:'session',approval_token:'approval',expected_revision:2,expires_in_seconds:120,project_id:'project',source_sha256:'a'.repeat(64),objective:params.objective,roles:1,model:'synthetic',model_digest:'b'.repeat(64),mode:'fixture',attempts_consumed:0,attempts_remaining:3};
    if(method==='attempt.start'){starts++;key=String(params.idempotency_key);throw transport;}
    if(method==='attempt.lookup'){lookups++;assert.equal(params.idempotency_key,key);return {session_id:session,office_id:'office',found,attempt:found?{...baseAttempt,state:'CANCELLED',request_key:key}:null};}
    throw Error(`Unexpected RPC ${method}`);
  });
  const button=(text:string)=>Array.from(app.document.querySelectorAll('button')).find(item=>item.textContent.includes(text));
  try{
    await until(()=>!!app.document.querySelector('.connected-projects button:not(:disabled)'));
    await enterDraft(app,'Revisión pendiente de confirmar.');await wait(20);
    button('Elegir archivo HTML')!.click();await until(()=>!!button('synthetic.html'));
    (app.document.querySelector('[title="other"]') as any).click();await wait(20);
    (app.document.querySelector('[title="project"]') as any).click();await wait(20);
    app.document.querySelector('form')!.dispatchEvent(new app.window.Event('submit',{bubbles:true,cancelable:true}));
    await until(()=>!!button('Autorizar y ejecutar'));button('Autorizar y ejecutar')!.click();
    await until(()=>starts===1&&!!app.document.querySelector('[role="alert"]'));
    await until(()=>!!button('Comprobar encargo')&&!button('Comprobar encargo')!.disabled);
    button('Comprobar encargo')!.click();await until(()=>lookups===1);
    if(found){
      await until(()=>!!button('Preparar otro encargo')&&!button('Preparar otro encargo')!.disabled);
      assert.ok(!button('Volver al borrador'),'The confirmed sent draft is not an unsent task');
      button('Preparar otro encargo')!.click();await until(()=>!!app.document.querySelector('#connected-objective'));
      assert.equal((app.document.querySelector('#connected-objective') as any).value,'');
      assert.ok(!button('synthetic.html'));
    }else{
      await until(()=>!!button('Descartar petición sin reserva')&&!button('Descartar petición sin reserva')!.disabled);
      button('Descartar petición sin reserva')!.click();await until(()=>!(app.document.querySelector('#connected-objective') as any)?.disabled);
      assert.equal((app.document.querySelector('#connected-objective') as any).value,'Revisión pendiente de confirmar.');
      assert.equal(!!button('synthetic.html'),transport!=='HOST_DISCONNECTED','A new peer needs a new source selection');
    }
    assert.equal(starts,1,'Lookup cannot repeat a start');
  }finally{await app.close();}
});

test('a draft precedes its attachment and survives a confirmed empty catalog and a failed refresh',async()=>{
  const methods:string[]=[];
  let reads=0;
  const app=await mount(async(method)=>{
    methods.push(method);
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return snapshot([],[project('project',0)]);
    if(method==='source.pick')return {entry_token:'grant',project_id:'project',filename:'example.html',sha256:'a'.repeat(64),bytes:60,session_id:'session',expires_in_seconds:120};
    if(method==='models.list'){
      reads++;
      if(reads===2)throw 'MODEL_METADATA_UNAVAILABLE';
      return {session_id:'session',models:reads===1?[]:[{model:'installed',model_digest:'b'.repeat(64),mode:'fixture'}]};
    }
    throw Error('Unexpected access');
  });
  const button=(text:string)=>Array.from(app.document.querySelectorAll('button')).find(b=>b.textContent.includes(text))!;
  try{
    await until(()=>button('Elegir archivo HTML')?.disabled===false);
    const field=app.document.querySelector('#connected-objective') as any;
    const objective='Identifica el campo que necesita una etiqueta.';
    Object.getOwnPropertyDescriptor(app.window.HTMLTextAreaElement.prototype,'value')!.set!.call(field,objective);
    field.dispatchEvent(new app.window.Event('input',{bubbles:true}));
    const composing=new app.window.KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,bubbles:true});
    Object.defineProperty(composing,'isComposing',{value:true});
    field.dispatchEvent(composing);
    button('Elegir archivo HTML').click();await until(()=>!button('Comprobar HTML').disabled);
    assert.equal(reads,0);
    field.dispatchEvent(new app.window.KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,bubbles:true}));
    await until(()=>!!app.document.querySelector('.model-guide'));
    assert.ok(button('Revisar encargo').disabled&&!button('Comprobar HTML').disabled);
    button('Comprobar modelos instalados').click();await until(()=>reads===2&&!!app.document.querySelector('[role="alert"]'));
    assert.ok(button('Revisar encargo').disabled&&!button('Comprobar HTML').disabled);
    await until(()=>!button('Comprobar modelos instalados').disabled);
    button('Comprobar modelos instalados').click();await until(()=>!button('Revisar encargo').disabled);
    assert.ok(!app.document.querySelector('.model-guide')&&!button('Comprobar HTML').disabled);
    assert.equal(field.value,objective);
    assert.ok(!methods.some(m=>m.startsWith('attempt.')));
  }finally{await app.close();}
});

test('a pending catalog does not delay static findings or overwrite the finished check',async()=>{
  let release!:()=>void;
  const calls:string[]=[];
  const app=await mount(async(method,params)=>{
    calls.push(method);
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return snapshot([],[project('project',0)]);
    if(method==='source.pick')return {entry_token:'source',project_id:'project',filename:'sample.html',sha256:'a'.repeat(64),bytes:50,session_id:'session'};
    if(method==='models.list'){
      await new Promise<void>(resolve=>{release=resolve;});
      throw 'HOST_RESPONSE_TIMEOUT';
    }
    if(method==='source.check')return {session_id:'session',project_id:'project',source_sha256:'a'.repeat(64),offset:params.offset,total:0,findings:[]};
    throw Error(method);
  });
  const button=(name:string)=>Array.from(app.document.querySelectorAll('button')).find(b=>b.textContent===name)!;
  try{
    await until(()=>button('Elegir archivo HTML')?.disabled===false);
    button('Elegir archivo HTML').click();
    await until(()=>!button('Comprobar HTML').disabled);
    button('Consultar al Director').click();
    await until(()=>typeof release==='function');
    assert.equal(button('Comprobar HTML').disabled,false);
    button('Comprobar HTML').click();
    await until(()=>!!app.document.querySelector('#static-result-title'));
    release();await wait(25);
    assert.ok(!app.document.querySelector('[role="alert"]'));
    assert.deepEqual(calls.filter(c=>c==='source.check'||c.startsWith('attempt.')),['source.check']);
  }finally{release?.();await app.close();}
});

test('browsing B identifies its balance and draft, and a B report timeout leaves Stop on A',async()=>{
  const live={...baseAttempt,id:'live',project_id:'A',source_name:'a.html'};
  const archive={...baseAttempt,id:'archive',project_id:'B',source_name:'b.html',ordinal:2,state:'ACCEPTED',report_available:true};
  const fixture=validReport();
  let poll!:()=>void,read!:()=>void;
  let appReady=false;
  const cancels:unknown[]=[],picks:unknown[]=[];
  const app=await mount(async(method,params)=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return {...snapshot([live,archive],[project('A',1),project('B',2)]),current_attempt:cancels.length?null:live};
    if(method==='attempt.get'&&params.attempt_id==='archive')return archive;
    if(method==='attempt.get'){
      if(poll===undefined&&appReady)await new Promise<void>(resolve=>{poll=resolve;});
      return live;
    }
    if(method==='report.get')return {...fixture.meta,attempt_id:'archive'};
    if(method==='report.read'){await new Promise<void>(resolve=>{read=resolve;});throw 'HOST_RESPONSE_TIMEOUT';}
    if(method==='attempt.cancel'){cancels.push(params.attempt_id);return {...live,state:'CANCELLED',revision:2,session_id:'session'};}
    if(method==='source.pick'){picks.push(params.project_id);return null;}
    if(method==='models.list')return {session_id:'session',models:[]};
    throw Error(method);
  });
  const button=(part:string)=>Array.from(app.document.querySelectorAll('button')).find(b=>b.textContent.includes(part))!;
  try{
    await until(()=>!!app.document.querySelector('.active-work button:not(:disabled)'));
    appReady=true;await until(()=>typeof poll==='function');
    app.document.querySelector<HTMLButtonElement>('.connected-projects [title="B"]')!.click();
    await until(()=>!!app.document.querySelector('.connected-projects .selected[title="B"]')&&!!app.document.querySelector('.connected-history button'));
    const balance=app.document.querySelector('.connected-quota')!;
    assert.match(balance.textContent,/B/);assert.match(balance.textContent,/1 intento disponible/);
    assert.match(app.document.querySelector('.active-work strong')!.textContent,/A/);
    app.document.querySelector<HTMLButtonElement>('.connected-history button')!.click();
    await until(()=>typeof read==='function');read();
    await until(()=>app.document.body.textContent.includes('HOST_RESPONSE_TIMEOUT'));
    const stop=app.document.querySelector<HTMLButtonElement>('.active-work button')!;
    assert.equal(stop.disabled,false);stop.click();stop.click();
    await until(()=>!app.document.querySelector('.active-work'));
    assert.deepEqual(cancels,['live']);
    button('Preparar otro encargo').click();
    await until(()=>!!button('Elegir archivo HTML')&&!button('Elegir archivo HTML').disabled);
    button('Elegir archivo HTML').click();await until(()=>picks.length===1);
    assert.deepEqual(picks,['B']);
  }finally{read?.();poll?.();await app.close();}
});

test('a cached empty catalog from a busy core cannot certify that installation is needed',async()=>{
  const app=await mount(async method=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return snapshot([],[project('project',0)]);
    if(method==='models.list')return {models:[],cached:true,session_id:'session'};
    throw Error('Unexpected operation');
  });
  try{
    const consult=()=>Array.from(app.document.querySelectorAll('button')).find(b=>b.textContent==='Consultar al Director');
    await until(()=>consult()?.disabled===false);
    consult()!.click();
    await until(()=>!!app.document.querySelector('[role="alert"],.model-guide'));
    assert.ok(!app.document.querySelector('.model-guide'),'An old catalog cannot instruct the user to install software');
    assert.match(app.document.querySelector('[role="alert"]')?.textContent||'',/ocupado/i);
  }finally{await app.close();}
});

test('static inspection pages the captured source without querying models or spending an attempt',async()=>{
  const methods:string[]=[];
  const source={entry_token:'grant',project_id:'project',filename:'partes.html',sha256:'a'.repeat(64),bytes:200,session_id:'session',expires_in_seconds:120};
  const app=await mount(async(method,params)=>{
    methods.push(method);
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return snapshot([],[project('project',0)]);
    if(method==='source.pick')return source;
    if(method==='source.check'){
      const offset=Number(params.offset);
      assert.deepEqual({...params},{entry_token:'grant',project_id:'project',offset});
      return {session_id:'session',project_id:'project',source_sha256:source.sha256,total:25,offset,
        findings:Array.from({length:Math.min(24,25-offset)},(_,i)=>({code:'IMAGE_ALT_MISSING',line:1+offset+i,column:1}))};
    }
    throw Error('Unexpected access');
  });
  const button=(label:string)=>Array.from(app.document.querySelectorAll('button')).find(b=>b.textContent===label)!;
  try{
    await until(()=>button('Elegir archivo HTML')?.disabled===false);
    button('Elegir archivo HTML').click();await until(()=>!button('Comprobar HTML').disabled);
    button('Comprobar HTML').click();await until(()=>app.document.querySelectorAll('.finding-list li').length===24);
    await until(()=>app.document.activeElement?.id==='static-result-title');
    button('Siguientes').click();await until(()=>app.document.querySelectorAll('.finding-list li').length===1);
    assert.match(app.document.querySelector('.finding-list')?.textContent||'',/Línea 25/);
    assert.equal(button('Siguientes').disabled,true);
    button('Anteriores').click();await until(()=>app.document.querySelectorAll('.finding-list li').length===24);
    button('Quitar').click();await until(()=>!app.document.querySelector('.static-results'));
    assert.ok(!methods.includes('models.list')&&!methods.some(m=>m.startsWith('attempt.')));
  }finally{await app.close();}
});

test('reconnect restores identity on a changed session and an archive read cannot redirect Stop',async()=>{
  const history={...baseAttempt,id:'archive',source_name:'anterior.html',state:'FAILED',objective:'Informe anterior',
    ordinal:1,execution_error_code:'MODEL_METADATA_UNAVAILABLE',request_key:'older'};
  const live={...baseAttempt,source_name:'actual.html',ordinal:2};
  let session='session',outage=false,stopped=false;
  const calls:{method:string;params:Record<string,unknown>}[]=[];
  const app=await mount(async(method,params)=>{
    calls.push({method,params});
    if(outage)throw 'HOST_DISCONNECTED';
    if(method==='describe')return {session_id:session,office_id:'office'};
    if(method==='snapshot.get')return {...snapshot([history],[project('project',2)]),current_attempt:{...live,state:stopped?'CANCELLED':'RUNNING'},session_id:session};
    if(method==='attempt.get')return {...(params.attempt_id==='archive'?history:live),session_id:session};
    if(method==='attempt.cancel'){assert.equal(params.attempt_id,live.id);stopped=true;return {...live,session_id:session,state:'CANCELLED',revision:2};}
    throw Error('unexpected operation');
  });
  const button=(label:string)=>Array.from(app.document.querySelectorAll('button')).find(b=>b.textContent.includes(label));
  try{
    await until(()=>app.document.querySelector('.breadcrumbs strong')?.textContent==='actual.html');
    outage=true;
    await until(()=>!!button('Reconectar')&&app.document.body.textContent.includes('HOST_DISCONNECTED'));
    assert.ok(!app.document.body.textContent.includes('Núcleo local conectado'));
    assert.ok(button('Detener trabajo')?.disabled);
    session='new-session';outage=false;
    button('Reconectar')!.click();
    await until(()=>!app.document.querySelector('[role="alert"]')&&app.document.body.textContent.includes('Núcleo local conectado'));
    assert.equal(calls.filter(c=>c.method==='describe').length,2);
    button('Informe anterior')!.click();
    await until(()=>app.document.querySelector('.execution-code')?.textContent.includes('MODEL_METADATA_UNAVAILABLE')===true);
    assert.equal(app.document.querySelector('.breadcrumbs strong')?.textContent,'anterior.html');
    assert.equal(button('Detener trabajo')?.disabled,false);
    assert.match(app.document.querySelector('.active-work')?.textContent||'',/Synthetic controlled task/);
    button('Detener trabajo')!.click();
    await until(()=>stopped);
    assert.equal(calls.filter(c=>c.method==='attempt.cancel').length,1);
    assert.ok(!calls.some(c=>['attempt.start','attempt.preview','models.list','events.read','attempt.events'].includes(c.method)));
  }finally{await app.close();}
});

test('activity counts only validated rows of the viewed attempt and opens without a model',async()=>{
  const history={...baseAttempt,state:'FAILED',execution_error_code:null};
  let mismatched=true, eventReads=0;
  const app=await mount(async(method,params)=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return snapshot([history]);
    if(method==='attempt.get')return history;
    if(method==='attempt.events'){
      eventReads++;assert.equal(params.attempt_id,history.id);assert.equal(params.limit,24);
      return {office_id:'office',session_id:'session',attempt_id:history.id,has_more:false,next_before:1,
        events:[{seq:1,stamp_ns:'1000000000',kind:'ATTEMPT_RESERVED',payload:{attempt:mismatched?'another':history.id}}]};
    }
    throw Error('unexpected operation');
  });
  try{
    await until(()=>!!app.document.querySelector('.connected-history button:not(:disabled)'));
    (app.document.querySelector('.connected-history button') as any).click();
    await until(()=>!!app.document.querySelector('#tab-activity'));
    app.document.querySelector<HTMLButtonElement>('#tab-activity')!.click();
    await until(()=>!!app.document.querySelector('.connected-event-details'));
    assert.match(app.document.body.textContent,/motivo original no está disponible/);
    assert.equal(eventReads,0);
    const disclosure=app.document.querySelector('.connected-event-details') as any;
    disclosure.open=true;disclosure.dispatchEvent(new app.window.Event('toggle'));
    await until(()=>disclosure.textContent.includes('Reintentar lectura'));
    assert.equal(disclosure.querySelectorAll('li').length,0);
    mismatched=false;(disclosure.querySelector('button') as any).click();
    await until(()=>disclosure.querySelectorAll('li').length===1);
    assert.match(disclosure.querySelector('summary')!.textContent,/1 en esta página/);
    assert.match(disclosure.querySelector('li')!.textContent,/Intento reservado/);
    assert.equal(disclosure.querySelector('li code')!.textContent,'#1');
    assert.equal(disclosure.querySelector('.event-fact strong')!.textContent,'Intento reservado');
    assert.equal(disclosure.querySelector('.event-fact span'),null);
  }finally{await app.close();}
});

test('a static response for another captured source stays out of the document',async()=>{
  const app=await mount(async method=>{
    if(method==='describe')return {session_id:'session',office_id:'office'};
    if(method==='snapshot.get')return snapshot([],[project('project',0)]);
    if(method==='source.pick')return {entry_token:'grant',project_id:'project',filename:'sample.html',sha256:'a'.repeat(64),bytes:30,session_id:'session',expires_in_seconds:120};
    if(method==='source.check')return {session_id:'session',project_id:'project',source_sha256:'b'.repeat(64),findings:[],offset:0,total:0};
    throw Error('Unexpected RPC');
  });
  try{
    await until(()=>!!app.document.querySelector('#static-picker:not(:disabled)'));
    (app.document.querySelector('#static-picker') as any).click();
    await until(()=>!!app.document.querySelector('.brief-alternative button:not(:disabled)'));
    (app.document.querySelector('.brief-alternative button') as any).click();
    await until(()=>!!app.document.querySelector('[role="alert"]'));
    assert.match(app.document.querySelector('[role="alert"]')?.textContent||'',/SOURCE_CHECK_CONTRACT/);
    assert.ok(!app.document.querySelector('.static-results'));
  }finally{await app.close();}
});
