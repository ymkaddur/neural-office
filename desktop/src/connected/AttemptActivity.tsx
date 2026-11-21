import {useEffect, useId, useState} from 'react';
import {request} from './client.ts';
import type {Event} from './model.ts';

type Page = {session_id:string; office_id:string; attempt_id:string; events:Event[]; next_before:number; has_more:boolean};
const pageSize=24;
// UI navigation is scoped to the durable attempt; receipts are always read again from the service.
const positions=new Map<string,{open:boolean;before:number}>();
const publicFields:Record<string,string>={
  ordinal:'Número de intento',call:'Llamada',role:'Rol',state:'Estado',reason:'Motivo',code:'Código',model:'Modelo',project:'Proyecto',attempt:'Intento',
  source_sha256:'Huella de entrada',prompt_sha256:'Huella del mensaje',output_sha256:'Huella de salida',payload_sha:'Huella de la petición',
  content_sha:'Huella de la respuesta',artifact_sha:'Huella de la entrega',tokens:'Tokens registrados',
};
const labels:Record<string,string>={
  ATTEMPT_RESERVED:'Intento reservado', LEASE_ACQUIRED:'Ejecución adquirida',
  MODEL_CALL_ADMITTED:'Llamada autorizada', MODEL_CALL_COMPLETED:'Respuesta registrada', OWNED_JOB_TERMINATED:'Ejecución cerrada',
  CANCELLATION_REQUESTED:'Parada solicitada', TERMINATION_UNKNOWN:'Terminación por confirmar',
  FINAL_VERDICT:'Entrega evaluada',
};

function validPage(page:Page, office:string, session:string, attempt:string, before:number) {
  if(page.office_id!==office||page.session_id!==session||page.attempt_id!==attempt||
    !Array.isArray(page.events)||page.events.length>pageSize||typeof page.has_more!=='boolean')return false;
  let previous=0;
  for(const event of page.events){
    if(!Number.isSafeInteger(event.seq)||event.seq<=previous||(before>0&&event.seq>=before)||
      event.payload?.attempt!==attempt||typeof event.kind!=='string'||typeof event.stamp_ns!=='string')return false;
    previous=event.seq;
  }
  return page.next_before===(page.events[0]?.seq??0)&&(!page.has_more||page.events.length===pageSize);
}

function timeOf(stamp:string) {
  if(!/^\d{1,19}$/.test(stamp))return '';
  const date=new Date(Number(BigInt(stamp)/1000000n));
  return Number.isNaN(date.valueOf())?'':date.toLocaleTimeString('es-ES');
}

export function AttemptActivity({office,session,attempt,revision}:{office:string;session:string;attempt:string;revision:number}){
  const key=JSON.stringify([office,attempt]);
  const eventsId=useId();
  const [open,setOpen]=useState(()=>positions.get(key)?.open??false);
  const [before,setBefore]=useState(()=>positions.get(key)?.before??0);
  useEffect(()=>{if(positions.size>200&&!positions.has(key))positions.delete(positions.keys().next().value!);positions.set(key,{open,before});},[key,open,before]);
  const [retry,setRetry]=useState(0);
  const [page,setPage]=useState<Page|null>(null);
  const [failed,setFailed]=useState(false);
  const latestRevision=before===0?revision:0;
  useEffect(()=>{
    if(!open)return;
    let current=true;
    setFailed(false);
    void request<Page>('attempt.events',{attempt_id:attempt,before,limit:pageSize}).then(next=>{
      if(!current)return;
      if(!validPage(next,office,session,attempt,before))throw Error('EVENT_PAGE_CHANGED');
      setPage(next);
    }).catch(()=>{if(current){setFailed(true);setPage(null);}});
    return ()=>{current=false;};
  },[open,office,session,attempt,before,latestRevision,retry]);
  function navigate(cursor:number){setPage(null);setBefore(cursor);}
  return <section className="connected-event-details">
    <button type="button" className="attempt-disclosure" aria-expanded={open} aria-controls={eventsId} onClick={()=>setOpen(value=>!value)}>
      Actividad del encargo{open&&page&&<span>{page.events.length} en esta página</span>}
    </button>
    <div id={eventsId} hidden={!open}>{open&&(failed?<p role="status">No se pudo leer la actividad. <button type="button" className="quiet-button" onClick={()=>setRetry(value=>value+1)}>Reintentar lectura</button></p>
      :page?<>{page.events.length===0?<p>Sin eventos registrados para este encargo.</p>:<ol>{page.events.map(event=><li key={event.seq}>
        <code>#{event.seq}</code>
        <div className="event-fact"><strong>{Object.hasOwn(labels,event.kind)?labels[event.kind]:event.kind.toLowerCase().replaceAll('_',' ')}</strong>
          {typeof event.payload.role==='string'&&<span>{event.payload.role}</span>}
          <details className="receipt-details"><summary>Datos del recibo #{event.seq}</summary><dl>{Object.entries(publicFields).flatMap(([field,label])=>{
            const value=event.payload[field];return typeof value==='string'||typeof value==='number'?[<div key={field}><dt>{label}</dt><dd>{String(value)}</dd></div>]:[];
          })}</dl></details></div>
        <time>{timeOf(event.stamp_ns)}</time>
      </li>)}</ol>}
      {page.has_more&&<button type="button" className="quiet-button" onClick={()=>navigate(page.next_before)}>Ver eventos anteriores</button>}
      {before>0&&<button type="button" className="quiet-button" onClick={()=>navigate(0)}>Volver a los más recientes</button>}</>:<p role="status">Leyendo actividad…</p>)}
    </div>
  </section>;
}
