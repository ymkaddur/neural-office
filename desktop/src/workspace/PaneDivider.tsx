import {useEffect,useRef,useState} from 'react';
import type {RefObject,PointerEvent,KeyboardEvent} from 'react';
import {clampPane,keyPane,paneBounds,PANE_DEFAULT,readPane} from './panes.ts';
import type {PaneKind} from './panes.ts';

type Props={kind:PaneKind; container:RefObject<HTMLElement|null>; controls:string; label:string};
export function PaneDivider({kind,container,controls,label}:Props) {
  const [initial]=useState(()=>readPane(kind,safeStorage()));
  const desired=useRef(initial);
  const extent=useRef(0);
  const drag=useRef<{id:number;start:number;left:number;width:number}|null>(null);
  const pending=useRef<number|null>(null);
  const frame=useRef<number|null>(null);
  const handle=useRef<HTMLDivElement>(null);
  const [position,setPosition]=useState(desired.current);
  const [bounds,setBounds]=useState(paneBounds(kind,0));
  function paint(value=desired.current) {
    const node=container.current;
    if(!node) return;
    const effective=clampPane(kind,value,extent.current);
    const pixels=kind==='navigation'?effective:(extent.current-9)*effective/100;
    node.style.setProperty(kind==='navigation'?'--nav-width':'--director-width',`${Math.max(0,pixels)}px`);
    setPosition(effective);
  }
  function persist() {
    try { sessionStorage.setItem(`neural-office.v541.pane.${kind}`,String(desired.current)); } catch { /* In-memory resizing still works. */ }
  }
  function clearFrame() { if(frame.current!==null) cancelAnimationFrame(frame.current); frame.current=null; pending.current=null; }
  function end(cancel=false) {
    const active=drag.current;
    if(!active) return;
    if(cancel) desired.current=active.start;
    else if(pending.current!==null) desired.current=pending.current;
    clearFrame(); drag.current=null; paint();
    if(handle.current?.hasPointerCapture(active.id)) handle.current.releasePointerCapture(active.id);
    if(!cancel) persist();
  }
  useEffect(()=>{
    const node=container.current;
    if(!node) return;
    const update=()=>{end(true);extent.current=node.getBoundingClientRect().width;setBounds(paneBounds(kind,extent.current));paint();};
    update();
    const observer=new ResizeObserver(update); observer.observe(node);
    const blur=()=>end(true);window.addEventListener('blur',blur);
    return ()=>{observer.disconnect();window.removeEventListener('blur',blur);clearFrame();};
  },[kind,container]);
  function down(e:PointerEvent<HTMLDivElement>) {
    if(e.button!==0||!e.isPrimary||drag.current) return;
    const rect=container.current!.getBoundingClientRect();
    extent.current=rect.width;
    drag.current={id:e.pointerId,start:desired.current,left:rect.left,width:rect.width};
    e.currentTarget.focus();e.currentTarget.setPointerCapture(e.pointerId);e.preventDefault();
  }
  function move(e:PointerEvent<HTMLDivElement>) {
    const active=drag.current;
    if(!active||active.id!==e.pointerId) return;
    const raw=kind==='navigation'?e.clientX-active.left:(e.clientX-active.left)/(active.width-9)*100;
    pending.current=clampPane(kind,raw,extent.current);
    if(frame.current===null) frame.current=requestAnimationFrame(()=>{
      frame.current=null;
      if(pending.current!==null) {desired.current=pending.current;pending.current=null;paint();}
    });
  }
  function key(e:KeyboardEvent<HTMLDivElement>) {
    if(e.key==='Escape'&&drag.current) {e.preventDefault();end(true);return;}
    if(e.key==='Enter') {e.preventDefault();end(true);desired.current=PANE_DEFAULT[kind];paint();persist();return;}
    const next=keyPane(kind,e.key,position,extent.current,e.shiftKey);
    if(next===null) return;
    e.preventDefault();end(true);desired.current=next;paint();persist();
  }
  return <div ref={handle} className={`pane-divider ${kind}-divider`} role="separator" tabIndex={0}
    aria-label={label} aria-controls={controls} aria-orientation="vertical" aria-valuemin={Math.round(bounds.min)}
    aria-valuemax={Math.round(bounds.max)} aria-valuenow={Math.round(position)} aria-valuetext={`${Math.round(position)} ${kind==='navigation'?'píxeles':'por ciento'}`}
    title={`${label} · arrastrar o flechas · Home/End · Enter: restablecer · Escape: cancelar arrastre`}
    onPointerDown={down} onPointerMove={move} onPointerUp={e=>{if(drag.current?.id===e.pointerId)end();}}
    onPointerCancel={()=>end(true)} onLostPointerCapture={()=>end(true)} onKeyDown={key}><span/></div>;
}
function safeStorage():Storage|null {try{return sessionStorage;}catch{return null;}}
