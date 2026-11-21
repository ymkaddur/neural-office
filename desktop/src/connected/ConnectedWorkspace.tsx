import {useCallback,useEffect,useLayoutEffect,useMemo,useRef,useState} from 'react';
import {AttemptActivity} from './AttemptActivity.tsx';
import {ProjectHistory} from './ProjectHistory.tsx';
import {PaneDivider} from '../workspace/PaneDivider.tsx';
import {hasNativeHost,readReport,request} from './client.ts';
import type {Finding,FindingPage,Report} from './client.ts';
import {acceptAttempt,approvalMatches,approvalScopeMatches,claimPending,releasePending,readPending,recordedDuration,remainingLabel,stateLabels,terminal,validateSnapshot} from './model.ts';
import type {Approval,Attempt,Model,Pending,Project,Snapshot,Source} from './model.ts';
import {readSavedDraft,ReviewDesk} from './ReviewDesk.tsx';
import type {Inspection} from './ReviewDesk.tsx';
import {attachmentApi,directorTextScope,excerptScope} from './attachments.ts';
import {AppearancePanel, CommandSearch, DeskDialog, Icon, useAppearance} from './DeskTools.tsx';
import type {DeskAction} from './DeskTools.tsx';
import './connected.css';
import './desk.css';
import '../office/office.css';
import {Bot} from '../office/TeamView.tsx';
import {Library} from '../office/Library.tsx';
import {Settings} from '../office/Settings.tsx';
import {useInspectionJobs} from './useInspectionJobs.ts';

type AttachmentAPI=ReturnType<typeof attachmentApi>;
type FragmentApproval=Awaited<ReturnType<AttachmentAPI['preview']>>;
type FragmentProposal={report:Inspection;objective:string;thread:string;project:string;scopeError?:string};


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
  HOST_BUSY:'El núcleo tiene otras lecturas pendientes. Actualiza la vista para consultar los datos.',
  ATTACHMENT_READER_BUSY:'Hay otra lectura de archivos en curso.',
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
function workNote(item:Attempt,offline:boolean) {
  if(offline&&!terminal(item.state))return 'La pantalla conserva la última lectura. Reconecta para conocer el estado del encargo.';
  switch(item.state){
    case 'RUNNING':return item.calls?.length?null:'Esperando el primer registro de llamada del modelo local.';
    case 'STOPPING':return 'La parada está solicitada. Esperamos a que el núcleo confirme que sus procesos han terminado.';
    case 'RECOVERY_REQUIRED':return 'El cierre anterior quedó pendiente. La recuperación comprueba el proceso y conserva el consumo.';
    case 'QUEUED':return 'La identidad y el consumo están guardados. Si se interrumpió el arranque, puedes recuperar este intento.';
    case 'ACCEPTED':return 'El informe coincide con las comprobaciones estáticas y sus recibos. Revisa por separado las sugerencias del modelo.';
    case 'FAILED':return failureAdvice(item.execution_error_code);
    case 'CANCELLED':return 'El núcleo ha confirmado la parada. El intento consumido se conserva.';
    case 'REJECTED':return 'El informe no superó la verificación. Puedes consultar el registro de este intento.';
    case 'VERIFYING':return 'El núcleo está contrastando el informe con la fuente capturada y los recibos.';
  }
}

