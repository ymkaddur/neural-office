import test from 'node:test';
import assert from 'node:assert/strict';
import { fixture, transition, readDraft, pageWindow, screenFrom } from './model.ts';

test('double click starts once and a late result cannot finish a stopped run',()=>{
  const running=transition(fixture('ready','Prepare'),{type:'START'});
  assert.equal(running.attempts,1);
  assert.equal(transition(running,{type:'START'}),running);
  const stopping=transition(running,{type:'STOP'});
  assert.equal(transition(stopping,{type:'FINISH',revision:running.revision}),stopping);
  assert.equal(transition(stopping,{type:'NEW'}),stopping);
  assert.equal(transition(stopping,{type:'START'}),stopping);
});
test('confirmation and failure retain consumption; stale acknowledgements are rejected',()=>{
  const s=transition(transition(fixture('ready','x'),{type:'START'}),{type:'STOP'});
  assert.equal(transition(s,{type:'CONFIRM_STOP',revision:s.revision-1}),s);
  const closed=transition(s,{type:'CONFIRM_STOP',revision:s.revision});
  assert.equal(closed.attempts,1); assert.equal(closed.closed,true);
  const again=transition(transition(closed,{type:'NEW'}),{type:'START'});
  assert.equal(again.attempts,2);
  assert.equal(transition(again,{type:'FAIL',revision:again.revision}).attempts,2);
  assert.equal(transition(again,{type:'FINISH',revision:s.revision}),again);
});
test('exhaustion and whitespace do not start; new work does not reset the quota',()=>{
  assert.equal(transition(fixture('ready','  '),{type:'START'}).attempts,0);
  let s=fixture('ready','x');
  for(let i=0;i<3;i++) { s=transition(s,{type:'START'}); s=transition(s,{type:'FAIL',revision:s.revision}); s=transition(s,{type:'NEW'}); }
  assert.equal(s.attempts,3); assert.equal(transition(s,{type:'START'}),s);
});
test('input is bounded, storage may fail, invalid routes are inert',()=>{
  assert.equal(transition(fixture('ready','x'),{type:'DRAFT',value:'a'.repeat(2001)}).draft.length,2000);
  assert.equal(readDraft({getItem:()=>{throw Error('blocked')}},'fallback'),'fallback');
  assert.equal(readDraft({getItem:()=> 'a'.repeat(2001)},'fallback'),'fallback');
  assert.equal(readDraft({getItem:()=>''},'fallback'),'');
  assert.equal(screenFrom('javascript:alert(1)'),'ready');
});
test('history stays paginated at empty, exact boundary and last partial page',()=>{
  assert.deepEqual(pageWindow(0,10),{page:0,pages:1,start:0,end:0});
  assert.equal(pageWindow(50,1).page,0);
  assert.deepEqual(pageWindow(51,1),{page:1,pages:2,start:50,end:51});
  assert.equal(pageWindow(10000,199).end-pageWindow(10000,199).start,50);
  assert.equal(pageWindow(10000,-1).page,0);
  assert.throws(()=>pageWindow(-1,0));
});
