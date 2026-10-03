import React, {useState} from 'react';
import {Check, Stars02} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge} from '../cadu-design-system/untitled-kit/badges.tsx';
import {Card} from './ReportsBlocks.jsx';
import {json} from './reportsCommon.jsx';
import {formatMetric} from './reportMetrics.js';

const API = '/connect/api/v2/reports';
const SEVERITY = {high: ['Alta', 'error'], medium: ['Média', 'warning'], low: ['Baixa', 'gray']};

/** On-demand agents: review the captured data, draft the next version, suggest metrics. They only propose. */
export function ReportAgents({report, csrf, document, journey, onApplyDraft, onAddMetrics}) {
  const [running, setRunning] = useState('');
  const [error, setError] = useState('');
  const [review, setReview] = useState(null);
  const [draft, setDraft] = useState(null);
  const [accepted, setAccepted] = useState({});
  const [suggestions, setSuggestions] = useState(null);
  const call = async kind => {
    setRunning(kind); setError('');
    try {
      const body = await json(`${API}/workspaces/${report.id}/agents/${kind}`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify({document, journey})});
      if (kind === 'review') setReview(body);
      if (kind === 'draft') {setDraft(body); setAccepted(Object.fromEntries([...body.changes, ...body.added].map(item => [item.id, true])));}
      if (kind === 'metrics') setSuggestions(body.suggestions);
    } catch (failure) {setError(failure.message);} finally {setRunning('');}
  };
  const applyDraft = () => {
    onApplyDraft({changes: draft.changes.filter(item => accepted[item.id]), added: draft.added.filter(item => accepted[item.id]), summary: draft.summary});
    setDraft(null);
  };
  const busy = Boolean(running);
  return <Card title="Agentes" description="Rodam quando você clica. Só propõem: nada muda sem você aceitar e salvar.">
    <div className="flex flex-col gap-2">
      <Button size="sm" color="secondary" iconLeading={Stars02} isDisabled={busy} isLoading={running === 'review'} onPress={() => call('review')}>Revisar dados capturados</Button>
      <Button size="sm" color="secondary" iconLeading={Stars02} isDisabled={busy} isLoading={running === 'draft'} onPress={() => call('draft')}>Propor nova versão</Button>
      <Button size="sm" color="secondary" iconLeading={Stars02} isDisabled={busy} isLoading={running === 'metrics'} onPress={() => call('metrics')}>Sugerir métricas</Button>
    </div>
    {error && <p role="alert" className="mt-3 text-sm text-error-primary">{error}</p>}

    {review && <div className="mt-4 flex flex-col gap-2 border-t border-secondary pt-4">
      <p className="text-sm font-semibold text-primary">{review.findings.length ? `${review.findings.length} ponto(s) nos dados` : 'Nenhum problema encontrado nos dados deste período.'}</p>
      {review.findings.map(item => <div key={item.code} className={`rounded-lg p-3 ring-1 ring-inset ${review.fix_first === item.code ? 'ring-2 ring-brand' : 'ring-secondary'}`}>
        <div className="flex flex-wrap items-center gap-2"><Badge type="pill-color" size="sm" color={SEVERITY[item.severity][1]}>{SEVERITY[item.severity][0]}</Badge>
          {review.fix_first === item.code && <Badge type="pill-color" size="sm" color="brand">Corrigir primeiro</Badge>}</div>
        <p className="mt-1 text-sm font-medium text-primary">{item.title}</p>
        <p className="text-sm text-tertiary">{item.evidence}</p>
        {item.action?.href && <a className="mt-1 inline-block text-sm font-semibold text-brand-secondary hover:underline" href={item.action.href}>{item.action.label} →</a>}
        {item.action?.kind === 'edit_period' && <p className="mt-1 text-sm text-secondary">{item.action.label}.</p>}
      </div>)}
    </div>}

    {draft && <div className="mt-4 flex flex-col gap-3 border-t border-secondary pt-4">
      <p className="text-sm font-semibold text-primary">Proposta de nova versão</p>
      {draft.summary && <p className="text-sm text-secondary">{draft.summary}</p>}
      {[...draft.changes.map(item => ({...item, label: item.title, text: item.after})), ...draft.added.map(item => ({...item, label: `Novo: ${item.title}`}))].map(item =>
        <label key={item.id} className="flex cursor-pointer gap-2 rounded-lg p-3 ring-1 ring-secondary ring-inset">
          <input type="checkbox" className="mt-1 size-4 shrink-0 accent-brand-600" checked={Boolean(accepted[item.id])} onChange={event => setAccepted(current => ({...current, [item.id]: event.target.checked}))}/>
          <span className="min-w-0"><span className="block text-sm font-semibold text-primary">{item.label}</span>
            <span className="block max-h-40 overflow-y-auto text-sm whitespace-pre-line text-secondary">{item.text}</span></span>
        </label>)}
      <div className="flex gap-2">
        <Button size="sm" color="primary" iconLeading={Check} isDisabled={!Object.values(accepted).some(Boolean)} onPress={applyDraft}>Aplicar ao rascunho</Button>
        <Button size="sm" color="tertiary" onPress={() => setDraft(null)}>Descartar</Button>
      </div>
      <p className="text-xs text-tertiary">Aplicar muda o editor; salve para criar a nova versão e publique quando quiser.</p>
    </div>}

    {suggestions && <div className="mt-4 flex flex-col gap-2 border-t border-secondary pt-4">
      <p className="text-sm font-semibold text-primary">Métricas sugeridas</p>
      {suggestions.map(item => <div key={item.id} className="rounded-lg p-3 ring-1 ring-secondary ring-inset">
        <div className="flex items-start justify-between gap-2"><span className="text-sm font-semibold text-primary">{item.name}</span><strong className="text-sm tabular-nums">{formatMetric(item.preview, item.unit)}</strong></div>
        <code className="block text-xs text-tertiary">{item.formula}</code>
        {item.why && <p className="mt-1 text-sm text-tertiary">{item.why}</p>}
        <Button size="sm" color="link-color" onPress={() => {onAddMetrics([item]); setSuggestions(current => current.filter(other => other.id !== item.id));}}>Adicionar ao relatório</Button>
      </div>)}
    </div>}
  </Card>;
}
