import React, {useEffect, useState} from 'react';
import {FAILURE_LABEL, ScorePill, Thumb, seconds, usd} from './ui';
import {ratioCss} from './Matrix';

function useNow(active) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);
  return now;
}

/** What is happening right now: the generation in progress, the queue and the latest results. */
export default function LiveQueue({runs, models, formats, blind, onOpen}) {
  const label = key => (blind ? 'Modelo oculto' : models.find(model => model.model_key === key)?.label || key);
  const formatLabel = run => formats.find(item => item.key === run.format_key)?.label || run.aspect_ratio || '';
  const running = runs.filter(run => run.status === 'running');
  const queued = runs.filter(run => run.status === 'queued').sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
  const recent = runs.filter(run => ['succeeded', 'failed', 'blocked'].includes(run.status) && run.finished_at)
    .sort((a, b) => (b.finished_at || '').localeCompare(a.finished_at || '')).slice(0, 8);
  const now = useNow(running.length > 0);
  const evaluating = runs.filter(run => run.status === 'succeeded' && !run.typesafe).length;
  if (!running.length && !queued.length && !recent.length) return null;
  return <section className="lab-live-panel" aria-label="Acompanhamento ao vivo">
    <div className="lab-live-panel__now">
      <small className="lab-muted">Agora</small>
      {running.length ? running.map(run => {
        const elapsed = run.started_at ? (now - new Date(run.started_at).getTime()) : null;
        return <div key={run.run_id} className="lab-live-panel__running">
          <i className="lab-spinner" aria-hidden="true"/>
          <div>
            <strong>{label(run.model_key)}</strong>
            <small>{run.experiment_title} · {formatLabel(run)}</small>
            <small className="lab-muted">{seconds(elapsed)} · estimado {usd(run.estimated_cost_usd)}</small>
          </div>
        </div>;
      }) : <p className="lab-muted">{queued.length ? 'Iniciando…' : 'Nada gerando.'}{evaluating ? ` ${evaluating} em avaliação.` : ''}</p>}
    </div>
    <div className="lab-live-panel__queue">
      <small className="lab-muted">Na fila · {queued.length}</small>
      <ol>{queued.slice(0, 4).map(run => <li key={run.run_id}>{label(run.model_key)} <span className="lab-muted">· {run.experiment_title} · {formatLabel(run)}</span></li>)}</ol>
      {queued.length > 4 && <small className="lab-muted">+{queued.length - 4} depois</small>}
    </div>
    <div className="lab-live-panel__recent">
      <small className="lab-muted">Últimos resultados</small>
      <div className="lab-live-panel__strip">
        {recent.map(run => <figure key={run.run_id}>
          <Thumb src={run.thumb_url} ratio={ratioCss(run.aspect_ratio)} status={run.status} onClick={() => onOpen(run)} alt={label(run.model_key)}/>
          <figcaption>
            <ScorePill score={run.typesafe?.scores?.overall}/>
            <small title={run.experiment_title}>{blind ? '' : label(run.model_key)}</small>
            <small className="lab-muted">{run.status === 'succeeded' ? (FAILURE_LABEL[run.typesafe?.primary_failure] || 'avaliando') : 'falhou'}</small>
          </figcaption>
        </figure>)}
      </div>
    </div>
  </section>;
}
