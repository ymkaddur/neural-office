import { useEffect, useReducer, useRef, useState } from 'react';
import { defaultObjective, sources, decisions, resultMarkdown } from './fixtures.ts';
import type { SourceId } from './fixtures.ts';
import type { Iteration } from './model.ts';
import {PaneDivider} from './PaneDivider.tsx';
import { fixture, isBusy, pageWindow, readDraft, screens, screenLabels, screenFrom, transition } from './model.ts';

type Overlay = {kind:'source'; id:SourceId; line?:number} | {kind:'control'} | {kind:'library'} | {kind:'measure'} | null;
type Sample = {mode:string; elapsedMs:number; dom:number; heapBytes:number|null; longTasks:number|null; visibility:string; rows:number};
const getHeap=()=> (performance as Performance & {memory?:{usedJSHeapSize:number}}).memory?.usedJSHeapSize ?? null;
const iconPaths:Record<string,string> = {
  plus:'M12 5v14M5 12h14', arrow:'M5 12h14m-6-6 6 6-6 6', back:'m14 6-6 6 6 6',
  file:'M5 3h9l5 5v13H5zM14 3v6h5M9 13h6M9 17h4',
  folder:'M3 6h7l2 2h9v12H3z', book:'M4 4h6l2 2 2-2h6v15h-6l-2 2-2-2H4zM12 6v15',
  check:'m5 12 4 4L19 6', close:'m6 6 12 12M6 18 18 6', stop:'M6 6h12v12H6z',
  settings:'M4 7h16M4 17h16M8 4v6M16 14v6', chevron:'m9 5 7 7-7 7',
  sun:'M12 3v2M12 19v2M3 12h2M19 12h2M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  moon:'M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11',
  download:'M12 3v12m-5-5 5 5 5-5M5 17v4h14v-4', layers:'m3 7 9-4 9 4-9 4zM3 12l9 4 9-4M3 17l9 4 9-4',
  warning:'m12 3 10 18H2zM12 9v5M12 17v1', clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M12 7v5l3 2',
  panel:'M3 4h18v16H3zM9 4v16', link:'m10 13 4-4M8 15l-2 2a3 3 0 0 1-4-4l4-4a3 3 0 0 1 4 0M14 9l2-2a3 3 0 0 1 4 4l-4 4a3 3 0 0 1-4 0',
  chip:'M6 6h12v12H6zM9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M18 9h4M2 15h4M18 15h4',
};
function Icon({name,size=17}:{name:string;size?:number}) { return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={iconPaths[name]||iconPaths.file}/></svg>; }
function DirectorMark() { return <span className="director-mark" aria-hidden="true"><span/><span/><span/></span>; }

