import {useLayoutEffect,useMemo,useRef,useState} from 'react';
import {Icon} from '../connected/DeskTools.tsx';
import type {Citation,Inspection} from '../connected/attachments.ts';
import {teamRoles,timeLabel,downloadFile,textFile,reportPdf,exportVersion,citationPosition,sourceLabel,receiptMarkdown} from './team.ts';
import type {Specialist, TeamReview} from './team.ts';

export type OfficeSignal = {
  action:string; finished:number; at:number; role?:Specialist; round?:number;
  phase?:'running'|'completed'|'failed';
};

export function Bot({role}:{role:Specialist|'director'}) {
  return <img className="arcade-bot" src={'/team/'+role+'.png'} alt="" draggable={false}/>;
}
const fileNumber=new Intl.NumberFormat('es-ES',{maximumFractionDigits:1});
function fileSize(bytes:number){
  if(bytes<1024)return bytes+' B';
  return bytes<1024*1024?fileNumber.format(bytes/1024)+' KiB':fileNumber.format(bytes/(1024*1024))+' MiB';
}
export function FileRow({name,blob,downloadName=name}:{name:string;blob:Blob|(()=>Blob);downloadName?:string}) {
  const [fault,setFault]=useState('');
  const [generated,setGenerated]=useState<{file:string;bytes:number}|null>(null);
  const bytes=typeof blob==='function'?(generated?.file===downloadName?generated.bytes:null):blob.size;
  function save(){
    try{
      const data=typeof blob==='function'?blob():blob;
      downloadFile(data,downloadName);setGenerated({file:downloadName,bytes:data.size});setFault('');
    }
    catch{setFault('No se pudo generar '+name+'. La entrega sigue disponible en el hilo.');}
  }
  return <><button type="button" className="workfile" onClick={save} aria-label={'Descargar '+name}>
    <Icon name={name.endsWith('.pdf')?'pdf':name.endsWith('.json')?'json':'note'}/><span><strong>{name}</strong><small>{name.split('.').at(-1)?.toUpperCase()} · {bytes===null?'Descargar':fileSize(bytes)}</small></span><span aria-hidden="true">↓</span></button>{fault&&<span role="alert">{fault}</span>}</>;
}
type SpecialistProps={report:Inspection|null;pending?:{objective:string;status:string};openSource:(c:Citation,role:Specialist,round:number)=>void;close:()=>void};
function SpecialistView({role,initialRound,report,pending,openSource,close}:{role:Specialist;initialRound?:number}&SpecialistProps) {
  const review=report?.team;
  const list=review?.receipts.filter(r=>r.role===role)??[];
  const [round,setRound]=useState(initialRound??list.at(-1)?.round??1);
  const row=list.find(r=>r.round===round);
  const showsSources=role==='researcher'||role==='implementer'||role==='integrator';
  const showsConclusions=role==='integrator'&&round===3;
  const receiptName=teamRoles[role].toLocaleLowerCase('es')+'-r'+round;
  const dialog=useRef<HTMLDialogElement>(null);
  useLayoutEffect(()=>{
    const origin=document.activeElement;const el=dialog.current;el?.showModal();
    return ()=>{el?.close();if(origin instanceof HTMLElement&&origin.isConnected)origin.focus();};
  },[]);
  return <dialog className="specialist-sheet" ref={dialog} aria-label={'Hilo de '+teamRoles[role]} onCancel={e=>{e.preventDefault();close();}}
    onClick={e=>{if(e.target===e.currentTarget){const b=e.currentTarget.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)close();}}}>
    <header><Bot role={role}/><div><h2>{teamRoles[role]}</h2><small>{report?'Entrega registrada':pending?'Encargo actual':'Hilo del especialista'} · Solo lectura</small></div><button autoFocus className="arc-icon" aria-label="Cerrar hilo del especialista" onClick={close}>×</button></header>
    {list.length>0?<><div className="round-switch" role="group" aria-label="Iteración del especialista">{list.map(r=><button key={r.round} aria-pressed={r.round===round} onClick={()=>setRound(r.round)}>Iteración {r.round}</button>)}</div>
      {row&&<div className="sheet-body" key={row.sha256}>{report?.objective&&<p className="specialist-objective">{report.objective}</p>}<div className="arc-byline"><Bot role="director"/><strong>Director</strong><span>→ {teamRoles[role]}</span></div><p>{row.instruction}</p>
        <div className="arc-byline"><Bot role={role}/><strong>{teamRoles[role]}</strong><time>{timeLabel(row.at)}</time></div>
        <details className="arc-disclosure" key={row.sha256} open={['implementer','verifier','integrator'].includes(role)}>
          <summary>{row.action}<small>{row.duration_us<1000?'Menos de 1 ms':Math.round(row.duration_us/1000)+' ms'}</small></summary>
          <ul>{row.details.map((d,i)=><li key={i}>{d}</li>)}</ul>
        </details>
        {report&&showsSources&&<section aria-label="Fuentes de la entrega"><h3>{showsConclusions?'Conclusiones de la entrega':'Fuentes de la entrega'}</h3>{report.findings.map((finding,i)=><div key={i}>
          {showsConclusions&&<p><strong>{finding.title}</strong><br/>{finding.detail}</p>}
          {finding.sources.map((c,j)=><button key={j} className="inline-link" onClick={()=>openSource(c,role,round)}>{[c.name,citationPosition(c)].filter(Boolean).join(' · ')}</button>)}
        </div>)}</section>}
        {report&&<FileRow name={receiptName+'.md'} downloadName={receiptName+'-'+exportVersion(report)+'.md'}
          blob={()=>textFile(receiptMarkdown(report,row,showsSources?report.findings:[],showsConclusions),'text/markdown;charset=utf-8')}/>}
        <details className="arc-disclosure receipt-id"><summary>Identidad del recibo</summary><code>{row.sha256}</code>{row.parent&&<><small>Recibo anterior</small><code>{row.parent}</code></>}</details></div>}</>:
      <div className="sheet-body">{pending?.objective&&<p className="specialist-objective">{pending.objective}</p>}<p role="status">{pending?.status??('Este hilo aún no tiene una intervención registrada de '+teamRoles[role]+'.')}</p></div>}
  </dialog>;
}
export function TeamRail({review,state,online,signal,selected,onSelect}:{review?:TeamReview;state?:'reading'|'stopping';online:boolean;signal:OfficeSignal|null;selected:Specialist|null;onSelect:(role:Specialist|null)=>void}){
  const [hover,setHover]=useState<Specialist|null>(null);
  const status=state==='stopping'?'Parada solicitada':!online?'Núcleo desconectado':state==='reading'?'Inspección en curso':review?'Entrega registrada':'Disponible';
  return <aside className="team-rail" aria-label="Equipo de la oficina"><header><strong>Equipo</strong><small>1 director · 6 especialistas</small></header>
    <div className="team-captain"><Bot role="director"/><span><strong>Director</strong><small>{status}</small></span></div>
    <h3>Especialistas</h3><div className="team-members">{(Object.entries(teamRoles) as [Specialist,string][]).map(([id,name])=>{
      const last=state?undefined:review?.receipts.filter(r=>r.role===id).at(-1);
      const actor=online&&state==='reading'&&signal?.role===id?signal:null;
      const running=actor?.phase==='running';
      const detail=actor?.phase==='failed'?'Operación fallida':actor?.phase==='completed'?actor.action:
        running?'Iteración '+actor.round+' · En curso':last?.action??(state?'Pendiente de recibo':'Sin actividad registrada');
      return <div className="member-wrap" key={id} onMouseEnter={()=>setHover(id)} onMouseLeave={()=>setHover(null)}>
        <button className="team-member" data-running={running||undefined} aria-expanded={selected===id} aria-haspopup="dialog" aria-label={'Abrir hilo de '+name} aria-describedby={'member-state-'+id+(hover===id&&last?' member-clock-'+id:'')} onFocus={()=>setHover(id)} onBlur={()=>setHover(null)} onKeyDown={e=>{if(e.key==='Escape')setHover(null);}} onClick={()=>{setHover(null);onSelect(id);}}>
          <Bot role={id}/><span><strong>{name}</strong><small id={'member-state-'+id}>{detail}</small></span></button>
        {hover===id&&<div className="member-peek" role="tooltip" id={'peek-'+id}><strong>{name}</strong><span>{detail}</span>{last&&<small id={'member-clock-'+id}>Última actividad · {timeLabel(last.at)}</small>}</div>}
      </div>;
    })}</div></aside>;
}
export function TeamOverlay({selected,...props}:{selected:{role:Specialist;round?:number}|null}&SpecialistProps){
  if(!selected)return null;
  return <SpecialistView key={selected.role+':'+(props.report?.id??'pending')} role={selected.role} initialRound={selected.round} {...props}/>;
}
export function TeamTrail({team,onSelect}:{team:TeamReview;onSelect:(role:Specialist,round:number)=>void}){
  const [expanded,setExpanded]=useState(false);
  const rounds=useMemo(()=>expanded?Array.from(new Set(team.receipts.map(r=>r.round)),round=>({round,receipts:team.receipts.filter(r=>r.round===round).map(r=>({...r,clock:timeLabel(r.at),iso:new Date(r.at*1000).toISOString()}))})):[],[expanded,team]);
  return <details className="arc-disclosure" open={expanded} onToggle={e=>setExpanded(e.currentTarget.open)}><summary>El equipo completó {team.receipts.length} pasos<small>{team.rounds} iteraciones</small></summary>
    {rounds.map(({round,receipts})=><div className="round-ledger" key={round}><strong>Iteración {round}</strong>{receipts.map(r=><button key={r.role} onClick={()=>onSelect(r.role,r.round)}><Bot role={r.role}/><span><strong>{teamRoles[r.role]}</strong> · {r.action}</span><time dateTime={r.iso}>{r.clock}</time></button>)}</div>)}</details>;
}
export function TeamDelivery({report}:{report:Inspection}){
  const team=report.team;
  const attachments=useMemo(()=>{
    if(!team)return null;
    const d=team.delivery;
    const decision=report.decision;
    const choice=decision?('Decisión registrada: '+({pdf:'usar la especificación PDF',json:'usar el manifiesto JSON',defer:'aplazar la elección'}[decision.choice])):null;
    const findings=report.findings.flatMap(f=>[{kind:'heading' as const,text:f.title+(f.status==='insufficient'?' · Pendiente':'')},f.detail,
      ...f.sources.flatMap(c=>[sourceLabel(c,report),...(c.quote?[{kind:'quote' as const,text:c.quote}]:[])]),'']);
    return {pdf:()=>reportPdf([{kind:'heading',text:'Neural Office | Informe de revisión'},'Proyecto: '+report.project_id,'Hilo: '+report.thread_id,'Entrega: '+report.id,'',
      ...(report.completed_at!==undefined?['Inspección terminada (UTC): '+new Date(report.completed_at*1000).toISOString()]:[]),
      d.objective,report.model_calls+' llamadas al modelo · '+report.reservations+' intentos','',...findings,
      ...d.limitations,'Revisión de la decisión: '+(decision?.revision??0),
      ...(choice&&decision?[choice,'Decisión registrada (UTC): '+new Date(decision.at*1000).toISOString()]:[]),'',{kind:'heading',text:'Capturas'},
      ...report.attachments.flatMap((s,i)=>{
        const cited=report.findings.some(f=>f.sources.some(c=>c.attachment_id===s.id&&c.sha256===s.sha256));
        return [{kind:'heading' as const,text:'Fuente '+(i+1)+' | '+s.name+' | '+s.bytes+' B | '+(cited?'Citada en hallazgos':'Captura sin cita')},
          'Captura '+s.id,'SHA-256 '+s.sha256];
      })]),
      json:()=>textFile(JSON.stringify(report,null,2),'application/json')};
  },[report,team]);
  if(!team||!attachments)return null;
  return <section className="team-delivery" aria-label="Trabajo del equipo y archivos de entrega">
    <div className="inline-files"><FileRow name="informe.pdf" downloadName={'informe-'+exportVersion(report)+'.pdf'} blob={attachments.pdf}/><FileRow name="evidencia.json" downloadName={'evidencia-'+exportVersion(report)+'.json'} blob={attachments.json}/></div>
  </section>;
}
