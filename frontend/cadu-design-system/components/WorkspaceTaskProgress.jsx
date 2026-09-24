import React, {useEffect, useMemo, useState} from 'react';

function statusFromActivity(runtime, diagnostics) {
  const explicit = String(runtime || '').trim();
  if (explicit && explicit !== 'Trabalhando') return explicit;
  const latest = diagnostics?.[diagnostics.length - 1];
  const title = String(latest?.title || '').trim();
  return title && latest?.tone !== 'error' ? title : 'Processando pedido';
}

export function WorkspaceTaskProgress({running = false, runtime = '', diagnostics = [], plugin = null, caduMark = ''}) {
  const status = useMemo(() => statusFromActivity(runtime, diagnostics), [runtime, diagnostics]);
  const recent = useMemo(() => (diagnostics || []).filter(item => item?.title && item.tone !== 'error').slice(-3), [diagnostics]);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!running) return undefined;
    const started = Date.now();
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed(Math.max(1, Math.round((Date.now() - started) / 1000))), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  if (!running) return null;
  return <div className="cadu-ds-task-progress">
    {plugin?.name && <div className="cadu-ds-task-progress__plugin" aria-label={`Plugin selecionado: ${plugin.name}`}>
      <span>{caduMark ? <img src={caduMark} alt=""/> : 'C'}</span><b>{plugin.name}</b>
    </div>}
    <div className="cadu-ds-task-progress__current">
      <div className="cadu-ds-task-progress__announcement" role="status" aria-live="polite" aria-atomic="true">
        <span className="cadu-ds-task-progress__spark" aria-hidden="true"/>
        <span key={status} className="cadu-ds-task-progress__text">{status}</span>
      </div>
      {elapsed >= 4 && <small aria-hidden="true">{elapsed}s</small>}
    </div>
    {recent.length > 1 && <details className="cadu-ds-task-progress__history"><summary>Atividade recente</summary><ul>{recent.map(item => <li key={item.id || `${item.title}-${item.detail || ''}`}>{item.title}</li>)}</ul></details>}
  </div>;
}
