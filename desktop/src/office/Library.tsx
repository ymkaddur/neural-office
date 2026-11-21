import {useEffect,useId,useLayoutEffect,useRef,useState} from 'react';
import {request} from '../connected/client.ts';
import {nameForProject} from '../connected/model.ts';
import {readSessionDraft} from '../connected/sessionDraft.ts';
import type {Inspection} from '../connected/attachments.ts';
import {DeskDialog,Icon} from '../connected/DeskTools.tsx';
type Kind='memory'|'skill';
type CopyIntent={session_id:string;project_id:string;thread_id:string;entry_id:string;expected_revision:number;active_revision:number;draft_revision:number;edit_id:string};
type CopyReceipt={project_id:string;thread_id:string;session_id:string;entry_id:string;edit_id:string;active_revision:number;draft_revision:number;evicted:{project_id:string;thread_id:string}|null};
type Entry={id:string;project:string;thread:string;report:string;revision:number;kind:Kind;title:string;body:string;proposal:string|null;retired:number;operation:string;at:number};
type Operation='create'|'edit'|'propose'|'accept'|'discard'|'retire';
type Target=Pick<Entry,'id'|'thread'|'report'|'kind'|'title'|'revision'>;
type Editor=Target & {op:'create'|'edit'|'propose'|'retire'};
const limitExplanation:Record<string,string>={
  LIBRARY_ENTRY_LIMIT:'El proyecto alcanzó el límite de 64 entradas. Puedes editar una entrada existente.',
  LIBRARY_REVISION_LIMIT:'Esta entrada alcanzó el límite de 48 revisiones. Puedes retirarla o crear otra entrada.',
  LIBRARY_ENTRY_NOT_FOUND:'La entrada ya no está disponible en este proyecto.',
  DRAFT_REVISION_CHANGED:'El borrador cambió desde que elegiste la skill. Revisa su contenido antes de volver a insertarla.',
  LIBRARY_DRAFT_TOO_LONG:'La instrucción no cabe en los 2.000 caracteres del encargo. Puedes acortar el borrador y volver aquí.',
};
function invalidText(value:string,max:number){
  const text=value.trim();
  if(!text)return 'Escribe al menos un carácter distinto de un espacio.';
  return Array.from(text).length>max?'Este campo admite hasta '+max+' caracteres.':'';
}
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
export function Library({project,session,thread,copyAvailable,source,online,openSource,openDraft}:{project:string;session:string;thread:string;copyAvailable:boolean;source:Inspection|null;online:boolean;openSource:(thread:string,report:string)=>void;openDraft:(receipt:CopyReceipt)=>void}){
  const [tab,setTab]=useState<Kind|'history'>('memory'),[query,setQuery]=useState('');
  const [rows,setRows]=useState<Entry[]>([]),[selected,setSelected]=useState(''),[versions,setVersions]=useState<Entry[]>([]);
  const [refresh,setRefresh]=useState(0),[fault,setFault]=useState(''),[busy,setBusy]=useState(false);
  const [form,setForm]=useState<Editor|null>(null),[title,setTitle]=useState(''),[body,setBody]=useState('');
  const [loading,setLoading]=useState(online),[edited,setEdited]=useState({title:false,body:false});
  const [notice,setNotice]=useState(''),[loaded,setLoaded]=useState(false);
  const mounted=useRef(false),flight=useRef(false),focusAfterRemoval=useRef(false),pendingCopy=useRef<CopyIntent|null>(null);
  const search=useRef<HTMLInputElement>(null),nameId=useId(),bodyId=useId();
  const titleIssue=invalidText(title,120),bodyIssue=invalidText(body,1500);
  useLayoutEffect(()=>{
    if(focusAfterRemoval.current&&!form&&!loading){focusAfterRemoval.current=false;search.current?.focus();}
  },[form,loading]);
  useEffect(()=>{mounted.current=true;return ()=>{mounted.current=false;};},[]);
  useEffect(()=>{
    let live=true;
    setLoading(online);
    if(online)request<Entry[]>('library.list',{project_id:project}).then(v=>{if(live){setRows(v);setLoaded(true);}}).catch(e=>{if(live)setFault(e.message);}).finally(()=>{if(live)setLoading(false);});
    return ()=>{live=false;};
  },[project,online,refresh]);
  const filtered=rows.filter(r=>(tab==='history'||(r.kind===tab&&!r.retired))&&r.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const current=filtered.find(r=>r.id===selected)??filtered[0];
  const changed=form&&form.op!=='create'?rows.find(row=>row.id===form.id&&row.revision!==form.revision):undefined;
  const conflict=!!form&&form.op!=='create'&&(!!changed||fault==='LIBRARY_REVISION_CHANGED'||fault==='LIBRARY_ENTRY_RETIRED');
  useEffect(()=>{
    let live=true;setVersions([]);
    if(tab==='history'&&online&&current)request<Entry[]>('library.history',{project_id:project,entry_id:current.id}).then(v=>{if(live)setVersions(v);}).catch(e=>{if(live)setFault(e.message);});
    return ()=>{live=false;};
  },[project,current?.id,current?.revision,online,tab]);
  function begin(op:Editor['op']){
    const target=op==='create'
      ?source&&tab!=='history'?{id:crypto.randomUUID(),kind:tab,thread:source.thread_id,report:source.id,revision:0,title:''}:null
      :current;
    if(!target)return;
    setFault('');setNotice('');setEdited({title:false,body:false});setForm({...target,op});setTitle(target.title);
    setBody(op==='create'?'':current?.proposal??current?.body??'');
  }
  async function insertSkill(){
    if(flight.current||!online||!copyAvailable||!current)return;
    flight.current=true;setBusy(true);setFault('');
    try{
      let intent=pendingCopy.current;
      if(!intent||intent.entry_id!==current.id||intent.expected_revision!==current.revision){
        const params={project_id:project,entry_id:current.id,expected_revision:current.revision};
        const [candidate,draft]=await Promise.all([
          request<{id:string;revision:number;active_revision:number}>('library.for_draft',params),
          readSessionDraft(session,project,thread),
        ]);
        if(!mounted.current)return;
        if(candidate.id!==current.id||candidate.revision!==current.revision||!Number.isSafeInteger(candidate.active_revision))throw Error('LIBRARY_REVISION_CHANGED');
        intent={...params,session_id:session,thread_id:thread,active_revision:candidate.active_revision,draft_revision:draft.revision,edit_id:crypto.randomUUID()};
        pendingCopy.current=intent;
      }
      const receipt=await request<CopyReceipt>('library.copy_to_draft',intent);
      if(receipt.edit_id!==intent.edit_id||receipt.session_id!==session||receipt.project_id!==project||receipt.thread_id!==thread||receipt.entry_id!==intent.entry_id||receipt.active_revision!==intent.active_revision||!Number.isSafeInteger(receipt.draft_revision)||receipt.draft_revision<=intent.draft_revision)throw Error('DRAFT_IDENTITY_CHANGED');
      pendingCopy.current=null;
      if(mounted.current)openDraft(receipt);
    }catch(e){
      if(mounted.current){
        const code=e instanceof Error?e.message:'';
        if(code==='DRAFT_REVISION_CHANGED'||code==='LIBRARY_REVISION_CHANGED'||code==='LIBRARY_DRAFT_TOO_LONG'||code==='LIBRARY_ENTRY_RETIRED')pendingCopy.current=null;
        setFault(code==='LIBRARY_ENTRY_RETIRED'?'La skill fue retirada. Tu borrador se conserva.':
          code==='LIBRARY_REVISION_CHANGED'?'La skill cambió. Revisa la versión vigente antes de usarla.':code);
        setRefresh(v=>v+1);
      }
    }finally{flight.current=false;if(mounted.current)setBusy(false);}
  }
  async function save(op:Operation,target:Target){
    if(flight.current||!online||conflict||(['create','edit','propose'].includes(op)&&(titleIssue||bodyIssue)))return;
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
      if(mounted.current){
        if(op==='retire'||op==='discard'){focusAfterRemoval.current=true;setLoading(true);setNotice(op==='retire'?'Entrada retirada.':'Propuesta descartada.');}
        setForm(null);setSelected(target.id);setRefresh(v=>v+1);
      }
    }catch(e){if(mounted.current){setFault(e instanceof Error?e.message:'Error de lectura');setRefresh(v=>v+1);}}
    finally{flight.current=false;if(mounted.current)setBusy(false);}
  }
  return <section className="office-library"><header><h1>Memoria del proyecto</h1><p>{nameForProject(project)}</p></header>
    <nav className="office-tabs" aria-label="Biblioteca del proyecto">{([['memory','Memoria'],['skill','Skills'],['history','Historial']] as const).map(([id,name])=><button key={id} aria-current={tab===id?'page':undefined} onClick={()=>{setSelected(current?.id??'');setTab(id);setQuery('');setNotice('');}}>{name}</button>)}</nav>
    {fault&&!form&&<p role="alert">No se pudo completar el cambio. <span>{limitExplanation[fault]??fault}</span></p>}
    <div className="library-columns"><section className="library-index"><label><Icon name="search"/><input ref={search} value={query} aria-label="Buscar en la biblioteca" placeholder={tab==='skill'?'Buscar una skill…':'Buscar en la memoria…'} onChange={e=>setQuery(e.target.value)}/></label>
      {filtered.map(r=><button key={r.id} onClick={()=>setSelected(r.id)} aria-pressed={r.id===current?.id}><strong>{r.title}</strong><small>{r.retired?'Retirada':r.proposal?'Propuesta pendiente':'Activa'} · r{r.revision}</small></button>)}
      {tab!=='history'&&<button className="library-add" disabled={!source||!online} onClick={()=>begin('create')}>＋ {tab==='skill'?'Proponer skill':'Añadir nota'}</button>}
      {!source&&tab!=='history'&&<small>Abre una entrega de este proyecto para registrar el origen.</small>}
    </section>
    <section className="library-detail"><p className="visually-hidden" role="status">{loading?'Cargando la biblioteca.':notice||(query?(filtered.length?filtered.length+' coincidencias.':'Sin coincidencias.'):'')}</p>{!current&&loading?<p>Cargando la biblioteca…</p>:!current&&!loaded?<p>{online?'No se pudo leer la biblioteca.':'Núcleo desconectado. La biblioteca volverá a estar disponible al reconectar.'}</p>:!current?<><h2>{query?'Sin coincidencias':tab==='skill'?'Todavía no hay skills':tab==='history'?'Sin revisiones':'Todavía no hay notas'}</h2><p>{query?'Prueba con otro nombre.':'Las entradas se vinculan al hilo y a la entrega de origen.'}</p></>:<>
      <h2>{current.title}</h2><p className="library-meta">{nameForProject(project)} · Revisión {current.revision}</p>
      {tab==='history'?<ol className="version-log">{versions.map(v=><li key={v.revision}><strong>r{v.revision} · {labels[v.operation]}</strong><time dateTime={new Date(v.at*1000).toISOString()}>{new Date(v.at*1000).toLocaleString('es-ES')}</time><span>{v.title}</span><p>{v.proposal??v.body}</p></li>)}</ol>:<>
        {current.body&&<><h3>{current.kind==='skill'?'Instrucción activa':'Nota del proyecto'}</h3>
          <p className={current.proposal?'library-copy replacing':'library-copy'}>{current.body}</p></>}
        {current.proposal&&<><h3>Propuesta pendiente</h3><p className="proposal-copy">{current.proposal}</p>
          <p>Se puede insertar en un encargo cuando la aceptes.</p><div className="arc-actions"><button disabled={busy||!online} onClick={()=>void save('accept',current)}>Aceptar propuesta</button><button disabled={busy||!online} onClick={()=>void save('discard',current)}>Descartar</button></div></>}
        <div className="arc-actions">{current.kind==='skill'&&current.body&&<><button disabled={!online||busy||!copyAvailable} onClick={()=>void insertSkill()}>Usar en un borrador</button>{!copyAvailable&&<small>La copia verificada necesita el núcleo con borradores de sesión.</small>}</>}
          {!current.proposal&&<button disabled={!online||busy} onClick={()=>begin(current.kind==='skill'?'propose':'edit')}>{current.kind==='skill'?'Proponer cambio':'Editar nota'}</button>}
          <button disabled={!online||busy} onClick={()=>begin('retire')}>Retirar</button></div></>}
      <button className="provenance-link" onClick={()=>openSource(current.thread,current.report)}><Icon name="thread"/>Abrir el hilo de origen</button></>}</section></div>
    {form&&<DeskDialog busy={busy} label={form.op==='retire'?'Retirar esta entrada':form.op==='create'?(form.kind==='skill'?'Proponer una skill':'Nueva nota'):form.op==='edit'?'Editar la nota':'Proponer un cambio'} close={()=>{if(!busy){setForm(null);setFault('');}}}>
      <form className="library-form" onSubmit={e=>{e.preventDefault();void save(form.op,form);}}>
        {form.op==='retire'?<p>«{form.title}» quedará disponible en el historial.</p>:<><label>Nombre<input required disabled={busy} aria-invalid={edited.title&&!!titleIssue||undefined} aria-describedby={edited.title&&titleIssue?nameId:undefined} value={title} readOnly={form.op==='propose'} onBlur={()=>setEdited(v=>({...v,title:true}))} onChange={e=>{e.currentTarget.setCustomValidity(invalidText(e.target.value,120));setEdited(v=>({...v,title:true}));setTitle(e.target.value);}}/>{edited.title&&titleIssue&&<small id={nameId}>{titleIssue}</small>}</label>
        <label>{form.kind==='skill'?'Instrucción':'Contenido'}<textarea required disabled={busy} aria-invalid={edited.body&&!!bodyIssue||undefined} aria-describedby={edited.body&&bodyIssue?bodyId:undefined} rows={6} value={body} onBlur={()=>setEdited(v=>({...v,body:true}))} onChange={e=>{e.currentTarget.setCustomValidity(invalidText(e.target.value,1500));setEdited(v=>({...v,body:true}));setBody(e.target.value);}}/>{edited.body&&bodyIssue&&<small id={bodyId}>{bodyIssue}</small>}</label></>}
        {conflict&&<section aria-label="Cambio de versión">
          <p role="alert">{changed?.retired?'Esta entrada fue retirada. Puedes copiar tu texto antes de cerrar.':'La entrada cambió en otra ventana. Tu texto sigue en este formulario.'}</p>
          {changed&&!changed.retired&&<><strong>Revisión {changed.revision} · {changed.title}</strong>
            <p className="library-copy">{changed.proposal??changed.body}</p>
            {form.op!=='create'&&(form.op!=='propose'||!changed.proposal)&&<button type="button" className="provenance-link"
              onClick={()=>{setForm({...changed,op:form.op});setFault('');}}>Revisar mi cambio sobre r{changed.revision}</button>}</>}
        </section>}
        <button className="desk-primary" disabled={busy||!online||conflict||(form.op!=='retire'&&(!!titleIssue||!!bodyIssue))}>{form.op==='retire'?'Confirmar retirada':'Guardar'}</button>
        {busy&&<p role="status">Guardando el cambio…</p>}
        {fault&&!conflict&&<p role="alert">{form.op==='create'&&fault==='LIBRARY_REVISION_CHANGED'?'Ya existe un alta para esta entrada. Revisa el historial antes de editarla.':limitExplanation[fault]??fault}</p>}</form></DeskDialog>}</section>;
}
