import {useEffect,useId,useLayoutEffect,useMemo,useRef,useState} from 'react';
import {request} from './client.ts';
import type {ReactNode} from 'react';
import type {InspectionJob} from './useInspectionJobs.ts';
import {PaneDivider} from '../workspace/PaneDivider.tsx';
import {attachmentApi,consultationQuestion} from './attachments.ts';
import type {ReviewDecision} from './attachments.ts';
import {Icon} from './DeskTools.tsx';
import type {SymbolName} from './DeskTools.tsx';

type Files=ReturnType<typeof attachmentApi>;
import {Bot, TeamDelivery, TeamRail, TeamOverlay, TeamTrail} from '../office/TeamView.tsx';
import type {OfficeSignal} from '../office/TeamView.tsx';
import type {Specialist} from '../office/team.ts';
export type Inspection=Awaited<ReturnType<Files['report']>>;
type FileItem=Awaited<ReturnType<Files['list']>>[number];
type Page=Awaited<ReturnType<Files['view']>>;
type Citation=Inspection['findings'][number]['sources'][number];
type Member=NonNullable<Page['entries']>[number];
function PackageTree({entries,selected,onOpen}:{entries:Member[];selected?:string;onOpen:(path:string,focus:boolean)=>void}){
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
      {leaves.map((entry,i)=><li key={entry.path+i}><button disabled={!entry.readable} title={entry.detail} aria-label={entry.path} aria-current={selected===entry.path?'true':undefined} onClick={e=>onOpen(entry.path,e.detail===0)}><Icon name={kindIcon(entry.kind)}/><strong>{entry.path.slice(prefix.length)}</strong><small>{size(entry.bytes)}</small></button>{!entry.readable&&<small>{entry.detail}</small>}</li>)}</ul>;
  }
  return branch(entries,'');
}
type Target={id:string;page?:number;member?:string;citation?:Citation};
type ThreadView={excluded?:string[];draft:string;expanded:boolean;scroll:number;target?:Target;reportId?:string};
const views=new Map<string,ThreadView>();
const objectiveLimit=2000;
const draftTtl=8*60*60*1000;
type SavedDraft={project:string;thread:string;text:string;expires:number};
function tabDrafts(office:string):SavedDraft[]{
  const key='office-saved-drafts:'+office;
  const raw=sessionStorage.getItem(key);
  if(!raw)return [];
  const records:unknown=JSON.parse(raw);
  if(!Array.isArray(records))return [];
  const current=records.filter((r):r is SavedDraft=>r&&typeof r.project==='string'&&typeof r.thread==='string'&&typeof r.text==='string'&&r.expires>Date.now());
  if(current.length!==records.length)sessionStorage.setItem(key,JSON.stringify(current));
  return current;
}
export function readSavedDraft(office:string,project:string,thread:string){
  try{return tabDrafts(office).find(r=>r.project===project&&r.thread===thread)?.text??'';}catch{return '';}
}
function saveTabDraft(office:string,project:string,thread:string,value:string){
  const rest=tabDrafts(office).filter(r=>r.project!==project||r.thread!==thread);
  if(value){
    if(rest.length>=32)throw Error('DRAFT_CAPACITY');
    rest.push({project,thread,text:value,expires:Date.now()+draftTtl});
  }
  sessionStorage.setItem('office-saved-drafts:'+office,JSON.stringify(rest));
}
const formatIcons:Record<string,SymbolName>={
  pdf:'pdf',zip:'zip',json:'json',html:'json',png:'png',jpeg:'png',gif:'png',webp:'png',bmp:'png',tiff:'png',
  xlsx:'table',ods:'table',pptx:'slide',odp:'slide',wav:'audio',isobmff:'media',identity:'binary',other:'binary',
};
const kindIcon=(kind:string='other'):SymbolName=>formatIcons[kind]??'note';
const size=(n:number)=>n<1024?n+' B':new Intl.NumberFormat('es-ES',{maximumFractionDigits:1}).format(n/1024)+' KiB';
const when=(s:number)=>new Date(s*1000).toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
function fault(e:unknown){
  const code=e instanceof Error?e.message:'ATTACHMENT_READ_FAILED';
  if(code==='HOST_PICKER_FILE_LIMIT')return 'La selección admite hasta ocho archivos. Elige ocho o menos para adjuntarlos.';
  if(code==='HOST_BUSY'||code==='ATTACHMENT_READER_BUSY')return 'El lector está ocupado. Espera a que termine la lectura en curso y vuelve a intentarlo.';
  const message:Record<string,string>={SNAPSHOT_SIZE:'Se admiten archivos de hasta 512 MiB y hasta 1 GiB por selección. Elige menos archivos si se supera el total.',ATTACHMENT_SELECTION_LIMIT:'Elige hasta ocho archivos. Las copias completas de esta selección admiten 24 MiB en total.',DECISION_CHANGED:'Otra ventana cambió la decisión. Se ha solicitado la lectura vigente.',NO_CITED_EXCERPTS:'Esta entrega aún no tiene fragmentos que se puedan autorizar.',EXCERPT_BUDGET:'Los fragmentos superan el espacio disponible para esta consulta.',ATTACHMENT_NOT_FOUND:'El núcleo ya no encuentra esta captura.',HOST_REQUEST_TIMEOUT:'La respuesta está pendiente. Actualiza la lectura antes de repetir la operación.',PROJECT_ROOT_ALREADY_REGISTERED:'La carpeta pertenece a otro proyecto. Abre el hilo de ese proyecto.',PROJECT_ROOT_CHANGED:'Elige archivos de la carpeta de este proyecto.'};
  return (message[code]??'No se pudo completar la lectura local.')+' ('+code+')';
}
function fileCapability(kind:string){return ({pdf:'Páginas y texto',zip:'Inventario del paquete',json:'Estructura y líneas',png:'Vista de imagen',jpeg:'Vista de imagen',html:'Texto y estructura',text:'Texto local',identity:'Identidad y huella',docx:'Texto del documento',xlsx:'Texto de las celdas',pptx:'Texto de diapositivas',wav:'Propiedades de audio',odt:'Texto del documento',ods:'Texto de las celdas',odp:'Texto de diapositivas'} as Record<string,string>)[kind]??'Información del archivo';}
function coordinate(c:Citation){return [c.page?'Pág. '+c.page:'',c.line?'Línea '+c.line:'',c.pointer??''].filter(Boolean).join(' · ');}
function AnswerList({findings,openSource}:{findings:Inspection['findings'];openSource:(source:Citation)=>void}){
  return <ol className="answer-list">{findings.map((finding,i)=>{
    const refs=finding.sources;
    const headingSource=refs.length===1&&refs[0].name===finding.title?refs[0]:null;
    return <li key={i}>
      {headingSource?<button className="inline-link answer-source" onClick={()=>openSource(headingSource)}>
        <strong>{finding.title}</strong>{coordinate(headingSource)&&<small>{coordinate(headingSource)}</small>}
      </button>:<strong>{finding.title}</strong>}
      <p>{finding.detail}</p>
      {!headingSource&&refs.map((c,j)=><button key={j} className="inline-link" onClick={()=>openSource(c)}>{[c.name,coordinate(c)].filter(Boolean).join(' · ')}</button>)}
    </li>;
  })}</ol>;
}
type Props={consumeReturn:()=>void;returnTo:{report?:string;instruction?:string}|null;onReport:(report:Inspection|null)=>void;office:string;session:string;project:string;thread:string;online:boolean;inspector:boolean;showInspector:()=>void;onUpdate:()=>void;onLegacy:()=>void;
  renderConsultation:(reportId:string)=>ReactNode;
  inspectFiles:(project:string,thread:string,ids:string[],objective:string)=>Promise<Inspection>;job?:InspectionJob;onDraft:(value:string)=>void;modelBlocked:boolean;onConsult:(report:Inspection,objective:string,origin:HTMLElement)=>void};
