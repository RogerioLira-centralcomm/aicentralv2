import React, {useState} from 'react';
import StudioDialog from '../cadu-studio-ui/StudioDialog';
import {Badge, CopyUrl, FAILURE_LABEL, Notes, ROLE_LABEL, ScorePill, StatusBadge, Swatches, percent, seconds, usd} from './ui';

const RATING_FIELDS = [
  ['composition', 'Composição'], ['product_fidelity', 'Fidelidade do produto'], ['brand_fidelity', 'Fidelidade da marca'],
  ['text_quality', 'Texto'], ['aesthetic', 'Estética'],
];

function Bar({label, value, invert = false}) {
  if (value == null) return null;
  const good = invert ? 1 - value : value;
  return <div className="lab-bar">
    <span>{label}</span>
    <i><b style={{width: `${Math.round(value * 100)}%`}} className={good >= 0.75 ? 'is-ok' : good >= 0.5 ? 'is-warn' : 'is-bad'}/></i>
    <strong>{percent(value)}</strong>
  </div>;
}

function Evaluation({run}) {
  const observer = run.observer?.payload || {};
  const observation = observer.observation || {};
  const measurements = observer.measurements || {};
  const ts = run.typesafe || {};
  const scores = ts.scores || {};
  if (!run.observer && !run.typesafe) return <p className="lab-muted">{run.status === 'succeeded' ? 'Avaliação em andamento…' : 'Sem avaliação: a geração não concluiu.'}</p>;
  return <div className="lab-eval">
    <div className="lab-eval__head">
      <ScorePill score={scores.overall}/>
      <div>
        <strong>{FAILURE_LABEL[ts.primary_failure] || 'Sem diagnóstico'}</strong>
        <small className="lab-muted">falha principal · confiança {percent(scores.primary_failure?.confidence)} · {ts.model || 'TypeSafe'}</small>
      </div>
    </div>
    {ts.payload?.error && <p className="lab-alert">TypeSafe: {ts.payload.error}</p>}
    <Bar label="Fidelidade à instrução" value={scores.instruction_fidelity}/>
    <Bar label="Texto exato" value={scores.text_exact}/>
    <Bar label="Aderência à marca" value={scores.brand_fit}/>
    <Bar label="Elemento proibido" value={scores.forbidden_present} invert/>
    <Bar label="Prompt perdeu requisito" value={scores.prompt_drift} invert/>
    {scores.references_respected && <p><small className="lab-muted">Referências:</small> <Badge>{scores.references_respected.choice}</Badge></p>}
    {scores.edit_scope && <p><small className="lab-muted">Escopo da edição:</small> <Badge>{scores.edit_scope.choice}</Badge></p>}
    {(ts.suggestions || []).map(item => <div key={item.failure} className="lab-suggestion">
      <small>Sugestão para o manifesto (aguarda revisão)</small>
      <p>{item.rationale}</p>
      <code>{JSON.stringify(item.change)}</code>
    </div>)}
    <h4>Texto lido na imagem</h4>
    {(measurements.text?.items || []).length ? <ul className="lab-checks">
      {measurements.text.items.map(item => <li key={item.text} className={item.exact ? 'is-ok' : 'is-bad'}>
        {item.exact ? '✓' : '✕'} “{item.text}”{item.accent_lost ? ' — perdeu acento' : ''}
      </li>)}
    </ul> : null}
    <p className="lab-mono">{(observation.visible_text || []).map(text => `“${text}”`).join(' · ') || 'nenhum texto'}</p>
    <h4>Cor</h4>
    <div className="lab-palette-compare">
      <div><small className="lab-muted">dominantes</small><Swatches colors={(measurements.palette?.dominant || []).map(item => item.hex)}/></div>
      {measurements.palette?.brand_distances && <div><small className="lab-muted">marca · aderência {percent(measurements.palette.adherence)}</small>
        <Swatches colors={measurements.palette.brand_distances.map(item => item.hex)}/></div>}
    </div>
    <h4>O que o observador viu</h4>
    <p>{observation.scene}</p>
    {observation.overall_fit && <p className="lab-muted">{observation.overall_fit}</p>}
    {(observation.references || []).length > 0 && <ul className="lab-checks">
      {observation.references.map(item => <li key={item.index}>{ROLE_LABEL[item.role] || item.role}: <strong>{item.verdict}</strong> {item.notes ? `— ${item.notes}` : ''}</li>)}
    </ul>}
    {(observation.unrequested_elements || []).length > 0 && <p><small className="lab-muted">Não pedido:</small> {observation.unrequested_elements.join('; ')}</p>}
    {(observation.defects || []).length > 0 && <p><small className="lab-muted">Defeitos:</small> {observation.defects.join('; ')}</p>}
    <p className="lab-muted lab-tiny">Observador {run.observer?.model} · {seconds(run.observer?.latency_ms)} · {usd(run.observer?.cost_usd)}</p>
  </div>;
}

