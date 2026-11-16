import {useEffect,useRef,useState} from 'react';
import {PaneDivider} from '../workspace/PaneDivider.tsx';
import {hasNativeHost,readReport,request} from './client.ts';
import type {Report} from './client.ts';
import {acceptAttempt,approvalMatches,mergeEvents,pendingKey,readPending,stateLabels,terminal,validateSnapshot,writePending} from './model.ts';
import type {Approval,Attempt,EventWindow,Model,Pending,Snapshot,Source} from './model.ts';
import './connected.css';

type LoadedReport=Awaited<ReturnType<typeof readReport>>;
type Description={session_id:string;inference:string;office_id:string};
let initialFlight:Promise<{description:Description;snapshot:Snapshot}>|null=null;
function initialData() {
  if(!initialFlight) initialFlight=Promise.all([
    request<Description>('describe'),request<Snapshot>('snapshot.get',{project_after:0,attempt_after:0,limit:100}),
  ]).then(([description,snapshot])=>({description,snapshot:validateSnapshot(snapshot)})).finally(()=>{initialFlight=null;});
  return initialFlight;
}
const makeProject=()=>`oficina-${crypto.randomUUID().slice(0,8)}`;
const short=(id:string)=>id.length>18?`${id.slice(0,9)}…${id.slice(-5)}`:id;
const roles:Record<string,string>={director:'Director',skeptic:'Revisor',integrator:'Integrador',planner:'Planificador',researcher:'Investigador',implementer:'Implementador',verifier:'Verificador'};
const errors:Record<string,string>={
  NATIVE_HOST_REQUIRED:'Abre la aplicación de escritorio para trabajar con tus archivos y modelos.',
  HOST_CONNECTION_UNAVAILABLE:'La conexión con el núcleo no está disponible. Comprueba el estado antes de volver a encargar trabajo.',
  HOST_REQUEST_TIMEOUT:'La respuesta está tardando. El encargo podría haberse registrado; consulta su estado, sin reenviarlo.',
  MODEL_METADATA_UNAVAILABLE:'Ollama no responde. Ábrelo y comprueba que tienes un modelo local descargado; después actualiza la lista.',
  MODEL_CATALOG_BUSY:'El núcleo está ocupado. La selección de modelo estará disponible al terminar.',
  SOURCE_GRANT_INVALID_OR_EXPIRED:'La selección temporal ha caducado. Vuelve a elegir el archivo para revisar sus bytes actuales.',
  APPROVAL_INVALID_OR_EXPIRED:'La aprobación ha caducado. Revisa de nuevo el encargo antes de ejecutarlo.',
  APPROVAL_CHANGED:'El encargo cambió o la aprobación caducó. Revisa otra vez su alcance.',
  DESKTOP_REVISION_CHANGED:'El estado del núcleo cambió. Actualiza y vuelve a revisar el encargo.',
  GLOBAL_INFERENCE_BUSY:'Ya hay un trabajo en curso. Espera a que termine o solicita su parada.',
  OFFICE_RUNNER_STILL_ACTIVE:'El controlador sigue activo. Solicita la parada y espera su confirmación antes de recuperar.',
  PROJECT_ROOT_ALREADY_REGISTERED:'Esa carpeta pertenece a otro proyecto. Selecciona su proyecto existente; no se reinicia el presupuesto.',
  PROJECT_ROOT_CHANGED:'Este proyecto pertenece a otra carpeta. Selecciona una fuente de la misma carpeta o crea otro proyecto.',
  PENDING_IDENTITY_NOT_SAVED:'No se pudo conservar la identidad del encargo. No se ha enviado.',
  PENDING_IDENTITY_INVALID:'La identidad pendiente guardada no es válida. No se enviará otro encargo automáticamente.',
};
function errorInfo(error:unknown) {
  const raw=error instanceof Error?error.message:'DESKTOP_OPERATION_FAILED';
  const code=/^[A-Z][A-Z0-9_]{0,95}$/.test(raw)?raw:'DESKTOP_OPERATION_FAILED';
  return {code,message:errors[code]||'No se pudo completar esta operación. No reenviamos el encargo automáticamente: comprueba su estado antes de continuar.'};
}
function DirectorMark(){return <span className="director-mark" aria-hidden="true"><span/><span/><span/></span>;}