export function ReviewDesk({onReport,returnTo,consumeReturn,office,session,project,thread,online,inspector,showInspector,onUpdate,onLegacy,modelBlocked,onConsult,inspectFiles,job,onDraft,renderConsultation}:Props){
  const files=useMemo(()=>attachmentApi(request),[office,session]);
  const key=JSON.stringify([office,project,thread]);
  const [savedDraft,setSavedDraft]=useState(()=>readSavedDraft(office,project,thread));
  const [memo]=useState(()=>views.get(key)??{draft:savedDraft,expanded:false,scroll:0});
  const [draft,setDraft]=useState(()=>{const merged=[memo.draft,returnTo?.instruction].filter(Boolean).join('\n');return [...merged].length<=objectiveLimit?merged:memo.draft;});
  const draftLength=[...draft].length;
  const overLimit=draftLength>objectiveLimit;
  const [excluded,setExcluded]=useState<string[]>(memo.excluded??[]);
  const inspecting=job?.state==='reading'||job?.state==='stopping';
  const [signal,setSignal]=useState<OfficeSignal|null>(null);
  useEffect(()=>{
    setSignal(null);
    if(!inspecting||!job||!online)return;
    let live=true;
    let timer:ReturnType<typeof setTimeout>;
    async function readSignal(){
      try {
        const item=await request<(OfficeSignal & {objective:string;sources:string[]})|null>('attachments.activity',{project_id:project,thread_id:thread});
        if(live)setSignal(item&&item.objective===job?.objective&&JSON.stringify(item.sources)===JSON.stringify(job?.ids)?item:null);
      } catch { if(live)setSignal(null); }
      if(live)timer=setTimeout(readSignal,450);
    }
    void readSignal();
    return ()=>{live=false;clearTimeout(timer);};
  },[online,inspecting,job?.key,project,thread,session]);
  const [items,setItems]=useState<FileItem[]>([]);
  const [threadReady,setThreadReady]=useState(false);
  const awaitingThread=!office||!session||!threadReady;
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
  const [historyOpen,setHistoryOpen]=useState(false);
  const [report,setReport]=useState<Inspection|null>(null);
  const [specialist,setSpecialist]=useState<{role:Specialist;round?:number;duringInspection?:boolean}|null>(null);
  const awaitingReceipt=specialist?.duringInspection&&job&&(job.state!=='complete'||job.reportId!==report?.id);
  const pendingSheet=awaitingReceipt?{
    objective:job.objective,
    status:job.state==='stopping'?'Parada solicitada.':job.state==='error'?'La lectura terminó sin una nueva entrega.':
      online&&signal&&signal.role===specialist.role?signal.action:'Esperando un recibo de este encargo.',
  }:undefined;
  const [mobileTeam,setMobileTeam]=useState(false);
  const [sourceOrigin,setSourceOrigin]=useState<{role:Specialist;round:number}|null>(null);
  useEffect(()=>{setSourceOrigin(null);},[report?.id]);
  useEffect(()=>{onReport(report);},[onReport,report]);
  const [working,setWorking]=useState('');
  const [problem,setProblem]=useState(''),[viewProblem,setViewProblem]=useState('');
  const [retryPicker,setRetryPicker]=useState(false);
  const [expanded,setExpanded]=useState(memo.expanded);
  const [editingDecision,setEditingDecision]=useState(false);
  useEffect(()=>{if(returnTo){if(returnTo.instruction&&[...[memo.draft,returnTo.instruction].filter(Boolean).join('\n')].length>objectiveLimit)setProblem('La instrucción supera el espacio disponible en el borrador. El texto anterior se conserva.');consumeReturn();}},[consumeReturn,returnTo,memo]);
  const receiptsId=useId();
  const [lastOpened]=useState(()=>{try{return sessionStorage.getItem('opened-report:'+key)??undefined;}catch{return undefined;}});
  const preferredReport=useRef(returnTo?.report??memo.reportId??lastOpened);
  const focusReport=useRef(returnTo?.report);
  const heading=useRef<HTMLHeadingElement>(null);
  const [zoom,setZoom]=useState(1);
  const [revision,setRevision]=useState(0);
  const alive=useRef(false),flight=useRef(false),read=useRef(0),scroll=useRef<HTMLDivElement>(null),inspectorRef=useRef<HTMLElement>(null);
  const desk=useRef<HTMLElement>(null);
  const sourceTitle=useRef<HTMLHeadingElement>(null);
  const inspectorFocus=useRef<{kind:'title'}|{kind:'file';id:string}|{kind:'page';page:number;step:1|-1}|null>(null);
  const selected=items.find(i=>i.id===selection?.id)??report?.attachments.find(i=>i.id===selection?.id);
  const snapshot=useRef<ThreadView>(memo);
  useEffect(()=>{
    if(returnTo?.report){preferredReport.current=returnTo.report;focusReport.current=returnTo.report;setSelection(null);setRevision(r=>r+1);}
  },[returnTo?.report]);
  useLayoutEffect(()=>{
    if(!report)return;
    try{sessionStorage.setItem('opened-report:'+key,report.id);}catch{/* Navigation still works within this window. */}
    if(focusReport.current===report.id){focusReport.current=undefined;heading.current?.focus();heading.current?.scrollIntoView({block:'nearest'});}
  },[report,key]);
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
      const wanted=preferredReport.current??job?.reportId;
      const last=wanted?past.find(p=>p.id===wanted):past[0];
      if(wanted&&!last){setReport(null);setProblem('La entrega elegida ya no aparece en este hilo. Puedes abrir otra desde su historial.');}
      if(last){const result=await files.report(project,thread,last.id);if(current&&read.current===version)setReport(result);}
      if(current&&read.current===version)setThreadReady(true);
    }).catch(e=>{if(current&&version===read.current)setProblem(fault(e));});
    return ()=>{current=false;};
  },[project,thread,session,online,revision,memo,job?.reportId]);
  useLayoutEffect(()=>{if(scroll.current&&report?.id===memo.reportId&&memo.scroll&&document.activeElement!==heading.current)scroll.current.scrollTop=memo.scroll;},[report?.id,memo]);
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
    flight.current=true;read.current++;setWorking(label);setProblem('');setRetryPicker(false);
    try{await work();}catch(e){
      if(alive.current&&!(e instanceof Error&&e.message==='ATTACHMENT_READ_CANCELLED')){
        setProblem(fault(e));setRetryPicker(e instanceof Error&&['HOST_PICKER_FILE_LIMIT','ATTACHMENT_SELECTION_LIMIT'].includes(e.message));
      }
    }finally{if(alive.current){flight.current=false;setWorking('');}}
  }
  useLayoutEffect(()=>{
    const panel=inspectorRef.current, title=sourceTitle.current, pending=inspectorFocus.current;
    if(!inspector){inspectorFocus.current=null;return;}
    if(!pending||!panel||!title)return;
    let target:HTMLElement|null=title;
    if(pending.kind==='file'){
      target=panel.querySelector<HTMLButtonElement>(`[data-capture-id="${CSS.escape(pending.id)}"]`);
    }else if(pending.kind==='page'){
      if(!preview||preview.page!==pending.page)return;
      inspectorFocus.current=null;
      if(document.activeElement!==title)return;
      target=panel.querySelector<HTMLButtonElement>(`[data-page-step="${pending.step}"]:not(:disabled)`)
        ?? panel.querySelector<HTMLButtonElement>('[data-page-step]:not(:disabled)');
    }
    inspectorFocus.current=null;
    (target??title).focus();
  },[inspector,selection,preview]);
  function open(target:Target,focus=false){
    inspectorFocus.current=focus?{kind:'title'}:null;
    showInspector();setSelection(target);
  }
  function returnToFiles(focus:boolean){
    inspectorFocus.current=focus&&selection?{kind:'file',id:selection.id}:null;
    setSelection(null);
  }
  function changePage(step:1|-1,focus:boolean){
    if(!selection||!preview?.page)return;
    const page=preview.page+step;
    inspectorFocus.current=focus?{kind:'page',page,step}:null;
    if(focus)sourceTitle.current?.focus();
    setSelection({...selection,page});
  }
  function pick(){void perform('Esperando la selección de archivos',async()=>{
    const picked=await files.pick(project,thread);
    if(picked.length)onUpdate();
    if(!alive.current)return;
    const all=await files.list(project,thread);
    const past=await files.history(project,thread);
    if(!alive.current)return;
    adoptItems(all);setHistory(past);
    if(picked.length){
      setSelection(null);
      if(!matchMedia('(max-width:680px)').matches)showInspector();
    }
  });}
  const included=items.filter(item=>!excluded.includes(item.id));
  function inspect(){if(!mayInspect)return;void perform(included.length?'Inspeccionando los archivos':'Registrando el encargo',async()=>{
    const before=readSavedDraft(office,project,thread);
    const next=await inspectFiles(project,thread,included.map(i=>i.id),draft.trim());
    if(before&&readSavedDraft(office,project,thread)===before){
      try{saveTabDraft(office,project,thread,'');if(alive.current)setSavedDraft('');}catch{/* The confirmed turn is already durable. */}
    }
    onUpdate();
    if(!alive.current)return;
    if(snapshot.current.draft.trim()===next.objective)onDraft('');
    preferredReport.current=next.id;setReport(next);setSelection(null);setDraft(old=>old.trim()===next.objective?'':old);setEditingDecision(false);setExpanded(false);
    const past=await files.history(project,thread);if(alive.current)setHistory(past);
  });}
  function keepDraft(){
    try{
      const value=draft===savedDraft?'':draft;
      saveTabDraft(office,project,thread,value);
      setSavedDraft(value);setProblem('');
      if(value)sessionStorage.setItem('office-thread:'+office,JSON.stringify([project,thread]));
    }catch(error){
      setProblem(error instanceof Error&&error.message==='DRAFT_CAPACITY'?'Ya hay 32 borradores guardados. Retira uno para guardar este.':'No se pudo guardar el borrador en esta pestaña. El texto sigue en el editor.');
    }
  }
  function reopen(id:string){void perform('Abriendo la entrega guardada',async()=>{
    const next=await files.report(project,thread,id);if(alive.current){preferredReport.current=next.id;focusReport.current=next.id;setReport(next);setSelection(null);setEditingDecision(false);setExpanded(false);}
  });}
  function decide(choice:ReviewDecision['choice']){
    if(!report)return;
    const saved=report;
    void perform('Guardando tu decisión',async()=>{
      try{
        const decision=await files.decide(project,thread,saved.id,choice,saved.decision?.revision??0);
        onUpdate();
        if(alive.current){setReport(current=>current?.id===saved.id?{...current,decision}:current);setEditingDecision(false);}
      }catch(error){if(alive.current)setRevision(r=>r+1);throw error;}
    });
  }
  const result=report?.findings[0];
  const mismatch=report?.findings.find(f=>f.rule==='first_response_hours'&&f.status==='mismatch');
  const hourSources=mismatch?.sources.filter(c=>c.unit==='h'&&typeof c.value==='number')??[];
  const decidedSource=hourSources.find(c=>c.kind===report?.decision?.choice);
  const decisionText=decidedSource?('Plazo elegido: '+decidedSource.value+' h · '+decidedSource.name):
    report?.decision?.choice==='defer'?'Decisión aplazada':'¿Qué plazo debe regir la entrega?';
  const plan=[
    {name:'Comparar el plazo',prompt:'Compara el plazo de primera respuesta.',ready:included.some(i=>i.kind==='pdf')&&included.some(i=>i.kind==='json')},
    {name:'Validar JSON',prompt:'Valida la sintaxis del JSON.',ready:included.some(i=>i.kind==='json')},
    {name:'Inventariar ZIP',prompt:'Muestra el inventario del ZIP.',ready:included.some(i=>i.kind==='zip')},
    {name:'Medir imágenes',prompt:'Comprueba las dimensiones de las imágenes.',ready:included.some(i=>['png','jpeg','gif','webp','bmp','tiff'].includes(i.kind))},
    {name:'Leer los archivos',prompt:'Inspecciona el contenido de los archivos adjuntos.',ready:included.length>0},
    {name:'Contar páginas',prompt:'Cuenta las páginas del PDF.',ready:included.some(i=>i.kind==='pdf')},
  ].filter(p=>p.ready);
  const selectionMatches=!!report&&report.attachments.length===included.length&&included.every(i=>report.attachments.some(a=>a.id===i.id&&a.sha256===i.sha256));
  const unavailable=report?.attachments.filter(a=>a.status&&a.status!=='ok')??[];
  const partial=unavailable.length>0;
  const changed=!!draft.trim()&&draft.trim()!==report?.objective;
  const mayInspect=online&&threadReady&&!working&&!inspecting&&!overLimit&&(included.length>0||!!draft.trim())&&included.length<=8&&(!report||!selectionMatches||changed);
  const availableAction=(!report||changed||!selectionMatches);
  const fileCount=(n:number)=>n===1?'1 archivo':n+' archivos';
  const stepCount=(n:number)=>n===1?'1 paso':n+' pasos';
  const singlePlan=plan.map(item=><button className="plan-option" key={item.name} onClick={()=>{
    const next=draft.trim()?draft+'\n'+item.prompt:item.prompt;
    if([...next].length>objectiveLimit){setProblem('La sugerencia supera los 2.000 caracteres del encargo. Acorta tu texto para añadirla.');return;}
    setDraft(next);onDraft(next);desk.current?.querySelector('textarea')?.focus();
  }}>{item.name}</button>);

  const fileResults=report?.findings.filter(f=>f.rule==='file_content')??[];
  const readable=fileResults.filter(f=>f.status==='observed');
  const textBrief=!!report&&!report.attachments.length&&result?.rule==='text_brief';
  const guidance=!!result&&['greeting','scope','text_brief'].includes(result.rule)&&!report?.team;
  const contentTitle=fileResults.length?(readable.length===fileResults.length?'He revisado '+fileCount(readable.length):'He leído '+readable.length+' de '+fileCount(fileResults.length)):null;
  const contentLead=fileResults.length?(readable.length?readable[0].title+' · '+readable[0].detail:'Solo se pudo registrar la identidad de los archivos seleccionados.'):null;
  const multiple=!!report&&report.findings.length>1;
  const answers=report?.findings??[];
  const pendingAnswers=answers.filter(f=>f.status==='insufficient').length;
  const multipleTitle=contentTitle&&fileResults.length===answers.length?contentTitle:pendingAnswers?'Hay '+pendingAnswers+' '+(pendingAnswers===1?'comprobación pendiente':'comprobaciones pendientes'):
    answers.every(f=>f.rule==='literal')?'Búsqueda en '+fileCount(answers.length):'Resultado de las comprobaciones';
  const anchor=selection?.citation;
  const pageCitation=anchor&&(preview?.kind!=='pdf'||!anchor.page||preview.page===anchor.page)?anchor:undefined;
  const literalCitation=!!pageCitation&&answers.some(f=>f.rule==='literal'&&f.sources.some(c=>c.attachment_id===pageCitation.attachment_id&&c.line===pageCitation.line&&c.quote===pageCitation.quote));
  const question=consultationQuestion(report,selectionMatches,draft);
  const canConsult=!!question&&threadReady&&!overLimit&&!inspecting&&!modelBlocked&&online&&!working;
  const htmlReviewLink=items.some(item=>item.kind==='html')&&<button className="legacy-link" onClick={onLegacy}><Icon name="json"/>Abrir revisión de HTML con roles <Icon name="arrow"/></button>;
  return <section ref={desk} className={'review-desk'+(inspector?' has-inspector':' with-team')+(mobileTeam?' show-team':'')} aria-label="Hilo de revisión">
    {!inspector&&<button className="mobile-team-switch" aria-expanded={mobileTeam} onClick={()=>setMobileTeam(!mobileTeam)}>{mobileTeam?'Volver al Director':'Ver equipo'}</button>}
    <div className="desk-thread">
      <div className="thread-scroll" ref={scroll} onScroll={e=>{snapshot.current.scroll=e.currentTarget.scrollTop;}}>
        <article className="thread-document">
          {report&&history.filter(h=>h.id!==report.id&&h.created_at<report.created_at).slice(0,4).reverse().map(h=><button key={h.id} className="earlier-turn" onClick={()=>reopen(h.id)}><Icon name="thread"/><span>{h.objective||'Inspección anterior'}</span><time>{when(h.created_at)}</time></button>)}
          {report?.objective&&<div className="user-turn"><div><strong>Tú</strong><time>{when(report.created_at)}</time></div><p>{report.objective}</p><small><Icon name="attach"/>{fileCount(report.attachments.length)} en esta entrega</small></div>}
          <div className="director-byline"><Bot role="director"/><strong>Director</strong>{report&&<><span className="source-label">{guidance?'Orientación del Director':'Comprobación local'} · {report.model_calls} llamadas al modelo</span><time>{when(report.completed_at??report.steps.at(-1)?.at??report.created_at)}</time></>}</div>
          <h1 ref={heading} tabIndex={-1}>{multiple?multipleTitle:contentTitle??(report?(result?.status==='mismatch'&&hourSources.length===2?hourSources[0].value+' h en la especificación, '+hourSources[1].value+' h en la entrega':result?.title??(partial?'Archivos con lectura limitada':'Lectura local registrada')):items.length?'¿Qué quieres comprobar?':'¿En qué trabajamos?')}</h1>
          {multiple?<AnswerList findings={answers} openSource={c=>open({id:c.attachment_id,page:c.page,citation:c},true)}/>:
          <p className="desk-lede">{contentLead??(report?(result?.status==='mismatch'?(report.decision?'Puedes revisar la elección del equipo y consultar las dos fuentes.':'Decide qué plazo debe aplicar el equipo. Puedes revisar los dos originales antes de elegir.'):result?.detail??'Abre las fuentes para revisar lo que pudo leerse.'):included.length?fileCount(included.length)+' en la selección. Elige una comprobación o escribe tu pregunta.':'Escribe tu encargo. Puedes añadir archivos cuando necesites que el Director compruebe una fuente.')}</p>}
          {(items.length>0&&(!report||guidance||result?.rule==='scope'))&&<div className="inspection-plan" aria-label="Comprobaciones disponibles">{singlePlan}</div>}
          {selection?.member&&<p className="reading-context"><Icon name="zip"/> Estás revisando {selection.member} en {selected?.name}. <button className="inline-link" onClick={()=>setSelection(null)}>Volver al hallazgo</button></p>}
          {report?.team&&<TeamDelivery report={report}/>}
          {partial&&!fileResults.length&&<section className="evidence-block"><div className="evidence-heading"><Icon name="activity"/><strong>Archivos con lectura limitada</strong></div>{unavailable.map(a=><button className="citation-row" key={a.id} onClick={()=>open({id:a.id},true)}><Icon name={kindIcon(a.kind)}/><span><strong>{a.name}</strong><small>{a.detail}</small></span><Icon name="arrow"/></button>)}</section>}
          {report&&!guidance&&<details className="evidence-drawer" open={report.findings.some(f=>f.status==='mismatch')}><summary>Fuentes y comprobaciones <small>{report.attachments.length} adjuntos</small></summary>
          {report.findings.filter(finding=>finding.sources.length>0||finding!==result).map((finding,i)=><section className="evidence-block" key={finding.rule+i} data-rule={finding.rule}>
            <div className="evidence-heading"><Icon name={finding.status==='mismatch'?'activity':'note'}/><strong>{finding.rule==='first_response_hours'?'Plazo de primera respuesta':finding.title}</strong><small>{finding.status==='mismatch'?'Discrepancia':finding.status==='match'?'Coincidencia':finding.status==='insufficient'?'Evidencia insuficiente':'Regla local'}</small></div>
            {finding!==result&&<p>{finding.detail}</p>}
            {finding.sources.map((c,j)=><button key={c.attachment_id+j} className={'citation-row'+(selection?.citation===c?' chosen':'')} onClick={()=>open({id:c.attachment_id,page:c.page,citation:c},true)}>
              <Icon name={kindIcon(c.kind)}/><span><strong>{typeof c.value==='number'&&c.unit?<b className="source-value">{c.value} {c.unit}</b>:null}{c.name}</strong><small>{c.unit&&typeof c.value==='number'?(c.kind==='pdf'?'Especificación':'Manifiesto'):c.quote||'Abrir la fuente'}</small></span><code>{coordinate(c)}</code><Icon name="arrow"/></button>)}
          </section>)}
          </details>}
          {result?.origin_report&&<button className="inline-link" onClick={()=>reopen(result.origin_report!)}>Abrir la decisión original</button>}
          {mismatch&&report&&<section className="human-decision" aria-label="Decisión del hilo">
            <div><Icon name="note"/><span>Decisión del hilo</span>{report.decision&&<time>{when(report.decision.at)}</time>}</div>
            <h2 aria-live="polite">{decisionText}</h2>
            {(!report.decision||editingDecision)?<div className="decision-options">{hourSources.map(c=><button key={c.attachment_id} disabled={!!working||!online} onClick={()=>decide(c.kind==='pdf'?'pdf':'json')}>Elegir {c.value} h · {c.kind==='pdf'?'PDF':'JSON'}</button>)}<button disabled={!!working||!online} onClick={()=>decide('defer')}>Aplazar</button></div>:<button className="inline-link" onClick={()=>setEditingDecision(true)}>Revisar decisión</button>}
          </section>}
          {report&&<section className="desk-events">
            {report.team&&<TeamTrail team={report.team} onSelect={(role,round)=>setSpecialist({role,round})}/>}
            <button type="button" className="event-disclosure" aria-expanded={expanded} aria-controls={receiptsId} onClick={()=>setExpanded(value=>!value)}>
              <Icon name="activity"/><strong>Actividad de la inspección</strong><small>{stepCount(report.steps.length)} · {report.reservations} intentos</small>
            </button>
            <ol id={receiptsId} aria-label="Registros de la inspección" hidden={!expanded}>{report.steps.map((step,i)=><li key={i}><Icon name={['ok','match','mismatch','observed'].includes(step.status)?'check':'activity'}/><div><strong>{step.action}</strong><p>{step.actor} · {step.detail}</p>{step.attachment_id&&<button className="inline-link" onClick={()=>open({id:step.attachment_id!},true)}>Abrir fuente</button>}</div><time>{when(step.at)}<small>{Math.round(step.duration_ms)} ms</small></time></li>)}</ol>
          </section>}
          {report&&renderConsultation(report.id)}
          {history.length>0&&<details className="desk-events" open={historyOpen} onToggle={e=>setHistoryOpen(e.currentTarget.open)}><summary><Icon name="clock"/>Entregas de este hilo <small>{history.length}</small></summary>{historyOpen&&history.map(h=><button key={h.id} disabled={!!working} className="history-entry" onClick={()=>reopen(h.id)}><span>{h.objective||'Inspección local'}<small>{fileCount(h.attachment_count)} · {h.finding_count} {h.finding_count===1?'comprobación':'comprobaciones'}{h.id===report?.id?' · Abierta':''}</small></span> <time>{new Date(h.created_at*1000).toLocaleString('es-ES')}</time></button>)}</details>}
        </article>
      </div>
      <div className="composer-wrap">
        {online&&!threadReady&&!problem&&<div className="desk-progress" role="status">Recuperando las fuentes y el historial del hilo…</div>}
        {problem&&<div className="desk-fault" role="alert">{problem} <button className="inline-link" disabled={!online||!!working} onClick={()=>{if(retryPicker)pick();else{setProblem('');setRevision(v=>v+1);}}}>{retryPicker?'Elegir archivos':'Actualizar lectura'}</button></div>}
        {inspecting&&<div className="desk-progress" role="status"><Icon name="activity"/>{!job?.ids.length?'Registrando el encargo en este hilo…':signal?signal.action+' · '+signal.finished+'/'+job.ids.length+' fuentes leídas':'Esperando el primer registro de lectura…'}</div>}
        {working&&!inspecting&&<div className="desk-progress" role="status"><Icon name="clock"/>{working}</div>}
        {report&&!selectionMatches?<p className="selection-note" role="status">La selección difiere de la entrega abierta. Envía el encargo con la selección actual antes de consultar al modelo.</p>:textBrief&&changed?<p className="selection-note">Envía el encargo modificado antes de consultarlo con el modelo.</p>:report&&changed&&question?<p className="selection-note">Consulta esta pregunta con las citas de la entrega abierta, o envíala para crear una nueva inspección.</p>:null}
        {job?.state==='error'&&!problem&&<p className={job.error==='ATTACHMENT_READ_CANCELLED'?'selection-note':'desk-fault'} role="status">{job.error==='ATTACHMENT_READ_CANCELLED'?'Lectura detenida por el núcleo. Se conservan el borrador y la selección.':fault(Error(job.error))}</p>}
        <div className="desk-composer"><textarea aria-label="Instrucción para el Director" value={draft} readOnly={awaitingThread} aria-invalid={overLimit||undefined} aria-describedby={draftLength>=1900?'desk-objective-limit':undefined} rows={2}
          placeholder={awaitingThread?'El editor se abrirá cuando se confirme este hilo.':'Escribe al Director…'} onChange={e=>{setDraft(e.target.value);onDraft(e.target.value);}}
          onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'&&!e.nativeEvent.isComposing&&e.nativeEvent.keyCode!==229&&mayInspect){e.preventDefault();inspect();}}}/>
          <div className="composer-actions"><button className="desk-attach" disabled={!online||!threadReady||!!working} onClick={pick}><Icon name="attach"/>Adjuntar archivos</button>
          {report&&<button className="desk-secondary" disabled={!canConsult} onClick={e=>question&&onConsult(report,question,e.currentTarget)}><Icon name="shield"/>Consultar al modelo</button>}
          <button className="desk-primary" title="Enviar al Director · Ctrl+Intro" aria-keyshortcuts="Control+Enter Meta+Enter" disabled={!availableAction||!mayInspect} onClick={inspect}><span aria-hidden="true">↑</span> Enviar · 0 intentos</button></div></div>
        {draftLength>=1900&&<small id="desk-objective-limit">{draftLength} / {objectiveLimit} caracteres{overLimit?' · Acorta el encargo para enviarlo.':''}</small>}
        <div className="desk-caption"><span><Icon name="folder"/>{project}</span>
          {(draft||savedDraft)&&<button type="button" className="inline-link" disabled={overLimit} title="Conservar el texto en esta pestaña hasta 8 horas" onClick={keepDraft}>{savedDraft&&(!draft||draft===savedDraft)?'Retirar borrador guardado':'Guardar borrador en esta pestaña'}</button>}
          <span>{draft?savedDraft===draft?'Borrador guardado':'Borrador en el editor':report?'Entrega guardada':'Encargo local'}</span></div>
      </div>
    </div>
    {!inspector&&<TeamRail review={report?.team} state={job?.state==='reading'||job?.state==='stopping'?job.state:undefined} online={online} signal={signal}
      selected={specialist?.role??null} onSelect={role=>setSpecialist(role?{role,duringInspection:!!inspecting}:null)}/>}
    <TeamOverlay selected={specialist} report={pendingSheet?null:report} pending={pendingSheet} close={()=>setSpecialist(null)} openSource={(c,role,round)=>{setSourceOrigin({role,round});setSpecialist(null);open({id:c.attachment_id,page:c.page,citation:c},true);}}/>
    {inspector&&<PaneDivider kind="inspection" container={desk} controls="desk-file-inspector" label="Ancho del hilo y el inspector"/>}
    {inspector&&<aside id="desk-file-inspector" ref={inspectorRef} tabIndex={-1} className="file-inspector" aria-label="Inspector de archivos">
      {sourceOrigin&&<button className="inline-link" onClick={()=>{setSpecialist(sourceOrigin);setSourceOrigin(null);}}>Volver al especialista · Iteración {sourceOrigin.round}</button>}
      <header><Icon name={selection?kindIcon(selected?.kind??'pdf'):'attach'}/><h2 ref={sourceTitle} tabIndex={-1}>{selection?(selection.member??selected?.name??'Evidencia'):'Adjuntos'}</h2>
        {selection?<button className="inline-link" onClick={e=>returnToFiles(e.detail===0)}>Ver adjuntos</button>:<small>{items.length&&included.length!==items.length?included.length+' de '+fileCount(items.length)+' en la selección':fileCount(items.length)}</small>}</header>
      <div className="inspector-scroll">{!selection?<>
        {items.length>8&&<p className="viewer-note" role="status">{included.length} archivos seleccionados de un máximo de 8. Desmarca uno para sustituirlo.</p>}
        {items.length?<ul className="file-list">{items.map(item=><li key={item.id}><input type="checkbox" aria-label={'Incluir '+item.name} checked={!excluded.includes(item.id)} disabled={!!working||(excluded.includes(item.id)&&included.length>=8)} onChange={e=>setExcluded(old=>e.target.checked?old.filter(id=>id!==item.id):[...old,item.id])}/><button data-capture-id={item.id} onClick={e=>open({id:item.id},e.detail===0)}><span className={'file-glyph '+item.kind}><Icon name={kindIcon(item.kind)}/></span><span><strong>{item.name}</strong><small>{fileCapability(item.kind)}</small></span><code>{size(item.bytes)}</code></button></li>)}</ul>:<div className="empty-files"><Icon name="folder"/><strong>Todavía no hay adjuntos</strong><p>Puedes adjuntar cualquier tipo de archivo.</p></div>}
        {htmlReviewLink}
      </>:<>
        <div className={selection.member&&inventory?.id===selection.id?'package-context has-member':'package-context'}>
        {selection.member&&inventory?.id===selection.id&&<nav aria-label="Árbol del paquete"><details className="member-index"><summary>Índice del paquete · {inventory.entries.length}</summary><PackageTree entries={inventory.entries} selected={selection.member} onOpen={(member,focus)=>open({id:selection.id,member},focus)}/></details></nav>}
        <div className="package-page">{selection.member&&<button className="package-back" onClick={e=>open({id:selection.id},e.detail===0)}>← {selected?.name} · Inventario</button>}
        {viewProblem?<div className="desk-fault" role="alert">{viewProblem} <button onClick={()=>setRevision(v=>v+1)}>Reintentar</button></div>:!preview?<p className="viewer-note" role="status">{online?'Leyendo la captura…':'Reconecta para abrir la fuente.'}</p>:<>
          <div className="viewer-toolbar"><strong>{selection.member??preview.kind.toUpperCase()}</strong>{preview.pages&&<div><button aria-label="Página anterior" data-page-step="-1" disabled={(preview.page??1)<=1} onClick={e=>changePage(-1,e.detail===0)}>‹</button>
          <span>{preview.page} / {preview.pages}</span><button aria-label="Página siguiente" data-page-step="1" disabled={(preview.page??1)>=preview.pages} onClick={e=>changePage(1,e.detail===0)}>›</button></div>}</div>
          {preview.image&&<><div className="image-tools"><button aria-label="Reducir zoom" disabled={zoom<=0.75} onClick={()=>setZoom(z=>z-.25)}>−</button><span>{zoom*100} %</span><button aria-label="Ampliar zoom" disabled={zoom>=3} onClick={()=>setZoom(z=>z+.25)}>＋</button>{preview.width&&<small>{preview.width} × {preview.height}</small>}</div>
            <div className="image-stage"><div style={{width:preview.width&&preview.height&&preview.kind!=='pdf'?'min('+zoom*100+'%, calc((100dvh - 340px) * '+(preview.width/preview.height)*zoom+'))':(zoom*100)+'%'}}><img alt={(preview.kind==='pdf'?'Página '+preview.page+' de ':'')+(selection.member??preview.name)} src={preview.image}/>{pageCitation?.region?.length===4&&pageCitation.page===preview.page&&<mark className="pdf-hit" aria-label="Posición de la cita" style={{left:pageCitation.region[0]*100+'%',top:pageCitation.region[1]*100+'%',width:pageCitation.region[2]*100+'%',height:pageCitation.region[3]*100+'%'}}/>}</div></div></>}
          {preview.entries&&<PackageTree entries={preview.entries} onOpen={(member,focus)=>open({id:selection.id,member},focus)}/>}
          {preview.signature&&<p className="viewer-note">Cabecera del archivo <code>{preview.signature}</code></p>}
          {preview.text&&(preview.kind!=='pdf'||literalCitation)&&<div className="source-text">{preview.text.split(literalCitation?/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/:/\r\n|\r|\n/).map((line,i)=><div className={pageCitation?.line===(preview.text_start_line??1)+i&&(!literalCitation||line.includes(pageCitation?.quote??''))?'line-target':''} key={i}>{(preview.kind==='json'||literalCitation)&&<span>{(preview.text_start_line??1)+i}</span>}<code>{line||' '}</code></div>)}</div>}
          {pageCitation&&<blockquote><strong>{coordinate(pageCitation)}</strong><p>{pageCitation.quote}</p></blockquote>}
          {preview.kind==='pdf'&&preview.text&&!literalCitation&&<details className="viewer-details"><summary>Texto de la página</summary><div className="source-text">{preview.text}</div></details>}
          <p className="viewer-note">{preview.detail}</p>
          {(preview.text_truncated||preview.fields_truncated)&&<p className="viewer-note">La vista muestra un extracto acotado.</p>}
          {preview.fields&&preview.fields.length>0&&<details className="viewer-details"><summary>Campos del JSON</summary>{preview.fields.map((f,i)=><p key={i}><code>{f.pointer}</code> · línea {f.line}</p>)}</details>}
          <details className="viewer-details"><summary>Identidad de la captura</summary>
            {selection.member?<dl className="capture-identities">
              <dt>SHA-256 del archivo del ZIP</dt>
              <dd>{preview.member_sha256?<code>{preview.member_sha256}</code>:'Huella del archivo no disponible'}</dd>
              <dt>SHA-256 del paquete</dt><dd><code>{preview.sha256}</code></dd>
            </dl>:<code>{preview.sha256}</code>}
          </details>
        </>}</div></div>
      </>}</div><footer><Icon name="shield"/>Capturas de sólo lectura</footer>
    </aside>}
  </section>;
}
