import {useEffect,useRef,useState} from 'react';
import {request} from '../connected/client.ts';
import type {Inspection} from '../connected/attachments.ts';
import {DeskDialog,Icon} from '../connected/DeskTools.tsx';
type Kind='memory'|'skill';
type Entry={id:string;project:string;thread:string;report:string;revision:number;kind:Kind;title:string;body:string;proposal:string|null;retired:number;operation:string;at:number};
type Operation='create'|'edit'|'propose'|'accept'|'discard'|'retire';
type Target=Pick<Entry,'id'|'thread'|'report'|'kind'|'title'|'revision'>;
type Editor=Target & {op:'create'|'edit'|'propose'|'retire'};
const labels:Record<string,string>={create:'Creación',edit:'Edición',propose:'Propuesta',accept:'Aceptación',discard:'Descartada',retire:'Retirada'};

async function creationRecorded(project:string,target:Target,title:string,body:string){
  try{
    const history=await request<Entry[]>('library.history',{project_id:project,entry_id:target.id});
    return history.some(row=>row.revision===1&&row.operation==='create'&&row.id===target.id
      &&row.project===project&&row.kind===target.kind&&row.thread===target.thread&&row.report===target.report
      &&row.title===title&&(row.kind==='skill'?row.proposal:row.body)===body);
  }catch{
    // The original mutation remains unconfirmed. Retrying keeps the editor's entry ID.
    return false;
  }
}
export function Library({project,source,online,openSource,useSkill}:{project:string;source:Inspection|null;online:boolean;openSource:(thread:string,report:string)=>void;useSkill:(text:string)=>void}){
  const [tab,setTab]=useState<Kind|'history'>('memory'),[query,setQuery]=useState('');
  const [rows,setRows]=useState<Entry[]>([]),[selected,setSelected]=useState(''),[versions,setVersions]=useState<Entry[]>([]);
  const [refresh,setRefresh]=useState(0),[fault,setFault]=useState(''),[busy,setBusy]=useState(false);
  const [form,setForm]=useState<Editor|null>(null),[title,setTitle]=useState(''),[body,setBody]=useState('');
  const mounted=useRef(false),flight=useRef(false);
  useEffect(()=>{mounted.current=true;return ()=>{mounted.current=false;};},[]);
  useEffect(()=>{
    let live=true;
    if(online)request<Entry[]>('library.list',{project_id:project}).then(v=>{if(live)setRows(v);}).catch(e=>{if(live)setFault(e.message);});
    return ()=>{live=false;};
  },[project,online,refresh]);
  const filtered=rows.filter(r=>(tab==='history'||(r.kind===tab&&!r.retired))&&r.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const current=filtered.find(r=>r.id===selected)??filtered[0];
  const changed=form&&form.op!=='create'?rows.find(row=>row.id===form.id&&row.revision!==form.revision):undefined;
  const conflict=!!form&&form.op!=='create'&&(!!changed||fault==='LIBRARY_REVISION_CHANGED'||fault==='LIBRARY_ENTRY_RETIRED');
  useEffect(()=>{
    let live=true;setVersions([]);
    if(online&&current)request<Entry[]>('library.history',{project_id:project,entry_id:current.id}).then(v=>{if(live)setVersions(v);}).catch(e=>{if(live)setFault(e.message);});
    return ()=>{live=false;};
  },[project,current?.id,current?.revision,online]);
  function begin(op:Editor['op']){
    const target=op==='create'
      ?source&&tab!=='history'?{id:crypto.randomUUID(),kind:tab,thread:source.thread_id,report:source.id,revision:0,title:''}:null
      :current;
    if(!target)return;
    setFault('');setForm({...target,op});setTitle(target.title);
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
  async function save(op:Operation,target:Target){
    if(flight.current||!online||conflict)return;
    const submittedTitle=(op==='create'||op==='edit'?title:target.title).trim();
    const submittedBody=op==='create'||op==='edit'||op==='propose'?body.trim():'';
    flight.current=true;setBusy(true);setFault('');
    try{
      try{
        await request('library.change',{project_id:project,thread_id:target.thread,report_id:target.report,entry_id:target.id,
          kind:target.kind,title:submittedTitle,body:submittedBody,operation:op,expected_revision:target.revision});
      }catch(error){
        if(op!=='create'||!await creationRecorded(project,target,submittedTitle,submittedBody))throw error;
      }
      if(mounted.current){setForm(null);setSelected(target.id);setRefresh(v=>v+1);}
    }catch(e){if(mounted.current){setFault(e instanceof Error?e.message:'Error de lectura');setRefresh(v=>v+1);}}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  }
  return <section className="office-library"><header><h1>Memoria del proyecto</h1><p>{project}</p></header>
    <nav className="office-tabs" aria-label="Biblioteca del proyecto">{([['memory','Memoria'],['skill','Skills'],['history','Historial']] as const).map(([id,name])=><button key={id} aria-current={tab===id?'page':undefined} onClick={()=>{setTab(id);setSelected('');setQuery('');}}>{name}</button>)}</nav>
    {fault&&!form&&<p role="alert">No se pudo completar el cambio. <code>{fault}</code></p>}
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
          <p>Se puede insertar en un encargo cuando la aceptes.</p><div className="arc-actions"><button disabled={busy||!online} onClick={()=>void save('accept',current)}>Aceptar propuesta</button><button disabled={busy||!online} onClick={()=>void save('discard',current)}>Descartar</button></div></>}
        <div className="arc-actions">{current.kind==='skill'&&current.body&&<button disabled={!online||busy} onClick={()=>void insertSkill()}>Usar en un borrador</button>}
          {!current.proposal&&<button disabled={!online||busy} onClick={()=>begin(current.kind==='skill'?'propose':'edit')}>{current.kind==='skill'?'Proponer cambio':'Editar nota'}</button>}
          <button disabled={!online||busy} onClick={()=>begin('retire')}>Retirar</button></div></>}
      <button className="provenance-link" onClick={()=>openSource(current.thread,current.report)}><Icon name="thread"/>Abrir el hilo de origen</button></>}</section></div>
    {form&&<DeskDialog label={form.op==='retire'?'Retirar esta entrada':form.op==='create'?(form.kind==='skill'?'Proponer una skill':'Nueva nota'):form.op==='edit'?'Editar la nota':'Proponer un cambio'} close={()=>{if(!busy){setForm(null);setFault('');}}}>
      <form className="library-form" onSubmit={e=>{e.preventDefault();void save(form.op,form);}}>
        {form.op==='retire'?<p>«{form.title}» quedará disponible en el historial.</p>:<><label>Nombre<input required disabled={busy} maxLength={120} value={title} readOnly={form.op==='propose'} onChange={e=>setTitle(e.target.value)}/></label>
        <label>{form.kind==='skill'?'Instrucción':'Contenido'}<textarea required disabled={busy} maxLength={1500} rows={6} value={body} onChange={e=>setBody(e.target.value)}/></label></>}
        {conflict&&<section aria-label="Cambio de versión">
          <p role="alert">{changed?.retired?'Esta entrada fue retirada. Puedes copiar tu texto antes de cerrar.':'La entrada cambió en otra ventana. Tu texto sigue en este formulario.'}</p>
          {changed&&!changed.retired&&<><strong>Revisión {changed.revision} · {changed.title}</strong>
            <p className="library-copy">{changed.proposal??changed.body}</p>
            {form.op!=='create'&&(form.op!=='propose'||!changed.proposal)&&<button type="button" className="provenance-link"
              onClick={()=>{setForm({...changed,op:form.op});setFault('');}}>Revisar mi cambio sobre r{changed.revision}</button>}</>}
        </section>}
        <button className="desk-primary" disabled={busy||!online||conflict||(form.op!=='retire'&&(!title.trim()||!body.trim()))}>{form.op==='retire'?'Confirmar retirada':'Guardar'}</button>
        {fault&&!conflict&&<p role="alert">{form.op==='create'&&fault==='LIBRARY_REVISION_CHANGED'?'Ya existe un alta para esta entrada. Revisa el historial antes de editarla.':fault}</p>}</form></DeskDialog>}</section>;
}
