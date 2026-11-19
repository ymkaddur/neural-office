import {useEffect,useLayoutEffect,useMemo,useRef,useState} from 'react';
import {request} from './client.ts';
import type {InspectionJob} from './useInspectionJobs.ts';
import {PaneDivider} from '../workspace/PaneDivider.tsx';
import {attachmentApi} from './attachments.ts';
import {Icon} from './DeskTools.tsx';
import type {SymbolName} from './DeskTools.tsx';

type Files=ReturnType<typeof attachmentApi>;
export type Inspection=Awaited<ReturnType<Files['report']>>;
type FileItem=Awaited<ReturnType<Files['list']>>[number];
type Page=Awaited<ReturnType<Files['view']>>;
type Citation=Inspection['findings'][number]['sources'][number];
type Member=NonNullable<Page['entries']>[number];
function PackageTree({entries,selected,onOpen}:{entries:Member[];selected?:string;onOpen:(path:string)=>void}){
  function branch(rows:Member[],prefix:string){
    const directories=new Map<string,Member[]>();
    const leaves:Member[]=[];
    for(const item of rows){
      const relative=item.path.slice(prefix.length);
      const split=relative.indexOf('/');
      if(split<0||split===relative.length-1){leaves.push(item);continue;}
      const folder=relative.slice(0,split+1);
      const children=directories.get(folder)??[];children.push(item);directories.set(folder,children);
    }
    return <ul className="package-list">{[...directories].map(([folder,children])=><li key={'dir:'+folder}><details open><summary><Icon name="folder"/>{folder.slice(0,-1)}</summary>{branch(children,prefix+folder)}</details></li>)}
      {leaves.map((entry,i)=><li key={entry.path+i}><button disabled={!entry.readable} title={entry.detail} aria-label={entry.path} aria-current={selected===entry.path?'true':undefined} onClick={()=>onOpen(entry.path)}><Icon name={kindIcon(entry.kind)}/><strong>{entry.path.slice(prefix.length)}</strong><small>{size(entry.bytes)}</small></button>{!entry.readable&&<small>{entry.detail}</small>}</li>)}</ul>;
  }
  return branch(entries,'');
}
type Target={id:string;page?:number;member?:string;citation?:Citation};
type ThreadView={excluded?:string[];draft:string;expanded:boolean;scroll:number;target?:Target;reportId?:string};
const views=new Map<string,ThreadView>();
const kindIcon=(kind:string='other'):SymbolName=>kind==='zip'?'zip':kind==='png'||kind==='jpeg'?'png':kind==='json'||kind==='html'?'json':'pdf';
const size=(n:number)=>n<1024?n+' B':new Intl.NumberFormat('es-ES',{maximumFractionDigits:1}).format(n/1024)+' KiB';
const when=(s:number)=>new Date(s*1000).toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
function fault(e:unknown){
  const code=e instanceof Error?e.message:'ATTACHMENT_READ_FAILED';
  const message:Record<string,string>={NO_CITED_EXCERPTS:'Esta entrega aún no tiene fragmentos que se puedan autorizar.',EXCERPT_BUDGET:'Los fragmentos superan el espacio disponible para esta consulta.',ATTACHMENT_NOT_FOUND:'El núcleo ya no encuentra esta captura.',HOST_REQUEST_TIMEOUT:'La respuesta está pendiente. Actualiza la lectura antes de repetir la operación.',PROJECT_ROOT_ALREADY_REGISTERED:'La carpeta pertenece a otro proyecto. Abre el hilo de ese proyecto.',PROJECT_ROOT_CHANGED:'Elige archivos de la carpeta de este proyecto.'};
  return (message[code]??'No se pudo completar la lectura local.')+' ('+code+')';
}
function fileCapability(kind:string){return ({pdf:'Páginas y texto',zip:'Inventario del paquete',json:'Estructura y líneas',png:'Vista de imagen',jpeg:'Vista de imagen',html:'Comprobación HTML'} as Record<string,string>)[kind]??'Información del archivo';}
function coordinate(c:Citation){return [c.page?'Pág. '+c.page:'',c.line?'Línea '+c.line:'',c.pointer??''].filter(Boolean).join(' · ');}
type Props={office:string;session:string;project:string;thread:string;online:boolean;inspector:boolean;showInspector:()=>void;onUpdate:()=>void;onLegacy:()=>void;
  inspectFiles:(project:string,thread:string,ids:string[],objective:string)=>Promise<Inspection>;job?:InspectionJob;onDraft:(value:string)=>void;modelBlocked:boolean;onConsult:(report:Inspection,objective:string,origin:HTMLElement)=>void};
