import React, {useEffect, useMemo, useState} from 'react';

function statusFromActivity(runtime, diagnostics) {
  const explicit = String(runtime || '').trim();
  if (explicit && explicit !== 'Trabalhando') return explicit;
  const latest = diagnostics?.[diagnostics.length - 1];
  const title = String(latest?.title || '').toLowerCase();
  const detail = String(latest?.detail || '').toLowerCase();
  if (detail.includes('web.search') || title.includes('pesquisa')) return 'Buscando fontes relevantes';
  if (detail.includes('web.read') || title.includes('leitura')) return 'Lendo as fontes encontradas';
  if (title.includes('contexto')) return 'Consultando o contexto disponível';
  if (title.includes('artefato')) return 'Preparando o material';
  if (title.includes('resposta')) return 'Finalizando a resposta';
  if (title.includes('preparando')) return 'Preparando o contexto';
  return 'Entendendo o pedido';
}

export function WorkspaceTaskProgress({running = false, runtime = '', diagnostics = []}) {
  const status = useMemo(() => statusFromActivity(runtime, diagnostics), [runtime, diagnostics]);
  const [elapsed, setElapsed] = useState(0);
  const completed = useMemo(() => {
    const ignored = /^(Entendendo o pedido|Resposta concluída|Execução concluída)$/i;
    const seen = new Set();
    return (diagnostics || []).filter(item => {
      const title = String(item?.title || '').trim();
      if (!title || ignored.test(title) || seen.has(title)) return false;
      seen.add(title);
      return true;
    }).slice(-3);
  }, [diagnostics]);
  useEffect(() => {
    if (!running) return undefined;
    const started = Date.now();
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed(Math.max(1, Math.round((Date.now() - started) / 1000))), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  if (!running) return null;
  return <div className="cadu-ds-task-progress">
    <div className="cadu-ds-task-progress__header"><span>Trabalhando{elapsed ? ` há ${elapsed} s` : ''}</span></div>
    {!!completed.length && <div className="cadu-ds-task-progress__results" aria-label="Etapas concluídas">{completed.map(item => <div key={item.id}><span aria-hidden="true">✓</span><p>{item.title}{item.detail && <small>{item.detail}</small>}</p></div>)}</div>}
    <div className="cadu-ds-task-progress__current" role="status" aria-live="polite" aria-atomic="true"><span className="cadu-ds-task-progress__spinner" aria-hidden="true"/><span key={status} className="cadu-ds-task-progress__text">{status}<span aria-hidden="true">…</span></span></div>
  </div>;
}