export function ConnectedWorkspace() {
  const native=hasNativeHost();
  const [session,setSession]=useState('');
  const [officeId,setOfficeId]=useState('');
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [models,setModels]=useState<Model[]>([]);
  const [modelDigest,setModelDigest]=useState('');
  const [projectId,setProjectId]=useState(makeProject);
  const [source,setSource]=useState<Source|null>(null);
  const [objective,setObjective]=useState('');
  const [roleCount,setRoleCount]=useState(1);
  const [approval,setApproval]=useState<{value:Approval;expiresAt:number}|null>(null);
  const [attempt,setAttempt]=useState<Attempt|null>(null);
  const [pending,setPending]=useState<Pending|null>(null);
  const [pendingMissing,setPendingMissing]=useState(false);
  const [storageBlocked,setStorageBlocked]=useState(false);
  const [report,setReport]=useState<LoadedReport|null>(null);
  const [doing,setDoing]=useState('');
  const [problem,setProblem]=useState<ReturnType<typeof errorInfo>|null>(null);
  const [notice,setNotice]=useState('');
  const [events,setEvents]=useState<EventWindow>({session_id:'',cursor:0,events:[]});
  const [dark,setDark]=useState(()=>{try{return localStorage.getItem('neural-office.v55.theme')!=='light';}catch{return true;}});
  const [navOpen,setNavOpen]=useState(false);
  const [resultTab,setResultTab]=useState<'report'|'evidence'>('report');
  const shell=useRef<HTMLDivElement>(null),surface=useRef<HTMLElement>(null),approvalDialog=useRef<HTMLDialogElement>(null);
  const mounted=useRef(false),operation=useRef(false),generation=useRef(0),eventsRef=useRef(events),sessionRef=useRef(''),officeRef=useRef('');
  const currentAttempt=useRef<Attempt|null>(null),previousFocus=useRef<HTMLElement|null>(null),navOpener=useRef<HTMLElement|null>(null);
  const active=attempt!==null&&!terminal(attempt.state);
  const project=snapshot?.projects.find(p=>p.id===projectId);
  const busy=active||!!pending||storageBlocked;
  const selectedModel=models.find(m=>m.model_digest===modelDigest);
  const status=attempt?stateLabels[attempt.state]:pending?'Comprobando un encargo anterior':session?'Listo para un encargo':'Conectando con tu oficina';
  const epoch=()=>generation.current;
  function noteError(error:unknown){if(mounted.current)setProblem(errorInfo(error));}
  function invalidate(){generation.current++;setApproval(null);setProblem(null);setNotice('');}
  function putAttempt(next:Attempt) {
    const accepted=acceptAttempt(currentAttempt.current,next);
    if(currentAttempt.current?.id!==accepted.id)setReport(null);
    currentAttempt.current=accepted;setAttempt(accepted);
  }
  function putEvents(value:EventWindow){eventsRef.current=value;setEvents(value);}
  async function refreshSnapshot() {
    const next=validateSnapshot(await request<Snapshot>('snapshot.get',{project_after:0,attempt_after:0,limit:100}));
    if(!mounted.current) return next;
    if(sessionRef.current&&sessionRef.current!==next.session_id) {invalidate();setSource(null);setModels([]);setModelDigest('');}
    sessionRef.current=next.session_id;officeRef.current=next.office_id;setSession(next.session_id);setOfficeId(next.office_id);setSnapshot(next);
    return next;
  }
  async function reconcile(saved:Pending) {
    if(saved.office_id!==officeRef.current)throw Error('PENDING_OFFICE_CHANGED');
    const result=await request<{found:boolean;attempt:Attempt|null}>('attempt.lookup',{project_id:saved.project_id,idempotency_key:saved.idempotency_key});
    if(!mounted.current) return;
    setProjectId(saved.project_id);
    if(result.found&&result.attempt) {if(result.attempt.project_id!==saved.project_id||result.attempt.request_key!==saved.idempotency_key)throw Error('LOOKUP_IDENTITY_CHANGED');putAttempt(result.attempt);setPendingMissing(false);setNotice('Encargo recuperado por su identidad original. No se ha vuelto a ejecutar.');}
    else if(result.found===false&&result.attempt===null) {setPendingMissing(true);setNotice('El núcleo no tiene una reserva para esta identidad. No se ha reenviado nada.');}
    else throw Error('LOOKUP_CONTRACT');
  }
  async function loadModels() {
    const result=await request<{models:Model[];session_id:string}>('models.list');
    if(!Array.isArray(result.models)||result.models.length>64||result.models.some(m=>typeof m.model!=='string'||!/^[a-f0-9]{64}$/.test(m.model_digest))) throw Error('MODEL_CONTRACT');
    if(!mounted.current||result.session_id!==sessionRef.current) return;
    setModels(result.models);setModelDigest(old=>result.models.some(m=>m.model_digest===old)?old:(result.models[0]?.model_digest||''));
  }
  async function act(label:string,work:()=>Promise<void>) {
    if(operation.current) return;
    operation.current=true;setDoing(label);setProblem(null);
    try {await work();}catch(error){noteError(error);}finally{operation.current=false;if(mounted.current)setDoing('');}
  }
  useEffect(()=>{
    mounted.current=true;
    if(!native) return ()=>{mounted.current=false;};
    let live=true;
    void initialData().then(async({description,snapshot:first})=>{
      if(!live) return;
      if(description.session_id!==first.session_id||description.office_id!==first.office_id) throw Error('SESSION_CHANGED');
      sessionRef.current=description.session_id;officeRef.current=description.office_id;setSession(description.session_id);setOfficeId(description.office_id);setSnapshot(first);
      putEvents({session_id:description.session_id,cursor:first.cursor,events:[]});
      let saved:Pending|null=null;
      try{saved=readPending(localStorage,description.office_id);setPending(saved);}catch(error){setStorageBlocked(true);throw error;}
      if(saved) {
        const result=await request<{found:boolean;attempt:Attempt|null}>('attempt.lookup',{project_id:saved.project_id,idempotency_key:saved.idempotency_key});
        if(!live)return;
        setProjectId(saved.project_id);
        if(result.found&&result.attempt){if(result.attempt.project_id!==saved.project_id||result.attempt.request_key!==saved.idempotency_key)throw Error('LOOKUP_IDENTITY_CHANGED');putAttempt(result.attempt);setNotice('Encargo recuperado por su identidad original. No se ha vuelto a ejecutar.');}
        else if(result.found===false&&result.attempt===null){setPendingMissing(true);setNotice('El núcleo no tiene una reserva para esta identidad. No se ha reenviado nada.');}
        else throw Error('LOOKUP_CONTRACT');
      }
      else {
        const activeProject=first.projects.find(p=>p.active)||first.projects[0];
        if(activeProject)setProjectId(activeProject.id);
        const unresolved=first.attempts.find(a=>!terminal(a.state));
        if(unresolved){setProjectId(unresolved.project_id);putAttempt(await request<Attempt>('attempt.get',{attempt_id:unresolved.id}));}
      }
      if(live) await loadModels();
    }).catch(error=>{if(live)noteError(error);});
    return ()=>{live=false;mounted.current=false;generation.current++;};
  },[native]);
  useEffect(()=>{try{localStorage.setItem('neural-office.v55.theme',dark?'dark':'light');}catch{}},[dark]);
  useEffect(()=>{
    const dialog=approvalDialog.current;
    if(approval&&!dialog?.open){previousFocus.current=document.activeElement as HTMLElement;dialog?.showModal();}
    if(!approval&&dialog?.open){dialog.close();previousFocus.current?.focus();}
  },[approval]);
  useEffect(()=>{
    if(!attempt||!terminal(attempt.state)||!pending||attempt.request_key!==pending.idempotency_key||attempt.project_id!==pending.project_id)return;
    try{localStorage.removeItem(pendingKey(pending.office_id));setPending(null);setPendingMissing(false);}catch{setStorageBlocked(true);}
  },[attempt,pending]);
  useEffect(()=>{
    if(!active||!attempt)return;
    const id=attempt.id;let cancelled=false,timer:ReturnType<typeof setTimeout>|undefined,failures=0;
    const tick=async()=>{
      try{
        const next=await request<Attempt>('attempt.get',{attempt_id:id});
        if(cancelled||!mounted.current||currentAttempt.current?.id!==id)return;
        putAttempt(next);
        const batch=await request<Parameters<typeof mergeEvents>[1]>('events.read',{after:eventsRef.current.cursor,limit:100});
        if(cancelled||!mounted.current)return;
        const result=mergeEvents(eventsRef.current,batch);
        if(result.resync){const fresh=await refreshSnapshot();if(!cancelled)putEvents({session_id:fresh.session_id,cursor:fresh.cursor,events:[]});}
        else putEvents(result.window);
        if(terminal(next.state)){await refreshSnapshot();return;}
        failures=0;
      }catch(error){if(!cancelled){failures++;noteError(error);}}
      if(!cancelled)timer=setTimeout(tick,Math.min(10000,2000*(failures+1)));
    };
    timer=setTimeout(tick,250);
    return()=>{cancelled=true;if(timer)clearTimeout(timer);};
  },[active,attempt?.id]);
  useEffect(()=>{
    setReport(null);
    if(!attempt?.report_available)return;
    let live=true;const id=attempt.id;
    void readReport(request,id,()=>live).then(result=>{if(live){if(result.report.source_sha256!==attempt.source_sha256)throw Error('REPORT_SOURCE_CHANGED');setReport(result);setResultTab('report');}}).catch(error=>{if(live)noteError(error);});
    return()=>{live=false;};
  },[attempt?.id,attempt?.report_available]);
  useEffect(()=>{
    const media=matchMedia('(max-width:850px)');const onChange=()=>{if(!media.matches)setNavOpen(false);};
    media.addEventListener('change',onChange);return()=>media.removeEventListener('change',onChange);
  },[]);
  useEffect(()=>{
    if(!navOpen)return;
    navOpener.current=document.activeElement as HTMLElement;
    const elements=()=>Array.from(document.querySelectorAll<HTMLButtonElement>('.connected-nav button:not(:disabled)')).filter(e=>e.getClientRects().length>0);
    elements()[0]?.focus();
    const onKey=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){event.preventDefault();setNavOpen(false);}
      if(event.key==='Tab'){
        const all=elements(),first=all[0],last=all.at(-1);
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
      }
    };
    document.addEventListener('keydown',onKey);
    return()=>{document.removeEventListener('keydown',onKey);if(navOpener.current?.getClientRects().length)navOpener.current.focus();else document.getElementById('connected-main')?.focus();};
  },[navOpen]);
  async function pickSource() {
    const expected=epoch();
    const picked=await request<Source|null>('source.pick',{project_id:projectId});
    if(!mounted.current||expected!==epoch()||picked===null)return;
    if(picked.session_id!==session||picked.project_id!==projectId||typeof picked.filename!=='string'||!/^[a-f0-9]{64}$/.test(picked.sha256))throw Error('SOURCE_CONTRACT');
    invalidate();setSource(picked);await refreshSnapshot();
  }
  async function prepare() {
    if(!source||!selectedModel||objective.trim().length<12||busy)return;
    const expected=epoch();
    const result=await request<Approval>('attempt.preview',{project_id:projectId,entry_token:source.entry_token,model_digest:modelDigest,roles:roleCount,objective:objective.trim()});
    if(!mounted.current||expected!==epoch())return;
    const expiresAt=performance.now()+result.expires_in_seconds*1000;
    if(!approvalMatches(result,session,source,objective,modelDigest,roleCount,expiresAt,performance.now()))throw Error('APPROVAL_CHANGED');
    setApproval({value:result,expiresAt});
  }
  async function start() {
    const reviewed=approval;
    if(!reviewed||!approvalMatches(reviewed.value,session,source,objective,modelDigest,roleCount,reviewed.expiresAt,performance.now())){setApproval(null);throw Error('APPROVAL_CHANGED');}
    const identity={office_id:officeId,project_id:projectId,idempotency_key:crypto.randomUUID()};
    try{writePending(localStorage,identity);}catch{setStorageBlocked(true);throw Error('PENDING_IDENTITY_NOT_SAVED');}
    setPending(identity);setPendingMissing(false);setApproval(null);
    // Identity is durable before send. Any ambiguous failure remains reconcilable.
    const next=await request<Attempt>('attempt.start',{approval_token:reviewed.value.approval_token,idempotency_key:identity.idempotency_key,expected_revision:reviewed.value.expected_revision});
    if(!mounted.current)return;
    putAttempt(next);setSource(null);setObjective('');await refreshSnapshot();
  }
  function newTask(newProject=false) {
    if(busy||operation.current)return;
    invalidate();setSource(null);setObjective('');setReport(null);setAttempt(null);currentAttempt.current=null;
    if(newProject)setProjectId(makeProject());
    setNavOpen(false);requestAnimationFrame(()=>document.getElementById('connected-objective')?.focus());
  }
  function chooseProject(id:string) {
    if(busy||operation.current)return;
    newTask();setProjectId(id);
  }
  async function chooseAttempt(item:Attempt) {
    invalidate();const expected=epoch();
    const next=await request<Attempt>('attempt.get',{attempt_id:item.id});
    if(!mounted.current||expected!==epoch())return;
    setSource(null);setProjectId(next.project_id);setNavOpen(false);putAttempt(next);
  }
  function tabKey(event:{key:string;preventDefault:()=>void}) {
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();
    const next=event.key==='Home'?'report':event.key==='End'?'evidence':resultTab==='report'?'evidence':'report';
    setResultTab(next);requestAnimationFrame(()=>document.getElementById(`tab-${next}`)?.focus());
  }
  async function refreshAll() {
    const fresh=await refreshSnapshot();
    if(attempt)putAttempt(await request<Attempt>('attempt.get',{attempt_id:attempt.id}));
    if(pending)await reconcile(pending);
    putEvents({session_id:fresh.session_id,cursor:fresh.cursor,events:[]});
  }
  async function nextHistoryPage() {
    if(!snapshot)return;
    const next=validateSnapshot(await request<Snapshot>('snapshot.get',{...snapshot.next,limit:100}));
    if(next.revision!==snapshot.revision){await refreshSnapshot();setNotice('El historial cambió. Se ha actualizado la primera página.');return;}
    setSnapshot(next);setNotice('Página siguiente del historial. Se conservan sólo cien entradas por página.');
  }

  if(!native)return <main className={`v541 connected offline ${dark?'theme-dark':''}`}>
    <div className="offline-wordmark"><DirectorMark/><strong>Neural Office</strong><span>V5.5</span></div>
    <section className="offline-content"><span className="eyebrow">Tu oficina, en tu equipo</span><h1>El trabajo real vive<br/>en el escritorio.</h1><p>Esta pestaña permite revisar la interfaz. Para elegir un archivo, usar tu modelo local y conservar el encargo, abre la aplicación de Neural Office.</p><a className="solid-button" href="?preview=1&screen=ready">Explorar las cinco pantallas de ejemplo <span aria-hidden="true">→</span></a><p className="offline-note">Los ejemplos son estáticos. No ejecutan modelos ni consumen intentos.</p></section>
    <footer>Software gratuito · Tus modelos locales · Apoyo voluntario</footer>
  </main>;

  return <div className={`v541 connected ${dark?'theme-dark':''}`}>
    <div ref={shell} className={`office-shell connected-shell ${navOpen?'nav-open':''}`}>
      <nav className="office-nav connected-nav" aria-label="Proyectos y encargos">
        <div className="wordmark"><DirectorMark/><strong>Neural Office</strong><span className="version-tag">5.5</span></div>
        <button className="connected-close-nav" onClick={()=>setNavOpen(false)}>Cerrar proyectos ×</button>
        <button className="new-task" disabled={busy||!!doing} onClick={()=>newTask()}><span aria-hidden="true">＋</span> Nuevo encargo</button>
        <div className="connected-nav-heading">Proyectos <button aria-label="Crear otro proyecto" title="Crear otro proyecto" disabled={busy||!!doing} onClick={()=>newTask(true)}>＋</button></div>
        <div className="connected-projects">{snapshot?.projects.map(p=><button key={p.id} className={p.id===projectId?'selected':''} disabled={busy||!!doing} onClick={()=>chooseProject(p.id)} title={p.id}><span>{short(p.id)}</span><small>{p.attempts_consumed}/3</small></button>)}{!snapshot?.projects.some(p=>p.id===projectId)&&<div className="connected-new-project"><span>Proyecto nuevo</span><small>Se creará al elegir la fuente</small></div>}</div>
        <div className="connected-nav-heading">Encargos guardados</div>
        <div className="connected-history">{snapshot?.attempts.filter(a=>a.project_id===projectId).map(a=><button key={a.id} className={a.id===attempt?.id?'selected':''} disabled={active||!!doing||!!pending} onClick={()=>void act('Abriendo encargo',()=>chooseAttempt(a))}><span className={`history-dot ${terminal(a.state)?'finished':''}`}/><span><strong>{a.objective}</strong><small>{stateLabels[a.state]} · intento {a.ordinal}</small></span></button>)}{!snapshot?.attempts.some(a=>a.project_id===projectId)&&<p className="history-empty">Aquí quedarán las entregas de este proyecto.</p>}</div>
        {(snapshot?.has_more.projects||snapshot?.has_more.attempts)&&<button className="nav-secondary" disabled={!!doing} onClick={()=>void act('Cargando historial',nextHistoryPage)}>Siguiente página del historial →</button>}
        <div className="nav-bottom"><div className="local-engine"><span className={`connected-indicator ${session?'online':''}`}/><div><strong>{session?'Núcleo local conectado':'Conexión pendiente'}</strong><small>Una inferencia a la vez<br/>CPU · contexto 8K</small></div></div><div className="nav-footer"><span>Registro local del encargo</span><button aria-label={dark?'Activar tema claro':'Activar tema oscuro'} onClick={()=>setDark(!dark)}>{dark?'☼':'◐'}</button></div></div>
      </nav>
      <PaneDivider kind="navigation" container={shell} controls="connected-main" label="Ancho de navegación"/>
      {navOpen&&<button className="connected-nav-backdrop" aria-label="Cerrar navegación" onClick={()=>setNavOpen(false)}/>}
      <main id="connected-main" className="office-workspace" tabIndex={-1} inert={navOpen||undefined}>
        <header className="workspace-header connected-header"><div className="breadcrumbs"><button className="connected-menu" aria-expanded={navOpen} aria-label="Mostrar proyectos" onClick={()=>setNavOpen(!navOpen)}>☰</button><span>Oficina</span><span aria-hidden="true">/</span><strong>{source?.filename||'Revisión HTML'}</strong></div><div className="header-actions"><span className="connected-quota">{project?`${project.attempts_consumed} de 3 intentos`:'Sin intentos consumidos'}</span><button className="quiet-button" disabled={!!doing||!session} onClick={()=>void act('Actualizando estado',refreshAll)}>Actualizar</button></div></header>
        {(problem||notice)&&<div className={`connected-notice ${problem?'problem':''}`} role={problem?'alert':'status'}><span>{problem?.message||notice}{problem&&<code>{problem.code}</code>}</span><button aria-label="Cerrar aviso" onClick={()=>{setProblem(null);setNotice('');}}>×</button></div>}
        {pending&&!active&&<div className="pending-bar" role="status"><span>Hay una petición cuya respuesta debemos comprobar antes de crear otra.</span><button className="quiet-button" disabled={!!doing} onClick={()=>void act('Buscando la reserva',()=>reconcile(pending))}>Comprobar encargo</button>{pendingMissing&&<button className="quiet-button" disabled={!!doing} onClick={()=>{try{localStorage.removeItem(pendingKey(pending.office_id));setPending(null);setPendingMissing(false);setNotice('Petición sin reserva descartada. Puedes preparar un encargo nuevo.');}catch{setStorageBlocked(true);}}}>Descartar petición sin reserva</button>}</div>}
        <section ref={surface} className={`connected-surface ${attempt?'with-delivery':''}`} aria-label="Encargo y entrega">
          <section className="connected-director" aria-labelledby="director-title">
            <div className="connected-director-heading"><div className="director-signature"><DirectorMark/><strong id="director-title">Director</strong></div><span className={`connected-status ${active?'active':''}`} role="status">{status}</span></div>
            <div className="connected-conversation">
              {!attempt?<div className="connected-opening"><span className="eyebrow">Un encargo. Una entrega revisable.</span><h1>¿Qué revisamos?</h1><p>Elige un HTML y un modelo local. El Director explicará los hallazgos del análisis estático; tú decides qué hacer con ellos.</p><div className="connected-scope"><span aria-hidden="true">↳</span><p>Se comprueban idioma, título, alternativas de imagen y posibles controles sin etiqueta. El archivo se lee sin ejecutarlo.</p></div></div>:<><div className="connected-user-request"><span>Tu encargo</span><p>{attempt.objective}</p></div><div className="connected-work-status"><strong>{stateLabels[attempt.state]}</strong><p>{attempt.state==='STOPPING'?'La parada está solicitada. Esperamos a que el núcleo confirme que sus procesos han terminado.':attempt.state==='RECOVERY_REQUIRED'?'El cierre anterior no quedó confirmado. La recuperación comprobará el proceso y conservará el consumo; no volverá a ejecutar el modelo.':attempt.state==='QUEUED'?'La identidad y el consumo están guardados. Si se interrumpió el arranque, recupera este intento; no lo reenvíes.':attempt.state==='ACCEPTED'?'El informe coincide con las comprobaciones estáticas y sus recibos. Revisa por separado las sugerencias del modelo.':attempt.state==='FAILED'?'El intento terminó sin una entrega validada. Consulta el estado y prepara otro encargo sólo cuando tengas claro el motivo.':attempt.state==='CANCELLED'?'El núcleo ha confirmado la parada. El intento consumido se conserva.':attempt.state==='VERIFYING'?'El núcleo está contrastando el informe con la fuente capturada y los recibos.':'El modelo trabaja con los hallazgos y el objetivo, dentro del perfil aprobado.'}</p></div>
                <ol className="connected-call-list" aria-label="Llamadas del modelo">{(attempt.calls||[]).map(call=><li key={call.seq}><span className="call-order">{call.seq}</span><strong>{roles[call.role]||call.role}</strong><span>{call.state==='DONE'?'Respuesta registrada':call.state==='STARTED'?'En curso':call.state}</span></li>)}</ol>
                {active&&<div className="connected-action-row"><button className="stop-button" disabled={!!doing||attempt.state==='STOPPING'} onClick={()=>void act('Solicitando parada',async()=>{putAttempt(await request<Attempt>('attempt.cancel',{attempt_id:attempt.id}));})}>■ {attempt.state==='STOPPING'?'Parada solicitada':'Detener trabajo'}</button><button className="quiet-button" disabled={!!doing} onClick={()=>void act('Comprobando recuperación',async()=>{putAttempt(await request<Attempt>('attempt.recover',{attempt_id:attempt.id,expected_revision:attempt.revision}));await refreshSnapshot();})}>Comprobar recuperación</button></div>}
                {terminal(attempt.state)&&<button className="quiet-button" disabled={!!doing||!!pending} onClick={()=>newTask()}>Preparar otro encargo →</button>}
                {!!events.events.length&&<details className="connected-event-details"><summary>Actividad desde esta apertura <span>{events.events.length}</span></summary><ol>{events.events.filter(e=>e.payload.attempt===attempt.id).map(e=><li key={e.seq}><code>#{e.seq}</code> {e.kind.replaceAll('_',' ').toLowerCase()}</li>)}</ol><p>Vista acotada a cien eventos. Las llamadas y el informe se consultan en el registro durable.</p></details>}
              </>}
            </div>
            {!attempt&&<form className="connected-composer" onSubmit={e=>{e.preventDefault();void act('Preparando revisión',prepare);}}>
              <label htmlFor="connected-objective">Tu encargo al Director</label><textarea id="connected-objective" placeholder="Ej.: revisa las barreras de accesibilidad de este HTML y prioriza qué debería corregir." value={objective} maxLength={2000} rows={4} disabled={busy||!session} onChange={e=>{invalidate();setObjective(e.target.value);}} onKeyDown={e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)&&!e.nativeEvent.isComposing&&e.nativeEvent.keyCode!==229){e.preventDefault();if(!doing)void act('Preparando revisión',prepare);}}}/>
              <div className="connected-source-row"><button type="button" className="source-picker" disabled={busy||!!doing||!session} onClick={()=>void act('Eligiendo fuente',pickSource)}><span aria-hidden="true">＋</span>{source?source.filename:'Elegir archivo HTML'}</button>{source&&<span>{Math.ceil(source.bytes/1024)} KB · copia capturada</span>}</div>
              <div className="connected-model-row"><label htmlFor="connected-model">Modelo local</label><select id="connected-model" value={modelDigest} disabled={busy||!!doing} onChange={e=>{invalidate();setModelDigest(e.target.value);}}><option value="" disabled>{models.length?'Selecciona un modelo':'No hay modelos disponibles'}</option>{models.map(m=><option key={m.model_digest} value={m.model_digest}>{m.model}</option>)}</select><button type="button" aria-label="Actualizar modelos locales" title="Actualizar modelos locales" disabled={busy||!!doing||!session} onClick={()=>void act('Consultando modelos',loadModels)}>↻</button></div>
              <details className="connected-profile"><summary>Perfil acotado <span>{roleCount} {roleCount===1?'rol':'roles'} · CPU</span></summary><label htmlFor="connected-roles">Roles secuenciales</label><select id="connected-roles" value={roleCount} disabled={busy||!!doing} onChange={e=>{invalidate();setRoleCount(Number(e.target.value));}}><option value={1}>1 · Director</option><option value={3}>3 · Director, revisor e integrador</option><option value={7}>7 · Equipo completo</option></select><p>Más roles producen más llamadas. No implican mayor calidad. Un solo modelo, contexto 8K y hasta 128 tokens de salida por llamada.</p></details>
              <div className="connected-send-row"><span>{doing||'Ctrl + Enter para revisar'}<small>{objective.length}/2000</small></span><button className="solid-button" type="submit" disabled={busy||!!doing||!source||!selectedModel||objective.trim().length<12}>Revisar encargo <span aria-hidden="true">→</span></button></div>
            </form>}
          </section>
          {attempt&&<><PaneDivider kind="director" container={surface} controls="connected-delivery" label="Ancho del Director"/><section id="connected-delivery" className="connected-delivery" aria-label="Entrega"><header><div><span className="eyebrow">Entrega</span><h2>Revisión del documento</h2></div><span className="delivery-state">{report?'Informe recibido':'Esperando informe'}</span></header><div className="connected-tabs" role="tablist" aria-label="Vista de entrega" onKeyDown={tabKey}><button role="tab" tabIndex={resultTab==='report'?0:-1} id="tab-report" aria-controls="panel-report" aria-selected={resultTab==='report'} onClick={()=>setResultTab('report')}>Informe</button><button role="tab" tabIndex={resultTab==='evidence'?0:-1} id="tab-evidence" aria-controls="panel-evidence" aria-selected={resultTab==='evidence'} onClick={()=>setResultTab('evidence')}>Evidencia y alcance</button></div><div className="connected-delivery-body" role="tabpanel" id={resultTab==='report'?'panel-report':'panel-evidence'} aria-labelledby={resultTab==='report'?'tab-report':'tab-evidence'} tabIndex={0}>
            {resultTab==='report'?(report?<ReportView report={report.report}/>:<div className="delivery-empty"><span aria-hidden="true">↳</span><h3>{terminal(attempt.state)?'No hay informe validado':'Aquí aparecerá la entrega'}</h3><p>{terminal(attempt.state)?'Conservamos el intento y su estado. No se presenta una respuesta incompleta como resultado.':'El núcleo publicará el documento después de completar las llamadas y verificar sus recibos.'}</p></div>):<div className="connected-evidence"><h3>Qué puedes comprobar</h3><dl><dt>Intento</dt><dd>{attempt.id}</dd><dt>Estado del núcleo</dt><dd>{attempt.state}</dd><dt>Modelo aprobado</dt><dd>{attempt.model}</dd><dt>Huella del modelo</dt><dd>{attempt.model_digest}</dd><dt>Huella de la fuente</dt><dd>{attempt.source_sha256}</dd><dt>Huella del informe</dt><dd>{report?.meta.sha256||'Todavía no disponible'}</dd></dl>{report&&<p>La lectura comprobó los fragmentos y la huella completa del informe antes de mostrarlo.</p>}<p>La aceptación verifica consistencia estática y procedencia de contenido. No certifica accesibilidad, seguridad ni que las sugerencias del modelo sean correctas.</p>{attempt.execution_error_code&&<p>Código de ejecución: <code>{attempt.execution_error_code}</code></p>}{report&&<details><summary>Informe original de sólo lectura</summary><pre>{report.text}</pre></details>}</div>}
          </div></section></>}
        </section>
        <footer className="connected-footer"><span>{attempt?.model||selectedModel?.model||'Selecciona tu modelo local'}</span><span>{active?'Trabajo acotado en curso':'Sin trabajo nuevo en segundo plano'} · Modelo local · sin APIs de proveedor configuradas</span></footer>
      </main>
    </div>
    <dialog ref={approvalDialog} className="connected-approval" aria-labelledby="approval-title" onCancel={e=>{e.preventDefault();setApproval(null);}} onClose={()=>setApproval(null)}>{approval&&<><div className="approval-heading"><span className="eyebrow">Antes de empezar</span><button aria-label="Cerrar revisión" onClick={()=>setApproval(null)}>×</button></div><h2 id="approval-title">Este es el encargo.</h2><p className="approval-objective">{approval.value.objective}</p><dl><dt>Fuente capturada</dt><dd>{source?.filename}</dd><dt>Modelo</dt><dd>{approval.value.model}</dd><dt>Trabajo</dt><dd>{approval.value.roles} {approval.value.roles===1?'rol':'roles'} secuenciales · CPU · contexto 8K</dd><dt>Presupuesto</dt><dd>Consumirá 1 intento. Quedan {approval.value.attempts_remaining} antes de empezar.</dd></dl><p>El archivo original no se modifica. Se generará un informe con comprobaciones estáticas y comentarios del modelo.</p><p className="approval-expiry">Esta autorización caduca en dos minutos. Si algo cambia, tendrás que revisarla otra vez.</p><div className="approval-actions"><button className="quiet-button" onClick={()=>setApproval(null)}>Volver al encargo</button><button className="solid-button" disabled={!!doing} onClick={()=>void act('Registrando encargo',start)}>Autorizar y ejecutar →</button></div></>}</dialog>
  </div>;
}
const findingLabels:Record<string,string>={HTML_LANGUAGE_MISSING:'El documento no declara su idioma',HTML_ELEMENT_MISSING:'No se encontró el elemento HTML',DOCUMENT_TITLE_MISSING:'Falta un título de documento no vacío',IMAGE_ALT_MISSING:'Una imagen no tiene atributo alt',CONTROL_LABEL_CANDIDATE:'Un control podría necesitar una etiqueta'};
function ReportView({report}:{report:Report}) {
  return <article className="connected-report"><span className="eyebrow">Comprobaciones estáticas</span><h3>{report.findings.length?`${report.findings.length} ${report.findings.length===1?'hallazgo para revisar':'hallazgos para revisar'}`:'Sin hallazgos en estas comprobaciones'}</h3><p className="report-scope">El alcance es limitado: estos resultados no sustituyen una revisión de accesibilidad en el navegador.</p><ol className="finding-list">{report.findings.map((f,index)=><li key={`${f.code}-${f.line}-${f.column}-${index}`}><span>{String(index+1).padStart(2,'0')}</span><div><strong>{findingLabels[f.code]||f.code}</strong><small>Línea {f.line} · columna {f.column}</small></div></li>)}</ol><div className="commentary-heading"><h3>Criterio del equipo</h3><span>Sugerencias por revisar</span></div>{report.role_outputs.map((r,index)=><section className="role-commentary" key={`${r.role}-${index}`}><h4>{roles[r.role]||r.role}</h4><p>{r.content}</p></section>)}</article>;
}