function errorInfo(error:unknown) {
  const raw=error instanceof Error?error.message:'DESKTOP_OPERATION_FAILED';
  const code=/^[A-Z][A-Z0-9_]{0,95}$/.test(raw)?raw:'DESKTOP_OPERATION_FAILED';
  return {code,message:errors[code]||'No se pudo completar esta operación. No reenviamos el encargo automáticamente: comprueba su estado antes de continuar.'};
}
const transportCodes=new Set(['HOST_DISCONNECTED','HOST_CLOSING','HOST_CONNECTION_UNAVAILABLE','HOST_RESPONSE_TIMEOUT','HOST_REQUEST_TIMEOUT','HOST_SIDECAR_START','HOST_SESSION_CHANGED','HOST_PIPE_UNAVAILABLE','HOST_RESPONSE_INVALID','HOST_REQUEST_FAILED','HOST_CONFIGURATION_REQUIRED','HOST_CONFIGURATION_INVALID']);
const readTimeout=(code:string)=>code==='HOST_REQUEST_TIMEOUT'||code==='HOST_RESPONSE_TIMEOUT';
const deliveryTabs={activity:'Actividad',report:'Informe',evidence:'Evidencia y alcance'} as const;
type DeliveryTab=keyof typeof deliveryTabs;
const tabOrder=Object.keys(deliveryTabs) as DeliveryTab[];
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
  const attachments=useMemo(()=>attachmentApi(request),[officeId,session]);
  const inspectionJobs=useInspectionJobs(officeId,session);
  const [draftThreads,setDraftThreads]=useState<Record<string,{project:string;thread:string;title:string}>>({});
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
  const [approval,setApproval]=useState<{value:Approval;excerpts?:FragmentApproval;expiresAt:number}|null>(null);
  const [attempt,setAttempt]=useState<Attempt|null>(null);
  const [pending,setPending]=useState<Pending|null>(null);
  const [pendingMissing,setPendingMissing]=useState(false);
  const [storageBlocked,setStorageBlocked]=useState(false);
  const [loadedReport,setReport]=useState<LoadedReport|null>(null);
  const [reportProblem,setReportProblem]=useState<{id:string;code:string}|null>(null);
  const [reportReadRevision,setReportReadRevision]=useState(0);
  const [doing,setDoing]=useState('');
  const stopFlight=useRef<symbol|null>(null);
  const [requestingStop,setRequestingStop]=useState(false);
  const [budgetPending,setBudgetPending]=useState(false);
  const [unconfirmedActive,setUnconfirmedActive]=useState<string|null>(null);
  const [problem,setProblem]=useState<ReturnType<typeof errorInfo>|null>(null);
  const [notice,setNotice]=useState('');
  const appearance=useAppearance(),dark=appearance.dark;
  const [section,setSection]=useState<'projects'|'library'|'settings'>('projects');
  const [openedReport,setOpenedReport]=useState<Inspection|null>(null);
  const [returnTo,setReturnTo]=useState<{report?:string;instruction?:string}|null>(null);
  const consumeReturn=useCallback(()=>setReturnTo(null),[]);
  const [deskPage,setDeskPage]=useState<'thread'|'html'|'attempt'>('thread');
  const [panel,setPanel]=useState<'appearance'|'search'|'project'|null>(null);
  const [projectName,setProjectName]=useState('');
  const [inspector,setInspector]=useState(false);
  const [threadByProject,setThreadByProject]=useState<Record<string,string>>({});
  const [threadRows,setThreadRows]=useState<{project:string;rows:Awaited<ReturnType<typeof attachments.threads>>}|null>(null);
  const [threadRevision,setThreadRevision]=useState(0);
  const [fragmentProposal,setFragmentProposal]=useState<FragmentProposal|null>(null);
  const fragmentOrigin=useRef<HTMLElement|null>(null);
  const proposalGeneration=useRef(0);
  function dismissProposal(){proposalGeneration.current++;setFragmentProposal(null);}
  const [navOpen,setNavOpen]=useState(false);
  const [tabChoice,setTabChoice]=useState<{attempt:string;tab:DeliveryTab}|null>(null);
  const shell=useRef<HTMLDivElement>(null),surface=useRef<HTMLElement>(null),approvalDialog=useRef<HTMLDialogElement>(null);
  const mounted=useRef(false),operation=useRef(false),generation=useRef(0),sessionRef=useRef(''),officeRef=useRef('');
  const currentAttempt=useRef<Attempt|null>(null),previousFocus=useRef<HTMLElement|null>(null),navOpener=useRef<HTMLElement|null>(null);
  // Unsent text stays in this window only. Cap storage without silently evicting work.
  const drafts=useRef(new Map<string,Draft>());
  const active=attempt!==null&&!terminal(attempt.state);
  const viewed=inspected??attempt;
  const sourceLabel=viewed?(viewed.source_name||`HTML · ${viewed.source_sha256.slice(0,12)}`):(source?.filename||'Nuevo encargo');
  const navProject=browsedProject??projectId;
  const threadId=threadByProject[navProject]??'main';
  const persistedThreads=threadRows?.project===navProject?threadRows.rows:[];
  const currentThreads=[...persistedThreads,...Object.values(draftThreads).filter(t=>t.project===navProject&&!persistedThreads.some(p=>p.id===t.thread)).map(t=>({id:t.thread,objective:t.title,created_at:0}))];
  const threadTitle=currentThreads.find(t=>t.id===threadId)?.objective||'Nuevo hilo';
  const project=snapshot?.projects.find(p=>p.id===navProject)??(pagedProject&&snapshot&&
    pagedProject.value.id===navProject&&pagedProject.session===snapshot.session_id&&pagedProject.office===snapshot.office_id&&
    pagedProject.revision===snapshot.revision?pagedProject.value:null);
  const resultTab:DeliveryTab=viewed&&tabChoice?.attempt===viewed.id?tabChoice.tab:viewed&&!terminal(viewed.state)?'activity':'report';
  const report=loadedReport&&loadedReport.meta.attempt_id===viewed?.id&&loadedReport.report.source_sha256===viewed?.source_sha256?loadedReport:null;
  const alert=connectionError??problem;
  const busy=initializing||active||!!pending||storageBlocked||!!connectionError;
  const exhausted=!!project&&project.attempts_consumed>=3;
  const available=viewed?.state==='ACCEPTED'&&viewed.report_available;
  const staticPage=source&&inspection?.token===source.entry_token&&inspection.page.session_id===session?inspection.page:null;
  const showingFindings=!!staticPage&&!assisted;
  const threadResponse=viewed?.analysis_scope===directorTextScope||viewed?.analysis_scope===excerptScope;
  const note=threadResponse&&viewed?.state==='ACCEPTED'?'La respuesta del modelo está disponible en el hilo del encargo.':viewed?workNote(viewed,!!connectionError):null;
  const selectedModel=models.find(m=>m.model_digest===modelDigest);
  const status=threadResponse&&viewed?.state==='ACCEPTED'?'Comentario recibido':viewed?stateLabels[viewed.state]:pending?'Comprobando un encargo anterior':session?'Listo para un encargo':'Conectando con tu oficina';
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
  function invalidate(){generation.current++;dismissProposal();setApproval(null);setProblem(null);setNotice('');}
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
    setProblem(null);setCatalog('loading');
    try {
      const result=await request<{models:Model[];session_id:string;cached?:boolean}>('models.list');
      if(!current())return;
      if(result.session_id!==sessionRef.current)throw Error('HOST_SESSION_CHANGED');
      if(result.cached===true)throw Error('MODEL_CATALOG_BUSY');
      if(!Array.isArray(result.models)||result.models.length>64||result.models.some(m=>!m||typeof m.model!=='string'||!/^[a-f0-9]{64}$/.test(m.model_digest)))throw Error('MODEL_CONTRACT');
      setModels(result.models);
      setCatalogEmpty(result.models.length===0);
      setModelDigest(old=>result.models.some(m=>m.model_digest===old)?old:(result.models[0]?.model_digest||''));
      setCatalog('ready');
    } catch(error) {
      if(!current())return;
      setModels([]);setModelDigest('');setCatalog('error');
      const issue=errorInfo(error);
      if(readTimeout(issue.code))setProblem({code:issue.code,message:'El catálogo de modelos no respondió. Puedes comprobar el HTML con las reglas locales.'});
      else noteError(error);
    }
  }
  async function act(label:string,work:()=>Promise<void>) {
    if(label==='Preparando revisión')previousFocus.current=document.activeElement as HTMLElement;
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
        if(previousOffice!==description.office_id){setDraftThreads({});setThreadByProject({});drafts.current.clear();setObjective('');setProjectId(makeProject());setReport(null);setAttempt(null);currentAttempt.current=null;}
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
            const other=await releasePending(localStorage,saved);
            if(!live)return;
            setPending(other);restoreActive=true;
          }else {putAttempt(found);setDeskPage('attempt');}
          setNotice('Encargo recuperado por su identidad original. No se ha vuelto a ejecutar.');
        }
        else {setPendingMissing(true);setNotice('El núcleo no tiene una reserva para esta identidad. No se ha reenviado nada.');}
      }
      if(!saved||restoreActive) {
        const activeProject=first.projects.find(p=>p.active)||first.projects[0];
        if(activeProject)setProjectId(activeProject.id);
        const unresolved=activeRow??(previousOffice===first.office_id?previousAttempt:null);
        if(unresolved){
          setProjectId(unresolved.project_id);putAttempt(unresolved);setDeskPage('attempt');setUnconfirmedActive(unresolved.id);
          const next=await request<Attempt>('attempt.get',{attempt_id:unresolved.id});
          if(!live)return;
          if(next.id!==unresolved.id||next.project_id!==unresolved.project_id)throw Error('ATTEMPT_IDENTITY_CHANGED');
          if(next.session_id&&next.session_id!==description.session_id)throw Error('HOST_SESSION_CHANGED');
          putAttempt(next);setUnconfirmedActive(null);
        }else if(!previousOffice){
          // Restore the navigation address only after the authority has checked pending and active work.
          let address:unknown;
          try{address=JSON.parse(sessionStorage.getItem('office-thread:'+description.office_id)??'null');}catch{/* Storage is optional. */}
          if(Array.isArray(address)&&address.length===2&&address.every(v=>typeof v==='string'&&v.length>0&&v.length<=120)){
            const [project,thread]=address;
            if(first.projects.some(p=>p.id===project)||readSavedDraft(first.office_id,project,thread)){setProjectId(project);setThreadByProject(old=>({...old,[project]:thread}));}
          }
        }
      }
      // Static inspection has no dependency on the model catalog.
    }).catch(error=>{if(live)noteError(error);}).finally(()=>{if(live)setInitializing(false);});
    return ()=>{live=false;mounted.current=false;generation.current++;};
  },[native,handshake]);
  useEffect(()=>{
    if(!assisted||!session||attempt||exhausted||initializing||connectionError)return;
    void loadModels();
    return ()=>{catalogRead.current++;};
  },[assisted,session,!!attempt,exhausted,initializing,!!connectionError]);
  useEffect(()=>{if(staticPage&&!assisted)inspectionTitle.current?.focus();},[staticPage,assisted]);
  useEffect(()=>{
    if(!officeId||!session||initializing||connectionError)return;
    let live=true;
    void attachments.threads(navProject).then(rows=>{if(live)setThreadRows({project:navProject,rows});})
      .catch(e=>{if(live){setThreadRows(null);setProblem(errorInfo(e));}});
    return ()=>{live=false;};
  },[officeId,session,navProject,initializing,!!connectionError,threadRevision]);
  useEffect(()=>{
    const shortcut=(e:KeyboardEvent)=>{
      if(e.defaultPrevented||e.isComposing||e.keyCode===229||e.altKey||!(e.ctrlKey||e.metaKey)||document.querySelector('dialog[open]'))return;
      const next=e.key.toLowerCase()==='k'?'search':e.key===','?'appearance':null;
      if(next){e.preventDefault();setNavOpen(false);if(next==='appearance'){setPanel(null);setSection('settings');}else setPanel(next);}
    };
    window.addEventListener('keydown',shortcut);return ()=>window.removeEventListener('keydown',shortcut);
  },[]);
  useLayoutEffect(()=>{
    const dialog=approvalDialog.current;
    if(approval&&!dialog?.open){dialog?.showModal();}
    if(!approval&&dialog?.open){dialog.close();const target=previousFocus.current;requestAnimationFrame(()=>{if(target?.isConnected&&!target.hasAttribute('disabled'))target.focus();else document.getElementById('connected-main')?.focus();});}
    if(!approval)return;
    const timer=setTimeout(()=>{
      setApproval(null);
      setProblem(errorInfo(Error('APPROVAL_INVALID_OR_EXPIRED')));
    },Math.max(0,Math.ceil(approval.expiresAt-performance.now())));
    return()=>clearTimeout(timer);
  },[approval]);
  useEffect(()=>{
    if(!attempt||!terminal(attempt.state)||!pending||attempt.request_key!==pending.idempotency_key||attempt.project_id!==pending.project_id)return;
    let current=true;
    void releasePending(localStorage,pending).then(other=>{if(current){setPending(other);setPendingMissing(false);}}).catch(()=>{if(current)setStorageBlocked(true);});
    return ()=>{current=false;};
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
        putAttempt(next);setUnconfirmedActive(null);
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
    setReport(null);setReportProblem(null);
    if(!viewed||!available)return;
    let live=true;const id=viewed.id;
    void readReport(request,id,()=>live).then(result=>{
      if(!live)return;
      if(result.report.source_sha256!==viewed.source_sha256)throw Error('REPORT_SOURCE_CHANGED');
      setReport(result);
    }).catch(error=>{
      if(!live)return;
      const issue=errorInfo(error);
      if(transportCodes.has(issue.code)&&!readTimeout(issue.code))noteError(error);
      else setReportProblem({id,code:issue.code});
    });
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
    if(!source||busy)return;
    const expected=epoch();
    const page=await request<FindingPage>('source.check',{project_id:projectId,entry_token:source.entry_token,offset});
    if(!mounted.current||expected!==epoch())return;
    if(page.session_id!==session||page.project_id!==projectId||page.source_sha256!==source.sha256||
       page.offset!==offset||!Number.isSafeInteger(page.total)||page.total<offset||
       (offset>0&&page.total===offset)||!Array.isArray(page.findings)||
       page.findings.length!==Math.min(24,page.total-offset)||page.findings.some(f=>
         !f||!Object.hasOwn(findingLabels,f.code)||!Number.isSafeInteger(f.line)||f.line<1||
         !Number.isSafeInteger(f.column)||f.column<1))throw Error('SOURCE_CHECK_CONTRACT');
    catalogRead.current++;
    if(catalog==='loading')setCatalog('idle');
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
    const bound=reviewed?.excerpts;
    const fragmentValid=!!bound&&bound===reviewed?.value&&bound.project_id===navProject&&bound.session_id===session&&bound.thread_id===threadId&&bound.model_digest===modelDigest;
    if(!reviewed||(bound?!fragmentValid:!approvalMatches(reviewed.value,session,source,objective,modelDigest,roleCount,reviewed.expiresAt,performance.now()))){setApproval(null);throw Error('APPROVAL_CHANGED');}
    const identity={office_id:officeId,project_id:reviewed.value.project_id,idempotency_key:crypto.randomUUID()};
    try{
      const other=await claimPending(localStorage,identity);
      if(other){setPending(other);setPendingMissing(false);setApproval(null);setNotice('Hay otra petición registrada en esta oficina. Comprueba su identidad antes de autorizar otra consulta.');return;}
    }catch{setStorageBlocked(true);throw Error('PENDING_IDENTITY_NOT_SAVED');}
    setPending(identity);setPendingMissing(false);setBudgetPending(true);setApproval(null);
    // Identity is durable before send. Any ambiguous failure remains reconcilable.
    const next=await request<Attempt>('attempt.start',{approval_token:reviewed.value.approval_token,idempotency_key:identity.idempotency_key,expected_revision:reviewed.value.expected_revision});
    if(!mounted.current)return;
    if(next.project_id!==identity.project_id||next.request_key!==identity.idempotency_key)throw Error('ATTEMPT_IDENTITY_CHANGED');
    drafts.current.delete(identity.project_id);setProjectId(identity.project_id);setBrowsedProject(null);setDeskPage(bound?'thread':'attempt');
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
  function openThread(project:string,id:string,reportId?:string){
    if(unconfirmedActive&&project!==currentAttempt.current?.project_id)return;
    setSection('projects');setReturnTo(reportId?{report:reportId}:null);setOpenedReport(null);
    invalidate();
    if(active){setBrowsedProject(project);setInspected(null);}else openDraft(project);
    setThreadByProject(old=>({...old,[project]:id}));setDeskPage('thread');setNavOpen(false);
    try{sessionStorage.setItem('office-thread:'+officeId,JSON.stringify([project,id]));}catch{/* The live view already holds this selection. */}
  }
  function newTask(newProject=false) {
    if(newProject&&unconfirmedActive)return;
    setInspector(false);
    openThread(newProject?makeProject():navProject,crypto.randomUUID());
  }
  function chooseProject(id:string) {
    openThread(id,threadByProject[id]??'main');
  }
  async function chooseAttempt(item:Attempt) {
    if(unconfirmedActive&&item.id!==unconfirmedActive)return;
    setDeskPage('attempt');
    if(!retainDraft())return;
    setNavOpen(false);
    invalidate();const expected=epoch();
    let next:Attempt;
    try{next=await request<Attempt>('attempt.get',{attempt_id:item.id});}
    catch(error){
      if(!mounted.current||expected!==epoch())return;
      const issue=errorInfo(error);
      if(!readTimeout(issue.code))throw error;
      setProblem({code:issue.code,message:'No se pudo abrir el encargo del historial. Puedes volver a seleccionarlo.'});
      return;
    }
    if(!mounted.current||expected!==epoch())return;
    if(next.id!==item.id||next.project_id!==item.project_id)throw Error('ATTEMPT_IDENTITY_CHANGED');
    if(next.session_id&&next.session_id!==sessionRef.current)throw Error('HOST_SESSION_CHANGED');
    setNavOpen(false);
    if(currentAttempt.current&&currentAttempt.current.id!==item.id&&(active||!terminal(currentAttempt.current.state))){
      setBrowsedProject(next.project_id);setInspected(next.id===currentAttempt.current.id?null:next);
    }else{
      confirmConnection();
      setInspected(null);setBrowsedProject(null);setSource(null);setProjectId(next.project_id);putAttempt(next);
    }
  }
  function tabKey(event:{key:string;preventDefault:()=>void}) {
    if(!viewed||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();
    const i=tabOrder.indexOf(resultTab);
    const next=event.key==='Home'?tabOrder[0]:event.key==='End'?tabOrder[tabOrder.length-1]:tabOrder[(i+(event.key==='ArrowRight'?1:-1)+tabOrder.length)%tabOrder.length];
    setTabChoice({attempt:viewed.id,tab:next});requestAnimationFrame(()=>document.getElementById(`tab-${next}`)?.focus());
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
      else if(currentAttempt.current?.id===item.id){putAttempt(next);setUnconfirmedActive(null);}
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

  const stopControl=active&&attempt?<button className="stop-button" disabled={initializing||!!connectionError||requestingStop||attempt.state==='STOPPING'} onClick={()=>void stopActive()}>■ {attempt.state==='STOPPING'?'Parada registrada':requestingStop?'Solicitando parada':'Detener trabajo'} · {attempt.project_id}</button>:null;
  const localStops=inspectionJobs.jobs.filter(j=>j.state==='reading'||j.state==='stopping').map(j=><div className="local-read-control" key={j.key}><span><Icon name="clock"/> {j.project} · Inspección local</span><button className="stop-button" disabled={j.state==='stopping'} onClick={()=>void inspectionJobs.stop(j).catch(noteError)}>{j.state==='stopping'?'Parada solicitada':'Detener lectura'} · {j.project}</button></div>);
  const allStops=<>{stopControl}{localStops}</>;
  const searchReports=useCallback((query:string)=>request<{id:string;thread_id:string;objective:string}[]>('attachments.search',{project_id:navProject,query}),[navProject,session]);
  function recoverAttempt(item:Attempt){
    if(stopFlight.current)return;
    const peer=peerGeneration.current;
    const stillHere=()=>mounted.current&&peer===peerGeneration.current&&currentAttempt.current?.id===item.id;
    function verifyIdentity(value:Attempt){
      if(value.id!==item.id||value.project_id!==item.project_id||value.session_id!==sessionRef.current)throw Error('ATTEMPT_IDENTITY_CHANGED');
    }
    void act('Comprobando el propietario de la consulta',async()=>{
      for(let turn=0;turn<2;turn++){
        const current=await request<Attempt>('attempt.get',{attempt_id:item.id});
        if(!stillHere())return;
        verifyIdentity(current);
        if(terminal(current.state)){putAttempt(current);break;}
        try{
          const restored=await request<Attempt>('attempt.recover',{attempt_id:item.id,expected_revision:current.revision});
          if(!stillHere())return;
          verifyIdentity(restored);putAttempt(restored);break;
        }catch(error){
          if(!stillHere())return;
          if(error instanceof Error&&error.message==='DESKTOP_REVISION_CHANGED'&&turn===0)continue;
          if(!(error instanceof Error)||error.message!=='OFFICE_RUNNER_STILL_ACTIVE')throw error;
          putAttempt(current);setNotice('El núcleo confirma que la consulta sigue en ejecución.');break;
        }
      }
      if(stillHere())await refreshSnapshot();
    });
  }
  const commands:DeskAction[]=[
    {id:'appearance',name:'Apariencia y lectura',run:()=>setSection('settings')},
    {id:'library',name:'Memoria y skills del proyecto',run:()=>setSection('library')},
    {id:'legacy-review',name:'Revisión especializada de HTML',run:()=>{setSection('projects');if(!active)openDraft(navProject);setDeskPage(active?'attempt':'html');}},
    {id:'inspector',name:inspector?'Ocultar inspector':'Abrir inspector',run:()=>setInspector(v=>!v)},
    ...(!busy&&!doing?[{id:'new',name:'Nuevo hilo',run:()=>newTask()}]:[]),
    ...(snapshot?.projects??[]).filter(p=>!unconfirmedActive||p.id===attempt?.project_id).map(p=>({id:'p-'+p.id,name:p.id,detail:'Proyecto',run:()=>chooseProject(p.id)})),
    ...currentThreads.map(t=>({id:'t-'+t.id,name:t.objective||'Hilo de revisión',detail:navProject,run:()=>openThread(navProject,t.id)})),
    ...(snapshot?.attempts??[]).filter(a=>!unconfirmedActive||a.id===unconfirmedActive).map(a=>({id:'a-'+a.id,name:a.objective,detail:a.project_id,run:()=>void act('Abriendo encargo',()=>chooseAttempt(a))})),
  ];
  async function previewFragments(){
    const proposal=fragmentProposal;
    if(!proposal||!selectedModel||busy||exhausted||proposal.thread!==threadId||proposal.project!==navProject)return;
    const before=performance.now(),expected=epoch(),ticket=proposalGeneration.current;
    let result:Awaited<ReturnType<typeof attachments.preview>>;
    try {
      result=await attachments.preview(proposal.project,proposal.thread,proposal.report.id,modelDigest,proposal.objective);
    }catch(error){
      if(!mounted.current||expected!==epoch()||ticket!==proposalGeneration.current)return;
      const code=error instanceof Error?error.message:'';
      if(code!=='EXCERPT_BUDGET'&&code!=='NO_CITED_EXCERPTS')throw error;
      const scopeError=code==='NO_CITED_EXCERPTS'?'La entrega carece de citas aptas para esta consulta. Abre una fuente y delimita el encargo.':
        proposal.report.attachments.length?'El permiso admite hasta 8 citas distintas y 4.608 bytes en total, incluidas sus referencias. Cierra la consulta e inspecciona menos fragmentos.':
        'El texto supera los 4.608 bytes del permiso. Acorta el encargo y vuelve a enviarlo.';
      setFragmentProposal({...proposal,scopeError});
      return;
    }
    const expires=before+result.expires_in_seconds*1000;
    if(!mounted.current||expected!==epoch()||ticket!==proposalGeneration.current)return;
    const textOnly=proposal.report.attachments.length===0&&proposal.report.findings.some(f=>f.rule==='text_brief');
    const scopeMatches=Array.isArray(result.fragments)&&(textOnly
      ?result.analysis_scope===directorTextScope&&result.fragments.length===0&&proposal.objective===proposal.report.objective
      :(!result.analysis_scope||result.analysis_scope===excerptScope)&&result.fragments.length>=1&&result.fragments.length<=8);
    if(!scopeMatches||result.project_id!==proposal.project||result.thread_id!==proposal.thread||result.report_id!==proposal.report.id||result.session_id!==session||result.model_digest!==modelDigest||result.objective!==proposal.objective||result.roles!==1||result.attempts_remaining<1||!Number.isFinite(expires)||expires<=performance.now())throw Error('APPROVAL_CHANGED');
    previousFocus.current=fragmentOrigin.current;dismissProposal();setApproval({value:result,excerpts:result,expiresAt:expires});
  }
  if(!native)return <main className={`v541 connected offline ${dark?'theme-dark':''}`}>
    <div className="offline-wordmark"><DirectorMark/><strong>Neural Office</strong><span>V5.35</span></div>
    <section className="offline-content"><span className="eyebrow">Neural Office · Escritorio Windows</span><h1>Revisa una entrega con el Director</h1><p>Abre Neural Office en Windows para adjuntar documentos, comprobar sus fuentes y consultar a tu modelo local.</p><p>Las instrucciones están en <code>desktop/README.md</code>, dentro de la descarga.</p>{import.meta.env.DEV&&<a className="solid-button" href="?preview=1&screen=ready">Galería histórica de desarrollo →</a>}<p className="offline-note">Esta página no ejecuta encargos.</p></section>
    <footer>Software gratuito · Tus modelos locales · Apoyo voluntario</footer>
  </main>;

  return <div className={`v541 connected desk513 arcade535 ${dark?'theme-dark':''}`} data-density={appearance.prefs.density} data-contrast={appearance.prefs.contrast} data-motion={appearance.prefs.motion} style={{'--desk-scale':appearance.prefs.scale/100} as React.CSSProperties}>
    <header className="desk-titlebar"><div className="desk-brand"><Bot role="director"/><strong>Neural Office</strong></div>
      <nav className="arc-global" aria-label="Navegación principal">{([['projects','Proyectos'],['library','Memoria y skills'],['settings','Ajustes']] as const).map(([id,label])=><button key={id} aria-current={section===id?'page':undefined} onClick={()=>{setSection(id);setNavOpen(false);}}>{label}</button>)}</nav>
      <button className="arc-search" aria-label="Buscar hilo o acción" title="Buscar · Ctrl K" onClick={()=>setPanel('search')}><Icon name="search"/></button>
      <div className="engine-state"><i className={session&&!connectionError&&!initializing?'ready':''}/>{initializing?'Conectando':connectionError?'Sin conexión':session?'Núcleo local':'Conexión pendiente'}</div></header>
    <div ref={shell} className={`office-shell connected-shell ${navOpen?'nav-open':''}`}>
      <nav className="office-nav connected-nav" aria-label="Proyectos y encargos">
        {navOpen&&<div className="nav-stop">{allStops}</div>}
        <button className="connected-close-nav" onClick={()=>setNavOpen(false)}>Cerrar proyectos ×</button>
        <button className="new-task" disabled={busy||!!doing} onClick={()=>newTask()}><span aria-hidden="true">＋</span> Nuevo hilo</button>
        <div className="connected-nav-heading">Proyectos <button aria-label="Crear otro proyecto" title="Crear otro proyecto" disabled={busy||!!doing} onClick={()=>{if(deskPage==='html'){newTask(true);setDeskPage('html');}else{setProjectName('');setNavOpen(false);setPanel('project');}}}>＋</button></div>
        <div className="connected-projects">{snapshot?.projects.map(p=><button key={p.id} className={p.id===navProject?'selected':''} disabled={initializing||!!doing||!!connectionError||(!!unconfirmedActive&&p.id!==attempt?.project_id)||(!active&&(!!pending||storageBlocked))} onClick={()=>chooseProject(p.id)} title={p.id}><Icon name="folder"/><span>{p.id}</span><small>{p.attempts_consumed}/3 usados</small></button>)}{!snapshot?.projects.some(p=>p.id===projectId)&&<div className="connected-new-project"><span title={projectId}>{projectId}</span>{project?.id===projectId&&!budgetPending&&<small>{remainingLabel(project.attempts_consumed)}</small>}</div>}</div>
        <div className="nav-threads">{currentThreads.map(t=><button key={t.id} className={t.id===threadId&&deskPage==='thread'?'chosen':''} title={t.objective||'Hilo de revisión'} aria-current={t.id===threadId&&deskPage==='thread'?'page':undefined} onClick={()=>openThread(navProject,t.id)}><Icon name="thread"/><span>{t.objective||'Hilo de revisión'}</span></button>)}</div>
        <ProjectHistory key={JSON.stringify([snapshot?.office_id,snapshot?.session_id,navProject])} project={navProject} showProjectName={navProject!==projectId} snapshot={snapshot} current={attempt} selected={viewed?.id}
          offline={!!connectionError||initializing} disabled={initializing||!!connectionError||!!doing||(!active&&!!pending)} onOpen={a=>void act('Abriendo encargo',()=>chooseAttempt(a))}
          onRefresh={()=>act('Actualizando historial',refreshAll)}/>
        {snapshot?.has_more.projects&&<button className="nav-secondary" disabled={initializing||!!doing} onClick={()=>void act('Cargando proyectos',nextProjects)}>Siguientes proyectos →</button>}
        {snapshot&&snapshot.next.project_after>100&&<button className="nav-secondary" disabled={initializing||!!doing} onClick={()=>void act('Cargando proyectos',refreshAll)}>Primeros proyectos</button>}
        <div className="nav-bottom"><button className="nav-setting" onClick={()=>{setNavOpen(false);setSection('settings');}}><Icon name="settings"/> Ajustes <kbd>Ctrl ,</kbd></button></div>
      </nav>
      <PaneDivider kind="navigation" container={shell} controls="connected-main" label="Ancho de navegación"/>
      {navOpen&&<button className="connected-nav-backdrop" aria-label="Cerrar navegación" onClick={()=>setNavOpen(false)}/>}
      <main id="connected-main" className="office-workspace" tabIndex={-1} inert={navOpen||undefined}>
        <header className="workspace-header connected-header">
          <div className="breadcrumbs"><button className="connected-menu" aria-expanded={navOpen} aria-label="Mostrar proyectos" onClick={()=>setNavOpen(!navOpen)}>☰</button><Icon name="folder"/><span>{navProject}</span><Icon name="arrow"/><strong>{section==='settings'?'Ajustes':section==='library'?'Memoria y skills':deskPage==='thread'?threadTitle:sourceLabel}</strong></div>
          <div className="header-actions" hidden={section!=='projects'}><span className="connected-quota" id="project-balance" role="group" aria-label={'Saldo del proyecto '+navProject}><span className="balance-owner">{navProject}</span><span>{budgetPending?'Cuota pendiente de actualizar':project?`${remainingLabel(project.attempts_consumed)}${connectionError?' · última lectura':''}`:'Cuota por confirmar'}</span></span>
            {deskPage==='thread'?<button className="desk-inspect-toggle" aria-pressed={inspector} onClick={()=>setInspector(v=>!v)}><Icon name="panel"/> Inspector</button>:<button className="quiet-button" onClick={()=>openThread(navProject,viewed?.thread_id??threadId)}>Volver al hilo</button>}
            <button className="quiet-button refresh-core" disabled={initializing||!!doing} onClick={()=>connectionError||!session?retryConnection():void act('Actualizando estado',refreshAll)}>{initializing?'Conectando…':connectionError||!session?'Reconectar':'Actualizar'}</button>
          </div>
        </header>
        {(alert||notice)&&<div className={`connected-notice ${alert?'problem':''}`} role={alert?'alert':'status'}><span>{alert?.message||notice}{alert&&<code>{alert.code}</code>}{connectionError&&lastConfirmed.current&&<small>Última confirmación a las {lastConfirmed.current.toLocaleTimeString('es-ES')}.</small>}</span>{!connectionError&&<button aria-label="Cerrar aviso" onClick={()=>{setProblem(null);setNotice('');}}>×</button>}</div>}
        {active&&attempt&&<div className="active-work" role="region" aria-label="Control del trabajo en curso"><button className="inline-link" onClick={()=>{setSection('projects');setInspected(null);setBrowsedProject(null);setDeskPage('attempt');}}><Icon name="activity"/><span>{attempt.project_id} · {stateLabels[attempt.state]}</span><small>{attempt.objective}</small></button>{stopControl}</div>}
        {localStops}
        {pending&&!active&&<div className="pending-bar" role="status"><span>Hay una petición cuya respuesta debemos comprobar antes de crear otra.</span><button className="quiet-button" disabled={initializing||!!doing} onClick={()=>connectionError&&!['HOST_RESPONSE_TIMEOUT','HOST_REQUEST_TIMEOUT'].includes(connectionError.code)?retryConnection():void act('Buscando la reserva',()=>reconcile(pending))}>Comprobar encargo</button>{pendingMissing&&<button className="quiet-button" disabled={initializing||!!doing||!!connectionError} onClick={()=>void act('Revisando la petición pendiente',async()=>{try{const other=await releasePending(localStorage,pending);setPending(other);setPendingMissing(false);setNotice(other?'Hay otra petición pendiente en esta oficina.':'Petición sin reserva descartada. Puedes preparar un encargo nuevo.');}catch{setStorageBlocked(true);}})}>Descartar petición sin reserva</button>}</div>}
        {section==='settings'?<Settings appearance={appearance} models={models} model={modelDigest} choose={setModelDigest} load={()=>void loadModels()} catalog={catalog} project={navProject} online={!!session&&!connectionError} quota={project&&!budgetPending?remainingLabel(project.attempts_consumed):'Por confirmar'}/>:section==='library'?<Library key={officeId+':'+navProject} project={navProject} online={!!session&&!connectionError} source={openedReport?.project_id===navProject?openedReport:null}
          openSource={(thread,id)=>{openThread(navProject,thread);setReturnTo({report:id});}} useSkill={instruction=>{setReturnTo({instruction});setSection('projects');setDeskPage('thread');}}/>:deskPage==='thread'?<ReviewDesk consumeReturn={consumeReturn} onReport={setOpenedReport} returnTo={returnTo} renderConsultation={reportId=>{
          const attached=viewed?.inspection_id===reportId&&viewed.thread_id===threadId&&viewed.project_id===navProject?viewed:null;
          if(!attached){
            const archived=snapshot?.attempts.filter(a=>a.inspection_id===reportId&&a.project_id===navProject&&a.thread_id===threadId)??[];
            return archived.map(a=><button key={a.id} className="history-entry" onClick={()=>void act('Abriendo consulta',()=>chooseAttempt(a))}>Consulta {a.ordinal} · {a.model}<span>{stateLabels[a.state]}</span></button>);
          }
          return <section className="thread-consult" aria-label="Consulta de este hilo">
            <div className="source-label">Consulta {attached.ordinal} · {attached.model}</div>
            <AttemptActivity key={session+attached.id} office={officeId} session={session} attempt={attached.id} revision={attached.cursor??attached.revision}/>
            {active&&!inspected&&!terminal(attached.state)&&<button className="inline-link" disabled={initializing||!!connectionError||!!doing||requestingStop} onClick={()=>recoverAttempt(attached)}>Comprobar recuperación</button>}
            {report?.report.inspection_id===reportId?<ReportView report={report.report} limited={report.meta.generation_limited}/>:<p role="status">{attached.state==='ACCEPTED'?'Recuperando el comentario':stateLabels[attached.state]}</p>}
            <button className="inline-link" onClick={()=>{setDeskPage('attempt');setTabChoice({attempt:attached.id,tab:'evidence'});}}>Ver recibo de la consulta</button>
          </section>;
        }} key={JSON.stringify([officeId,session,navProject,threadId])} office={officeId} session={session} project={navProject} thread={threadId} online={!!session&&!initializing&&!connectionError}
          job={inspectionJobs.jobs.find(j=>j.project===navProject&&j.thread===threadId)} inspectFiles={inspectionJobs.inspect} onDraft={value=>{
            const key=JSON.stringify([officeId,navProject,threadId]);setDraftThreads(old=>{
              if(!value.trim()){const next={...old};delete next[key];return next;}
              const title=value.trim();if(old[key]?.title===title)return old;
              return {...old,[key]:{project:navProject,thread:threadId,title}};
            });
          }} inspector={inspector} showInspector={()=>setInspector(true)} onUpdate={()=>{setThreadRevision(v=>v+1);void refreshSnapshot().catch(noteError);}} modelBlocked={busy||!!doing||exhausted||budgetPending}
          onConsult={(report,query,origin)=>{proposalGeneration.current++;fragmentOrigin.current=origin;setFragmentProposal({report,objective:query,project:navProject,thread:threadId});void loadModels();}}
          onLegacy={()=>{if(!active)openDraft(navProject);setDeskPage(active?'attempt':'html');}}/>:<>
        <section ref={surface} className={`connected-surface ${viewed?'with-delivery':''}`} aria-label="Encargo y entrega">
          <section className="connected-director" aria-labelledby={viewed?'director-title':showingFindings?'static-result-title':'desk-title'}>
            {viewed&&<div className="connected-director-heading"><div className="director-signature"><DirectorMark/><strong id="director-title">Director</strong></div><span className={`connected-status ${active&&!inspected&&!connectionError?'active':''}`} role="status">{connectionError&&viewed&&!terminal(viewed.state)?`Último estado · ${status}`:status}</span></div>}
            {!viewed&&<div id="static-workspace" role="region" aria-labelledby={showingFindings?'static-result-title':'desk-title'} className={'brief-desk static-workspace'+(showingFindings?' has-findings':'')}>
              <header className="brief-intro">
                <div className="brief-byline"><DirectorMark/><span>{showingFindings?'Comprobación local':'Director · Revisión de HTML'}</span></div>
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
                      <option value="" disabled>{catalog==='loading'?'Consultando modelos…':catalogEmpty?'Sin modelos compatibles':'Selecciona un modelo'}</option>
                      {models.map(m=><option key={m.model_digest} value={m.model_digest}>{m.model}</option>)}</select>
                    <button type="button" aria-label="Actualizar modelos locales" title="Actualizar modelos locales"
                      disabled={busy||!!doing||!session||catalog==='loading'||exhausted} onClick={()=>void loadModels()}>↻</button>
                  </div>
                  {!catalogEmpty&&<details className="connected-profile"><summary>Perfil acotado <span>{roleCount} {roleCount===1?'rol':'roles'} · CPU</span></summary>
                    <label htmlFor="connected-roles">Roles secuenciales</label><select id="connected-roles" value={roleCount} disabled={busy||!!doing}
                      onChange={e=>{invalidate();setRoleCount(Number(e.target.value));}}>
                      <option value={1}>1 · Director</option><option value={3}>3 · Director, revisor e integrador</option><option value={7}>7 · Equipo completo</option>
                    </select><p>Los roles usan el mismo modelo por turnos. Cada llamada admite hasta 128 tokens de salida.</p></details>}
                </div>}
                {assisted&&catalogEmpty&&<section className="model-guide" aria-label="Configurar Ollama">
                  <h2>Modelo local para la consulta</h2><p>La última consulta a Ollama no encontró un modelo compatible. En PowerShell puedes descargar uno con <code>ollama pull qwen2.5:0.5b</code> y actualizar la lista. Puedes seguir comprobando el HTML sin modelo.</p>
                  <button type="button" className="quiet-button" disabled={busy||!!doing||catalog==='loading'} onClick={()=>void loadModels()}>Comprobar modelos instalados</button>
                </section>}
                {!showingFindings&&<div className="brief-actions">
                  <div className="brief-primary">
                    {assisted?<button type="submit" className="solid-button" disabled={busy||exhausted||budgetPending||!!doing||catalog!=='ready'||!source||!selectedModel||objective.trim().length<12}>Revisar encargo <span aria-hidden="true">→</span></button>:
                      <button type="button" className={source?'quiet-button':'solid-button'} disabled={busy||!!doing||!session} onClick={()=>changeMode(true)}>Consultar al Director</button>}
                    <small>{exhausted?'3 intentos consumidos · cuota agotada':budgetPending?'Cuota pendiente de actualizar':assisted&&!catalogEmpty&&objective.trim().length>0&&objective.trim().length<12?'Escribe al menos 12 caracteres':'1 intento al autorizar'}</small>
                  </div>
                  <div className="brief-alternative">
                    <button type="button" className={source&&!assisted?'solid-button':'quiet-button'} disabled={busy||!!doing||!source}
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
                <div className="review-foot"><button className="quiet-button" disabled={busy||!!doing} onClick={()=>changeMode(true)}>Consultar al Director</button>
                  <span>1 intento al autorizar</span><button className="text-repeat" disabled={busy||!!doing||!source} onClick={()=>void act('Comprobando HTML',()=>inspectSource())}>Comprobar HTML</button></div>
              </section>}
            </div>}
            {inspected&&attempt&&<div className="history-context"><span>Consultando el historial</span><button className="quiet-button" onClick={()=>{invalidate();setInspected(null);setBrowsedProject(null);}}>{active?'Volver al trabajo en curso':'Volver al último encargo'}</button></div>}
            {viewed&&<div className="connected-conversation"><div className="connected-user-request"><span>Tu encargo</span><h1>{viewed.objective}</h1></div>
                {viewed&&<AttemptActivity key={session+viewed.id} office={officeId} session={session} attempt={viewed.id} revision={viewed.cursor??viewed.revision}/>}
                {note&&<div className="connected-work-status"><p>{note}</p></div>}
                {viewed.state==='FAILED'&&viewed.execution_error_code&&<p className="execution-code">Código de ejecución <code>{viewed.execution_error_code}</code></p>}
                {active&&!inspected&&!terminal(viewed.state)&&<div className="connected-action-row"><button className="quiet-button" disabled={initializing||!!connectionError||!!doing||requestingStop} onClick={()=>recoverAttempt(viewed)}>Comprobar recuperación</button></div>}
                {!active&&!connectionError&&terminal(viewed.state)&&<button className="quiet-button" disabled={!!doing||!!pending} onClick={()=>viewed.thread_id?openThread(viewed.project_id,viewed.thread_id,viewed.inspection_id):openDraft(viewed.project_id)}>{viewed.thread_id?'Revisar la decisión del hilo':drafts.current.has(viewed.project_id)?'Volver al borrador':'Preparar otro encargo →'}{(inspected||navProject!==viewed.project_id)&&` · ${viewed.project_id}`}</button>}
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
          {viewed&&<><PaneDivider kind="director" container={surface} controls="connected-delivery" label="Ancho del Director"/>
            <section id="connected-delivery" className="connected-delivery" aria-label="Actividad y entrega">
              <header><div className="delivery-document"><span>Documento del encargo</span><h2>{sourceLabel}</h2></div>
                <span className="delivery-state">{report?'Informe recibido':available?'Informe por leer':terminal(viewed.state)?'Sin informe validado':'Esperando informe'}</span>
              </header>
              <div className="connected-tabs" role="tablist" aria-label="Vista de entrega" onKeyDown={tabKey}>
                {tabOrder.map(tab=><button key={tab} role="tab" tabIndex={resultTab===tab?0:-1} id={'tab-'+tab} aria-controls={'panel-'+tab}
                  aria-selected={resultTab===tab} onFocus={()=>setTabChoice({attempt:viewed.id,tab})}
                  onClick={()=>setTabChoice({attempt:viewed.id,tab})}>{deliveryTabs[tab]}</button>)}
              </div>
              <div className="connected-delivery-body" role="tabpanel" id={'panel-'+resultTab} aria-labelledby={'tab-'+resultTab} tabIndex={0}
                onFocusCapture={()=>{if(tabChoice?.attempt!==viewed.id||tabChoice.tab!==resultTab)setTabChoice({attempt:viewed.id,tab:resultTab});}}>
              {resultTab==='activity'?<div className="activity-panel">
                <section className="call-receipts" aria-labelledby="calls-title">
                  <h2 id="calls-title">Llamadas al modelo</h2>
                  <p>{viewed.model} · hasta {viewed.roles} {viewed.roles===1?'llamada autorizada':'llamadas secuenciales autorizadas'}</p>
                  {viewed.calls?.length ? <ol className="connected-call-list" aria-label="Llamadas del modelo">{viewed.calls.map((call,index)=>{
                    const duration=recordedDuration(call,viewed.observed_ms,!terminal(viewed.state));
                    return <li key={call.seq} className={call.state==='STARTED'?'call-started':undefined}><span className="call-order">{index+1}</span><strong>{roles[call.role]||call.role}</strong>
                      <span className="call-fact">{call.state==='DONE'?'Respuesta registrada':call.state==='STARTED'?(connectionError?'En curso en la última lectura':'En curso'):call.state==='INTERRUPTED'?'Interrumpida':call.state}
                        {duration&&<small>{duration}{call.state==='STARTED'?' al último registro':''}</small>}</span></li>;
                  })}</ol>
                    : <p>{viewed.calls?'La última lectura contiene cero llamadas.':'Pendiente de leer las llamadas del encargo.'}</p>}
                </section>
                {viewed.observed_ms!==undefined&&Number.isSafeInteger(viewed.observed_ms)&&viewed.observed_ms>0&&viewed.observed_ms<=8640000000000000&&
                  <p className="activity-read">Última lectura del encargo · <time>{new Date(viewed.observed_ms).toLocaleTimeString('es-ES')}</time></p>}

              </div>:resultTab==='report'?(report?<ReportView report={report.report} limited={report.meta.generation_limited}/>:reportProblem?.id===viewed.id?
                <div className="report-read-error" role="alert"><h3>No se pudo leer este informe</h3>
                  <p>El informe sigue guardado en {viewed.project_id}. Puedes volver a leerlo sin consumir un intento.</p>
                  <code>{reportProblem.code}</code> <button className="quiet-button" onClick={()=>setReportReadRevision(v=>v+1)}>Reintentar lectura del informe</button>
                </div>:<div className="delivery-empty"><h3>{available?'Leyendo el informe':terminal(viewed.state)?'No hay informe validado':'El informe está pendiente'}</h3>
                  <p>{available?'Recuperando el contenido guardado.':terminal(viewed.state)?'Conservamos el intento y su estado.':'Puedes seguir las llamadas y los registros de este encargo en Actividad.'}</p>
                </div>):<div className="connected-evidence"><h3>Qué puedes comprobar</h3><dl><dt>Documento</dt><dd>{sourceLabel}</dd><dt>Intento</dt><dd>{viewed.id}</dd><dt>Último estado registrado</dt><dd>{viewed.state}</dd><dt>Modelo aprobado</dt><dd>{viewed.model}</dd><dt>Huella del modelo</dt><dd>{viewed.model_digest}</dd><dt>Huella de la fuente</dt><dd>{viewed.source_sha256}</dd><dt>Huella del informe</dt><dd>{report?.meta.sha256||'Todavía no disponible'}</dd></dl>{report&&<p>La lectura comprobó los fragmentos y la huella completa del informe antes de mostrarlo.</p>}<p>La aceptación verifica consistencia estática y procedencia de contenido. No certifica accesibilidad, seguridad ni que las sugerencias del modelo sean correctas.</p>{viewed.execution_error_code&&<p>Código de ejecución: <code>{viewed.execution_error_code}</code></p>}{report&&<details><summary>Informe original de sólo lectura</summary><pre>{report.text}</pre></details>}</div>}
          </div></section></>}
        </section>
        <footer className="connected-footer"><span>{viewed?.model||(assisted?(selectedModel?.model||'Selecciona tu modelo local') :showingFindings?'Análisis estático':'Director')}</span><span>{connectionError?'Último estado guardado':active?'Trabajo acotado en curso':viewed||assisted?'Modelo local · CPU':'Lectura local del archivo'}</span></footer>
        </>}
      </main>
    </div>
    {panel==='appearance'&&<AppearancePanel control={allStops} appearance={appearance} close={()=>setPanel(null)}/>}
    {panel==='search'&&<CommandSearch key={navProject} control={allStops} items={commands} project={navProject} search={searchReports} openReport={(thread,id)=>{openThread(navProject,thread);setReturnTo({report:id});}} close={()=>setPanel(null)}/>}
    {panel==='project'&&<DeskDialog label="Nuevo proyecto" close={()=>setPanel(null)}><form className="prefs-body" onSubmit={e=>{e.preventDefault();const id=projectName.trim();if(!id||busy||doing)return;openThread(id,'main');setPanel(null);}}><label htmlFor="new-project-name">Nombre del proyecto</label><input id="new-project-name" autoFocus required maxLength={80} value={projectName} onChange={e=>setProjectName(e.target.value)}/><div className="approval-actions"><button type="submit" className="desk-primary" disabled={!projectName.trim()||busy||!!doing}>Abrir proyecto</button></div></form></DeskDialog>}
    {fragmentProposal&&<DeskDialog label={fragmentProposal.report.attachments.length?'Consultar los extractos':'Consultar el encargo de texto'} close={dismissProposal}><div className="prefs-body"><p>{fragmentProposal.objective}</p>
      <label htmlFor="fragment-model">Modelo local</label><select id="fragment-model" disabled={catalog!=='ready'||!!doing} value={modelDigest} onChange={e=>setModelDigest(e.target.value)}>{!models.length&&<option value="">{catalog==='loading'?'Consultando Ollama…':'Sin modelos disponibles'}</option>}{models.map(m=><option key={m.model_digest} value={m.model_digest}>{m.model}</option>)}</select>
      {catalog==='error'&&<p role="alert">No se pudo leer el catálogo de Ollama. La inspección local sigue disponible.</p>}
      {fragmentProposal.scopeError?<p role="alert">{fragmentProposal.scopeError}</p>:fragmentProposal.report.attachments.length>0&&<p>El permiso admite hasta 8 citas distintas y 4.608 bytes con sus referencias.</p>}
      <div className="approval-actions"><button className="desk-secondary" disabled={catalog==='loading'||!!doing} onClick={()=>void loadModels()}>Actualizar modelos</button><button className="desk-primary" disabled={!!doing||!selectedModel||catalog!=='ready'||busy} onClick={()=>void act('Preparando permiso',previewFragments)}>Revisar permiso</button></div></div></DeskDialog>}
    <dialog ref={approvalDialog} className="connected-approval" aria-labelledby="approval-title"
      onCancel={e=>{e.preventDefault();setApproval(null);}} onClose={()=>setApproval(null)}>
      {approval&&<>
        <header className="approval-header">
          <div className="approval-heading">
            <span className="eyebrow">Antes de empezar</span>
            <button aria-label="Cerrar revisión" onClick={()=>setApproval(null)}>×</button>
          </div>
          <h2 id="approval-title">{approval.excerpts?'Autorizar una consulta':'Este es el encargo.'}</h2>
        </header>
        <div className="approval-body" role="region" aria-label="Detalles del permiso" tabIndex={0}>
          <p className="approval-objective">{approval.value.objective}</p>
          <dl>
            <dt>Proyecto</dt><dd>{approval.value.project_id}</dd>
            <dt>Entrada autorizada</dt><dd>{approval.excerpts?.analysis_scope===directorTextScope?'Solo el texto del encargo':approval.excerpts?'Extractos de la entrega':source?.filename}</dd>
            <dt>Modelo</dt><dd>{approval.value.model}</dd>
            <dt>Trabajo</dt><dd>Hasta {approval.value.roles} {approval.value.roles===1?'llamada':'llamadas secuenciales'} · CPU · 128 tokens de salida por llamada</dd>
          </dl>
          {approval.excerpts&&approval.excerpts.analysis_scope!==directorTextScope&&<div className="permission-excerpts">
            <h3>Fragmentos que recibirá el modelo</h3>
            {approval.excerpts.fragments.map((f,i)=><blockquote key={i}>
              <strong>{f.name}</strong> <small>{f.page?'pág. '+f.page:f.line?'línea '+f.line:''}</small>
              <p>{f.quote}{f.unit&&typeof f.value==='number'?' · '+f.value+' '+f.unit:''}</p>
            </blockquote>)}
          </div>}
          <p>{approval.excerpts?.analysis_scope===directorTextScope?'El modelo recibirá el texto que aparece arriba. Su respuesta quedará en este hilo.':'El modelo recibe una copia de las entradas autorizadas. Los comentarios se guardan junto a la entrega.'}</p>
          <p className="approval-expiry">Vigencia máxima de esta autorización: {approval.value.expires_in_seconds} segundos. Si caduca, vuelve a revisar el encargo.</p>
        </div>
        <footer className="approval-footer">
          <p className="approval-cost">Consumirá 1 intento. Con la reserva, el saldo pasará a {approval.value.attempts_remaining-1} de 3.</p>
          <div className="approval-actions">
            <button className="quiet-button" onClick={()=>setApproval(null)}>Volver al encargo</button>
            <button className="solid-button" disabled={!!doing} onClick={()=>void act('Registrando encargo',start)}>Autorizar y ejecutar →</button>
          </div>
        </footer>
      </>}
    </dialog>
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
          <p className="finding-rule">Regla local <code>{code}</code></p>
        </details>}
      </div>
    </li>;
  })}</ol>;
}
function ReportView({report,limited}:{report:Report;limited?:boolean}) {
  const limitNotice=limited===true&&<p className="report-scope">El modelo alcanzó el límite de salida. Su respuesta puede estar incompleta.</p>;
  if(report.scope===directorTextScope)return <article className="connected-report excerpt-delivery"><h3>Respuesta del Director</h3>
    {limitNotice}<p className="model-answer">{report.role_outputs[0].content}</p><small>Respuesta del modelo local · Pendiente de contrastar</small></article>;
  const hours=(report.authorized_fragments??[]).flatMap(f=>f.unit==='h'&&typeof f.value==='number'?[{...f,value:f.value}]:[]);
  const pdf=hours.filter(f=>f.page),json=hours.filter(f=>f.pointer==='/response_sla_hours');
  const measured=pdf.length===1&&json.length===1;
  const hasHour=(output:string,value:number)=>new RegExp('(?:^|[^0-9.,])'+value+'(?![0-9]|[.,][0-9])').test(output);
  const omitted=measured&&hours.some(f=>!report.role_outputs.some(o=>hasHour(o.content,f.value)));
  if(report.scope==='local-inspection-excerpts-v1')return <article className="connected-report excerpt-delivery">{limitNotice}
    {measured?<><h3>{pdf[0].value===json[0].value?'Las dos fuentes coinciden':'Las dos fuentes discrepan'}</h3>
      <p className="report-scope">Comparación local de los extractos autorizados.</p>
      <div className="source-hour-list" aria-label="Valores en las fuentes">{hours.map((f,i)=><p key={i}><strong>{f.value} h</strong> · {f.name} · {f.page?'pág. '+f.page:'línea '+f.line}</p>)}</div>
      <details className="model-notes"><summary>Opinión del modelo · por contrastar</summary>
        {omitted&&<p className="report-scope">El comentario omite al menos una de las cifras citadas.</p>}
        {report.role_outputs.map((out,i)=><p className="model-answer" key={i}>{out.content}</p>)}</details></>:
      <><h3>Opinión del modelo</h3><p className="report-scope">Contrasta el comentario con sus fuentes.</p>
      {report.role_outputs.map((out,i)=><p className="model-answer" key={i}>{out.content}</p>)}</>}
    <details><summary>Fuentes que recibió el modelo</summary>{report.authorized_fragments?.map((f,i)=><blockquote key={i}><strong>{f.name}</strong> {f.page?'· pág. '+f.page:f.line?'· línea '+f.line:''}<p>{f.quote}{f.unit&&typeof f.value==='number'?' · '+f.value+' '+f.unit:''}</p></blockquote>)}</details></article>;
  return <article className="connected-report"><span className="eyebrow">Comprobaciones estáticas</span>
    <h3>{findingTitle(report.findings.length)}</h3><p className="report-scope">{report.findings.length?'Ubicaciones de la captura. Comprueba los candidatos en el navegador.':'Comprueba en el navegador el nombre de los controles y la función de las imágenes.'}</p>
    <FindingList findings={report.findings}/>
    {limitNotice}<details className="model-notes"><summary>Comentarios del modelo <span>· sugerencias por revisar</span></summary>
      {report.role_outputs.map((r,index)=><section className="role-commentary" key={`${r.role}-${index}`}><h4>{roles[r.role]||r.role}</h4><p>{r.content}</p></section>)}
    </details></article>;
}
