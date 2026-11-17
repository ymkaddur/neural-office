import test from 'node:test';
import assert from 'node:assert/strict';
import {dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
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
  define:{'process.env.NODE_ENV':'"production"'},loader:{'.css':'empty'}}).then(result=>result.outputFiles[0].text);
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

test('paging attempts retains the bounded project page and its authoritative quota',async()=>{
  const projects=Array.from({length:34},(_,i)=>project(`p${i}`,3));
  const attempts=Array.from({length:102},(_,i)=>({...baseAttempt,id:`a${i}`,project_id:`p${Math.floor(i/3)}`,ordinal:i%3+1,state:'CANCELLED',request_key:`k${i}`}));
  let pages=0;
  const app=await mount(async(method,params)=>{
    if(method==='describe')return {session_id:'session',office_id:'office',inference:'injected-test-backend'};
    if(method==='snapshot.get'){
      pages++;
      const after=params.attempt_after as number;
      const result=snapshot(attempts.slice(after,after+100),(params.project_after as number)>0?[]:projects);
      result.next={project_after:34,attempt_after:Math.min(after+100,102)};
      result.has_more.attempts=after===0;return result;
    }
    if(method==='models.list')return {models:[],session_id:'session'};
    throw Error('Unexpected synthetic RPC');
  });
  try{
    await until(()=>app.document.querySelectorAll('.connected-projects button').length===34);
    (Array.from(app.document.querySelectorAll('.connected-projects button')).find(button=>button.getAttribute('title')==='p33') as any).click();
    await until(()=>app.document.querySelector('.connected-projects button.selected')?.getAttribute('title')==='p33');
    const next=Array.from(app.document.querySelectorAll('button')).find(button=>/Siguiente.*(?:historial|encargos)/i.test(button.textContent));
    assert.ok(next);next.click();
    await until(()=>pages===2);await wait(30);
    assert.equal(app.document.querySelectorAll('.connected-projects button').length,34);
    assert.match(app.document.querySelector('.connected-quota')?.textContent||'',/3 de 3/);
    assert.equal(app.document.querySelectorAll('.connected-history button').length,2);
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
