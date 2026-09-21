import React, {useMemo} from 'react';

const TASK_STEPS = [
  {id: 'context', label: 'Entendendo o pedido'},
  {id: 'search', label: 'Encontrando fontes'},
  {id: 'read', label: 'Lendo fontes relevantes'},
  {id: 'synthesis', label: 'Comparando e organizando'},
  {id: 'answer', label: 'Preparando a resposta'},
];

function stepFromDiagnostic(item) {
  const title = String(item?.title || '').toLowerCase();
  if (title.includes('pesquisa')) return 2;
  if (title.includes('leitura')) return 3;
  if (title.includes('contexto consultado') || title.includes('artefato')) return 4;
  if (title.includes('resposta') || title.includes('conclu')) return 4;
  return 0;
}

function userFacingUpdate(item) {
  const detail = String(item?.detail || '').toLowerCase();
  if (detail.includes('web.search')) return 'Buscando fontes relevantes';
  if (detail.includes('web.read')) return 'Lendo as fontes selecionadas';
  if (item?.title === 'Pesquisa inicial concluída') return 'Lendo as fontes selecionadas';
  if (item?.title === 'Leitura das fontes concluída') return 'Comparando fontes e organizando achados';
  if (item?.title === 'Contexto consultado') return 'Organizando o contexto disponível';
  if (item?.title === 'Artefato criado') return 'Material de trabalho preparado';
  if (item?.title === 'Resposta concluída') return 'Resposta pronta para revisão';
  return item?.title || 'Trabalho em andamento';
}

export function WorkspaceTaskProgress({running = false, runtime = '', diagnostics = [], compact = false}) {
  const model = useMemo(() => {
    const latest = diagnostics[diagnostics.length - 1];
    const activeIndex = Math.max(0, Math.min(TASK_STEPS.length - 1, stepFromDiagnostic(latest)));
    return {activeIndex, latest, update: userFacingUpdate(latest)};
  }, [diagnostics]);

  if (!running) return null;
  return <section className={`cadu-ds-task-progress${compact ? ' is-compact' : ''}`} aria-label="Andamento da tarefa" aria-live="polite">
    <header>
      <span className="cadu-ds-task-progress__pulse" aria-hidden="true"/>
      <div><strong>{runtime || 'Trabalhando'}</strong><small>{model.update}</small></div>
      <b>{model.activeIndex + 1}/{TASK_STEPS.length}</b>
    </header>
    <ol>
      {TASK_STEPS.map((step, index) => <li key={step.id} className={index < model.activeIndex ? 'is-done' : index === model.activeIndex ? 'is-active' : ''}>
        <span aria-hidden="true">{index < model.activeIndex ? '✓' : index + 1}</span>
        <strong>{step.label}</strong>
      </li>)}
    </ol>
  </section>;
}
