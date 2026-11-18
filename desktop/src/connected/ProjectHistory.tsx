import {useEffect, useState} from 'react';
import {request} from './client.ts';
import {acceptAttempt, stateLabels, terminal} from './model.ts';
import type {Attempt, Snapshot} from './model.ts';

type Props = {
  project: string; snapshot: Snapshot | null; selected?: string; disabled: boolean;
  offline: boolean; onOpen: (item: Attempt) => void; onRefresh: () => Promise<void>;
};
type Page = Pick<Snapshot, 'session_id' | 'office_id' | 'revision' | 'attempts'> & {project_id: string};

export function ProjectHistory({project, snapshot, selected, disabled, offline, onOpen, onRefresh}: Props) {
  const [page, setPage] = useState<Page | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const scoped = snapshot?.has_more.attempts;
  const office = snapshot?.office_id, session = snapshot?.session_id, revision = snapshot?.revision;
  useEffect(() => {
    if (!scoped || offline) return;
    let current = true;
    setFailed(false);
    request<Page>('project.history', {project_id: project}).then(reply => {
      if (!current) return;
      if (reply.project_id !== project || reply.office_id !== office || reply.session_id !== session ||
          !Number.isSafeInteger(reply.revision) || reply.revision !== revision ||
          !Array.isArray(reply.attempts) || reply.attempts.length > 3) throw Error('HISTORY_CONTRACT');
      let previous = 4;
      const ids = new Set<string>();
      for (const row of reply.attempts) {
        acceptAttempt(null, row);
        if (row.project_id !== project || ids.has(row.id) || !Number.isInteger(row.ordinal) ||
            row.ordinal < 1 || row.ordinal >= previous) throw Error('HISTORY_CONTRACT');
        previous = row.ordinal;
        ids.add(row.id);
      }
      setPage(reply);
    }).catch(() => { if (current) setFailed(true); });
    return () => { current = false; };
  }, [project, office, session, scoped, offline, retry, revision]);
  const rows = scoped ? (page?.revision === revision ? page?.attempts : undefined)
    : snapshot?.attempts.filter(a => a.project_id === project).sort((a,b) => b.ordinal-a.ordinal);
  return <div className="connected-history">
    {failed && <p role="status">No se pudo confirmar el historial. <button className="nav-secondary" disabled={offline||disabled} onClick={() => void onRefresh().then(() => setRetry(n => n+1))}>Reintentar lectura</button></p>}
    {rows?.map(a => <button key={a.id} className={a.id === selected ? 'selected' : ''} aria-current={a.id === selected ? 'true' : undefined} disabled={disabled || failed} onClick={() => onOpen(a)}>
      <span className={`history-dot ${terminal(a.state) ? 'finished' : ''}`}/><span><strong>{a.objective}</strong><small>{stateLabels[a.state]} · intento {a.ordinal}</small></span>
    </button>)}
    {!failed && !rows && <p className="history-empty">{offline ? 'Historial pendiente de conexión.' : 'Leyendo historial…'}</p>}
    {!failed && rows?.length === 0 && <p className="history-empty">Aquí quedarán las entregas de este proyecto.</p>}
  </div>;
}
