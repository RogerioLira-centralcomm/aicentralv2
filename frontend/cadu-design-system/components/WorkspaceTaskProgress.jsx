import React, {useMemo} from 'react';

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
  if (!running) return null;
  return <div className="cadu-ds-task-progress" role="status" aria-live="polite" aria-atomic="true">
    <span className="cadu-ds-task-progress__spinner" aria-hidden="true"/>
    <span key={status} className="cadu-ds-task-progress__text">{status}<span aria-hidden="true">…</span></span>
  </div>;
}
