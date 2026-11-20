import {useLayoutEffect,useMemo,useRef,useState} from 'react';
import {Icon} from '../connected/DeskTools.tsx';
import type {Citation,Inspection} from '../connected/attachments.ts';
import {teamRoles,timeLabel,downloadFile,textFile,reportPdf} from './team.ts';
import type {Specialist, TeamReview} from './team.ts';

export function Bot({role}:{role:Specialist|'director'}) {
  return <img className="arcade-bot" src={'/team/'+role+'.png'} alt="" draggable={false}/>;
}
export function FileRow({name,blob,downloadName=name}:{name:string;blob:Blob|(()=>Blob);downloadName?:string}) {
  const [fault,setFault]=useState('');
  function save(){
    try{downloadFile(typeof blob==='function'?blob():blob,downloadName);setFault('');}
    catch{setFault('No se pudo generar '+name+'. La entrega sigue disponible en el hilo.');}
  }
  return <><button type="button" className="workfile" onClick={save} aria-label={'Descargar '+name}>
    <Icon name={name.endsWith('.pdf')?'pdf':name.endsWith('.json')?'json':'note'}/><span><strong>{name}</strong><small>{name.split('.').at(-1)?.toUpperCase()} · {typeof blob==='function'?'Descargar':new Intl.NumberFormat('es-ES',{maximumFractionDigits:1}).format(blob.size/1024)+' KB'}</small></span><span aria-hidden="true">↓</span></button>{fault&&<span role="alert">{fault}</span>}</>;
}
function position(c:Citation){
  return [c.page&&'Pág. '+c.page,c.line&&'Línea '+c.line,c.column&&'Col. '+c.column,c.pointer,c.member].filter(Boolean).join(' · ');
}
type SpecialistProps={report:Inspection|null;openSource:(c:Citation,role:Specialist,round:number)=>void;close:()=>void};
function SpecialistView({role,initialRound,report,openSource,close}:{role:Specialist;initialRound?:number}&SpecialistProps) {
  const review=report?.team;
  const list=review?.receipts.filter(r=>r.role===role)??[];
  const [round,setRound]=useState(initialRound??list.at(-1)?.round??1);
  const row=list.find(r=>r.round===round);
  const dialog=useRef<HTMLDialogElement>(null);
  useLayoutEffect(()=>{
    const origin=document.activeElement;const el=dialog.current;el?.showModal();
    return ()=>{el?.close();if(origin instanceof HTMLElement&&origin.isConnected)origin.focus();};
  },[]);
  return <dialog className="specialist-sheet" ref={dialog} aria-label={'Hilo de '+teamRoles[role]} onCancel={e=>{e.preventDefault();close();}}
    onClick={e=>{if(e.target===e.currentTarget){const b=e.currentTarget.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)close();}}}>
    <header><Bot role={role}/><div><h2>{teamRoles[role]}</h2><small>Hilo del especialista · Solo lectura</small></div><button autoFocus className="arc-icon" aria-label="Cerrar hilo del especialista" onClick={close}>×</button></header>
    {list.length>0?<><div className="round-switch" role="group" aria-label="Iteración del especialista">{list.map(r=><button key={r.round} aria-pressed={r.round===round} onClick={()=>setRound(r.round)}>Iteración {r.round}</button>)}</div>
      {row&&<div className="sheet-body"><div className="arc-byline"><Bot role="director"/><strong>Director</strong><span>→ {teamRoles[role]}</span></div><p>{row.instruction}</p>
        <div className="arc-byline"><Bot role={role}/><strong>{teamRoles[role]}</strong><time>{timeLabel(row.at)}</time></div>
        <details className="arc-disclosure" key={row.sha256} open={['implementer','verifier','integrator'].includes(role)}>
          <summary>{row.action}<small>{row.duration_us<1000?'Menos de 1 ms':Math.round(row.duration_us/1000)+' ms'}</small></summary>
          <ul>{row.details.map((d,i)=><li key={i}>{d}</li>)}</ul>
        </details>
        {report&&(role==='researcher'||role==='implementer'||role==='integrator')&&<section aria-label="Fuentes de la entrega"><h3>{role==='integrator'&&round===3?'Conclusiones de la entrega':'Fuentes de la entrega'}</h3>{report.findings.map((finding,i)=><div key={i}>
          {role==='integrator'&&round===3&&<p><strong>{finding.title}</strong><br/>{finding.detail}</p>}
          {finding.sources.map((c,j)=><button key={j} className="inline-link" onClick={()=>openSource(c,role,round)}>{[c.name,position(c)].filter(Boolean).join(' · ')}</button>)}
        </div>)}</section>}
        <FileRow name={teamRoles[role].toLocaleLowerCase('es')+'-r'+round+'.md'} blob={textFile('# '+teamRoles[role]+' · Iteración '+round+'\n\n'+row.instruction+'\n\n'+row.details.join('\n')+'\n\nRecibo '+row.sha256,'text/markdown;charset=utf-8')}/>
        <details className="arc-disclosure receipt-id"><summary>Identidad del recibo</summary><code>{row.sha256}</code>{row.parent&&<><small>Recibo anterior</small><code>{row.parent}</code></>}</details></div>}</>:
      <div className="sheet-body"><p>Este hilo aún no tiene una intervención registrada de {teamRoles[role]}.</p></div>}
  </dialog>;
}
export function TeamRail({review,active,selected,onSelect}:{review?:TeamReview;active:boolean;selected:Specialist|null;onSelect:(role:Specialist|null)=>void}){
  const [hover,setHover]=useState<Specialist|null>(null);
  return <aside className="team-rail" aria-label="Equipo de la oficina"><header><strong>Equipo</strong><small>1 director · 6 especialistas</small></header>
    <div className="team-captain"><Bot role="director"/><span><strong>Director</strong><small>{active?'Inspección en curso':review?'Entrega registrada':'Disponible'}</small></span></div>
    <h3>Especialistas</h3><div className="team-members">{(Object.entries(teamRoles) as [Specialist,string][]).map(([id,name])=>{
      const last=active?undefined:review?.receipts.filter(r=>r.role===id).at(-1);
      return <div className="member-wrap" key={id} onMouseEnter={()=>setHover(id)} onMouseLeave={()=>setHover(null)}>
        <button className="team-member" aria-expanded={selected===id} aria-haspopup="dialog" aria-label={'Abrir hilo de '+name} aria-describedby={hover===id?'peek-'+id:undefined} onFocus={()=>setHover(id)} onBlur={()=>setHover(null)} onKeyDown={e=>{if(e.key==='Escape')setHover(null);}} onClick={()=>{setHover(null);onSelect(id);}}>
          <Bot role={id}/><span><strong>{name}</strong><small>{last?last.action:active?'Pendiente de recibo':'Sin actividad registrada'}</small></span></button>
        {hover===id&&<div className="member-peek" role="tooltip" id={'peek-'+id}><strong>{name}</strong><span>{last?last.action:'Aún no hay recibos'}</span>{last&&<small>Última actividad · {timeLabel(last.at)}</small>}</div>}
      </div>;
    })}</div></aside>;
}
export function TeamOverlay({selected,...props}:{selected:{role:Specialist;round?:number}|null}&SpecialistProps){
  if(!selected)return null;
  return <SpecialistView key={selected.role} role={selected.role} initialRound={selected.round} {...props}/>;
}
export function TeamTrail({team,onSelect}:{team:TeamReview;onSelect:(role:Specialist,round:number)=>void}){
  return <details className="arc-disclosure"><summary>El equipo completó {team.receipts.length} pasos<small>{team.rounds} iteraciones</small></summary>
    {Array.from(new Set(team.receipts.map(r=>r.round))).map(round=><div className="round-ledger" key={round}><strong>Iteración {round}</strong>{team.receipts.filter(r=>r.round===round).map(r=><button key={r.role} onClick={()=>onSelect(r.role,r.round)}><Bot role={r.role}/><span>{r.action}</span><time>{timeLabel(r.at)}</time></button>)}</div>)}</details>;
}
export function TeamDelivery({report}:{report:Inspection}){
  const team=report.team;
  const attachments=useMemo(()=>{
    if(!team)return null;
    const d=team.delivery;
    const decision=report.decision;
    const choice=decision?('Decisión registrada: '+({pdf:'usar la especificación PDF',json:'usar el manifiesto JSON',defer:'aplazar la elección'}[decision.choice])):null;
    const findings=report.findings.flatMap(f=>[f.title+(f.status==='insufficient'?' · Pendiente':''),f.detail,
      ...f.sources.map(c=>[c.name,position(c),c.quote].filter(Boolean).join(' | ')),'']);
    return {pdf:()=>reportPdf(['Neural Office | Informe de revisión','Proyecto: '+report.project_id,'Hilo: '+report.thread_id,'Entrega: '+report.id,'',
      d.objective,report.model_calls+' llamadas al modelo · '+report.reservations+' intentos','',...findings,
      ...d.limitations,...(choice?[choice]:[]),'','Capturas',...report.attachments.map(s=>s.name+' | '+s.bytes+' B | '+s.sha256)]),
      json:textFile(JSON.stringify(report,null,2),'application/json')};
  },[report,team]);
  if(!team||!attachments)return null;
  return <section className="team-delivery" aria-label="Trabajo del equipo y archivos de entrega">
    <div className="inline-files"><FileRow name="informe.pdf" downloadName={'informe-'+report.id+'.pdf'} blob={attachments.pdf}/><FileRow name="evidencia.json" downloadName={'evidencia-'+report.id+'.json'} blob={attachments.json}/></div>
  </section>;
}
