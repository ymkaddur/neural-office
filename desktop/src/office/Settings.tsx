import {useLayoutEffect,useRef,useState} from 'react';
import {useAppearance} from '../connected/DeskTools.tsx';
import {nameForProject, type Model} from '../connected/model.ts';

type Props={initialTab?:string;appearance:ReturnType<typeof useAppearance>;models:Model[];model:string;choose:(id:string)=>void;load:()=>void;catalog:string;project:string;online:boolean;quota:string};
export function Settings({initialTab='General',appearance,models,model,choose,load,catalog,project,online,quota}:Props){
  const [tab,setTab]=useState(initialTab);
  const heading=useRef<HTMLHeadingElement>(null);
  useLayoutEffect(()=>{heading.current?.focus();},[]);
  const {prefs,update}=appearance;
  const section=(s:string)=>tab==='General'||tab===s;
  return <section className="office-settings"><nav aria-label="Secciones de ajustes">{['General','Apariencia','Modelos locales','Autonomía y permisos','Accesibilidad','Datos'].map(s=><button aria-current={tab===s?'page':undefined} key={s} onClick={()=>setTab(s)}>{s}</button>)}</nav><div className="settings-scroll"><div className="settings-content">
    <h1 tabIndex={-1} ref={heading}>{tab==='General'?'Ajustes generales':tab}</h1>
    {section('Apariencia')&&<section>{tab==='General'&&<h2>Apariencia</h2>}<label>Tema<select value={prefs.theme} onChange={e=>update({...prefs,theme:e.target.value as typeof prefs.theme})}><option value="system">Sistema</option><option value="dark">Oscuro</option><option value="light">Claro</option></select></label>
      <label>Densidad<select value={prefs.density} onChange={e=>update({...prefs,density:e.target.value as typeof prefs.density})}><option value="comfortable">Cómoda</option><option value="compact">Compacta</option></select></label></section>}
    {section('Accesibilidad')&&<section>{tab==='General'&&<h2>Accesibilidad</h2>}<label>Reducir movimiento<input type="checkbox" checked={prefs.motion} onChange={e=>update({...prefs,motion:e.target.checked})}/></label>
      <label>Alto contraste<input type="checkbox" checked={prefs.contrast} onChange={e=>update({...prefs,contrast:e.target.checked})}/></label>
      <label>Tamaño de texto<select value={prefs.scale} onChange={e=>update({...prefs,scale:Number(e.target.value) as typeof prefs.scale})}>{[100,115,125].map(n=><option key={n} value={n}>{n} %</option>)}</select></label></section>}
    {section('Modelos locales')&&<section><h2>Modelo local</h2><label>Modelo para consultas<select disabled={!models.length} value={model} onChange={e=>choose(e.target.value)}><option value="">Seleccionar modelo</option>{models.map(m=><option key={m.model_digest} value={m.model_digest}>{m.model}</option>)}</select></label>
      <div className="settings-row"><span role="status">{catalog==='ready'?(models.length?models.length+' modelos disponibles':'Sin modelos disponibles'):catalog==='loading'?'Consultando Ollama…':catalog==='error'?'Consulta no disponible':'Catálogo pendiente de consulta'}</span><button disabled={!online||catalog==='loading'} onClick={load}>Consultar Ollama</button></div></section>}
    {section('Autonomía y permisos')&&<section>{tab==='General'&&<h2>Autonomía y permisos</h2>}<div className="settings-row"><span>Inspección local</span><strong>3 rondas · 6 especialistas</strong></div><div className="settings-row"><span>Consulta al modelo</span><strong>Autorización por encargo</strong></div><div className="settings-row"><span>Intentos del proyecto</span><strong>{quota}</strong></div></section>}
    {section('Datos')&&<section><h2>Datos del proyecto</h2><div className="settings-row"><span>Proyecto actual</span><strong>{nameForProject(project)}</strong></div><div className="settings-row"><span>Almacenamiento</span><strong>Oficina local</strong></div></section>}
    {!appearance.saved&&<p role="status">La preferencia solo pudo guardarse en esta ventana.</p>}
  </div></div></section>;
}
