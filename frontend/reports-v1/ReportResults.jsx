import React, {useEffect, useState} from 'react';
import {ArrowDown, ArrowUp} from '@untitledui/icons';
import {Card, Alert, EmptyNote} from './ReportsBlocks.jsx';
import {json, shortDate} from './reportsCommon.jsx';
import {currency, number} from './hubs/shared.jsx';

const API = '/connect/api/v2/reports';
const pct = value => value == null ? '—' : `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;

/** Variation vs the previous period of the same length; `inverse` when lower is better (CPA, CPC). */
function Delta({now, before, inverse = false}) {
  if (now == null || !before) return null;
  const change = (now - before) * 100 / before;
  if (!Number.isFinite(change) || Math.abs(change) < 0.5) return <small className="block text-xs text-quaternary">estável</small>;
  const good = inverse ? change < 0 : change > 0;
  const Icon = change > 0 ? ArrowUp : ArrowDown;
  return <small className={`flex items-center gap-0.5 text-xs ${good ? 'text-success-primary' : 'text-error-primary'}`}><Icon size={12} aria-hidden="true"/>{pct(Math.abs(change))}</small>;
}

function Kpi({label, value, children}) {
  return <div className="bg-primary px-4 py-3"><dt className="text-sm text-tertiary">{label}</dt><dd className="mt-0.5 text-xl font-semibold text-primary tabular-nums">{value}</dd>{children}</div>;
}

/** Funnel row: each stage with its volume and the rate from the stage before. */
function Funnel({stages}) {
  const top = Math.max(...stages.map(stage => stage.value || 0), 1);
  return <ol className="flex flex-col gap-2">{stages.map((stage, index) => {
    const before = index ? stages[index - 1].value : null;
    return <li key={stage.label} className="grid grid-cols-[150px_minmax(0,1fr)_110px] items-center gap-3 text-sm">
      <span className="text-secondary">{stage.label}<small className="block text-xs text-quaternary">{stage.source}</small></span>
      <span className="h-6 overflow-hidden rounded bg-secondary"><span className="block h-full rounded bg-brand-solid" style={{width: `${Math.max(2, 100 * (stage.value || 0) / top)}%`}}/></span>
      <span className="text-right tabular-nums text-primary">{stage.display ?? number(stage.value)}{before ? <small className="block text-xs text-tertiary">{pct(100 * (stage.value || 0) / before)} da etapa anterior</small> : null}</span>
    </li>;
  })}</ol>;
}

/** Results at the top of a report: real media numbers for its campaign(s) and, for a flow, the journey in one funnel. */
export function ReportResults({report, onJourney, onTotals}) {
  const document = report.document || {};
  const flow = document.scope === 'flow' && document.flow_id;
  const [media, setMedia] = useState({loading: true});
  const [journey, setJourney] = useState(flow ? {loading: true} : null);
  useEffect(() => {
    let live = true;
    setMedia({loading: true});
    json(`${API}/workspaces/${report.id}/results`).then(body => {
      if (!live) return;
      setMedia({body});
      onTotals?.(body.totals);
      if (flow) json(`${API}/flow/flows/${document.flow_id}/journey?${new URLSearchParams({start_date: body.period.start, end_date: body.period.end})}`)
        .then(value => {
          if (!live) return;
          setJourney({body: value});
          // What a publication freezes from the journey: totals and step sessions, no personal data.
          const names = Object.fromEntries((value.config?.nodes || []).map(node => [node.id, node.title || node.label || node.name || node.id]));
          if (value.status === 'ready') onJourney?.({funnel: value.funnel, steps: (value.nodes || []).filter(node => node.sessions != null).map(node => ({name: names[node.id], sessions: node.sessions}))});
        }).catch(failure => live && setJourney({error: failure.message}));
    }).catch(failure => live && setMedia({error: failure.message}));
    return () => {live = false;};
  }, [report.id, report.revision]);

  const body = media.body;
  const money = value => currency(value, body?.currency);
  const t = body?.totals, p = body?.previous;
  const j = journey?.body?.status === 'ready' ? journey.body : null;
  const labels = Object.fromEntries((j?.config?.nodes || []).map(node => [node.id, node.title || node.label || node.name || node.id]));
  const steps = (j?.nodes || []).filter(node => node.sessions != null);
  const title = flow ? `Resultados · fluxo ${document.flow_name}` : 'Resultados da campanha';
  const description = body ? `${shortDate(body.period.start)} – ${shortDate(body.period.end)}${body.period.defaulted ? ' (últimos 30 dias; defina o período no documento)' : ''} · comparado aos ${Math.round((new Date(body.period.end) - new Date(body.period.start)) / 864e5) + 1} dias anteriores` : 'Dados reais das fontes conectadas.';

  return <Card title={title} description={description}>
    {media.loading ? <p className="text-sm text-tertiary">Carregando resultados…</p>
      : media.error ? <Alert>{media.error}</Alert>
      : !t ? <EmptyNote title={flow ? 'Nenhuma campanha ligada a este fluxo' : 'Relatório sem campanha'}>{flow ? 'Ligue campanhas ao fluxo ou às etapas em Site & Jornada › Fluxos para ver investimento e custo por conversão.' : 'Vincule uma campanha para ver os resultados de mídia.'}</EmptyNote>
      : <div className="flex flex-col gap-6">
        <dl className="grid gap-px overflow-hidden rounded-lg bg-border-secondary ring-1 ring-secondary sm:grid-cols-3 lg:grid-cols-6">
          <Kpi label="Investimento" value={money(t.cost)}><Delta now={t.cost} before={p?.cost}/></Kpi>
          <Kpi label="Impressões" value={number(t.impressions)}><Delta now={t.impressions} before={p?.impressions}/></Kpi>
          <Kpi label="Cliques" value={number(t.clicks)}><Delta now={t.clicks} before={p?.clicks}/></Kpi>
          <Kpi label="CTR" value={pct(t.ctr)}><Delta now={t.ctr} before={p?.ctr}/></Kpi>
          <Kpi label="Conversões (mídia)" value={number(t.conversions)}><Delta now={t.conversions} before={p?.conversions}/></Kpi>
          <Kpi label={t.roas != null ? 'ROAS' : 'CPA'} value={t.roas != null ? t.roas.toLocaleString('pt-BR') : money(t.cpa)}>{t.roas != null ? <Delta now={t.roas} before={p?.roas}/> : <Delta now={t.cpa} before={p?.cpa} inverse/>}</Kpi>
        </dl>

        {flow && <section className="flex flex-col gap-3">
          <h3 className="text-md font-semibold text-primary">Da mídia à conversão</h3>
          {journey?.loading ? <p className="text-sm text-tertiary">Carregando a jornada…</p>
            : journey?.error ? <Alert>{journey.error}</Alert>
            : !j ? <p className="text-sm text-tertiary">Jornada indisponível: publique o fluxo para medir as etapas.</p>
            : <>
              <Funnel stages={[
                {label: 'Impressões', source: 'Mídia', value: t.impressions},
                {label: 'Cliques', source: 'Mídia', value: t.clicks},
                {label: 'Entradas no fluxo', source: 'Super Tag', value: j.funnel?.entries},
                {label: 'Conversões do fluxo', source: 'Super Tag', value: j.funnel?.conversions},
              ]}/>
              <dl className="grid gap-px overflow-hidden rounded-lg bg-border-secondary ring-1 ring-secondary sm:grid-cols-3">
                <Kpi label="Custo por entrada" value={j.funnel?.entries ? money(t.cost / j.funnel.entries) : '—'}/>
                <Kpi label="Custo por conversão do fluxo" value={j.funnel?.conversions ? money(t.cost / j.funnel.conversions) : '—'}/>
                <Kpi label="Clique → entrada" value={t.clicks && j.funnel?.entries != null ? pct(100 * j.funnel.entries / t.clicks) : '—'}/>
              </dl>
              {steps.length > 0 && <table className="w-full text-sm"><thead><tr><th className="py-2 text-left font-medium text-tertiary">Etapa</th><th className="py-2 text-right font-medium text-tertiary">Sessões</th></tr></thead>
                <tbody>{steps.map(node => <tr key={node.id} className="border-t border-secondary"><td className="py-2 text-primary">{labels[node.id]}</td><td className="py-2 text-right tabular-nums">{number(node.sessions)}</td></tr>)}</tbody></table>}
              {j.collection?.status === 'no_data' && <p className="text-sm text-tertiary">Nenhum evento da Super Tag no período.</p>}
            </>}
        </section>}

        {body.campaigns.length > 0 && <section className="flex flex-col gap-2">
          <h3 className="text-md font-semibold text-primary">{body.campaigns.length === 1 ? 'Campanha' : `Campanhas (${body.campaigns.length})`}</h3>
          <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm">
            <thead><tr>{['Campanha', 'Investimento', 'Cliques', 'CTR', 'Conversões', 'CPA'].map((head, index) => <th key={head} className={`py-2 font-medium text-tertiary ${index ? 'text-right' : 'text-left'}`}>{head}</th>)}</tr></thead>
            <tbody>{body.campaigns.map(row => <tr key={row.id} className="border-t border-secondary">
              <td className="py-2 text-primary">{row.name}<small className="block text-xs text-tertiary">{row.platform === 'google_ads' ? 'Google Ads' : row.platform || 'manual'}{row.external_id ? ` · ID ${row.external_id}` : ''}</small></td>
              <td className="py-2 text-right tabular-nums">{money(row.cost)}</td><td className="py-2 text-right tabular-nums">{number(row.clicks)}</td>
              <td className="py-2 text-right tabular-nums">{pct(row.ctr)}</td><td className="py-2 text-right tabular-nums">{number(row.conversions)}</td>
              <td className="py-2 text-right tabular-nums">{money(row.cpa)}</td></tr>)}</tbody>
          </table></div>
        </section>}
        {!t.impressions && !t.cost && <p className="text-sm text-tertiary">Sem dados de mídia no período. Confira os envios em Fontes de dados › Conexões e chaves.</p>}
      </div>}
  </Card>;
}