export function ReviewDesk({office,session,project,thread,online,inspector,showInspector,onUpdate,onLegacy,modelBlocked,onConsult,inspectFiles,job,onDraft}:Props){
  const files=useMemo(()=>attachmentApi(request),[office,session]);
  const key=JSON.stringify([office,project,thread]);
  const [memo]=useState(()=>views.get(key)??{draft:'',expanded:false,scroll:0});
  const [draft,setDraft]=useState(memo.draft);
  const [excluded,setExcluded]=useState<string[]>(memo.excluded??[]);
  const inspecting=job?.state==='reading'||job?.state==='stopping';
  const [items,setItems]=useState<FileItem[]>([]);
  const knownIds=useRef<string[]>([]);
  function adoptItems(rows:FileItem[]){
    const ordered=[...new Set([...knownIds.current,...rows.map(f=>f.id)])].filter(id=>rows.some(f=>f.id===id));
    knownIds.current=ordered;
    setExcluded(old=>{
      const retained=ordered.filter(id=>!old.includes(id)).slice(0,8);
      return ordered.filter(id=>!retained.includes(id));
    });
    setItems(rows);
  }
  const [selection,setSelection]=useState<Target|null>(memo.target??null);
  const [preview,setPreview]=useState<Page|null>(null);
  const [inventory,setInventory]=useState<{id:string;entries:Member[]}|null>(null);
  const [history,setHistory]=useState<Awaited<ReturnType<typeof files.history>>>([]);
  const [report,setReport]=useState<Inspection|null>(null);
  const [working,setWorking]=useState('');
  const [problem,setProblem]=useState(''),[viewProblem,setViewProblem]=useState('');
  const [expanded,setExpanded]=useState(memo.expanded);
  const [zoom,setZoom]=useState(1);
  const [revision,setRevision]=useState(0);
  const alive=useRef(false),flight=useRef(false),read=useRef(0),scroll=useRef<HTMLDivElement>(null),inspectorRef=useRef<HTMLElement>(null);
  const desk=useRef<HTMLElement>(null);
  const selected=items.find(i=>i.id===selection?.id)??report?.attachments.find(i=>i.id===selection?.id);
  const snapshot=useRef<ThreadView>(memo);
  snapshot.current={...snapshot.current,draft,expanded,excluded,target:selection??undefined,reportId:report?.id??memo.reportId};
  useEffect(()=>{alive.current=true;return ()=>{alive.current=false;const entry=snapshot.current;if(views.size>=128&&!views.has(key)){const old=[...views.keys()].find(k=>!views.get(k)?.draft);if(old)views.delete(old);}views.set(key,entry);};},[key]);
  useEffect(()=>{
    if(!online)return;
    let current=true;
    const version=++read.current;
    void files.list(project,thread).then(async rows=>{
      if(!current||read.current!==version)return;
      const past=await files.history(project,thread);
      if(!current||read.current!==version)return;
      adoptItems(rows);setHistory(past);
      const last=past.find(p=>p.id===(job?.reportId??memo.reportId))??past[0];
      if(last){const result=await files.report(project,thread,last.id);if(current&&read.current===version)setReport(result);}
    }).catch(e=>{if(current&&version===read.current)setProblem(fault(e));});
    return ()=>{current=false;};
  },[project,thread,session,online,revision,memo,job?.reportId]);
  useLayoutEffect(()=>{if(scroll.current&&report&&memo.scroll)scroll.current.scrollTop=memo.scroll;},[report?.id,memo]);
  useEffect(()=>{
    if(preview&&selection?.citation?.line)inspectorRef.current?.querySelector('.line-target')?.scrollIntoView({block:'nearest'});
  },[preview,selection]);
  useEffect(()=>{
    setPreview(null);setViewProblem('');setZoom(1);
    if(!selection||!online||!inspector)return;
    let current=true;
    void files.view(project,thread,selection.id,{page:selection.page??1,...(selection.member?{member:selection.member}:{})})
      .then(value=>{if(current){setPreview(value);if(!selection.member&&value.entries)setInventory({id:selection.id,entries:value.entries});}}).catch(e=>{if(current)setViewProblem(fault(e));});
    return ()=>{current=false;};
  },[selection,online,inspector,session,project,thread,revision]);
  async function perform(label:string,work:()=>Promise<void>){
    if(!online||flight.current)return;
    flight.current=true;read.current++;setWorking(label);setProblem('');
    try{await work();}catch(e){if(alive.current)setProblem(fault(e));}finally{if(alive.current){flight.current=false;setWorking('');}}
  }
  function open(target:Target,focus=false){showInspector();setSelection(target);if(focus)requestAnimationFrame(()=>inspectorRef.current?.focus());}
  function pick(){void perform('Esperando la selección de archivos',async()=>{
    const picked=await files.pick(project,thread);
    if(picked.length)onUpdate();
    if(!alive.current)return;
    const all=await files.list(project,thread);
    const past=await files.history(project,thread);
    if(!alive.current)return;
    adoptItems(all);setHistory(past);if(picked.length){setSelection(null);showInspector();}
  });}
  const included=items.filter(item=>!excluded.includes(item.id));
  function inspect(){void perform('Inspeccionando los archivos',async()=>{
    const next=await inspectFiles(project,thread,included.map(i=>i.id),draft.trim());
    onUpdate();
    if(!alive.current)return;
    setReport(next);setSelection(null);setDraft(old=>old.trim()===next.objective?'':old);setExpanded(false);
    const past=await files.history(project,thread);if(alive.current)setHistory(past);
  });}
  function reopen(id:string){void perform('Abriendo la entrega guardada',async()=>{
    const next=await files.report(project,thread,id);if(alive.current){setReport(next);setSelection(null);setExpanded(false);}
  });}
  const result=report?.findings.find(f=>f.rule==='first_response_hours')??report?.findings[0];
  const selectionMatches=!!report&&report.attachments.length===included.length&&included.every(i=>report.attachments.some(a=>a.id===i.id&&a.sha256===i.sha256));
  const unavailable=report?.attachments.filter(a=>a.status&&a.status!=='ok')??[];
  const partial=unavailable.length>0;
  const mayInspect=online&&!working&&!inspecting&&included.length>0&&included.length<=8;
  const citedCount=report?.findings.reduce((total,f)=>total+f.sources.filter(s=>s.quote).length,0)??0;
  const canConsult=selectionMatches&&!inspecting&&citedCount>0&&citedCount<=8&&!modelBlocked&&online&&!working;
  return <section ref={desk} className={'review-desk'+(inspector?' has-inspector':'')} aria-label="Hilo de revisión">
    <div className="desk-thread">
      <div className="thread-scroll" ref={scroll} onScroll={e=>{snapshot.current.scroll=e.currentTarget.scrollTop;}}>
        <article className="thread-document">
          {report?.objective&&<div className="user-turn"><div><strong>Tú</strong><time>{when(report.created_at)}</time></div><p>{report.objective}</p><small><Icon name="attach"/>{report.attachments.length} adjuntos en esta entrega</small></div>}
          <div className="director-byline"><span><Icon name="mark"/></span><strong>Director</strong>{report&&<time>{when(report.created_at)}</time>}</div>
          <h1>{report?(partial?(unavailable.length===report.attachments.length?'Los archivos requieren revisión':'La inspección tiene lecturas pendientes'):(result?.title??'Inspección terminada')):items.length?'La entrega está preparada':'¿Qué entrega quieres revisar?'}</h1>
          <p className="desk-lede">{report?(result?.detail??'Abre los archivos y los registros de esta inspección.'):items.length?'Puedes inspeccionar los archivos en este equipo y abrir sus fuentes desde la entrega.':'Adjunta los archivos y dime qué quieres comprobar.'}</p>
          {!report&&items.length>0&&<div className="work-rows">{items.map(item=><button key={item.id} onClick={()=>open({id:item.id},true)}><Icon name={kindIcon(item.kind)}/><strong>{item.name}</strong><small>{fileCapability(item.kind)}</small><Icon name="arrow"/></button>)}</div>}
          {partial&&<section className="evidence-block"><div className="evidence-heading"><Icon name="activity"/><strong>Archivos con lectura limitada</strong></div>{unavailable.map(a=><button className="citation-row" key={a.id} onClick={()=>open({id:a.id},true)}><Icon name={kindIcon(a.kind)}/><span><strong>{a.name}</strong><small>{a.detail}</small></span><Icon name="arrow"/></button>)}</section>}
          {report?.findings.map((finding,i)=><section className="evidence-block" key={finding.rule+i}>
            <div className="evidence-heading"><Icon name={finding.status==='mismatch'?'activity':'note'}/><strong>{finding.rule==='first_response_hours'?'Plazo de primera respuesta':finding.title}</strong><small>{finding.status==='mismatch'?'Discrepancia':finding.status==='match'?'Coincidencia':finding.status==='insufficient'?'Evidencia insuficiente':'Regla local'}</small></div>
            {finding!==result&&<p>{finding.detail}</p>}
            {finding.sources.map((c,j)=><button key={c.attachment_id+j} className={'citation-row'+(selection?.citation===c?' chosen':'')} onClick={()=>open({id:c.attachment_id,page:c.page,citation:c},true)}>
              <Icon name={kindIcon(c.kind)}/><span><strong>{c.name}</strong><small>{c.quote}</small></span><code>{coordinate(c)}</code><Icon name="arrow"/></button>)}
          </section>)}
          {report&&<details className="desk-events" open={expanded} onToggle={e=>setExpanded(e.currentTarget.open)}>
            <summary><Icon name="activity"/><strong>Actividad de la inspección</strong><small>{report.steps.length} registros · {report.reservations} intentos</small></summary>
            <ol>{report.steps.map((step,i)=><li key={i}><Icon name={['ok','match','mismatch','observed'].includes(step.status)?'check':'activity'}/><div><strong>{step.action}</strong><p>{step.actor} · {step.detail}</p>{step.attachment_id&&<button className="inline-link" onClick={()=>open({id:step.attachment_id!},true)}>Abrir fuente</button>}</div><time>{when(step.at)}<small>{Math.round(step.duration_ms)} ms</small></time></li>)}</ol>
          </details>}
          {history.length>1&&<details className="desk-events"><summary><Icon name="clock"/>Entregas de este hilo <small>{history.length}</small></summary>{history.map(h=><button key={h.id} disabled={!!working} className="history-entry" onClick={()=>reopen(h.id)}>{h.objective||'Inspección local'} <time>{new Date(h.created_at*1000).toLocaleString('es-ES')}</time></button>)}</details>}
        </article>
      </div>
      <div className="composer-wrap">
        {problem&&<div className="desk-fault" role="alert">{problem} <button className="inline-link" disabled={!online||!!working} onClick={()=>{setProblem('');setRevision(v=>v+1);}}>Actualizar lectura</button></div>}
        {working&&!inspecting&&<div className="desk-progress" role="status"><Icon name="clock"/>{working}</div>}
        {citedCount>8&&selectionMatches?<p className="selection-note" role="status">Esta entrega tiene {citedCount} citas. Una consulta admite hasta ocho. Puedes abrir la revisión HTML con roles desde el inspector.</p>:report&&!selectionMatches?<p className="selection-note" role="status">La selección difiere de la entrega abierta. Vuelve a inspeccionar para consultar esos archivos.</p>:null}
        {job?.state==='error'&&!problem&&<p className="desk-fault" role="status">{job.error==='ATTACHMENT_READ_CANCELLED'?'Lectura detenida por el núcleo.':fault(Error(job.error))}</p>}
        <div className="desk-composer"><textarea aria-label="Instrucción para el Director" value={draft} maxLength={2000} rows={2}
          placeholder={report?'Añade una instrucción para el Director…':'¿Qué quieres revisar en los archivos?'} onChange={e=>{setDraft(e.target.value);onDraft(e.target.value);}}
          onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'&&!e.nativeEvent.isComposing&&e.nativeEvent.keyCode!==229&&mayInspect){e.preventDefault();inspect();}}}/>
          <div className="composer-actions"><button className="desk-attach" disabled={!online||!!working} onClick={pick}><Icon name="attach"/>Adjuntar archivos</button>
          <button className="desk-secondary" disabled={!canConsult} onClick={e=>report&&onConsult(report,draft.trim()||report.objective||'Revisa las fuentes citadas de la entrega.',e.currentTarget)}><Icon name="shield"/>Consultar al modelo</button>
          <button className="desk-primary" disabled={!mayInspect} onClick={inspect}><Icon name="check"/>Inspeccionar · 0 intentos</button></div></div>
        <div className="desk-caption"><span><Icon name="folder"/>{project}</span><span>Lectura local</span></div>
      </div>
    </div>
    {inspector&&<PaneDivider kind="inspection" container={desk} controls="desk-file-inspector" label="Ancho del hilo y el inspector"/>}
    {inspector&&<aside id="desk-file-inspector" ref={inspectorRef} tabIndex={-1} className="file-inspector" aria-label="Inspector de archivos">
      <header><Icon name={selection?kindIcon(selected?.kind??'pdf'):'attach'}/><h2>{selection?(selected?.name??'Evidencia'):'Adjuntos'}</h2>
        {selection?<button className="inline-link" onClick={()=>setSelection(null)}>Ver adjuntos</button>:<small>{items.length} archivos</small>}</header>
      <div className="inspector-scroll">{!selection?<>
        {items.length>8&&<p className="viewer-note" role="status">{included.length} archivos seleccionados de un máximo de 8. Desmarca uno para sustituirlo.</p>}
        {items.length?<ul className="file-list">{items.map(item=><li key={item.id}><input type="checkbox" aria-label={'Incluir '+item.name} checked={!excluded.includes(item.id)} disabled={!!working||(excluded.includes(item.id)&&included.length>=8)} onChange={e=>setExcluded(old=>e.target.checked?old.filter(id=>id!==item.id):[...old,item.id])}/><button onClick={()=>open({id:item.id})}><span className={'file-glyph '+item.kind}><Icon name={kindIcon(item.kind)}/></span><span><strong>{item.name}</strong><small>{fileCapability(item.kind)}</small></span><code>{size(item.bytes)}</code></button></li>)}</ul>:<div className="empty-files"><Icon name="folder"/><strong>Todavía no hay adjuntos</strong><p>PDF, ZIP, JSON, imágenes y HTML</p></div>}
        <button className="legacy-link" onClick={onLegacy}><Icon name="json"/>Abrir revisión de HTML con roles <Icon name="arrow"/></button>
      </>:<>
        <div className={selection.member&&inventory?.id===selection.id?'package-context has-member':'package-context'}>
        {selection.member&&inventory?.id===selection.id&&<nav aria-label="Árbol del paquete"><PackageTree entries={inventory.entries} selected={selection.member} onOpen={member=>open({id:selection.id,member})}/></nav>}
        <div className="package-page">{selection.member&&<button className="package-back" onClick={()=>open({id:selection.id})}>← Inventario del paquete</button>}
        {viewProblem?<div className="desk-fault" role="alert">{viewProblem} <button onClick={()=>setRevision(v=>v+1)}>Reintentar</button></div>:!preview?<p className="viewer-note" role="status">{online?'Leyendo la captura…':'Reconecta para abrir la fuente.'}</p>:<>
          <div className="viewer-toolbar"><strong>{selection.member??preview.kind.toUpperCase()}</strong>{preview.pages&&<div><button aria-label="Página anterior" disabled={(preview.page??1)<=1} onClick={()=>open({...selection,citation:undefined,page:(preview.page??1)-1})}>‹</button>
          <span>{preview.page} / {preview.pages}</span><button aria-label="Página siguiente" disabled={(preview.page??1)>=preview.pages} onClick={()=>open({...selection,citation:undefined,page:(preview.page??1)+1})}>›</button></div>}</div>
          {preview.image&&<><div className="image-tools"><button aria-label="Reducir zoom" disabled={zoom<=0.75} onClick={()=>setZoom(z=>z-.25)}>−</button><span>{zoom*100} %</span><button aria-label="Ampliar zoom" disabled={zoom>=3} onClick={()=>setZoom(z=>z+.25)}>＋</button>{preview.width&&<small>{preview.width} × {preview.height}</small>}</div>
            <div className="image-stage"><div style={{width:(zoom*100)+'%'}}><img alt={preview.kind==='pdf'?'Página '+preview.page+' de '+preview.name:preview.name} src={preview.image}/>{selection.citation?.region?.length===4&&selection.citation.page===preview.page&&<mark className="pdf-hit" aria-label="Posición de la cita" style={{left:selection.citation.region[0]*100+'%',top:selection.citation.region[1]*100+'%',width:selection.citation.region[2]*100+'%',height:selection.citation.region[3]*100+'%'}}/>}</div></div></>}
          {preview.entries&&<PackageTree entries={preview.entries} onOpen={member=>open({id:selection.id,member})}/>}
          {preview.text&&preview.kind!=='pdf'&&<div className="source-text">{preview.text.split(/\r\n|\r|\n/).map((line,i)=><div className={selection.citation?.line===(preview.text_start_line??1)+i?'line-target':''} key={i}>{preview.kind==='json'&&<span>{(preview.text_start_line??1)+i}</span>}<code>{line||' '}</code></div>)}</div>}
          {selection.citation&&<blockquote><strong>{coordinate(selection.citation)}</strong><p>{selection.citation.quote}</p></blockquote>}
          {preview.kind==='pdf'&&preview.text&&<details className="viewer-details"><summary>Texto de la página</summary><div className="source-text">{preview.text}</div></details>}
          <p className="viewer-note">{preview.detail}</p>
          {(preview.text_truncated||preview.fields_truncated)&&<p className="viewer-note">La vista muestra un extracto acotado.</p>}
          {preview.fields&&preview.fields.length>0&&<details className="viewer-details"><summary>Campos del JSON</summary>{preview.fields.map((f,i)=><p key={i}><code>{f.pointer}</code> · línea {f.line}</p>)}</details>}
          <details className="viewer-details"><summary>Identidad de la captura</summary><code>{preview.sha256}</code></details>
        </>}</div></div>
      </>}</div><footer><Icon name="shield"/>Capturas de sólo lectura</footer>
    </aside>}
  </section>;
}
