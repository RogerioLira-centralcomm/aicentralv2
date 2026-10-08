import React from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {RadarAnimation} from './RadarAnimation.jsx';

// Etapas mostradas na hora do clique; as de verdade (com tokens e detalhes) chegam do servidor logo depois.
export const PENDING_STEPS = [
  ['buzz', 'Procurando o que está em alta', 'O Perplexity busca o que está gerando buzz agora sobre o conceito.'],
  ['check', 'Conferindo as fontes', 'Só entra o que tem data recente e link que abre.'],
  ['angles', 'Montando os ângulos', 'Ideias para a marca falar do conceito aproveitando o buzz.'],
  ['save', 'Organizando o resultado', 'O buzz e os ângulos ficam salvos para virar plano.'],
].map(([key, label, hint], index) => ({key, label, hint, status: index === 0 ? 'running' : 'pending', tokens: 0, detail: '', parallel: false}));
const STEP_STATUS = {pending: 'Aguardando', running: 'Em andamento', done: 'Concluída', failed: 'Falhou', skipped: 'Pulada'};
export const tokens = value => Number(value || 0).toLocaleString('pt-BR');

function StepNode({step}) {
  return <li className={`radar-step is-${step.status}`}>
    <span className="radar-step__mark" aria-hidden="true">
      {step.status === 'done' ? <Icon name="check" size={12}/> : step.status === 'failed' ? <Icon name="close" size={12}/> : null}
    </span>
    <span className="radar-step__copy">
      <strong>{step.label}</strong>
      <small>{step.detail || step.hint}</small>
      {(step.preview || []).length > 0 && <span className="radar-step__preview">{step.preview.map(item => <i key={item.url || item.title}
        title={item.url || item.title}>{item.title}{item.score != null && <b>{item.score}</b>}</i>)}</span>}
    </span>
    <span className="radar-step__meta"><small className="sr-only">{STEP_STATUS[step.status]}</small>{step.tokens > 0 && <>{tokens(step.tokens)} tokens</>}</span>
  </li>;
}

/**
 * The run as a chain: two independent discovery flows side by side, then the
 * steps that depend on both. Each node shows what it found and what it cost.
 */
export function RunChain({run}) {
  const steps = run.steps || [];
  const parallel = steps.filter(step => step.parallel);
  const serial = steps.filter(step => !step.parallel);
  const running = run.status === 'running';
  return <section className="radar-run" aria-labelledby="radar-run-title" aria-live="polite">
    <div className={`radar-run__head${running ? ' is-running' : ''}`}>
      <RadarAnimation steps={steps} running={running}/>
      <div>
        <h2 id="radar-run-title">{running ? 'O Radar está procurando' : run.status === 'failed' ? 'A busca parou' : 'Busca concluída'}</h2>
        <p>{run.focus ? `Tema: ${run.focus}` : 'Tema a partir da marca e do projeto escolhidos.'}</p>
        <p className="radar-run__cost"><Icon name="analysis" size={14}/>
          <span><b>{tokens(run.tokens)}</b> tokens usados{run.estimated_tokens ? ` de até ${tokens(run.estimated_tokens)} reservados` : ''}.
            {running ? ' Você paga só o que for usado.' : ''}</span></p>
        {run.error && <p className="radar-run__error">{run.error}</p>}
      </div>
    </div>
    {/* Terminada a busca, o passo a passo recolhe: o que importa é o resultado. */}
    <details className="radar-chain-details" key={run.status} open={run.status !== 'done'}>
      <summary>Como a busca foi feita</summary>
      <ol className="radar-chain">
        {parallel.length > 0 && <li className="radar-chain__fork"><span className="radar-chain__label">Em paralelo</span><ol>{parallel.map(step => <StepNode key={step.key} step={step}/>)}</ol></li>}
        {serial.map(step => <StepNode key={step.key} step={step}/>)}
      </ol>
    </details>
  </section>;
}