function Plan({run}) {
  const plan = run.adaptation_plan || {};
  const groups = [['sent', 'Enviadas como imagem'], ['converted_to_text', 'Viraram texto'], ['post_processed', 'Pós-processadas'], ['dropped', 'Descartadas']];
  const params = plan.parameters || {};
  return <div className="lab-plan">
    <p><strong>{plan.summary}</strong></p>
    {plan.pipeline === 'studio' && <p>Pipeline do Studio · mockup {plan.mockup?.effective === 'image' ? 'enviado como imagem' : plan.mockup?.effective === 'text' ? 'descrito em texto' : 'desligado'}
      {plan.mockup?.degraded ? ' (o modelo não aceita a imagem)' : ''}{run.request_summary?.studio?.calls > 1 ? ` · ${run.request_summary.studio.calls} chamadas (correção de margem)` : ''}</p>}
    {plan.blocked && <p className="lab-alert">{plan.blocked}</p>}
    <div className="lab-plan__grid">
      {groups.map(([key, label]) => <div key={key} className="lab-plan__col">
        <small>{label}</small>
        {(plan[key] || []).length ? (plan[key] || []).map(ref => <span key={`${key}-${ref.ref_id}`} className="lab-plan__ref">
          {ROLE_LABEL[ref.role] || ref.role} · {ref.label}{ref.reason ? <em> — {ref.reason}</em> : ''}{ref.how === 'composer_overlay' ? <em> — Composer</em> : ''}
        </span>) : <span className="lab-muted">—</span>}
      </div>)}
    </div>
    <h4>Parâmetros</h4>
    <p className="lab-mono">{JSON.stringify(params.applied || {})}</p>
    {(params.transformed || []).map(item => <p key={item.param} className="lab-muted">{item.param}: {item.from} → {item.to} ({item.reason})</p>)}
    {(params.dropped || []).map(item => <p key={item.param} className="lab-muted">{item.param} descartado ({item.reason})</p>)}
    <h4>Custo e rota</h4>
    <p>Estimado {usd(run.estimated_cost_usd)} · real {usd(run.actual_cost_usd)} {run.cost_source ? `(${run.cost_source === 'provider' ? 'informado pelo provider' : 'tokens × preço do catálogo'})` : ''}</p>
    <p className="lab-muted">{run.provider_model_id} · {run.provider === 'openai_direct' ? 'OpenAI direto' : 'OpenRouter'} · perfil v{run.profile_version} · tentativa {run.attempt}</p>
    {run.usage && Object.keys(run.usage).length > 0 && <p className="lab-mono lab-tiny">{JSON.stringify(run.usage)}</p>}
  </div>;
}

function Rating({run, api, onSaved, blind}) {
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);
  const save = async verdict => {
    setBusy(true);
    try { const data = await api.post(`/runs/${run.run_id}/rating`, {...values, verdict, blind}); onSaved(data.run); setValues({}); }
    finally { setBusy(false); }
  };
  return <div className="lab-rating">
    {RATING_FIELDS.map(([key, label]) => <div key={key} className="lab-rating__row">
      <span>{label}</span>
      <div role="radiogroup" aria-label={label}>{[1, 2, 3, 4, 5].map(value =>
        <button type="button" key={value} aria-pressed={values[key] === value} className={values[key] === value ? 'is-on' : ''}
          onClick={() => setValues(current => ({...current, [key]: value}))}>{value}</button>)}</div>
    </div>)}
    <textarea rows={2} placeholder="Observações da avaliação" value={values.notes || ''} onChange={event => setValues(current => ({...current, notes: event.target.value}))}/>
    <div className="lab-row">
      <button type="button" className="lab-btn" disabled={busy} onClick={() => save('approved')}>Aprovar</button>
      <button type="button" className="lab-btn is-ghost" disabled={busy} onClick={() => save('discarded')}>Descartar</button>
    </div>
    {(run.ratings || []).length > 0 && <ul className="lab-ratings">{run.ratings.map(item => <li key={item.id}>
      <Badge kind={item.verdict === 'approved' ? 'is-succeeded' : 'is-failed'}>{item.verdict === 'approved' ? 'Aprovada' : 'Descartada'}</Badge>
      {RATING_FIELDS.filter(([key]) => item[key]).map(([key, label]) => `${label} ${item[key]}`).join(' · ')}
      {item.notes ? ` — ${item.notes}` : ''}{item.blind ? ' (cega)' : ''}
    </li>)}</ul>}
  </div>;
}

