import {useEffect,useRef,useState} from 'react';
import {request} from '../connected/client.ts';
import type {Inspection} from '../connected/attachments.ts';
import {DeskDialog,Icon} from '../connected/DeskTools.tsx';
type Kind='memory'|'skill';
type Entry={id:string;project:string;thread:string;report:string;revision:number;kind:Kind;title:string;body:string;proposal:string|null;retired:number;operation:string;at:number};
type Operation='create'|'edit'|'propose'|'accept'|'discard'|'retire';
const labels:Record<string,string>={create:'Creación',edit:'Edición',propose:'Propuesta',accept:'Aceptación',discard:'Descartada',retire:'Retirada'};
export function Library({project,source,online,openSource,useSkill}:{project:string;source:Inspection|null;online:boolean;openSource:(thread:string,report:string)=>void;useSkill:(text:string)=>void}){
  const [tab,setTab]=useState<Kind|'history'>('memory'),[query,setQuery]=useState('');
  const [rows,setRows]=useState<Entry[]>([]),[selected,setSelected]=useState(''),[versions,setVersions]=useState<Entry[]>([]);
  const [refresh,setRefresh]=useState(0),[fault,setFault]=useState(''),[busy,setBusy]=useState(false);
  const [form,setForm]=useState<Operation|null>(null),[title,setTitle]=useState(''),[body,setBody]=useState('');
  const mounted=useRef(false),flight=useRef(false);
  useEffect(()=>{mounted.current=true;return ()=>{mounted.current=false;};},[]);
  useEffect(()=>{
    let live=true;
    if(online)request<Entry[]>('library.list',{project_id:project}).then(v=>{if(live)setRows(v);}).catch(e=>{if(live)setFault(e.message);});
    return ()=>{live=false;};
  },[project,online,refresh]);
  const filtered=rows.filter(r=>(tab==='history'||(r.kind===tab&&!r.retired))&&r.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const current=filtered.find(r=>r.id===selected)??filtered[0];
  useEffect(()=>{
    let live=true;setVersions([]);
    if(online&&current)request<Entry[]>('library.history',{project_id:project,entry_id:current.id}).then(v=>{if(live)setVersions(v);}).catch(e=>{if(live)setFault(e.message);});
    return ()=>{live=false;};
  },[project,current?.id,current?.revision,online]);
  function begin(op:Operation){
    setFault('');setForm(op);setTitle(op==='create'?'':current?.title??'');
    setBody(op==='create'?'':current?.proposal??current?.body??'');
  }
  async function insertSkill(){
    if(flight.current||!online||!current)return;
    flight.current=true;setBusy(true);setFault('');
    try{
      const value=await request<{id:string;revision:number;body:string}>('library.for_draft',{
        project_id:project,entry_id:current.id,expected_revision:current.revision});
      if(mounted.current&&value.id===current.id&&value.revision===current.revision)useSkill(value.body);
    }catch(e){
      if(mounted.current){
        const code=e instanceof Error?e.message:'';
        setFault(code==='LIBRARY_ENTRY_RETIRED'?'La skill fue retirada. Tu borrador se conserva.':
          code==='LIBRARY_REVISION_CHANGED'?'La skill cambió. Revisa la versión vigente antes de usarla.':code);
        setRefresh(v=>v+1);
      }
    }finally{flight.current=false;if(mounted.current)setBusy(false);}
  }
  async function save(op:Operation){
    if(flight.current||!online)return;
    const origin=op==='create'?source&&{thread:source.thread_id,report:source.id}:current;
    if(!origin)return;
    const id=op==='create'?crypto.randomUUID():current!.id;
    flight.current=true;setBusy(true);setFault('');
    try{
      await request('library.change',{project_id:project,thread_id:origin.thread,report_id:origin.report,entry_id:id,
        kind:op==='create'?tab:current!.kind,title:op==='create'||op==='edit'?title:current!.title,body:body.trim(),operation:op,
        expected_revision:op==='create'?0:current!.revision});
      if(mounted.current){setForm(null);setSelected(id);setRefresh(v=>v+1);}
    }catch(e){if(mounted.current){setFault(e instanceof Error?e.message:'Error de lectura');setRefresh(v=>v+1);}}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  }
  return <section className="office-library"><header><h1>Memoria del proyecto</h1><p>{project}</p></header>
    <nav className="office-tabs" aria-label="Biblioteca del proyecto">{([['memory','Memoria'],['skill','Skills'],['history','Historial']] as const).map(([id,name])=><button key={id} aria-current={tab===id?'page':undefined} onClick={()=>{setTab(id);setSelected('');setQuery('');}}>{name}</button>)}</nav>
    {fault&&<p role="alert">No se pudo completar el cambio. <code>{fault}</code></p>}
    <div className="library-columns"><section className="library-index"><label><Icon name="search"/><input value={query} aria-label="Buscar en la biblioteca" placeholder={tab==='skill'?'Buscar una skill…':'Buscar en la memoria…'} onChange={e=>setQuery(e.target.value)}/></label>
      {filtered.map(r=><button key={r.id} onClick={()=>setSelected(r.id)} aria-pressed={r.id===current?.id}><strong>{r.title}</strong><small>{r.retired?'Retirada':r.proposal?'Propuesta pendiente':'Activa'} · r{r.revision}</small></button>)}
      {tab!=='history'&&<button className="library-add" disabled={!source||!online} onClick={()=>begin('create')}>＋ {tab==='skill'?'Proponer skill':'Añadir nota'}</button>}
      {!source&&tab!=='history'&&<small>Abre una entrega de este proyecto para registrar el origen.</small>}
    </section>
    <section className="library-detail">{!current?<><h2>{query?'Sin coincidencias':tab==='skill'?'Todavía no hay skills':tab==='history'?'Sin revisiones':'Todavía no hay notas'}</h2><p>{query?'Prueba con otro nombre.':'Las entradas se vinculan al hilo y a la entrega de origen.'}</p></>:<>
      <h2>{current.title}</h2><p className="library-meta">{project} · Revisión {current.revision}</p>
      {tab==='history'?<ol className="version-log">{versions.map(v=><li key={v.revision}><strong>r{v.revision} · {labels[v.operation]}</strong><time>{new Date(v.at*1000).toLocaleString('es-ES')}</time><p>{v.proposal??v.body}</p></li>)}</ol>:<>
        {current.body&&<><h3>{current.kind==='skill'?'Instrucción activa':'Nota del proyecto'}</h3>
          <p className={current.proposal?'library-copy replacing':'library-copy'}>{current.body}</p></>}
        {current.proposal&&<><h3>Propuesta pendiente</h3><p className="proposal-copy">{current.proposal}</p>
          <p>Se puede insertar en un encargo cuando la aceptes.</p><div className="arc-actions"><button disabled={busy||!online} onClick={()=>void save('accept')}>Aceptar propuesta</button><button disabled={busy||!online} onClick={()=>void save('discard')}>Descartar</button></div></>}
        <div className="arc-actions">{current.kind==='skill'&&current.body&&<button disabled={!online||busy} onClick={()=>void insertSkill()}>Usar en un borrador</button>}
          {!current.proposal&&<button disabled={!online||busy} onClick={()=>begin(current.kind==='skill'?'propose':'edit')}>{current.kind==='skill'?'Proponer cambio':'Editar nota'}</button>}
          <button disabled={!online||busy} onClick={()=>begin('retire')}>Retirar</button></div></>}
      <button className="provenance-link" onClick={()=>openSource(current.thread,current.report)}><Icon name="thread"/>Abrir el hilo de origen</button></>}</section></div>
    {form&&<DeskDialog label={form==='retire'?'Retirar esta entrada':form==='create'?(tab==='skill'?'Proponer una skill':'Nueva nota'):form==='edit'?'Editar la nota':'Proponer un cambio'} close={()=>{if(!busy)setForm(null);}}>
      <form className="library-form" onSubmit={e=>{e.preventDefault();void save(form);}}>
        {form==='retire'?<p>«{current?.title}» quedará disponible en el historial.</p>:<><label>Nombre<input required maxLength={120} value={title} readOnly={form==='propose'} onChange={e=>setTitle(e.target.value)}/></label>
        <label>{tab==='skill'?'Instrucción':'Contenido'}<textarea required maxLength={1500} rows={6} value={body} onChange={e=>setBody(e.target.value)}/></label></>}
        <button className="desk-primary" disabled={busy||!online}>{form==='retire'?'Confirmar retirada':'Guardar'}</button>
        {fault&&<p role="alert">{fault}</p>}</form></DeskDialog>}</section>;
}
