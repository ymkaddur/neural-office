import test from 'node:test';
import assert from 'node:assert/strict';
import {clampPane,keyPane,paneBounds,readPane,PANE_DEFAULT} from './panes.ts';
test('invalid and blocked storage preserve usable defaults',()=>{
  for(const raw of [null,'',' ','NaN','Infinity','-1','0','999','44px']) {
    assert.equal(readPane('director',{getItem:()=>raw}),44);
    assert.equal(readPane('navigation',{getItem:()=>raw}),208);
  }
  assert.equal(readPane('director',{getItem:()=>{throw Error('blocked');}}),44);
  assert.equal(readPane('director',{getItem:()=>'53.5'}),53.5);
});
test('pane sizes fit exact minimum, narrow, wide and nonfinite containers',()=>{
  for(const width of [0,1,619,628,629,630,800,1707,3440,NaN,Infinity]) {
    for(const desired of [-Infinity,-10,0,44,50,100,Infinity,NaN]) {
      const value=clampPane('director',desired,width),bounds=paneBounds('director',width);
      assert.ok(Number.isFinite(value)&&value>=bounds.min&&value<=bounds.max);
      if(Number.isFinite(width)&&width>=629) {
        assert.ok((width-9)*value/100>=300-1e-8);
        assert.ok((width-9)*(1-value/100)>=320-1e-8);
      }
    }
  }
});
test('keyboard limits, reset defaults and cumulative steps stay bounded',()=>{
  for(const kind of ['navigation','director'] as const) {
    const bounds=paneBounds(kind,1000);
    assert.equal(keyPane(kind,'Home',50,1000),bounds.min);
    assert.equal(keyPane(kind,'End',50,1000),bounds.max);
    assert.equal(keyPane(kind,'ArrowLeft',bounds.min,1000,true),bounds.min);
    assert.equal(keyPane(kind,'ArrowRight',bounds.max,1000,true),bounds.max);
    assert.equal(keyPane(kind,'Tab',PANE_DEFAULT[kind],1000),null);
  }
});