export default function RunDetail({run, models, experimentSpec, state, api, blind, onClose, onUpdated, onNotes, onRegenerate}) {
  const [tab, setTab] = useState('eval');
  const [showRaw, setShowRaw] = useState(false);
  const model = models.find(item => item.model_key === run.model_key);
  const hasRaw = run.raw_url && run.raw_url !== run.image_url;
  const image = showRaw && hasRaw ? run.raw_url : run.image_url;
  const tabs = [['eval', 'Avaliação'], ['plan', 'Plano'], ['prompt', 'Prompts'], ['rate', 'Nota humana'], ['notes', 'Anotações']];
  const reevaluate = async () => { const data = await api.post(`/runs/${run.run_id}/evaluate`, {}); onUpdated(data.run); };
  return <StudioDialog className="lab-detail" label="Detalhe da geração" onClose={onClose} closeOnBackdrop>
    <header className="lab-detail__head">
      <div>
        <small className="lab-muted">{run.experiment_title}</small>
        <h3>{blind ? 'Modelo oculto (avaliação cega)' : model?.label || run.model_key}</h3>
      </div>
      <div className="lab-row">
        <StatusBadge status={run.status}/>
        <span>{seconds(run.latency_ms)}</span>
        <span>{usd(run.actual_cost_usd ?? run.estimated_cost_usd)}</span>
        <button type="button" className="lab-btn is-ghost is-small" onClick={onClose} aria-label="Fechar">Fechar</button>
      </div>
    </header>
    <div className="lab-detail__body">
      <div className="lab-detail__media">
        <div className="lab-detail__frame">{image ? <img src={image} alt="Resultado"/> : <p className="lab-muted">{run.error?.message || 'Sem imagem.'}</p>}</div>
        {hasRaw && <div className="lab-segmented" role="group" aria-label="Versão da imagem">
          <button type="button" aria-pressed={!showRaw} onClick={() => setShowRaw(false)}>Com Composer</button>
          <button type="button" aria-pressed={showRaw} onClick={() => setShowRaw(true)}>Saída do modelo</button>
        </div>}
        <CopyUrl url={run.public_url}/>
        {run.width && <p className="lab-muted lab-tiny">{run.width}×{run.height}px · avaliado sobre a saída do modelo</p>}
        {run.error && <div className="lab-alert"><strong>{run.error.message}</strong>{run.error.detail ? <p className="lab-mono lab-tiny">{run.error.detail}</p> : null}</div>}
        <div className="lab-row">
          <button type="button" className="lab-btn is-small" onClick={() => onRegenerate(run)}>Gerar de novo</button>
          {run.status === 'succeeded' && <button type="button" className="lab-btn is-ghost is-small" onClick={reevaluate}>Reavaliar</button>}
        </div>
      </div>
      <div className="lab-detail__panel">
        <div className="lab-tabs is-small" role="tablist">{tabs.map(([key, label]) =>
          <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}>{label}</button>)}</div>
        {tab === 'eval' && <Evaluation run={run}/>}
        {tab === 'plan' && <Plan run={run}/>}
        {tab === 'prompt' && <div className="lab-prompts">
          <h4>Instrução original</h4><p>{run.instruction || "—"}</p>
          <h4>Prompt enviado ao modelo</h4><pre>{run.model_prompt}</pre>
        </div>}
        {tab === 'rate' && <Rating run={run} api={api} onSaved={onUpdated} blind={blind}/>}
        {tab === 'notes' && <Notes notes={state.notes} scope="run" scopeKey={run.run_id} api={api} onSaved={onNotes} placeholder="O que esta geração ensina sobre o modelo?"/>}
      </div>
    </div>
  </StudioDialog>;
}
