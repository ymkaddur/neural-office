import { useEffect, useReducer, useRef, useState } from 'react';
import { busy, initialState, reduce, roleNames } from './state.ts';
import type { RoleCount, Scenario } from './state.ts';
import baselineData from './baseline.json';
const baseline: {status: string; description: string; rows: {roles: number; samples: number; seconds: number; workingSetGiB: number}[]} = baselineData;

type Page = 'workspace' | 'history' | 'models' | 'skills' | 'measurements';
const labels = { READY: 'Listo para empezar', BOOTING: 'Preparando el modelo', RUNNING: 'Equipo trabajando',
  VERIFYING: 'Verificando el resultado', STOPPING: 'Confirmando la parada', CANCELLED: 'Trabajo detenido',
  ACCEPTED: 'Informe disponible', FAILED: 'El modelo no pudo arrancar', RECOVERY_REQUIRED: 'Revisión de recuperación' };
const findings = [
  { title: 'Idioma del documento', detail: 'El elemento HTML no declara un idioma.', line: 'Línea 2', code: 'HTML_LANGUAGE_MISSING' },
  { title: 'Título de la página', detail: 'El título está vacío. Añade uno que describa la página.', line: 'Documento', code: 'DOCUMENT_TITLE_MISSING' },
  { title: 'Texto alternativo', detail: 'La imagen no tiene un atributo alt.', line: 'Línea 6', code: 'IMAGE_ALT_MISSING' },
  { title: 'Etiqueta del campo', detail: 'Revisa la etiqueta accesible del campo de nombre.', line: 'Línea 7', code: 'CONTROL_LABEL_CANDIDATE' },
];
function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, string> = {
    grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    clock: 'M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
    chip: 'M6 6h12v12H6z M9 1v5 M15 1v5 M9 18v5 M15 18v5 M1 9h5 M1 15h5 M18 9h5 M18 15h5 M9 9h6v6H9z',
    book: 'M4 3h7l1 2 1-2h7v16h-7l-1 2-1-2H4z M12 5v16',
    chart: 'M3 3v18h18 M7 16v-5 M12 16V6 M17 16V9',
    plus: 'M12 5v14 M5 12h14', arrow: 'M5 12h14 M13 6l6 6-6 6',
    check: 'M5 12l4 4L19 6', stop: 'M6 6h12v12H6z', file: 'M5 3h9l5 5v13H5z M14 3v6h5 M9 13h6 M9 17h6',
    moon: 'M20 15A9 9 0 0 1 9 4 9 9 0 1 0 20 15', shield: 'M12 3l8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6z M8 12l3 3 5-6',
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.file} /></svg>;
}

