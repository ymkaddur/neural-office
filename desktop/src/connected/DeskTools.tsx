import {useEffect, useLayoutEffect, useRef, useState} from 'react';
import type {ReactNode} from 'react';

const shapes = {
  mark:<><path d="M4 19V4l16 15V5M4 11h15"/><circle cx="4" cy="4" r="2"/><circle cx="20" cy="19" r="2"/></>,
  folder:<path d="M3 6h6l2 2h10v11H3z"/>, thread:<path d="M4 4h16v12H9l-5 4z"/>,
  search:<><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></>,
  attach:<path d="m9 15 7-7a2 2 0 0 0-3-3l-8 8a5 5 0 0 0 7 7l9-9M8 13l7-7"/>,
  pdf:<><path d="M5 3h9l5 5v13H5zM14 3v6h5M8 13h8m-8 4h6"/></>,
  json:<path d="m7 7-5 5 5 5m10-10 5 5-5 5m-4-13-3 20"/>,
  zip:<path d="M3 4h18v4H3zM5 8v12h14V8M9 12h6"/>,
  png:<><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1"/><path d="m4 17 5-5 3 3 3-4 6 6"/></>,
  check:<><circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/></>,
  activity:<path d="M2 12h4l3-8 5 16 3-8h5"/>,
  panel:<><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M14 4v16"/></>,
  arrow:<path d="m9 5 7 7-7 7"/>, settings:<><path d="M3 7h18M3 17h18"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/></>,
  shield:<><path d="m12 2 8 4v6c0 5-5 8-8 10-3-2-8-5-8-10V6z"/><path d="m8 12 3 3 5-6"/></>,
  clock:<><circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/></>,
  note:<path d="M5 3h14v18H5zM8 8h8m-8 4h8m-8 4h5"/>,
};
export type SymbolName=keyof typeof shapes;
export function Icon({name}:{name:SymbolName}) {return <svg className="no-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;}
export const appearanceKey='neural-office.v513.appearance';
export type Appearance={theme:'system'|'light'|'dark';density:'comfortable'|'compact';scale:100|115|125;contrast:boolean;motion:boolean};
const defaults:Appearance={theme:'system',density:'comfortable',scale:100,contrast:false,motion:false};
function loadAppearance():Appearance {
  try {
    const p=JSON.parse(localStorage.getItem(appearanceKey)??'null');
    if(!p||typeof p!=='object')return defaults;
    return {theme:['dark','light','system'].includes(p.theme)?p.theme:'system',density:p.density==='compact'?'compact':'comfortable',
      scale:[100,115,125].includes(p.scale)?p.scale:100,contrast:p.contrast===true,motion:p.motion===true};
  }catch{return defaults;}
}
export function useAppearance(){
  const [prefs,setPrefs]=useState(loadAppearance);
  const [system,setSystem]=useState(()=>matchMedia('(prefers-color-scheme: dark)').matches);
  const [saved,setSaved]=useState(true);
  useEffect(()=>{
    const m=matchMedia('(prefers-color-scheme: dark)');
    const changed=()=>setSystem(m.matches);
    const fromStorage=(event:StorageEvent)=>{if(event.key===appearanceKey||event.key===null)setPrefs(loadAppearance());};
    m.addEventListener('change',changed);window.addEventListener('storage',fromStorage);
    return ()=>{m.removeEventListener('change',changed);window.removeEventListener('storage',fromStorage);};
  },[]);
  function update(next:Appearance){setPrefs(next);try{localStorage.setItem(appearanceKey,JSON.stringify(next));setSaved(true);}catch{setSaved(false);}}
  return {prefs,update,saved,dark:prefs.theme==='dark'||(prefs.theme==='system'&&system)};
}
export function DeskDialog({label,close,children,wide=false}:{label:string;close:()=>void;children:ReactNode;wide?:boolean}){
  const ref=useRef<HTMLDialogElement>(null);
  useLayoutEffect(()=>{const origin=document.activeElement;const dialog=ref.current;dialog?.showModal();return ()=>{dialog?.close();if(origin instanceof HTMLElement&&origin.isConnected)origin.focus();};},[]);
  return <dialog ref={ref} aria-label={label} className={'desk-dialog'+(wide?' wide':'')} onCancel={e=>{e.preventDefault();close();}}>
    <header><h2>{label}</h2><button className="desk-icon-button" aria-label={'Cerrar '+label} onClick={close}>×</button></header>{children}</dialog>;
}
function Choices<T extends string|number>({label,value,options,onChange}:{label:string;value:T;options:ReadonlyArray<readonly [T,string]>;onChange:(v:T)=>void}){
  return <div className="desk-segment" role="group" aria-label={label}>{options.map(([v,text])=><button key={v} aria-pressed={v===value} onClick={()=>onChange(v)}>{text}</button>)}</div>;
}
function PaletteSample({night}:{night:boolean}){
  return <div className={'palette-sample '+(night?'night':'sand')} aria-hidden="true"><div className="sample-bar"><Icon name="mark"/> Neural Office</div><div className="sample-layout"><div><i/><i/><i/></div><div><span>Director</span><strong>Revisar entrega</strong><i/><i/></div><div><span>Adjuntos</span><i/><i/></div></div></div>;
}
export function AppearancePanel({appearance,close,control}:{appearance:ReturnType<typeof useAppearance>;close:()=>void;control?:ReactNode}){
  const {prefs,update,dark,saved}=appearance;
  return <DeskDialog wide label="Apariencia" close={close}><div className="prefs-body">{control}
    <div className="pref-row"><div><strong>Tema</strong><p>{prefs.theme==='system'?'Siguiendo al sistema · ':''}{dark?'Azul noche':'Arena'}</p></div>
      <Choices label="Tema" value={prefs.theme} options={[['system','Sistema'],['light','Claro'],['dark','Oscuro']]} onChange={theme=>update({...prefs,theme})}/></div>
    <div className="palette-samples">{[false,true].map(night=><button key={String(night)} aria-pressed={dark===night} onClick={()=>update({...prefs,theme:night?'dark':'light'})}><PaletteSample night={night}/><strong>{night?'Azul noche':'Arena'}</strong>{dark===night&&<Icon name="check"/>}</button>)}</div>
    <h3>Lectura y teclado</h3>
    <div className="pref-row"><strong>Densidad</strong><Choices label="Densidad" value={prefs.density} options={[['comfortable','Cómoda'],['compact','Compacta']]} onChange={density=>update({...prefs,density})}/></div>
    <div className="pref-row"><strong>Tamaño de texto</strong><Choices label="Tamaño de texto" value={prefs.scale} options={[[100,'100 %'],[115,'115 %'],[125,'125 %']]} onChange={scale=>update({...prefs,scale})}/></div>
    <div className="pref-row"><label htmlFor="desk-contrast">Alto contraste</label><input type="checkbox" id="desk-contrast" checked={prefs.contrast} onChange={e=>update({...prefs,contrast:e.target.checked})}/></div>
    <div className="pref-row"><label htmlFor="desk-motion">Reducir movimiento</label><input type="checkbox" id="desk-motion" checked={prefs.motion} onChange={e=>update({...prefs,motion:e.target.checked})}/></div>
    <div className="pref-row"><span>Buscar hilo o acción</span><kbd>Ctrl K</kbd></div>
    {!saved&&<p role="status">La preferencia se aplica en esta ventana. El perfil no permitió guardarla.</p>}
    <button className="desk-primary" onClick={close}>Volver al hilo</button>
  </div></DeskDialog>;
}
export type DeskAction={id:string;name:string;detail?:string;run:()=>void};
export function CommandSearch({items,close,control}:{items:DeskAction[];close:()=>void;control?:ReactNode}){
  const [query,setQuery]=useState('');
  const norm=(s:string)=>s.normalize('NFD').replace(/\p{M}/gu,'').toLowerCase();
  const choices=items.filter(item=>norm(item.name+' '+(item.detail??'')).includes(norm(query.trim())));
  return <DeskDialog label="Buscar hilo o acción" close={close}><div className="command-body">{control}
    <input aria-label="Buscar por nombre o proyecto" autoFocus value={query} placeholder="Nombre del hilo, proyecto o acción…" onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='ArrowDown'){e.preventDefault();e.currentTarget.parentElement?.querySelector<HTMLButtonElement>('.command-results button')?.focus();}}}/>
    <div className="command-results">{choices.map(item=><button key={item.id} onClick={()=>{close();item.run();}}><span>{item.name}</span><small>{item.detail}</small></button>)}{!choices.length&&<p>Sin coincidencias.</p>}</div>
  </div></DeskDialog>;
}
