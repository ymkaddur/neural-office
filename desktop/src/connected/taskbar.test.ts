import test from 'node:test';
import assert from 'node:assert/strict';
import {dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {Window} from 'happy-dom';
import {build} from 'esbuild';

test('the native main window receives ordered activity signals and terminal cleanup',async()=>{
  const out = await build({stdin:{contents:`
    import React from 'react';
    import {createRoot} from 'react-dom/client';
    import {flushSync} from 'react-dom';
    import {useTaskbarProgress} from './useTaskbarProgress';
    const root=createRoot(document.getElementById('root'));
    function Trial(props){ useTaskbarProgress(props); return null; }
    window.draw = props=>flushSync(()=>root.render(<Trial {...props}/>));
    window.done = ()=>flushSync(()=>root.unmount());
  `,resolveDir:dirname(fileURLToPath(import.meta.url)),loader:'tsx'},write:false,bundle:true,
    format:'iife',platform:'browser',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
  const view=new Window({settings:{enableJavaScriptEvaluation:true}});
  const states:string[]=[];
  let release!:()=>void;
  const blocked=new Promise<void>(resolve=>{release=resolve;});
  Object.assign(view,{isTauri:true,__TAURI_INTERNALS__:{metadata:{currentWindow:{label:'main'}},
    invoke:async(command:string,params:{label:string;value:{status:string}})=>{
      assert.equal(command,'plugin:window|set_progress_bar');
      assert.equal(params.label,'main');
      states.push(params.value.status);
      if(states.length===1)await blocked;
    }}});
  view.document.body.innerHTML='<div id="root"></div>';
  try {
    view.eval(out.outputFiles[0].text);
    view.draw({active:true,stopping:false,reading:false});
    view.draw({active:true,stopping:true,reading:false});
    view.draw({active:false,stopping:false,reading:false});
    await new Promise(resolve=>setTimeout(resolve,15));
    assert.deepEqual(states,['indeterminate']);
    release();
    await new Promise(resolve=>setTimeout(resolve,15));
    assert.deepEqual(states,['indeterminate','paused','none']);
    view.draw({active:false,stopping:false,reading:true});
    view.done();
    await new Promise(resolve=>setTimeout(resolve,15));
    assert.deepEqual(states.slice(-2),['indeterminate','none']);
  } finally {
    release();
    await view.happyDOM.close();
  }
});