export function App() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [page, setPage] = useState<Page>('workspace');
  const [tab, setTab] = useState<'activity' | 'report' | 'evidence'>('activity');
  const [dark, setDark] = useState(false);
  const [objective, setObjective] = useState('Revisa la accesibilidad básica del HTML de ejemplo y prepara un informe con sus evidencias.');
  const [history, setHistory] = useState<{ generation: number; phase: string; roles: number }[]>([]);
  const [notice, setNotice] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const working = busy(state);
  const roles = roleNames(state.roles);

  useEffect(() => {
    const generation = state.generation, sequence = state.eventSequence + 1;
    let kind: 'READY' | 'ROLE_COMPLETED' | 'VERIFIED' | 'TERMINATED' | 'FAILED' | 'INTERRUPTED' | null = null;
    if (state.phase === 'BOOTING') kind = state.scenario === 'startup-timeout' ? 'FAILED' : 'READY';
    if (state.phase === 'RUNNING') kind = state.scenario === 'interrupted' ? 'INTERRUPTED' : 'ROLE_COMPLETED';
    if (state.phase === 'VERIFYING') kind = 'VERIFIED';
    if (state.phase === 'STOPPING') kind = 'TERMINATED';
    if (!kind) return;
    const timer = window.setTimeout(() => dispatch({ type: 'EVENT', generation, sequence, kind }), state.phase === 'RUNNING' ? 850 : 650);
    return () => window.clearTimeout(timer);
  }, [state]);
  useEffect(() => {
    if (['ACCEPTED', 'FAILED', 'CANCELLED'].includes(state.phase)) {
      setHistory(previous => previous.some(h => h.generation === state.generation) ? previous
        : [...previous, { generation: state.generation, phase: state.phase, roles: state.roles }]);
    }
  }, [state.phase, state.generation, state.roles]);

  function simulate() {
    if (!objective.trim()) { setNotice('Escribe un objetivo para la demostración.'); return; }
    setNotice(''); setTab('activity'); dispatch({type: 'START'});
  }
  function exportReport() {
    const blob = new Blob([JSON.stringify({ mode: 'SIMULATION', source: 'packaged synthetic HTML', findings,
      scope: 'Prototype fixture. No model was called and this is not a production audit.' }, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = 'neural-office-demo-report.json'; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const navigation: [Page, string, string][] = [
    ['workspace', 'Mi oficina', 'grid'], ['history', 'Historial', 'clock'],
    ['models', 'Modelos', 'chip'], ['skills', 'Skills y memoria', 'book'], ['measurements', 'Mediciones', 'chart'],
  ];

  return <div className={`app ${dark ? 'dark' : ''}`}>
    <a className="skip" href="#content">Saltar al contenido</a>
    <aside className="sidebar" aria-label="Navegación principal">
      <div className="brand"><span className="brand-mark">N<span>·</span></span><div>Neural Office<small>TU EQUIPO, EN LOCAL</small></div></div>
      <button className="new-project" onClick={() => dialog.current?.showModal()}><Icon name="plus" size={17} /> Explorar la demo</button>
      <nav>{navigation.map(([id, label, icon]) => <button key={id} className={page === id ? 'selected' : ''} aria-current={page === id ? 'page' : undefined} onClick={() => setPage(id)}><Icon name={icon} /><span>{label}</span>{id === 'workspace' && <span className="count">1</span>}</button>)}</nav>
      <div className="project-list"><p className="eyebrow">PROYECTO DE EJEMPLO</p><button onClick={() => setPage('workspace')}><span className="project-dot" /> Auditoría del sitio</button><p className="sidebar-help">Una entrada local.<br />Un resultado que puedes revisar.</p></div>
      <div className="sidebar-bottom"><div className="local-label"><Icon name="shield" size={17} /><span>Software libre · MIT</span></div><button className="theme-toggle" onClick={() => setDark(!dark)} aria-pressed={dark}><Icon name="moon" size={17} />{dark ? 'Usar tema claro' : 'Usar tema oscuro'}</button><small>V5.3 · Vista previa de diseño</small></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><button className="mobile-theme" aria-label="Cambiar tema" aria-pressed={dark} onClick={() => setDark(!dark)}><Icon name="moon" size={18} /></button><span>Mi espacio <span className="slash">/</span> {navigation.find(n => n[0] === page)?.[1]}</span><span className="preview-badge"><span /> DEMO SIN MOTOR</span></header>
      <div className="demo-notice"><Icon name="shield" size={16} /><span>Prototipo interactivo. Las tareas se simulan en esta pestaña; no ejecutan modelos ni modifican archivos.</span></div>
      <div className="body-grid">
        <main id="content" tabIndex={-1}>
          {page === 'workspace' && <>
            <div className="page-heading"><div><p className="eyebrow">TU OFICINA</p><h1>De una idea a un resultado.</h1><p>Define el trabajo. Sigue a tu equipo. Revisa la evidencia.</p></div><div className="round-icon"><Icon name="grid" size={26} /></div></div>
            <section className="composer" aria-label="Preparar demostración">
              <label htmlFor="objective">¿Qué quieres resolver?</label>
              <textarea id="objective" value={objective} maxLength={2000} disabled={working} onChange={e => setObjective(e.target.value)} rows={3} />
              <div className="attachment"><Icon name="file" size={18} /><span>audit-sample.html<small>Ejemplo sintético incluido · solo lectura</small></span><span className="file-tag">HTML</span></div>
              <div className="composer-actions"><span><span className="status-dot" />Modelo de ejemplo · CPU</span><button className="primary" onClick={simulate} disabled={working || state.attempts >= 3 || !objective.trim()}>Simular auditoría <Icon name="arrow" size={17} /></button></div>
            </section>
            <div role="status" aria-live="polite" className="live-status">{notice || (state.attempts >= 3 && !working ? 'Presupuesto de demo agotado. Recarga la página para iniciar otra sesión de ejemplo.' : labels[state.phase])}</div>
            <div className="work-title"><h2>Auditoría del sitio <span className="subtle-tag">DEMO</span></h2><span className={`phase ${state.phase === 'ACCEPTED' ? 'good' : ''}`}>{labels[state.phase]}</span></div>
            <div className="tabs" role="tablist" aria-label="Vistas del trabajo">{(['activity', 'report', 'evidence'] as const).map(id => <button key={id} role="tab" tabIndex={tab === id ? 0 : -1} onKeyDown={e => { const views = ['activity','report','evidence'] as const; let next = views.indexOf(id); if (e.key === 'ArrowRight') next = (next + 1) % views.length; else if (e.key === 'ArrowLeft') next = (next + views.length - 1) % views.length; else if (e.key === 'Home') next = 0; else if (e.key === 'End') next = views.length - 1; else return; e.preventDefault(); setTab(views[next]); document.getElementById('tab-' + views[next])?.focus(); }} aria-selected={tab === id} aria-controls={`panel-${id}`} id={`tab-${id}`} onClick={() => setTab(id)}>{id === 'activity' ? 'Actividad' : id === 'report' ? 'Informe' : 'Evidencias'}{id === 'evidence' && <span>4</span>}</button>)}</div>
            <section className="work-panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
              {tab === 'activity' && <><div className="plan-header"><h3>Un equipo, un objetivo</h3><span>{state.completed}/{state.roles} pasos de la demo</span></div><ol className="role-list">{roles.map((role, index) => <li key={role} className={index < state.completed ? 'done' : index === state.completed && state.phase === 'RUNNING' ? 'current' : ''}><div className="role-number">{index < state.completed ? <Icon name="check" size={16} /> : String(index + 1).padStart(2, '0')}</div><div><strong>{role}</strong><p>{role === 'Director' ? 'Delimita el alcance y organiza la revisión.' : role === 'Integrador' ? 'Reúne hallazgos y límites en un informe.' : 'Revisa la evidencia desde su responsabilidad.'}</p></div><span className="role-state">{index < state.completed ? 'Completado' : index === state.completed && state.phase === 'RUNNING' ? 'En curso' : 'Pendiente'}</span></li>)}</ol><div className="verification-note"><Icon name="shield" size={18} /><p>El resultado se contrasta con comprobaciones estáticas. Los comentarios del modelo necesitan revisión humana.</p></div></>}
              {tab === 'report' && (state.phase === 'ACCEPTED' ? <><div className="plan-header"><h3>Informe de ejemplo</h3><button className="text-button" onClick={exportReport}>Exportar demo JSON</button></div><p className="muted">Cuatro hallazgos del archivo sintético. Esta vista usa un informe de demostración.</p>{findings.map(f => <article className="finding" key={f.code}><div><h4>{f.title}</h4><p>{f.detail}</p></div><span>{f.line}</span></article>)}</> : <div className="empty-state"><Icon name="file" size={32} /><h3>Tu resultado aparecerá aquí</h3><p>Completa la simulación para explorar el informe. Una tarea detenida o fallida no se presenta como terminada.</p></div>)}
              {tab === 'evidence' && <><h3>De dónde salen los hallazgos</h3><p className="muted">Ejemplo público incluido en el repositorio. Son cuatro heurísticas, no una certificación de accesibilidad.</p>{findings.map(f => <article className="evidence-row" key={f.code}><Icon name="file" size={18} /><div><strong>{f.title}</strong><code>{f.code}</code></div><span>{f.line}</span></article>)}</>}
            </section>
            {state.error && <div className="error-card" role="alert"><strong>{state.phase === 'RECOVERY_REQUIRED' ? 'La terminación debe confirmarse' : 'Escenario de fallo de arranque'}</strong><p>{state.phase === 'RECOVERY_REQUIRED' ? 'La demo mantiene el trabajo bloqueado hasta que simules la confirmación de que ha terminado. El intento sigue consumido.' : 'Esta simulación representa un timeout. No diagnostica la causa del incidente histórico R13 ni llama a Ollama.'}</p><code>{state.error}</code>{state.phase === 'RECOVERY_REQUIRED' && <button className="secondary" onClick={() => dispatch({type: 'RECOVER'})}>Simular terminación confirmada</button>}</div>}
          </>}
          {page === 'history' && <><PageHeading title="Un historial que puedes seguir." text="Actividad de esta sesión de demostración. Se borra al recargar la pestaña." /><section className="card"><h2>Trabajos de ejemplo</h2>{history.length ? history.map(h => <div className="history-row" key={h.generation}><Icon name="file" /><div><strong>Auditoría de ejemplo · {h.generation}</strong><p>{h.roles} roles · intento consumido</p></div><span>{labels[h.phase as keyof typeof labels]}</span></div>) : <div className="empty-state"><Icon name="clock" size={32} /><h3>Todo empieza con una tarea</h3><p>La simulación dejará aquí su resultado, incluso si la detienes.</p><button className="secondary" onClick={() => setPage('workspace')}>Ir a mi oficina</button></div>}</section></>}
          {page === 'models' && <><PageHeading title="Elige con información." text="V5.3 diseña la selección. La conexión al motor de escritorio llegará en V5.5." /><section className="card model-card"><div className="model-avatar"><Icon name="chip" size={32} /></div><h2>Modelo local de ejemplo</h2><p>Configuración de la demo: CPU · contexto de 8.192 tokens · un modelo activo.</p><span className="subtle-tag">SIN CONEXIÓN A OLLAMA</span><div className="info-strip">La selección real deberá comprobar identidad del modelo, disponibilidad y presupuesto antes de iniciar un trabajo.</div></section><section className="card"><h3>Perfiles que mediremos en V5.4</h3><div className="profile-grid">{['Eficiencia', 'Equilibrado', 'Calidad'].map(name => <div key={name}><strong>{name}</strong><p>Capacidad planificada.<br />Sin cifras de rendimiento prometidas.</p></div>)}</div></section></>}
          {page === 'skills' && <><PageHeading title="Conocimiento que merece quedarse." text="Biblioteca prevista para V6–V8. No hay skills instaladas ni aprendizaje activo en este prototipo." /><section className="card"><div className="plan-header"><h2>Una base pequeña y revisable</h2><span className="subtle-tag">PLANIFICADO</span></div><div className="feature-row"><Icon name="book" /><div><h3>Skills declarativas</h3><p>Propósito, entradas, permisos, versión y evaluación antes de activarlas.</p></div></div><div className="feature-row"><Icon name="shield" /><div><h3>Memoria por proyecto</h3><p>Fuentes visibles, información que caduca y borrado controlado.</p></div></div><div className="feature-row"><Icon name="chart" /><div><h3>Promoción basada en evidencia</h3><p>Una skill solo mejora el sistema si supera una evaluación independiente.</p></div></div></section></>}
          {page === 'measurements' && <><PageHeading title="Optimizar empieza por medir." text="Resultados observados, separados de la simulación de tareas." /><section className="card"><div className="plan-header"><h2>Referencia CPU · V5.3</h2><span className="subtle-tag">{baseline.status}</span></div><p className="muted">{baseline.description}</p>{baseline.rows.length > 0 && <div className="table-scroll"><table><thead><tr><th>Roles</th><th>Ensayos</th><th>Mediana total</th><th>Pico RAM¹</th></tr></thead><tbody>{baseline.rows.map(r => <tr key={r.roles}><td>{r.roles}</td><td>{r.samples}</td><td>{r.seconds.toFixed(2)} s</td><td>{r.workingSetGiB.toFixed(2)} GiB</td></tr>)}</tbody></table></div>}<div className="info-strip">¹ Suma de conjuntos residentes muestreada del backend; puede contar páginas compartidas más de una vez. No incluye la interfaz. La calidad de los comentarios no está evaluada.</div><p className="muted">GPU, consumo eléctrico y tiempo hasta el primer token: sin medir en esta referencia.</p></section></>}
          <footer className="content-footer">Construido para que el trabajo sea tuyo. <span>Gratis · Open source · Sin funciones de pago</span></footer>
        </main>
        <aside className="inspector" aria-label="Detalles y controles de la demostración">
          <div className="inspector-heading"><Icon name="chip" size={18} /><h2>Control del trabajo</h2></div>
          <div className="inspector-block"><p className="eyebrow">PRESUPUESTO DE DEMO</p><div className="budget-number">{state.attempts}<span> / 3 intentos</span></div><div className="budget-track" aria-hidden="true">{[0, 1, 2].map(n => <span key={n} className={n < state.attempts ? 'used' : ''} />)}</div><p>Detener o fallar también consume un intento. Los límites reales siguen en el núcleo.</p></div>
          <div className="inspector-block"><label className="eyebrow" htmlFor="roles">EQUIPO DE LA DEMO</label><select id="roles" disabled={working} value={state.roles} onChange={e => dispatch({type:'CONFIGURE', roles:Number(e.target.value) as RoleCount, scenario:state.scenario})}><option value="1">1 rol · revisión breve</option><option value="3">3 roles · revisión contrastada</option><option value="7">7 roles · recorrido completo</option></select><p>Los roles trabajan en secuencia. Más roles no garantizan más calidad.</p></div>
          <div className="inspector-block"><label className="eyebrow" htmlFor="scenario">EXPLORAR UN ESCENARIO</label><select id="scenario" disabled={working} value={state.scenario} onChange={e => dispatch({type:'CONFIGURE', roles:state.roles, scenario:e.target.value as Scenario})}><option value="success">Recorrido completo</option><option value="startup-timeout">Fallo al arrancar</option><option value="interrupted">Recuperación pendiente</option></select><p>Escenarios sintéticos para revisar la experiencia antes de conectarla al motor.</p></div>
          <div className="inspector-block"><p className="eyebrow">RECURSOS EN ESTA VISTA</p><dl><div><dt>Inferencias reales</dt><dd>0</dd></div><div><dt>RAM del modelo</dt><dd>Sin medir</dd></div><div><dt>GPU del modelo</dt><dd>No utilizada</dd></div></dl><button className="text-button" onClick={() => setPage('measurements')}>Ver referencia medida <Icon name="arrow" size={14} /></button></div>
          <button className="stop-button" disabled={!['BOOTING','RUNNING','VERIFYING'].includes(state.phase)} onClick={() => dispatch({type:'CANCEL'})}><Icon name="stop" size={15} />Detener simulación</button>
          <p className="inspector-footnote">La interfaz solicita acciones. El núcleo deberá validar permisos, presupuesto y estado.</p>
        </aside>
      </div>
    </div>
    <dialog ref={dialog} aria-labelledby="demo-dialog-title"><div className="dialog-content"><p className="eyebrow">VISTA PREVIA V5.3</p><h2 id="demo-dialog-title">Explora cómo se sentirá tu oficina.</h2><p>Prueba el recorrido completo, detén una tarea o elige un fallo de arranque. Toda la actividad ocurre en memoria dentro de esta pestaña.</p><p>La aplicación Python sigue siendo el piloto operativo. Este diseño no abre archivos, inicia modelos ni crea proyectos reales.</p><button className="primary" onClick={() => {dialog.current?.close(); setPage('workspace');}}>Entendido, explorar <Icon name="arrow" size={17} /></button></div></dialog>
  </div>;
}
function PageHeading({title,text}:{title:string;text:string}) { return <div className="page-heading"><div><p className="eyebrow">NEURAL OFFICE</p><h1>{title}</h1><p>{text}</p></div></div>; }
