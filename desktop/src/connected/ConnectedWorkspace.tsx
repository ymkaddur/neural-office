import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {AttemptActivity} from './AttemptActivity.tsx';
import {ProjectHistory} from './ProjectHistory.tsx';
import {PaneDivider} from '../workspace/PaneDivider.tsx';
import {hasNativeHost,readReport,request} from './client.ts';
import type {Finding,FindingPage,Report} from './client.ts';
import {acceptAttempt,approvalMatches,approvalScopeMatches,pendingKey,readPending,recordedDuration,remainingLabel,stateLabels,terminal,validateSnapshot,writePending} from './model.ts';
import type {Approval,Attempt,Model,Pending,Project,Snapshot,Source} from './model.ts';
import './connected.css';

type LoadedReport=Awaited<ReturnType<typeof readReport>>;
type Description={session_id:string;inference:string;office_id:string};
type Draft={objective:string;source:Source|null;modelDigest:string;roleCount:number;assisted:boolean;afterAttempt?:string};
let initialFlight:Promise<{description:Description;snapshot:Snapshot}>|null=null;
function initialData() {
  if(!initialFlight) initialFlight=request<Description>('describe').then(async description=>({
    description,snapshot:validateSnapshot(await request<Snapshot>('snapshot.get',{project_after:0,attempt_after:0,limit:100})),
  })).finally(()=>{initialFlight=null;});
  return initialFlight;
}
async function lookupAttempt(saved:Pending,session:string) {
  const result=await request<{session_id:string;office_id:string;found:boolean;attempt:Attempt|null}>('attempt.lookup',{project_id:saved.project_id,idempotency_key:saved.idempotency_key});
  if(result.office_id!==saved.office_id||result.session_id!==session)throw Error('HOST_SESSION_CHANGED');
  if(result.found===false&&result.attempt===null)return null;
  if(result.found!==true||!result.attempt)throw Error('LOOKUP_CONTRACT');
  if(result.attempt.project_id!==saved.project_id||result.attempt.request_key!==saved.idempotency_key)throw Error('LOOKUP_IDENTITY_CHANGED');
  return acceptAttempt(null,result.attempt);
}
const makeProject=()=>`oficina-${crypto.randomUUID().slice(0,8)}`;
const short=(id:string)=>id.length>18?`${id.slice(0,9)}…${id.slice(-5)}`:id;
const roles:Record<string,string>={director:'Director',skeptic:'Revisor',integrator:'Integrador',planner:'Planificador',researcher:'Investigador',implementer:'Implementador',verifier:'Verificador'};
const errors:Record<string,string>={
  PILOT_FINDINGS_LIMIT:'El modelo admite hasta 24 hallazgos por encargo. Puedes leerlos todos en la comprobación sin modelo.',
  PROMPT_BYTE_BUDGET:'El encargo supera el espacio de entrada del modelo. Acorta la petición o utiliza la comprobación sin modelo.',
  REPORT_NOT_ACCEPTED:'El núcleo no aceptó esta entrega. Puedes consultar el estado del intento.',
  FILE_STREAM_EXCLUDED:'Selecciona un archivo HTML ordinario mediante el selector de archivos.',
  NATIVE_HOST_REQUIRED:'Abre la aplicación de escritorio para trabajar con tus archivos y modelos.',
  HOST_CONNECTION_UNAVAILABLE:'La conexión con el núcleo no está disponible. Comprueba el estado antes de volver a encargar trabajo.',
  HOST_DISCONNECTED:'Se perdió el enlace con el núcleo. Reconecta para consultar el mismo encargo.',
  HOST_RESPONSE_TIMEOUT:'El núcleo no ha confirmado la respuesta. Comprueba el estado del mismo encargo.',
  HOST_SESSION_CHANGED:'El núcleo ha cambiado de sesión. Reconecta para confirmar la oficina y el encargo.',
  HOST_SIDECAR_START:'No ha sido posible iniciar el núcleo local. Comprueba su configuración y vuelve a conectar.',
  HOST_REQUEST_TIMEOUT:'La respuesta está tardando. El encargo podría haberse registrado; consulta su estado, sin reenviarlo.',
  MODEL_METADATA_UNAVAILABLE:'Ollama no responde. Ábrelo y comprueba que tienes un modelo local descargado; después actualiza la lista.',
  MODEL_CATALOG_BUSY:'El núcleo está ocupado. La selección de modelo estará disponible al terminar.',
  SOURCE_GRANT_INVALID_OR_EXPIRED:'La selección temporal ha caducado. Vuelve a elegir el archivo para revisar sus bytes actuales.',
  APPROVAL_INVALID_OR_EXPIRED:'La aprobación ha caducado. Revisa de nuevo el encargo antes de ejecutarlo.',
  APPROVAL_CHANGED:'El encargo cambió o la aprobación caducó. Revisa otra vez su alcance.',
  ATTEMPT_BUDGET_EXHAUSTED:'Este proyecto ha consumido sus 3 intentos. Puedes seguir comprobando HTML sin modelo y consultar sus entregas.',
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
const transportCodes=new Set(['HOST_DISCONNECTED','HOST_CLOSING','HOST_CONNECTION_UNAVAILABLE','HOST_RESPONSE_TIMEOUT','HOST_REQUEST_TIMEOUT','HOST_SIDECAR_START','HOST_SESSION_CHANGED','HOST_PIPE_UNAVAILABLE','HOST_RESPONSE_INVALID','HOST_REQUEST_FAILED','HOST_CONFIGURATION_REQUIRED','HOST_CONFIGURATION_INVALID']);
function failureAdvice(code?:string|null){
  switch(code){
    case 'MODEL_METADATA_UNAVAILABLE': case 'METADATA_UNAVAILABLE':
      return 'No se pudieron leer los metadatos del modelo. Comprueba que Ollama y el modelo elegido están disponibles.';
    case 'LOCAL_MODEL_NOT_FOUND': case 'INSTALL_OLLAMA_FIRST':
      return 'Comprueba la instalación de Ollama y el catálogo local antes de preparar otra consulta.';
    case 'OWNED_BACKEND_START_FAILED': case 'OWNED_BACKEND_START_TIMEOUT':
      return 'El motor local no terminó de arrancar. Comprueba su disponibilidad antes de autorizar otra consulta.';
    case 'EXECUTION_FAILED':return 'El registro confirma el fallo. No se identificó un motivo que se pueda mostrar.';
    case 'ATTEMPT_INTERRUPTED':
      return 'Se confirmó el cierre del proceso antes de completar el encargo.';
    default:return code?'La ejecución falló. Puedes inspeccionar la actividad y conservar este intento.':'El registro conserva el fallo. El motivo original no está disponible.';
  }
}
function DirectorMark(){return <span className="director-mark" aria-hidden="true"><span/><span/><span/></span>;}

export function ConnectedWorkspace() {
  const native=hasNativeHost();
  const [initializing,setInitializing]=useState(native);
  const [handshake,setHandshake]=useState(0);
  const [connectionError,setConnectionError]=useState<ReturnType<typeof errorInfo>|null>(null);
  const peerGeneration=useRef(0), lastConfirmed=useRef<Date|null>(null);
  const [inspected,setInspected]=useState<Attempt|null>(null);
  const [browsedProject,setBrowsedProject]=useState<string|null>(null);
  const [session,setSession]=useState('');
  const [officeId,setOfficeId]=useState('');
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [pagedProject,setPagedProject]=useState<{session:string;office:string;revision:number;value:Project}|null>(null);
  const [models,setModels]=useState<Model[]>([]);
  const [modelDigest,setModelDigest]=useState('');
  const [catalog,setCatalog]=useState<'idle'|'loading'|'ready'|'error'>('idle');
  const [catalogEmpty,setCatalogEmpty]=useState(false);
  const catalogRead=useRef(0);
  const [projectId,setProjectId]=useState(makeProject);
  const [source,setSource]=useState<Source|null>(null);
  const [objective,setObjective]=useState('');
  const [roleCount,setRoleCount]=useState(1);
  const [assisted,setAssisted]=useState(false);
  const [inspection,setInspection]=useState<{token:string;page:FindingPage}|null>(null);
  const inspectionTitle=useRef<HTMLHeadingElement>(null);
  const [approval,setApproval]=useState<{value:Approval;expiresAt:number}|null>(null);
  const [attempt,setAttempt]=useState<Attempt|null>(null);
  const [pending,setPending]=useState<Pending|null>(null);
  const [pendingMissing,setPendingMissing]=useState(false);
  const [storageBlocked,setStorageBlocked]=useState(false);
  const [loadedReport,setReport]=useState<LoadedReport|null>(null);
  const [reportReadRevision,setReportReadRevision]=useState(0);
  const [doing,setDoing]=useState('');
  const stopFlight=useRef<symbol|null>(null);
  const [requestingStop,setRequestingStop]=useState(false);
  const [budgetPending,setBudgetPending]=useState(false);
  const [problem,setProblem]=useState<ReturnType<typeof errorInfo>|null>(null);
  const [notice,setNotice]=useState('');
  const [dark,setDark]=useState(()=>{try{return localStorage.getItem('neural-office.v55.theme')!=='light';}catch{return true;}});
  const [graphite,setGraphite]=useState(()=>{try{return localStorage.getItem('neural-office.v510.palette')!=='mineral';}catch{return true;}});
  const [navOpen,setNavOpen]=useState(false);
  const [resultTab,setResultTab]=useState<'report'|'evidence'>('report');
  const shell=useRef<HTMLDivElement>(null),surface=useRef<HTMLElement>(null),approvalDialog=useRef<HTMLDialogElement>(null);
  const mounted=useRef(false),operation=useRef(false),generation=useRef(0),sessionRef=useRef(''),officeRef=useRef('');
  const currentAttempt=useRef<Attempt|null>(null),previousFocus=useRef<HTMLElement|null>(null),navOpener=useRef<HTMLElement|null>(null);
  // Unsent text stays in this window only. Cap storage without silently evicting work.
  const drafts=useRef(new Map<string,Draft>());
  const active=attempt!==null&&!terminal(attempt.state);
  const viewed=inspected??attempt;
  const sourceLabel=viewed?(viewed.source_name||`HTML · ${viewed.source_sha256.slice(0,12)}`):(source?.filename||'Nuevo encargo');
  const navProject=browsedProject??projectId;
  const selectedProject=viewed?.project_id??projectId;
  const project=snapshot?.projects.find(p=>p.id===selectedProject)??(pagedProject&&snapshot&&
    pagedProject.value.id===selectedProject&&pagedProject.session===snapshot.session_id&&pagedProject.office===snapshot.office_id&&
    pagedProject.revision===snapshot.revision?pagedProject.value:null);
  const report=loadedReport&&loadedReport.meta.attempt_id===viewed?.id&&loadedReport.report.source_sha256===viewed?.source_sha256?loadedReport:null;
  const alert=connectionError??problem;
  const busy=initializing||active||!!pending||storageBlocked||!!connectionError;
  const exhausted=!!project&&project.attempts_consumed>=3;
  const available=viewed?.state==='ACCEPTED'&&viewed.report_available;
  const staticPage=source&&inspection?.token===source.entry_token&&inspection.page.session_id===session?inspection.page:null;
  const showingFindings=!!staticPage&&!assisted;
  const selectedModel=models.find(m=>m.model_digest===modelDigest);
  const status=viewed?stateLabels[viewed.state]:pending?'Comprobando un encargo anterior':session?'Listo para un encargo':'Conectando con tu oficina';
  const epoch=()=>generation.current;
  function noteError(error:unknown){
    if(!mounted.current)return;
    const issue=errorInfo(error);
    if(issue.code==='READ_SUPERSEDED')return;
    if(transportCodes.has(issue.code))setConnectionError(old=>old?.code===issue.code?old:issue);
    else setProblem(issue);
  }
  function confirmConnection(){
    lastConfirmed.current=new Date();
    setConnectionError(null);
  }
  function retryConnection(){
    peerGeneration.current++;
    stopFlight.current=null;setRequestingStop(false);
    setInitializing(true);setApproval(null);setHandshake(old=>old+1);
  }
  function invalidate(){generation.current++;setApproval(null);setProblem(null);setNotice('');}
  function putAttempt(next:Attempt) {
    const previous=currentAttempt.current;
    const accepted=acceptAttempt(previous,next);
    if(currentAttempt.current?.id!==accepted.id&&!inspected)setReport(null);
    currentAttempt.current=accepted;setAttempt(accepted);
    if(previous?.id===accepted.id&&!terminal(previous.state)&&terminal(accepted.state)){
      const peer=peerGeneration.current;
      setBudgetPending(true);
      void refreshSnapshot().catch(error=>{if(mounted.current&&peer===peerGeneration.current)noteError(error);});
    }
  }
  async function refreshSnapshot() {
    const generation=peerGeneration.current;
    const next=validateSnapshot(await request<Snapshot>('snapshot.get',{project_after:0,attempt_after:0,limit:100}));
    if(!mounted.current||generation!==peerGeneration.current)throw Error('READ_SUPERSEDED');
    if(next.session_id!==sessionRef.current||next.office_id!==officeRef.current)throw Error('HOST_SESSION_CHANGED');
    setSnapshot(current=>current&&current.revision>next.revision?current:next);
    setBudgetPending(false);
    confirmConnection();
    return next;
  }
  async function reconcile(saved:Pending) {
    if(saved.office_id!==officeRef.current)throw Error('PENDING_OFFICE_CHANGED');
    const peer=peerGeneration.current;
    const found=await lookupAttempt(saved,sessionRef.current);
    if(!mounted.current||peer!==peerGeneration.current||saved.office_id!==officeRef.current) return;
    setProjectId(saved.project_id);
    if(found) {discardSubmittedDraft(found);putAttempt(found);setPendingMissing(false);setNotice('Encargo recuperado por su identidad original. No se ha vuelto a ejecutar.');}
    else {setPendingMissing(true);setNotice('El núcleo no tiene una reserva para esta identidad. No se ha reenviado nada.');}
    confirmConnection();
  }
  async function loadModels() {
    const ticket=++catalogRead.current,peer=peerGeneration.current;
    const current=()=>mounted.current&&ticket===catalogRead.current&&peer===peerGeneration.current;
    setCatalog('loading');
    try {
      const result=await request<{models:Model[];session_id:string}>('models.list');
      if(!current())return;
      if(result.session_id!==sessionRef.current)throw Error('HOST_SESSION_CHANGED');
      if(!Array.isArray(result.models)||result.models.length>64||result.models.some(m=>!m||typeof m.model!=='string'||!/^[a-f0-9]{64}$/.test(m.model_digest)))throw Error('MODEL_CONTRACT');
      setModels(result.models);
      setCatalogEmpty(result.models.length===0);
      setModelDigest(old=>result.models.some(m=>m.model_digest===old)?old:(result.models[0]?.model_digest||''));
      setCatalog('ready');
    } catch(error) {
      if(!current())return;
      setModels([]);setModelDigest('');setCatalog('error');throw error;
    }
  }
  async function act(label:string,work:()=>Promise<void>) {
    if(operation.current) return;
    operation.current=true;setDoing(label);setProblem(null);
    try {await work();}catch(error){noteError(error);}finally{operation.current=false;if(mounted.current)setDoing('');}
  }
  async function stopActive() {
    const target=currentAttempt.current;
    if(stopFlight.current||!target||terminal(target.state)||target.state==='STOPPING'||initializing||connectionError)return;
    const flight=Symbol(),peer=peerGeneration.current;
    stopFlight.current=flight;setRequestingStop(true);
    try{
      const reply=await request<Attempt>('attempt.cancel',{attempt_id:target.id});
      if(!mounted.current||peer!==peerGeneration.current||currentAttempt.current?.id!==target.id)return;
      if(reply.id!==target.id||reply.project_id!==target.project_id)throw Error('ATTEMPT_IDENTITY_CHANGED');
      if(reply.session_id!==sessionRef.current)throw Error('HOST_SESSION_CHANGED');
      putAttempt(reply);
    }catch(error){if(mounted.current&&peer===peerGeneration.current)noteError(error);}
    finally{if(mounted.current&&stopFlight.current===flight){stopFlight.current=null;setRequestingStop(false);}}
  }
  useEffect(()=>{
    mounted.current=true;
    if(!native) return ()=>{mounted.current=false;};
    let live=true;
    const previousOffice=officeRef.current, previousSession=sessionRef.current, previousAttempt=currentAttempt.current;
    void initialData().then(async({description,snapshot:first})=>{
      if(!live) return;
      if(description.session_id!==first.session_id||description.office_id!==first.office_id) throw Error('HOST_SESSION_CHANGED');
      if(previousSession&&(previousSession!==description.session_id||previousOffice!==description.office_id)){
        invalidate();setModels([]);setModelDigest('');setCatalog('idle');setCatalogEmpty(false);setSource(null);setInspection(null);setInspected(null);setBrowsedProject(null);
        for(const draft of drafts.current.values())draft.source=null;
        if(previousOffice!==description.office_id){drafts.current.clear();setObjective('');setProjectId(makeProject());setReport(null);setAttempt(null);currentAttempt.current=null;}
      }
      setProblem(null);setPendingMissing(false);
      sessionRef.current=description.session_id;officeRef.current=description.office_id;setSession(description.session_id);setOfficeId(description.office_id);setSnapshot(first);
      setBudgetPending(false);confirmConnection();
      let saved:Pending|null=null;
      try{saved=readPending(localStorage,description.office_id);setPending(saved);setStorageBlocked(false);}catch(error){setStorageBlocked(true);throw error;}
      const activeRow=first.current_attempt??first.attempts.find(a=>!terminal(a.state));
      let restoreActive=false;
      if(saved) {
        const found=await lookupAttempt(saved,sessionRef.current);
        if(!live)return;
        setProjectId(saved.project_id);
        if(found){
          discardSubmittedDraft(found);
          if(activeRow&&activeRow.id!==found.id&&terminal(found.state)){
            if(readPending(localStorage,saved.office_id)?.idempotency_key===saved.idempotency_key)localStorage.removeItem(pendingKey(saved.office_id));
            setPending(null);restoreActive=true;
          }else putAttempt(found);
          setNotice('Encargo recuperado por su identidad original. No se ha vuelto a ejecutar.');
        }
        else {setPendingMissing(true);setNotice('El núcleo no tiene una reserva para esta identidad. No se ha reenviado nada.');}
      }
      if(!saved||restoreActive) {
        const activeProject=first.projects.find(p=>p.active)||first.projects[0];
        if(activeProject)setProjectId(activeProject.id);
        const unresolved=activeRow??(previousOffice===first.office_id?previousAttempt:null);
        if(unresolved){
          setProjectId(unresolved.project_id);putAttempt(unresolved);
          const next=await request<Attempt>('attempt.get',{attempt_id:unresolved.id});
          if(!live)return;
          if(next.id!==unresolved.id||next.project_id!==unresolved.project_id)throw Error('ATTEMPT_IDENTITY_CHANGED');
          if(next.session_id&&next.session_id!==description.session_id)throw Error('HOST_SESSION_CHANGED');
          putAttempt(next);
        }
      }
      // Static inspection has no dependency on the model catalog.
    }).catch(error=>{if(live)noteError(error);}).finally(()=>{if(live)setInitializing(false);});
    return ()=>{live=false;mounted.current=false;generation.current++;};
  },[native,handshake]);
  useEffect(()=>{
    if(!assisted||!session||attempt||exhausted||initializing||connectionError)return;
    let live=true;
    void loadModels().catch(error=>{if(live)noteError(error);});
    return ()=>{live=false;catalogRead.current++;};
  },[assisted,session,!!attempt,exhausted,initializing,!!connectionError]);
  useEffect(()=>{if(staticPage&&!assisted)inspectionTitle.current?.focus();},[staticPage,assisted]);
  useEffect(()=>{try{localStorage.setItem('neural-office.v55.theme',dark?'dark':'light');}catch{}},[dark]);
  useEffect(()=>{try{localStorage.setItem('neural-office.v510.palette',graphite?'graphite':'mineral');}catch{}},[graphite]);
  useLayoutEffect(()=>{
    const dialog=approvalDialog.current;
    if(approval&&!dialog?.open){previousFocus.current=document.activeElement as HTMLElement;dialog?.showModal();}
    if(!approval&&dialog?.open){dialog.close();previousFocus.current?.focus();}
    if(!approval)return;
    const timer=setTimeout(()=>{
      setApproval(null);
      setProblem(errorInfo(Error('APPROVAL_INVALID_OR_EXPIRED')));
    },Math.max(0,Math.ceil(approval.expiresAt-performance.now())));
    return()=>clearTimeout(timer);
  },[approval]);
  useEffect(()=>{
    if(!attempt||!terminal(attempt.state)||!pending||attempt.request_key!==pending.idempotency_key||attempt.project_id!==pending.project_id)return;
    try{localStorage.removeItem(pendingKey(pending.office_id));setPending(null);setPendingMissing(false);}catch{setStorageBlocked(true);}
  },[attempt,pending]);
  useEffect(()=>{
    if(initializing||!active||!attempt)return;
    const id=attempt.id, peer=peerGeneration.current;let cancelled=false,timer:ReturnType<typeof setTimeout>|undefined,failures=0;
    const tick=async()=>{
      try{
        const next=await request<Attempt>('attempt.get',{attempt_id:id});
        if(cancelled||!mounted.current||peer!==peerGeneration.current||currentAttempt.current?.id!==id)return;
        if(next.id!==id||next.project_id!==currentAttempt.current.project_id)throw Error('ATTEMPT_IDENTITY_CHANGED');
        if(next.session_id&&next.session_id!==sessionRef.current)throw Error('HOST_SESSION_CHANGED');
        putAttempt(next);
        confirmConnection();failures=0;
        if(terminal(next.state))return;
      }catch(error){
        if(!cancelled&&peer===peerGeneration.current){
          failures++;noteError(error);
          if(error instanceof Error&&['HOST_DISCONNECTED','HOST_CLOSING','HOST_SESSION_CHANGED'].includes(error.message))return;
        }
      }
      if(!cancelled)timer=setTimeout(tick,Math.min(10000,2000*(failures+1)));
    };
    timer=setTimeout(tick,250);
    return()=>{cancelled=true;if(timer)clearTimeout(timer);};
  },[initializing,active,attempt?.id,handshake]);
  useEffect(()=>{
    setReport(null);
    if(!viewed||!available)return;
    let live=true;const id=viewed.id;
    void readReport(request,id,()=>live).then(result=>{if(live){if(result.report.source_sha256!==viewed.source_sha256)throw Error('REPORT_SOURCE_CHANGED');setReport(result);}}).catch(error=>{if(live)noteError(error);});
    return()=>{live=false;};
  },[viewed?.id,available,reportReadRevision,session]);
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
    if(picked.session_id!==session||picked.project_id!==projectId||typeof picked.filename!=='string'||typeof picked.entry_token!=='string'||!/^[A-Za-z0-9_-]{1,64}$/.test(picked.entry_token)||!Number.isSafeInteger(picked.bytes)||picked.bytes<1||picked.bytes>262144||!/^[a-f0-9]{64}$/.test(picked.sha256))throw Error('SOURCE_CONTRACT');
    invalidate();setSource(picked);await refreshSnapshot();
  }
  async function inspectSource(offset=0) {
    if(!source||busy||catalogEmpty||catalog==='loading')return;
    const expected=epoch();
    const page=await request<FindingPage>('source.check',{project_id:projectId,entry_token:source.entry_token,offset});
    if(!mounted.current||expected!==epoch())return;
    if(page.session_id!==session||page.project_id!==projectId||page.source_sha256!==source.sha256||
       page.offset!==offset||!Number.isSafeInteger(page.total)||page.total<offset||
       (offset>0&&page.total===offset)||!Array.isArray(page.findings)||
       page.findings.length!==Math.min(24,page.total-offset)||page.findings.some(f=>
         !f||!Object.hasOwn(findingLabels,f.code)||!Number.isSafeInteger(f.line)||f.line<1||
         !Number.isSafeInteger(f.column)||f.column<1))throw Error('SOURCE_CHECK_CONTRACT');
    setInspection({token:source.entry_token,page});
    setAssisted(false);
  }
  function changeMode(value:boolean) {
    invalidate();
    catalogRead.current++;
    if(catalog==='loading')setCatalog('idle');
    setAssisted(value);
    requestAnimationFrame(()=>(value?document.getElementById('connected-objective'):
      document.getElementById('static-result-title')||document.getElementById('static-picker'))?.focus());
  }
  async function prepare() {
    if(!source||catalog!=='ready'||!selectedModel||objective.trim().length<12||busy||exhausted||budgetPending)return;
    const expected=epoch();
    const requestedAt=performance.now();
    const result=await request<Approval>('attempt.preview',{project_id:projectId,entry_token:source.entry_token,model_digest:modelDigest,roles:roleCount,objective:objective.trim()});
    if(!mounted.current||expected!==epoch())return;
    const expiresAt=requestedAt+result.expires_in_seconds*1000;
    if(!approvalScopeMatches(result,session,source,objective,modelDigest,roleCount,expiresAt,performance.now()))throw Error('APPROVAL_CHANGED');
    if(result.attempts_remaining===0){
      setBudgetPending(true);
      void refreshSnapshot().catch(noteError);
      throw Error('ATTEMPT_BUDGET_EXHAUSTED');
    }
    setApproval({value:result,expiresAt});
  }
  async function start() {
    const reviewed=approval;
    if(reviewed&&performance.now()>=reviewed.expiresAt){setApproval(null);throw Error('APPROVAL_INVALID_OR_EXPIRED');}
    if(!reviewed||!approvalMatches(reviewed.value,session,source,objective,modelDigest,roleCount,reviewed.expiresAt,performance.now())){setApproval(null);throw Error('APPROVAL_CHANGED');}
    const identity={office_id:officeId,project_id:projectId,idempotency_key:crypto.randomUUID()};
    try{writePending(localStorage,identity);}catch{setStorageBlocked(true);throw Error('PENDING_IDENTITY_NOT_SAVED');}
    setPending(identity);setPendingMissing(false);setApproval(null);
    // Identity is durable before send. Any ambiguous failure remains reconcilable.
    const next=await request<Attempt>('attempt.start',{approval_token:reviewed.value.approval_token,idempotency_key:identity.idempotency_key,expected_revision:reviewed.value.expected_revision});
    if(!mounted.current)return;
    drafts.current.delete(projectId);
    putAttempt(next);setSource(null);setObjective('');await refreshSnapshot();
  }
  function retainDraft() {
    if(attempt)return true;
    if(!objective&&!source){drafts.current.delete(projectId);return true;}
    if(!drafts.current.has(projectId)&&drafts.current.size>=20){
      setNotice('Hay veinte borradores en esta ventana. Vacía o envía uno antes de cambiar de proyecto; tu texto actual sigue aquí.');return false;
    }
    drafts.current.set(projectId,{objective,source,modelDigest,roleCount,assisted});return true;
  }
  function discardSubmittedDraft(found:Attempt) {
    if(drafts.current.get(found.project_id)?.afterAttempt!==found.id)drafts.current.delete(found.project_id);
  }
  function noteNext(item:Attempt,text:string) {
    const previous=drafts.current.get(item.project_id);
    if(!text&&!previous?.source){drafts.current.delete(item.project_id);return;}
    if(!previous&&drafts.current.size>=20)return;
    drafts.current.set(item.project_id,{source:null,modelDigest:'',roleCount:1,...previous,
      assisted:true,objective:text,afterAttempt:item.id});
  }
  function openDraft(id:string) {
    if(busy||operation.current||!retainDraft())return;
    const draft=drafts.current.get(id);
    invalidate();setInspected(null);setBrowsedProject(null);setProjectId(id);setSource(draft?.source?.session_id===session?draft.source:null);
    setInspection(null);setAssisted(draft?.assisted??false);
    setObjective(draft?.objective||'');setRoleCount(draft?.roleCount||1);
    if(draft)setModelDigest(models.some(m=>m.model_digest===draft.modelDigest)?draft.modelDigest:'');
    setReport(null);setAttempt(null);currentAttempt.current=null;
    setNavOpen(false);requestAnimationFrame(()=>(document.getElementById('connected-objective')||document.getElementById('static-picker'))?.focus());
  }
  function newTask(newProject=false) {
    openDraft(newProject?makeProject():projectId);
  }
  function chooseProject(id:string) {
    if(active){setBrowsedProject(id);return;}
    openDraft(id);
  }
  async function chooseAttempt(item:Attempt) {
    if(!retainDraft())return;
    setNavOpen(false);
    invalidate();const expected=epoch();
    const next=await request<Attempt>('attempt.get',{attempt_id:item.id});
    if(!mounted.current||expected!==epoch())return;
    if(next.id!==item.id||next.project_id!==item.project_id)throw Error('ATTEMPT_IDENTITY_CHANGED');
    if(next.session_id&&next.session_id!==sessionRef.current)throw Error('HOST_SESSION_CHANGED');
    confirmConnection();setNavOpen(false);
    if(currentAttempt.current&&currentAttempt.current.id!==item.id&&(active||!terminal(currentAttempt.current.state))){
      setInspected(next.id===currentAttempt.current.id?null:next);
    }else{
      setInspected(null);setBrowsedProject(null);setSource(null);setProjectId(next.project_id);putAttempt(next);
    }
  }
  function tabKey(event:{key:string;preventDefault:()=>void}) {
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();
    const next=event.key==='Home'?'report':event.key==='End'?'evidence':resultTab==='report'?'evidence':'report';
    setResultTab(next);requestAnimationFrame(()=>document.getElementById(`tab-${next}`)?.focus());
  }
  async function refreshAll() {
    const peer=peerGeneration.current, selected=epoch();
    await refreshSnapshot();
    const stillCurrent=()=>mounted.current&&peer===peerGeneration.current&&selected===epoch();
    for(const item of [attempt,inspected]){
      if(!item||!stillCurrent())continue;
      const next=await request<Attempt>('attempt.get',{attempt_id:item.id});
      if(!stillCurrent())return;
      if(next.id!==item.id||next.project_id!==item.project_id)throw Error('ATTEMPT_IDENTITY_CHANGED');
      if(next.session_id&&next.session_id!==sessionRef.current)throw Error('HOST_SESSION_CHANGED');
      if(item===inspected)setInspected(acceptAttempt(item,next));
      else if(currentAttempt.current?.id===item.id)putAttempt(next);
      if(next.id===viewed?.id&&next.state==='ACCEPTED'&&next.report_available&&!report)setReportReadRevision(v=>v+1);
    }
    if(pending&&stillCurrent())await reconcile(pending);
  }
  async function nextProjects() {
    if(!snapshot)return;
    const next=validateSnapshot(await request<Snapshot>('snapshot.get',{
      project_after:snapshot.next.project_after,attempt_after:0,limit:100}));
    if(next.revision!==snapshot.revision||next.session_id!==snapshot.session_id||next.office_id!==snapshot.office_id){await refreshSnapshot();setNotice('El historial cambió. Se ha actualizado la primera página.');return;}
    if(project)setPagedProject({session:snapshot.session_id,office:snapshot.office_id,revision:snapshot.revision,value:project});
    setSnapshot(next);
    setNotice('Página siguiente de proyectos.');
  }

  if(!native)return <main className={`v541 connected offline ${dark?'theme-dark':''}`}>
    <div className="offline-wordmark"><DirectorMark/><strong>Neural Office</strong><span>V5.11</span></div>
    <section className="offline-content"><span className="eyebrow">Neural Office · Escritorio Windows</span><h1>Encarga una revisión al Director</h1><p>En el escritorio de Windows puedes escribir tu objetivo, adjuntar un HTML y seguir la revisión con tu modelo local.</p><p>Las instrucciones están en <code>desktop/README.md</code>, dentro de la descarga.</p>{import.meta.env.DEV&&<a className="solid-button" href="?preview=1&screen=ready">Galería histórica de desarrollo →</a>}<p className="offline-note">Esta página no ejecuta encargos.</p></section>
    <footer>Software gratuito · Tus modelos locales · Apoyo voluntario</footer>
  </main>;

  return <div className={`v541 connected ${dark?'theme-dark':''} ${graphite?'palette-graphite':''}`}>
    <div ref={shell} className={`office-shell connected-shell ${navOpen?'nav-open':''}`}>
      <nav className="office-nav connected-nav" aria-label="Proyectos y encargos">
        <div className="wordmark"><DirectorMark/><strong>Neural Office</strong><span className="version-tag">5.11</span></div>
        <button className="connected-close-nav" onClick={()=>setNavOpen(false)}>Cerrar proyectos ×</button>
        <button className="new-task" disabled={busy||!!doing} onClick={()=>newTask()}><span aria-hidden="true">＋</span> Nuevo encargo</button>
        <div className="connected-nav-heading">Proyectos <button aria-label="Crear otro proyecto" title="Crear otro proyecto" disabled={busy||!!doing} onClick={()=>newTask(true)}>＋</button></div>
        <div className="connected-projects">{snapshot?.projects.map(p=><button key={p.id} className={p.id===navProject?'selected':''} disabled={initializing||!!doing||!!connectionError||(active?p.attempts_consumed<=p.legacy_consumed:!!pending||storageBlocked)} onClick={()=>chooseProject(p.id)} title={p.id}><span>{short(p.id)}</span><small>{p.attempts_consumed}/3 usados</small></button>)}{!snapshot?.projects.some(p=>p.id===projectId)&&<div className="connected-new-project"><span>Proyecto actual</span><small>{project?.id===projectId&&!budgetPending?remainingLabel(project.attempts_consumed):'Cuota por confirmar'}</small></div>}</div>
        <div className="connected-nav-heading">Encargos guardados</div>
        <ProjectHistory key={JSON.stringify([snapshot?.office_id,snapshot?.session_id,navProject])} project={navProject} snapshot={snapshot} selected={viewed?.id}
          offline={!!connectionError||initializing} disabled={initializing||!!connectionError||!!doing||(!active&&!!pending)} onOpen={a=>void act('Abriendo encargo',()=>chooseAttempt(a))}
          onRefresh={()=>act('Actualizando historial',refreshAll)}/>
        {snapshot?.has_more.projects&&<button className="nav-secondary" disabled={initializing||!!doing} onClick={()=>void act('Cargando proyectos',nextProjects)}>Siguientes proyectos →</button>}
        {snapshot&&snapshot.next.project_after>100&&<button className="nav-secondary" disabled={initializing||!!doing} onClick={()=>void act('Cargando proyectos',refreshAll)}>Primeros proyectos</button>}
        <div className="nav-bottom"><div className="local-engine"><span className={`connected-indicator ${session&&!connectionError&&!initializing?'online':''}`}/><div><strong>{initializing?'Conectando con el núcleo':connectionError?'Conexión por confirmar':session?(active?'Núcleo local conectado':'Última conexión confirmada'):'Conexión pendiente'}</strong><small>{lastConfirmed.current?`Última lectura · ${lastConfirmed.current.toLocaleTimeString('es-ES')}`:'Esperando al núcleo'}</small></div></div><div className="nav-footer"><button className="palette-switch" aria-label={graphite?'Comparar con paleta mineral V5.9':'Activar variante grafito'} title={graphite?'Comparar con V5.9':'Comparar con grafito'} onClick={()=>setGraphite(!graphite)}>{graphite?'Paleta · Grafito':'Paleta · Mineral'}</button><button aria-label={dark?'Activar tema claro':'Activar tema oscuro'} onClick={()=>setDark(!dark)}>{dark?'☼':'◐'}</button></div></div>
      </nav>
      <PaneDivider kind="navigation" container={shell} controls="connected-main" label="Ancho de navegación"/>
      {navOpen&&<button className="connected-nav-backdrop" aria-label="Cerrar navegación" onClick={()=>setNavOpen(false)}/>}
      <main id="connected-main" className="office-workspace" tabIndex={-1} inert={navOpen||undefined}>
        <header className="workspace-header connected-header">
          <div className="breadcrumbs"><button className="connected-menu" aria-expanded={navOpen} aria-label="Mostrar proyectos" onClick={()=>setNavOpen(!navOpen)}>☰</button><span>Oficina</span><span aria-hidden="true">/</span><strong title={sourceLabel}>{sourceLabel}</strong></div>
          <div className="header-actions"><span className="connected-quota" title="Saldo del proyecto seleccionado">{budgetPending?'Cuota pendiente de actualizar':project?`${remainingLabel(project.attempts_consumed)}${connectionError?' · última lectura':''}`:'Cuota por confirmar'}</span>
            <button className="quiet-button" disabled={initializing||!!doing} onClick={()=>connectionError||!session?retryConnection():void act('Actualizando estado',refreshAll)}>{initializing?'Conectando…':connectionError||!session?'Reconectar':'Actualizar'}</button>
          </div>
        </header>
        {(alert||notice)&&<div className={`connected-notice ${alert?'problem':''}`} role={alert?'alert':'status'}><span>{alert?.message||notice}{alert&&<code>{alert.code}</code>}{connectionError&&lastConfirmed.current&&<small>Última confirmación a las {lastConfirmed.current.toLocaleTimeString('es-ES')}.</small>}</span>{!connectionError&&<button aria-label="Cerrar aviso" onClick={()=>{setProblem(null);setNotice('');}}>×</button>}</div>}
        {active&&attempt&&<div className="active-work" role="region" aria-label="Control del trabajo en curso"><div><strong>Trabajo en curso{inspected&&inspected.project_id!==attempt.project_id?` · ${attempt.project_id}`:''}</strong><span title={attempt.objective}>{attempt.objective}</span></div><button className="stop-button" disabled={initializing||!!connectionError||requestingStop||attempt.state==='STOPPING'} onClick={()=>void stopActive()}>■ {attempt.state==='STOPPING'?'Parada solicitada':requestingStop?'Solicitando parada':'Detener trabajo'}</button></div>}
        {pending&&!active&&<div className="pending-bar" role="status"><span>Hay una petición cuya respuesta debemos comprobar antes de crear otra.</span><button className="quiet-button" disabled={initializing||!!doing} onClick={()=>connectionError&&!['HOST_RESPONSE_TIMEOUT','HOST_REQUEST_TIMEOUT'].includes(connectionError.code)?retryConnection():void act('Buscando la reserva',()=>reconcile(pending))}>Comprobar encargo</button>{pendingMissing&&<button className="quiet-button" disabled={initializing||!!doing||!!connectionError} onClick={()=>{try{localStorage.removeItem(pendingKey(pending.office_id));setPending(null);setPendingMissing(false);setNotice('Petición sin reserva descartada. Puedes preparar un encargo nuevo.');}catch{setStorageBlocked(true);}}}>Descartar petición sin reserva</button>}</div>}
        <section ref={surface} className={`connected-surface ${viewed?'with-delivery':''}`} aria-label="Encargo y entrega">
          <section className="connected-director" aria-labelledby={viewed?'director-title':showingFindings?'static-result-title':'desk-title'}>
            {viewed&&<div className="connected-director-heading"><div className="director-signature"><DirectorMark/><strong id="director-title">Director</strong></div><span className={`connected-status ${active&&!inspected&&!connectionError?'active':''}`} role="status">{connectionError&&viewed&&!terminal(viewed.state)?`Último estado · ${status}`:status}</span></div>}
            {!viewed&&<div id="static-workspace" role="region" aria-labelledby={showingFindings?'static-result-title':'desk-title'} className={'brief-desk static-workspace'+(showingFindings?' has-findings':'')}>
              <header className="brief-intro">
                <div className="brief-byline"><DirectorMark/><span>{showingFindings?'Comprobación local':'Director'}</span></div>
                {showingFindings&&staticPage?
                  <h1 id="static-result-title" ref={inspectionTitle} tabIndex={-1}>{findingTitle(staticPage.total)}</h1>:
                  <h1 id="desk-title">¿Qué necesitas revisar?</h1>}
              </header>
              <form className="brief-form" onSubmit={e=>{
                e.preventDefault();
                if(busy||doing||!session)return;
                if(!assisted)changeMode(true);
                else void act('Preparando revisión',prepare);
              }}>
                {!showingFindings&&<div className="brief-writing">
                  <div className="brief-label"><label htmlFor="connected-objective">Tu encargo al Director</label>{objective.length>0&&<small>{objective.length}/2000</small>}</div>
                  <textarea id="connected-objective" name="objective" rows={3} maxLength={2000} value={objective}
                    disabled={busy||!session} placeholder="Por ejemplo, ¿qué campo de este formulario necesita una etiqueta y cómo lo compruebo?"
                    onChange={e=>{invalidate();setObjective(e.target.value);}}
                    onKeyDown={e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)&&!e.nativeEvent.isComposing&&e.nativeEvent.keyCode!==229){
                      e.preventDefault();if(!busy&&!doing&&session){if(assisted)void act('Preparando revisión',prepare);else changeMode(true);}
                    }}}/>
                </div>}
                <div className="brief-source">
                  <span className="brief-file-icon" aria-hidden="true">&lt;/&gt;</span>
                  <div className="brief-file"><button id="static-picker" type="button" className="source-picker"
                    disabled={busy||!!doing||!session} onClick={()=>void act('Eligiendo fuente',pickSource)}>{source?source.filename:'Elegir archivo HTML'}</button>
                    <small>{source?formatBytes(source.bytes)+' · copia de solo lectura':'Archivo adjunto · HTML o HTM · hasta 256 KiB'}</small></div>
                  {source&&<button type="button" className="quiet-button remove-source" aria-label="Quitar fuente del borrador"
                    disabled={busy||!!doing} onClick={()=>{invalidate();setInspection(null);setSource(null);}}>Quitar</button>}
                </div>
                {assisted&&<div className="brief-settings">
                  <div className="connected-model-row"><label htmlFor="connected-model">Modelo local</label>
                    <select id="connected-model" value={modelDigest} disabled={busy||!!doing||catalog!=='ready'||!models.length}
                      onChange={e=>{invalidate();setModelDigest(e.target.value);}}>
                      <option value="" disabled>{catalog==='loading'?'Consultando modelos…':catalogEmpty?'Sin modelos instalados':'Selecciona un modelo'}</option>
                      {models.map(m=><option key={m.model_digest} value={m.model_digest}>{m.model}</option>)}</select>
                    <button type="button" aria-label="Actualizar modelos locales" title="Actualizar modelos locales"
                      disabled={busy||!!doing||!session||catalog==='loading'||exhausted} onClick={()=>void act('Consultando modelos',loadModels)}>↻</button>
                  </div>
                  {!catalogEmpty&&<details className="connected-profile"><summary>Perfil acotado <span>{roleCount} {roleCount===1?'rol':'roles'} · CPU</span></summary>
                    <label htmlFor="connected-roles">Roles secuenciales</label><select id="connected-roles" value={roleCount} disabled={busy||!!doing}
                      onChange={e=>{invalidate();setRoleCount(Number(e.target.value));}}>
                      <option value={1}>1 · Director</option><option value={3}>3 · Director, revisor e integrador</option><option value={7}>7 · Equipo completo</option>
                    </select><p>Los roles usan el mismo modelo por turnos. Cada llamada admite hasta 128 tokens de salida.</p></details>}
                </div>}
                {catalogEmpty&&<section className="model-guide" aria-label="Configurar Ollama">
                  <h2>Instala un modelo para continuar</h2><p>Abre Ollama y descarga un modelo de texto. Por ejemplo, en PowerShell puedes ejecutar <code>ollama pull qwen2.5:0.5b</code>. Después vuelve a consultar el catálogo. Tu borrador sigue aquí.</p>
                  <button type="button" className="quiet-button" disabled={busy||!!doing} onClick={()=>void act('Actualizando catálogo',loadModels)}>Comprobar modelos instalados</button>
                </section>}
                {!showingFindings&&<div className="brief-actions">
                  <div className="brief-primary">
                    {assisted?<button type="submit" className="solid-button" disabled={busy||exhausted||budgetPending||!!doing||catalog!=='ready'||!source||!selectedModel||objective.trim().length<12}>Revisar encargo <span aria-hidden="true">→</span></button>:
                      <button type="button" className="solid-button" disabled={busy||!!doing||!session||catalogEmpty} onClick={()=>changeMode(true)}>Consultar al Director</button>}
                    <small>{exhausted?'3 intentos consumidos · cuota agotada':budgetPending?'Cuota pendiente de actualizar':assisted&&!catalogEmpty&&objective.trim().length>0&&objective.trim().length<12?'Escribe al menos 12 caracteres':'1 intento al autorizar'}</small>
                  </div>
                  <div className="brief-alternative">
                    <button type="button" className="quiet-button" disabled={busy||!!doing||!source||catalogEmpty||catalog==='loading'}
                      onClick={()=>void act('Comprobando HTML',()=>inspectSource())}>Comprobar HTML</button>
                    <small>0 intentos · sin modelo</small>
                  </div>
                </div>}
              </form>
              {showingFindings&&staticPage&&<section className="static-results review-sheet" aria-labelledby="static-result-title">
                <p>{staticPage.total?'Ubicaciones en la copia seleccionada.':'Las reglas aplicadas no detectaron incidencias. Verifica el comportamiento de la página en el navegador.'}</p>
                <FindingList findings={staticPage.findings} offset={staticPage.offset}/>
                {staticPage.total>24&&<div className="static-pages">
                  <button className="quiet-button" disabled={busy||!!doing||staticPage.offset===0} onClick={()=>void act('Leyendo ubicaciones',()=>inspectSource(staticPage.offset-24))}>Anteriores</button>
                  <span>{staticPage.offset+1}–{staticPage.offset+staticPage.findings.length} de {staticPage.total}</span>
                  <button className="quiet-button" disabled={busy||!!doing||staticPage.offset+24>=staticPage.total} onClick={()=>void act('Leyendo ubicaciones',()=>inspectSource(staticPage.offset+24))}>Siguientes</button>
                </div>}
                <div className="review-foot"><button className="quiet-button" disabled={busy||!!doing||catalogEmpty} onClick={()=>changeMode(true)}>Consultar al Director</button>
                  <span>1 intento al autorizar</span><button className="text-repeat" disabled={busy||!!doing||catalogEmpty} onClick={()=>void act('Comprobando HTML',()=>inspectSource())}>Comprobar HTML</button></div>
              </section>}
            </div>}
            {inspected&&attempt&&<div className="history-context"><span>Consultando el historial</span><button className="quiet-button" onClick={()=>{invalidate();setInspected(null);setBrowsedProject(null);}}>{active?'Volver al trabajo en curso':'Volver al último encargo'}</button></div>}
            {viewed&&<div className="connected-conversation"><div className="connected-user-request"><span>Tu encargo</span><h1>{viewed.objective}</h1></div><div className="connected-work-status"><strong>{stateLabels[viewed.state]}</strong><p>{connectionError&&!terminal(viewed.state)?'La pantalla conserva la última lectura. Reconecta para saber si el trabajo sigue en curso.':viewed.state==='STOPPING'?'La parada está solicitada. Esperamos a que el núcleo confirme que sus procesos han terminado.':viewed.state==='RECOVERY_REQUIRED'?'El cierre anterior no quedó confirmado. La recuperación comprobará el proceso y conservará el consumo; no volverá a ejecutar el modelo.':viewed.state==='QUEUED'?'La identidad y el consumo están guardados. Si se interrumpió el arranque, recupera este intento; no lo reenvíes.':viewed.state==='ACCEPTED'?'El informe coincide con las comprobaciones estáticas y sus recibos. Revisa por separado las sugerencias del modelo.':viewed.state==='FAILED'?failureAdvice(viewed.execution_error_code):viewed.state==='CANCELLED'?'El núcleo ha confirmado la parada. El intento consumido se conserva.':viewed.state==='VERIFYING'?'El núcleo está contrastando el informe con la fuente capturada y los recibos.':'La última lectura del registro indica trabajo en curso. Si el proceso se interrumpió, comprueba su recuperación.'}</p></div>
                {viewed.state==='FAILED'&&viewed.execution_error_code&&<p className="execution-code">Código de ejecución <code>{viewed.execution_error_code}</code></p>}
                <section className="call-receipts" aria-labelledby="calls-title">
                  <h2 id="calls-title">Llamadas al modelo</h2>
                  <p>{viewed.model} · hasta {viewed.roles} {viewed.roles===1?'llamada autorizada':'llamadas secuenciales autorizadas'}</p>
                  {viewed.calls?.length ? <ol className="connected-call-list" aria-label="Llamadas del modelo">{viewed.calls.map((call,index)=>{
                    const duration=recordedDuration(call,viewed.observed_ms,!terminal(viewed.state));
                    return <li key={call.seq}><span className="call-order">{index+1}</span><strong>{roles[call.role]||call.role}</strong>
                      <span className="call-fact">{call.state==='DONE'?'Respuesta registrada':call.state==='STARTED'?(connectionError?'En curso en la última lectura':'En curso'):call.state==='INTERRUPTED'?'Interrumpida':call.state}
                        {duration&&<small>{duration}{call.state==='STARTED'?' al último registro':''}</small>}</span></li>;
                  })}</ol>
                    : <p>{viewed.calls?'La última lectura contiene cero llamadas.':'Pendiente de leer las llamadas del encargo.'}</p>}
                </section>
                {active&&!inspected&&<div className="connected-action-row"><button className="quiet-button" disabled={initializing||!!connectionError||!!doing} onClick={()=>void act('Comprobando recuperación',async()=>{putAttempt(await request<Attempt>('attempt.recover',{attempt_id:viewed.id,expected_revision:viewed.revision}));await refreshSnapshot();})}>Comprobar recuperación</button></div>}
                {!active&&!connectionError&&terminal(viewed.state)&&<button className="quiet-button" disabled={!!doing||!!pending} onClick={()=>newTask()}>{drafts.current.has(projectId)?'Volver al borrador':'Preparar otro encargo →'}</button>}
                <AttemptActivity key={session+'·'+viewed.id} office={officeId} session={session} attempt={viewed.id} revision={viewed.cursor??viewed.revision}/>
                {!inspected&&(active||drafts.current.get(viewed.project_id)?.afterAttempt===viewed.id)&&<details key={officeId+':'+viewed.id} className="next-draft">
                  <summary>Preparar el siguiente encargo</summary>
                  <label htmlFor="next-objective">Borrador en esta ventana</label>
                  <textarea id="next-objective" maxLength={2000} rows={3} defaultValue={drafts.current.get(viewed.project_id)?.objective||''}
                    disabled={!drafts.current.has(viewed.project_id)&&drafts.current.size>=20}
                    onInput={e=>noteNext(viewed,e.currentTarget.value)}/>
                  <p>{!drafts.current.has(viewed.project_id)&&drafts.current.size>=20?'Hay veinte borradores abiertos. Recupera uno al terminar.':'Podrás revisarlo y autorizarlo cuando termine el encargo actual.'}</p>
                </details>}
            </div>}
          </section>
          {viewed&&<><PaneDivider kind="director" container={surface} controls="connected-delivery" label="Ancho del Director"/><section id="connected-delivery" className="connected-delivery" aria-label="Entrega"><header><div><span className="eyebrow">Entrega</span><h2>Revisión del documento</h2></div><span className="delivery-state">{report?'Informe recibido':available?'Informe por leer':terminal(viewed.state)?'Sin informe validado':'Esperando informe'}</span></header><div className="connected-tabs" role="tablist" aria-label="Vista de entrega" onKeyDown={tabKey}><button role="tab" tabIndex={resultTab==='report'?0:-1} id="tab-report" aria-controls="panel-report" aria-selected={resultTab==='report'} onClick={()=>setResultTab('report')}>Informe</button><button role="tab" tabIndex={resultTab==='evidence'?0:-1} id="tab-evidence" aria-controls="panel-evidence" aria-selected={resultTab==='evidence'} onClick={()=>setResultTab('evidence')}>Evidencia y alcance</button></div><div className="connected-delivery-body" role="tabpanel" id={resultTab==='report'?'panel-report':'panel-evidence'} aria-labelledby={resultTab==='report'?'tab-report':'tab-evidence'} tabIndex={0}>
            {resultTab==='report'?(report?<ReportView report={report.report}/>:<div className="delivery-empty"><span aria-hidden="true">↳</span><h3>{available?'Informe pendiente de lectura':terminal(viewed.state)?'No hay informe validado':'Aquí aparecerá la entrega'}</h3><p>{available?'La entrega está guardada en el núcleo. Su contenido aún no está disponible en esta vista. Si la lectura falla, pulsa Actualizar para volver a leerla sin ejecutar otro encargo.':terminal(viewed.state)?'Conservamos el intento y su estado. No se presenta una respuesta incompleta como resultado.':'El núcleo publicará el documento después de completar las llamadas y verificar sus recibos.'}</p></div>):<div className="connected-evidence"><h3>Qué puedes comprobar</h3><dl><dt>Documento</dt><dd>{sourceLabel}</dd><dt>Intento</dt><dd>{viewed.id}</dd><dt>Último estado registrado</dt><dd>{viewed.state}</dd><dt>Modelo aprobado</dt><dd>{viewed.model}</dd><dt>Huella del modelo</dt><dd>{viewed.model_digest}</dd><dt>Huella de la fuente</dt><dd>{viewed.source_sha256}</dd><dt>Huella del informe</dt><dd>{report?.meta.sha256||'Todavía no disponible'}</dd></dl>{report&&<p>La lectura comprobó los fragmentos y la huella completa del informe antes de mostrarlo.</p>}<p>La aceptación verifica consistencia estática y procedencia de contenido. No certifica accesibilidad, seguridad ni que las sugerencias del modelo sean correctas.</p>{viewed.execution_error_code&&<p>Código de ejecución: <code>{viewed.execution_error_code}</code></p>}{report&&<details><summary>Informe original de sólo lectura</summary><pre>{report.text}</pre></details>}</div>}
          </div></section></>}
        </section>
        <footer className="connected-footer"><span>{viewed?.model||(assisted?(selectedModel?.model||'Selecciona tu modelo local') :showingFindings?'Análisis estático':'Director')}</span><span>{connectionError?'Último estado guardado':active?'Trabajo acotado en curso':viewed||assisted?'Modelo local · CPU':'Lectura local del archivo'}</span></footer>
      </main>
    </div>
    <dialog ref={approvalDialog} className="connected-approval" aria-labelledby="approval-title" onCancel={e=>{e.preventDefault();setApproval(null);}} onClose={()=>setApproval(null)}>{approval&&<><div className="approval-heading"><span className="eyebrow">Antes de empezar</span><button aria-label="Cerrar revisión" onClick={()=>setApproval(null)}>×</button></div><h2 id="approval-title">Este es el encargo.</h2><p className="approval-objective">{approval.value.objective}</p><dl><dt>Fuente capturada</dt><dd>{source?.filename}</dd><dt>Modelo</dt><dd>{approval.value.model}</dd><dt>Trabajo</dt><dd>Hasta {approval.value.roles} {approval.value.roles===1?'llamada':'llamadas secuenciales'} · CPU · 128 tokens de salida por llamada</dd><dt>Presupuesto</dt><dd>Consumirá 1 intento. Quedan {approval.value.attempts_remaining} antes de empezar.</dd></dl><p>El archivo original no se modifica. Se generará un informe con comprobaciones estáticas y comentarios del modelo.</p><p className="approval-expiry">Vigencia máxima de esta autorización: {approval.value.expires_in_seconds} segundos. Si caduca, vuelve a revisar el encargo.</p><div className="approval-actions"><button className="quiet-button" onClick={()=>setApproval(null)}>Volver al encargo</button><button className="solid-button" disabled={!!doing} onClick={()=>void act('Registrando encargo',start)}>Autorizar y ejecutar →</button></div></>}</dialog>
  </div>;
}
const findingLabels:Record<string,string>={HTML_LANGUAGE_MISSING:'El documento no declara su idioma',HTML_ELEMENT_MISSING:'No se encontró el elemento HTML',DOCUMENT_TITLE_MISSING:'Falta un título de documento no vacío',IMAGE_ALT_MISSING:'Una imagen no tiene atributo alt',CONTROL_LABEL_CANDIDATE:'Un control podría necesitar una etiqueta'};
const findingActions:Record<string,string>={
  HTML_LANGUAGE_MISSING:'Declara en html el idioma principal del contenido, por ejemplo lang="es" si corresponde.',
  HTML_ELEMENT_MISSING:'Comprueba si elegiste un documento completo o un fragmento. Esta revisión espera un documento HTML.',
  DOCUMENT_TITLE_MISSING:'Añade un title descriptivo en head. Debe identificar el propósito de esta página.',
  IMAGE_ALT_MISSING:'Describe la información o función de la imagen. Si sólo decora, usa alt=""; decide según su contexto.',
  CONTROL_LABEL_CANDIDATE:'Comprueba el nombre accesible en el navegador. Añade texto a la etiqueta asociada y comprueba que cada referencia aria-labelledby apunte al elemento correcto.',
};
function formatBytes(bytes:number) {
  return bytes<1024?`${bytes} B`:`${Math.ceil(bytes/1024)} KiB`;
}
function findingTitle(count:number) {
  return count?`${count} ${count===1?'hallazgo para revisar':'hallazgos para revisar'}`:'Sin hallazgos en estas comprobaciones';
}
function FindingList({findings,offset=0}:{findings:Finding[];offset?:number}) {
  return <ol className="finding-list" start={offset+1}>{findings.map((finding,index)=>{
    const {code,line,column}=finding;
    const label=Object.hasOwn(findingLabels,code)?findingLabels[code]:code;
    const action=Object.hasOwn(findingActions,code)?findingActions[code]:undefined;
    const global=code==='DOCUMENT_TITLE_MISSING'||code==='HTML_ELEMENT_MISSING';
    return <li key={`${code}-${line}-${column}-${index}`}>
      <span aria-hidden="true">{String(offset+index+1).padStart(2,'0')}</span>
      <div><strong>{label}</strong>
        <small>Línea {line} · columna {column}{global?' · comprobación global del documento':''}</small>
        {action&&<details className="finding-action">
          <summary aria-label={`Qué revisar: ${label}`}>Qué revisar</summary><p>{action}</p>
        </details>}
      </div>
    </li>;
  })}</ol>;
}
function ReportView({report}:{report:Report}) {
  return <article className="connected-report"><span className="eyebrow">Comprobaciones estáticas</span>
    <h3>{findingTitle(report.findings.length)}</h3><p className="report-scope">{report.findings.length?'Ubicaciones de la captura. Comprueba los candidatos en el navegador.':'Comprueba en el navegador el nombre de los controles y la función de las imágenes.'}</p>
    <FindingList findings={report.findings}/>
    <details className="model-notes"><summary>Comentarios del modelo <span>· sugerencias por revisar</span></summary>
      {report.role_outputs.map((r,index)=><section className="role-commentary" key={`${r.role}-${index}`}><h4>{roles[r.role]||r.role}</h4><p>{r.content}</p></section>)}
    </details></article>;
}