export function Workspace() {
  const initialScreen=useRef(screenFrom(new URLSearchParams(location.search).get('screen')));
  const [state,dispatch]=useReducer(transition,undefined,()=>fixture(initialScreen.current,initialScreen.current==='ready'?readDraft(safeStorage(),defaultObjective):defaultObjective));
  const shell=useRef<HTMLDivElement>(null);
  const surface=useRef<HTMLElement>(null);
  const [version,setVersion]=useState<Iteration>(initialScreen.current==='result'?3:initialScreen.current==='stopping'?2:1);
  const [overlay,setOverlay]=useState<Overlay>(null);
  const [tab,setTab]=useState<'document'|'changes'|'sources'>('document');
  const [dark,setDark]=useState(()=>{ try{return sessionStorage.getItem('neural-office.v541.theme')==='dark';}catch{return false;} });
  const [navOpen,setNavOpen]=useState(false);
  const [notice,setNotice]=useState('');
  const [deliveryOpen,setDeliveryOpen]=useState(true);
  const [samples,setSamples]=useState<Sample[]>([]);
  const [measuring,setMeasuring]=useState(false);
  const [eventTotal,setEventTotal]=useState(0);
  const [eventPage,setEventPage]=useState(0);
  const [storageWarning,setStorageWarning]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null);
  const measurementCleanup=useRef<()=>void>(()=>{});
  const previousFocus=useRef<HTMLElement|null>(null);
  const running=state.screen==='running';
  const stopping=state.screen==='stopping';
  const busy=isBusy(state);
  const ready=state.screen==='ready';
  const complete=state.screen==='result';
  const error=state.screen==='error';
  const artifactVisible=!ready && deliveryOpen;
  const status=ready?'Listo para un encargo':running?`Etapa ${state.iteration} de 3 · avance manual`:complete?'Entrega lista para tu revisión':error?'Necesita atención':state.closed?'Ejemplo detenido':'Confirmación de parada pendiente';
  const revised=version>=2;
  const finalVersion=complete&&version===3;
  const sendLabel=complete?'Probar un ajuste':error||stopping?'Reintentar ejemplo':'Iniciar ejemplo';
  const composerLabel=complete?'Siguiente mensaje al Director':error||stopping?'Encargo para reintentar':'Objetivo para el Director';
  useEffect(()=>{setVersion(state.iteration);},[state.iteration,state.revision]);
  useEffect(()=>{if(!ready){setDeliveryOpen(true);setTab('document');}},[state.revision]);

  useEffect(()=>{
    if(ready) {try {sessionStorage.setItem('neural-office.v541.draft',state.draft);} catch {setStorageWarning(true);}}
  },[state.draft,ready]);
  useEffect(()=>{try{sessionStorage.setItem('neural-office.v541.theme',dark?'dark':'light');}catch{}},[dark]);
  useEffect(()=>{
    if(overlay) { if(!dialog.current?.open) { previousFocus.current=document.activeElement as HTMLElement; dialog.current?.showModal(); } }
    else { if(dialog.current?.open) dialog.current.close(); previousFocus.current?.focus(); }
  },[overlay]);
  useEffect(()=>()=>measurementCleanup.current(),[]);
  useEffect(()=>{
    const narrow=matchMedia('(max-width:1000px)');
    const change=()=>{
      if(!narrow.matches) setNavOpen(false);
      else if(document.activeElement?.classList.contains('pane-divider')) document.getElementById('workspace-main')?.focus();
    };
    narrow.addEventListener('change',change);
    return ()=>narrow.removeEventListener('change',change);
  },[]);
  useEffect(()=>{
    if(!navOpen) return;
    const opener=document.activeElement as HTMLElement|null;
    const nav=document.querySelector('.office-nav');
    const buttons=()=>Array.from(nav?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')||[]).filter(b=>b.getClientRects().length);
    buttons()[0]?.focus();
    const keys=(e:KeyboardEvent)=>{
      if(dialog.current?.open) return;
      if(e.key==='Escape'){e.preventDefault();setNavOpen(false);}
      if(e.key==='Tab'){const all=buttons(),first=all[0],last=all.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}
    };
    document.addEventListener('keydown',keys);
    return ()=>{document.removeEventListener('keydown',keys);if(opener?.getClientRects().length) opener.focus();else document.getElementById('workspace-main')?.focus();};
  },[navOpen]);

  function newTask() { dispatch({type:'NEW'});setNotice('');setNavOpen(false);setTab('document');document.getElementById('director-input')?.focus(); }
  function exportReport() {
    if(!complete) return;
    const blob=new Blob([resultMarkdown],{type:'text/markdown;charset=utf-8'}), url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url;a.download='norte-propuesta-ejemplo.md';a.click();
    window.setTimeout(()=>URL.revokeObjectURL(url),1000);setNotice('Entrega de ejemplo exportada.');
  }
  function startSample(stress:boolean) {
    if(measuring) return;
    setMeasuring(true);setEventPage(0);setEventTotal(stress?10000:0);
    let longTasks=0;
    let observer:PerformanceObserver|null=null;
    if(PerformanceObserver.supportedEntryTypes?.includes('longtask')) { observer=new PerformanceObserver(list=>{longTasks+=list.getEntries().length;});observer.observe({entryTypes:['longtask']}); }
    const started=performance.now();
    const timer=window.setTimeout(()=>{
      if(observer) longTasks+=observer.takeRecords().length;
      observer?.disconnect();
      setSamples(v=>[...v.slice(-9),{mode:stress?'10 000 eventos / 50 visibles':'Reposo, panel abierto',elapsedMs:performance.now()-started,
        dom:document.querySelectorAll('*').length,heapBytes:getHeap(),longTasks:observer?longTasks:null,visibility:document.visibilityState,rows:stress?10000:0}]);
      setMeasuring(false);measurementCleanup.current=()=>{};
    },5000);
    measurementCleanup.current=()=>{clearTimeout(timer);observer?.disconnect();};
  }
  function downloadMeasurements() {
    const blob=new Blob([JSON.stringify({scope:'Browser preview only, not Tauri/core/model memory',samples},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='neural-office-v541-ui-samples.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  const pagination=pageWindow(eventTotal,eventPage);
  const currentSource=overlay?.kind==='source'?sources[overlay.id]:null;

  return <div className={`v541 ${dark?'theme-dark':''}`}>
    <a className="skip-link" href="#workspace-main">Saltar al trabajo</a>
    <div className="review-strip" aria-label="Revisión del prototipo">
      <span className="review-label"><strong>V5.4.1</strong><span className="review-descriptor">Vista previa · sin motor</span></span>
      <nav aria-label="Cinco pantallas de diseño">{screens.map((screen,i)=><a key={screen} href={`?preview=1&screen=${screen}`} aria-current={state.screen===screen?'page':undefined}><span>{i+1}</span>{screenLabels[screen]}</a>)}</nav>
      <button className="review-measure" onClick={()=>setOverlay({kind:'measure'})}><Icon name="chip" size={14}/><span>Medir</span></button>
    </div>
    <div ref={shell} className={`office-shell ${navOpen?'nav-open':''}`}>
      <aside id="office-navigation" className="office-nav" aria-label="Proyectos y herramientas">
        <button className="mobile-nav-close" aria-label="Cerrar navegación" onClick={()=>setNavOpen(false)}><Icon name="close"/></button>
        <div className="wordmark"><span className="office-symbol">n<span>/</span></span><strong>Neural Office</strong><span className="version-tag">local</span></div>
        <button className="new-task" onClick={newTask} disabled={busy}><Icon name="plus"/>Nuevo encargo<span className="keyhint">↗</span></button>
        <div className="nav-label">ESPACIO DE TRABAJO</div>
        <button className="project-item" onClick={()=>{setNavOpen(false);setNotice('Norte es el proyecto sintético incluido en esta vista.');}}><Icon name="folder"/><span>Norte</span><Icon name="chevron" size={12}/></button>
        <div className="session-tree">
          <button className="session-item active" aria-current="page" onClick={()=>{setNavOpen(false);setNotice('Estás en el encargo de lanzamiento.');}}><span className={`small-dot ${complete?'done':''}`}/><span>Preparar el lanzamiento</span></button>
          <span className={`session-caption ${error||complete?'needs-attention':''}`}>{error?'Necesita atención':complete?'Pendiente de tu revisión':running?`Etapa ${state.iteration} · ejemplo`:stopping?state.closed?'Detenido':'Esperando cierre':'Listo para comenzar'}</span>
        </div>
        <button className="nav-secondary" onClick={()=>setOverlay({kind:'source',id:'brief'})}><Icon name="file"/>Fuentes del proyecto<span>3</span></button>
        <div className="nav-bottom">
          <button onClick={()=>setOverlay({kind:'library'})}><Icon name="book"/>Skills y memoria<small>Diseño</small></button>
          <button onClick={()=>setOverlay({kind:'control'})}><Icon name="settings"/>Control del trabajo</button>
          <div className="nav-separator"/>
          <div className="local-engine"><span className="engine-indicator"/><div><strong>Modelo sin conectar</strong><small>Todo este recorrido es un ejemplo</small></div></div>
          <div className="nav-footer"><span>Libre. Local. Tuyo.</span><button aria-label={dark?'Usar tema claro':'Usar tema oscuro'} onClick={()=>setDark(!dark)}><Icon name={dark?'sun':'moon'}/></button></div>
        </div>
      </aside>
      <PaneDivider kind="navigation" container={shell} controls="office-navigation" label="Navegación"/>
      {navOpen&&<button className="nav-scrim" aria-label="Cerrar navegación" onClick={()=>setNavOpen(false)}/>}
      <div className="office-workspace" inert={navOpen || undefined}>
        <header className="workspace-header">
          <button className="icon-button nav-toggle" aria-label="Abrir navegación" aria-expanded={navOpen} onClick={()=>setNavOpen(!navOpen)}><Icon name="panel"/></button>
          <div className="breadcrumbs"><span>Norte</span><Icon name="chevron" size={11}/><strong>{ready?'Nuevo encargo':'Preparar el lanzamiento'}</strong></div>
          <div className="header-actions">{running&&<button className="mobile-stop-control" aria-label="Detener ejemplo" onClick={()=>dispatch({type:'STOP'})}><Icon name="stop" size={14}/></button>}{!ready&&<button className="quiet-button artifact-toggle" aria-pressed={deliveryOpen} onClick={()=>setDeliveryOpen(!deliveryOpen)}><Icon name="panel"/><span>{deliveryOpen?'Ocultar entrega':'Ver entrega'}</span></button>}<button className="icon-button" aria-label="Ver límites y permisos" onClick={()=>setOverlay({kind:'control'})}><Icon name="settings"/></button></div>
        </header>
        {!ready&&<div className="iteration-rail" role="group" aria-label="Iteraciones del ejemplo">
          {([1,2,3] as const).map(n=>{const available=!error&&n<=state.iteration;const done=complete||n<state.iteration;
            return <button key={n} aria-pressed={version===n&&available} disabled={!available} onClick={()=>{setVersion(n);setDeliveryOpen(true);setTab('document');}}>
              <span className="iteration-number">{`0${n}`}</span><span><strong>{n===1?'Borrador':n===2?'Revisión':'Entrega'}</strong><small>{error?'Sin iniciar':done?'Disponible':n===state.iteration?stopping?'Interrumpida':'En esta etapa':'Pendiente'}</small></span>
            </button>;})}<span className="rail-caption">Etapas ≠ intentos</span>
        </div>}
        <main ref={surface} id="workspace-main" tabIndex={-1} className={`work-surface ${ready?'is-ready':''} ${artifactVisible?'with-artifact':''}`}>
          <section id="director-pane" className="director-surface" aria-label="Conversación con el Director">
            {ready ? <div className="starting-point">
              <div className="director-signature"><DirectorMark/><span>Tu Director</span><span className="quiet-label">UN ENCARGO, UN EQUIPO</span></div>
              <h1>¿En qué trabajamos?</h1>
              <p className="opening-copy">Un objetivo claro. Tres etapas visibles.<br/>Habla con el Director y revisa el resultado junto a sus fuentes.</p>
              <div className="context-preview"><div className="context-heading"><Icon name="folder"/><span>Contexto de Norte</span><span>3 fuentes</span></div>
                {(Object.keys(sources) as SourceId[]).map(id=><button key={id} onClick={()=>setOverlay({kind:'source',id})}><Icon name="file"/><strong>{sources[id].name}</strong><span>{sources[id].label}</span><Icon name="chevron" size={13}/></button>)}
              </div>
              <div className="starter-prompts"><span>Prueba un enfoque</span><button onClick={()=>dispatch({type:'DRAFT',value:defaultObjective})}>Preparar un lanzamiento<Icon name="arrow" size={13}/></button><button onClick={()=>dispatch({type:'DRAFT',value:'Contrasta las promesas del brief de Norte con las funciones disponibles y señala las contradicciones.'})}>Encontrar contradicciones<Icon name="arrow" size={13}/></button></div>
            </div> : <div className="conversation-scroll">
              <div className="message user-message"><span className="message-author">Tú</span><p>{state.objective}</p><div className="message-files"><Icon name="file" size={13}/><span>3 fuentes de Norte</span></div></div>
              {complete&&<div className="message director-message closing-message"><div className="message-author"><DirectorMark/><strong>Director</strong><span>Entrega</span></div><h2>La propuesta está lista.</h2><p>He retirado la sincronización del mensaje: el alcance dice que todavía no existe. La entrega se centra en notas locales y una lista de espera.</p><button className="delivery-link" onClick={()=>{setDeliveryOpen(true);setTab('changes');}}><Icon name="layers"/><span>Ver qué cambió<small>Borrador → revisión → entrega</small></span><Icon name="arrow" size={15}/></button><p className="message-footnote">Queda por validar si el mensaje se entiende. Las fuentes de este ejemplo son sintéticas.</p></div>}
              {stopping&&<div className={`interruption stop-state ${state.closed?'confirmed':''}`} role="status"><Icon name={state.closed?'check':'stop'} size={22}/><h2>{state.closed?'El ejemplo se ha detenido.':'La parada está solicitada.'}</h2><p>{state.closed?'El borrador se conserva como trabajo parcial. Puedes preparar otro encargo.':'El Director espera la confirmación de cierre. Hasta entonces, el trabajo sigue bloqueado.'}</p><div className="stop-checks"><span><Icon name="check" size={13}/>Solicitud recibida</span><span><Icon name={state.closed?'check':'clock'} size={13}/>{state.closed?'Cierre confirmado en la demo':'Confirmación de cierre pendiente'}</span></div>{state.closed?<button className="solid-button" onClick={newTask}>Preparar otro encargo<Icon name="arrow" size={14}/></button>:<button className="quiet-button" onClick={()=>dispatch({type:'CONFIRM_STOP',revision:state.revision})}>Simular cierre confirmado<Icon name="check" size={14}/></button>}<p className="message-footnote">El intento permanece consumido. El borrador no se convierte en una entrega validada.</p></div>}
              {running&&<div className="message director-message"><div className="message-author"><DirectorMark/><strong>Director</strong><span>Plan</span></div><p>Compararé el brief con el alcance y consolidaré una propuesta revisable.</p>
                <p className="message-footnote">Director → Revisor → Integrador. Un solo equipo; tres etapas dentro del mismo intento.</p>
              </div>}
              {!error&&<div className="work-event" aria-label="Actividad del ejemplo">
                <div className="event-heading"><span className="activity-dot"/><strong>{complete?'Trabajo del equipo':'Actividad del equipo'}</strong><span>Ejemplo</span></div>
                <ol className="activity-ledger">
                  <li aria-current={running&&state.iteration===1?'step':undefined} className={running&&state.iteration>1?'ledger-compact':''}><span className="ledger-index">01</span><div><strong>Director <small>Borrador</small></strong><p>Delimitar el encargo y preparar una primera propuesta.</p><button onClick={()=>setOverlay({kind:'source',id:'brief',line:3})}>brief.md:3–7<Icon name="link" size={12}/></button></div><span className="ledger-state">{state.iteration>1||complete?'Listo':stopping?'Parcial':'En curso'}</span></li>
                  <li aria-current={running&&state.iteration===2?'step':undefined} className={state.iteration<2?'ledger-pending':running&&state.iteration>2?'ledger-compact':''}><span className="ledger-index">02</span><div><strong>Revisor <small>Contraste</small></strong><p>{state.iteration>=2?'Retirar la sincronización: no existe en el alcance.':'Comprobar cada promesa con las fuentes.'}</p><button onClick={()=>setOverlay({kind:'source',id:'scope',line:6})}>alcance.md:6<Icon name="link" size={12}/></button></div><span className="ledger-state">{complete||state.iteration>2?'Listo':state.iteration===2?stopping?'Parcial':'En curso':'Pendiente'}</span></li>
                  <li aria-current={running&&state.iteration===3?'step':undefined} className={state.iteration<3?'ledger-pending':''}><span className="ledger-index">03</span><div><strong>Integrador <small>Entrega</small></strong><p>{complete?'Añadir la lista de espera y dejar la fecha por validar.':'Consolidar los cambios y las comprobaciones pendientes.'}</p>{state.iteration>=3&&<button onClick={()=>setOverlay({kind:'source',id:'brief',line:7})}>brief.md:7<Icon name="link" size={12}/></button>}</div><span className="ledger-state">{complete?'Listo':state.iteration===3?stopping?'Parcial':'En curso':'Pendiente'}</span></li>
                </ol>
              </div>}
              {error&&<div className="interruption error-state" role="alert"><Icon name="warning" size={22}/><h2>No se pudo iniciar.</h2><p>No hay entrega generada. Conservamos el encargo para editarlo o reintentar el recorrido.</p><div className="interruption-actions"><button className="solid-button" onClick={()=>setOverlay({kind:'control'})}>Revisar el estado<Icon name="arrow" size={14}/></button><button className="quiet-button" onClick={()=>document.getElementById('director-input')?.focus()}>Editar el encargo</button></div><details><summary>Detalle del ejemplo</summary><code>MODEL_UNAVAILABLE_DEMO</code><p>Escenario sintético. No diagnostica el timeout histórico R13. Fallar consume un intento de este recorrido.</p></details></div>}

            </div>}
            <div className="composer-zone">
              <div className="composer-box"><label className="composer-label" htmlFor="director-input">{composerLabel}<span aria-hidden="true">{state.draft.length}/2000</span></label><textarea id="director-input" rows={ready?3:2} maxLength={2000} aria-describedby="composer-hint" value={state.draft} disabled={busy} placeholder={busy?'El equipo tiene el encargo. Puedes detener el ejemplo.':complete?'¿Qué cambiarías en esta entrega?':'Describe un resultado concreto…'} onChange={e=>dispatch({type:'DRAFT',value:e.target.value})} onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'&&!busy&&!e.nativeEvent.isComposing&&!e.repeat){e.preventDefault();dispatch({type:'START'});}}}/>
                <div className="composer-footer"><button className="context-chip" onClick={()=>setOverlay({kind:'source',id:'brief'})}><Icon name="file" size={14}/><span>3 fuentes</span></button><span className="composer-local">Local · ejemplo</span>{running?<button className="stop-control" onClick={()=>dispatch({type:'STOP'})}><Icon name="stop" size={13}/>Detener ejemplo</button>:stopping&&!state.closed?<span className="pending-label"><Icon name="clock" size={14}/>Esperando cierre</span>:<button className="send-button" aria-label={sendLabel} title={`${sendLabel} · Ctrl+Enter`} disabled={!state.draft.trim()||state.attempts>=3} onClick={()=>{setNotice('');dispatch({type:'START'});}}><span>{sendLabel}</span><Icon name="arrow" size={16}/></button>}</div>
              </div>
              <div className="composer-caption"><span id="composer-hint">{storageWarning?'No se pudo conservar el borrador en esta pestaña.':state.attempts>=3?'Límite de 3 intentos alcanzado en esta escena.':ready?'Borrador guardado en esta pestaña · Ctrl+Enter':complete?'Ajuste de interfaz: la respuesta de Norte es fija.':'Recorrido manual · 0 llamadas al modelo'}</span>{running&&<button onClick={()=>dispatch(state.iteration<3?{type:'ADVANCE',revision:state.revision,from:state.iteration}:{type:'FINISH',revision:state.revision})}>{state.iteration===1?'Simular revisión':state.iteration===2?'Simular integración':'Mostrar entrega'}<Icon name="arrow" size={12}/></button>}</div>
            </div>
          </section>
          {artifactVisible&&<PaneDivider kind="director" container={surface} controls="director-pane" label="Conversación con el Director"/>}
          {artifactVisible&&<section className="artifact-surface" aria-label="Entrega del trabajo">
            <div className="artifact-toolbar"><div className="artifact-tabs" role="tablist" aria-label="Vistas de la entrega">{(['document','changes','sources'] as const).map((id,i)=><button role="tab" id={`artifact-${id}`} aria-controls="artifact-panel" tabIndex={tab===id?0:-1} aria-selected={tab===id} key={id} onClick={()=>setTab(id)} onKeyDown={e=>{const ids=['document','changes','sources'] as const;let n=i;if(e.key==='ArrowRight')n=(i+1)%3;else if(e.key==='ArrowLeft')n=(i+2)%3;else if(e.key==='Home')n=0;else if(e.key==='End')n=2;else return;e.preventDefault();setTab(ids[n]);document.getElementById(`artifact-${ids[n]}`)?.focus();}}>{id==='document'?'Entrega':id==='changes'?'Cambios':'Fuentes'}{id==='sources'&&<span>3</span>}</button>)}</div><button className="icon-button" disabled={!finalVersion} title={finalVersion?'Exportar v3':'Disponible al terminar y seleccionar Entrega (v3)'} aria-label="Exportar entrega de ejemplo a Markdown" onClick={exportReport}><Icon name="download"/></button></div>
            <div id="artifact-panel" role="tabpanel" aria-labelledby={`artifact-${tab}`} className="artifact-scroll">
              {tab==='document'&&<article className={`document ${!finalVersion?'draft-document':''}`}><div className="document-overline"><span>PROPUESTA DE LANZAMIENTO</span><span className="revision-chip">{error?'Sin generar':version===1?'v1 · Borrador':version===2?'v2 · Revisada':complete?'v3 · Entrega':'v3 · En preparación'}</span></div><h1>Lanzamiento de Norte</h1><p className="document-deck">Propuesta y decisiones · contexto sintético</p>
                {error?<div className="document-unavailable"><Icon name="file" size={28}/><h2>La entrega está pendiente.</h2><p>Las fuentes siguen disponibles. El modelo no llegó a redactar en este escenario.</p><button className="quiet-button" onClick={()=>setTab('sources')}>Revisar las fuentes<Icon name="arrow" size={14}/></button></div>:<><div className="document-meta"><span><Icon name="file" size={13}/>3 fuentes</span><span>Material sintético</span><span>{finalVersion?'Lista para revisar':revised?'Versión intermedia':'Trabajo parcial'}</span></div><section className="document-section"><span className="section-number">01</span><div><h2>La recomendación</h2><p>{revised?'Notas locales, guardadas en tu equipo y exportables a Markdown.':'Notas locales con sincronización entre dispositivos.'} {version===3?'Mostrar una tarea completa y cerrar la página con una lista de espera, sin anunciar fechas.':revised?'Falta consolidar la llamada a la acción y las comprobaciones finales.':'Esta primera propuesta está pendiente de contrastar con el alcance.'}</p><button className="source-citation" onClick={()=>setOverlay({kind:'source',id:'brief',line:3})}>brief.md <span>3–7</span><Icon name="link" size={12}/></button></div></section>
                <section className="document-section"><span className="section-number">02</span><div><h2>Decisiones de la propuesta</h2><div className="decision-list">{decisions.slice(0,version===3?3:revised?2:1).map((d,i)=><div className="decision" key={d.title}><span>{String(i+1).padStart(2,'0')}</span><div><h3>{d.title}</h3><p>{d.body}</p><button className="source-citation" onClick={()=>setOverlay({kind:'source',id:d.source,line:d.line})}>{sources[d.source].name}<span>L{d.line}</span><Icon name="link" size={12}/></button></div></div>)}</div></div></section>
                {version===3?<><section className="document-section"><span className="section-number">03</span><div><h2>La primera entrega</h2><ol className="deliverable-list"><li>Explicar dónde se guardan los archivos.</li><li>Mostrar escribir, guardar y exportar una nota.</li><li>Preparar el texto de la lista de espera.</li><li>Revisar el mensaje con alguien que no conozca Norte.</li></ol></div></section><div className="open-question"><span>POR VALIDAR</span><p>Que el mensaje se entienda. El interés del público todavía no se ha medido.</p></div></>:<div className="draft-end"><span className="draft-rule"/><span>{stopping?'Trabajo parcial conservado · sin validar':complete?'Versión anterior · selecciona Entrega para ver v3':'La propuesta continúa en la siguiente etapa del ejemplo'}</span></div>}</>}
                <footer className="document-footer"><span>NORTE / NOTA DE TRABAJO</span><span>Ejemplo · Neural Office</span></footer></article>}
              {tab==='changes'&&<div className="changes-view"><div className="document-overline">DECISIONES ENTRE VERSIONES</div><h2>Qué cambió y por qué.</h2>{!error&&state.iteration>=2?<><div className="diff-label"><Icon name="file"/>v1 → v2 · Corregir una promesa</div><div className="diff-line removed"><span>−</span><p>Notas locales con sincronización entre dispositivos.</p></div><div className="diff-line added"><span>+</span><p>Notas locales, guardadas en tu equipo y exportables a Markdown.</p></div><button className="source-citation" onClick={()=>setOverlay({kind:'source',id:'scope',line:6})}>Motivo: alcance.md:6<Icon name="arrow" size={13}/></button>{state.iteration===3?<><div className="diff-label"><Icon name="check"/>v2 → v3 · Concretar el siguiente paso</div><div className="diff-line added"><span>+</span><p>Lista de espera sin fecha anunciada. Validar la comprensión del mensaje antes de publicar.</p></div><button className="source-citation" onClick={()=>setOverlay({kind:'source',id:'brief',line:7})}>Motivo: brief.md:6–7<Icon name="arrow" size={13}/></button></>:<p>La tercera etapa todavía está pendiente.</p>}<p className="changes-note">Comparación de fixtures sintéticas. Los archivos fuente permanecen intactos.</p></>:<p>Sin cambios comparables todavía. Avanza manualmente a Revisión para inspeccionar v1 → v2.</p>}</div>}
              {tab==='sources'&&<div className="sources-view"><div className="document-overline">CONTEXTO DEL ENCARGO</div><h2>Contexto del encargo.</h2><p>Contenido sintético incluido en esta vista previa. No se ha leído ningún archivo de tu equipo.</p>{(Object.keys(sources) as SourceId[]).map(id=><button className="source-row" key={id} onClick={()=>setOverlay({kind:'source',id})}><Icon name="file" size={22}/><span><strong>{sources[id].name}</strong><small>{sources[id].label}</small></span><span>{sources[id].text.split('\n').length} líneas</span><Icon name="arrow" size={14}/></button>)}</div>}
            </div>
          </section>}
        </main>
        <footer className="statusbar"><span className={`status-dot ${error?'error':complete?'success':''}`}/><span aria-live="polite">{notice||status}</span><button onClick={()=>setOverlay({kind:'control'})}><span>{state.attempts}/3 intentos de ejemplo</span><Icon name="settings" size={12}/></button></footer>
      </div>
    </div>
    <dialog ref={dialog} className={`workspace-dialog ${overlay?.kind==='measure'?'measurement-dialog':''}`} aria-labelledby="dialog-title" onCancel={()=>setOverlay(null)} onClose={()=>setOverlay(null)}>
      <div className="dialog-heading"><span>{overlay?.kind==='source'?'FUENTE DEL EJEMPLO':overlay?.kind==='measure'?'MEDICIÓN LOCAL':overlay?.kind==='library'?'BIBLIOTECA':'CONTROL DEL TRABAJO'}</span><button className="icon-button" aria-label="Cerrar panel" onClick={()=>setOverlay(null)}><Icon name="close"/></button></div>
      <div className="dialog-body">
        {currentSource&&<><h2 id="dialog-title">{currentSource.name}</h2><p>{currentSource.label} · Solo lectura · Material sintético</p><div className="source-picker">{(Object.keys(sources) as SourceId[]).map(id=><button className={overlay?.kind==='source'&&overlay.id===id?'selected':''} key={id} onClick={()=>setOverlay({kind:'source',id})}>{sources[id].name}</button>)}</div><div className="source-code">{currentSource.text.split('\n').map((line,i)=><div className={overlay?.kind==='source'&&overlay.line===i+1?'highlighted':''} key={i}><span>{i+1}</span><code>{line||' '}</code></div>)}</div></>}
        {overlay?.kind==='control'&&<><h2 id="dialog-title">El límite también es parte del plan.</h2><p>Estos valores pertenecen al recorrido de ejemplo de esta pestaña. La UI no concede autoridad al motor.</p><dl className="control-facts"><div><dt>Intentos consumidos</dt><dd>{state.attempts} de 3</dd></div><div><dt>Iteración mostrada</dt><dd>{ready||error?'Sin comenzar':`${state.iteration} de 3 · ${complete?'entrega disponible':stopping?'interrumpida':'en el ejemplo'}`}</dd></div><div><dt>Límite propuesto de iteraciones</dt><dd>Hasta 3, con salida anticipada</dd></div><div><dt>Modelo real</dt><dd>Sin conectar</dd></div><div><dt>Inferencias en esta interfaz</dt><dd>0</dd></div><div><dt>Archivos del usuario</dt><dd>Ninguno</dd></div><div><dt>RAM / GPU del modelo</dt><dd>No medidas en esta vista</dd></div></dl><p className="control-note">Un intento no equivale a una iteración ni a un empleado. Detener o fallar mantiene el consumo del ejemplo. Cambiar de pantalla en la barra superior carga otra escena de diseño.</p></>}
        {overlay?.kind==='library'&&<><h2 id="dialog-title">Saber qué sabe tu oficina.</h2><p>La biblioteca se conectará en V5.7. Su diseño debe permitir ver instrucciones, fuentes, permisos y versiones antes de reutilizarlas.</p><div className="library-outline"><Icon name="book" size={24}/><div><strong>Sin skills activas ni memoria aprendida</strong><p>Este prototipo utiliza únicamente las tres fuentes sintéticas de Norte. No guarda recuerdos ni ejecuta aprendizajes de fondo.</p></div></div><button className="quiet-button" onClick={()=>setOverlay({kind:'source',id:'brief'})}>Inspeccionar el contexto incluido<Icon name="arrow" size={14}/></button></>}
        {overlay?.kind==='measure'&&<><h2 id="dialog-title">Medir antes de prometer.</h2><p>Muestras acotadas de 5 segundos. Heap del navegador, elementos y tareas largas; no RAM total del escritorio ni consumo del modelo. No hay muestreo cuando termina la ventana.</p><div className="measurement-actions"><button disabled={measuring} className="solid-button" onClick={()=>startSample(false)}>Medir reposo</button><button disabled={measuring} className="quiet-button" onClick={()=>startSample(true)}>Ensayar 10 000 eventos</button><button disabled={!samples.length||measuring} className="quiet-button" onClick={downloadMeasurements}>Exportar mediciones</button></div><div role="status" className="measurement-status">{measuring?'Midiendo durante 5 segundos…':samples.length?'Muestra terminada. No hay un colector activo.':'Sin muestras de esta pestaña.'}</div>{samples.length>0&&<div className="sample-table"><table><thead><tr><th>Muestra</th><th>Tiempo</th><th>DOM</th><th>Heap JS</th><th>Tareas largas</th></tr></thead><tbody>{samples.map((s,i)=><tr key={i}><td>{s.mode}</td><td>{Math.round(s.elapsedMs)} ms</td><td>{s.dom}</td><td>{s.heapBytes===null?'No disponible':(s.heapBytes/1048576).toFixed(2)+' MiB'}</td><td>{s.longTasks}</td></tr>)}</tbody></table></div>}{eventTotal>0&&<div className="event-history"><div className="history-heading"><strong>Historial sintético</strong><span>{pagination.start+1}–{pagination.end} de {eventTotal}</span></div><div className="history-rows">{Array.from({length:pagination.end-pagination.start},(_,i)=><div key={pagination.start+i}><code>{String(pagination.start+i+1).padStart(5,'0')}</code><span>Fuente comprobada</span><span>Ejemplo</span></div>)}</div><div className="history-pagination"><button disabled={pagination.page===0||measuring} onClick={()=>setEventPage(pagination.page-1)}>Anterior</button><span>Página {pagination.page+1} / {pagination.pages}</span><button disabled={pagination.page===pagination.pages-1||measuring} onClick={()=>setEventPage(pagination.page+1)}>Siguiente</button></div><p>Se generan solo las 50 filas visibles. Esta prueba mide la vista paginada, no almacenar 10 000 eventos reales en memoria.</p></div>}</>}
      </div>
    </dialog>
  </div>;
}
function safeStorage():Storage|null {try{return sessionStorage;}catch{return null;}}
