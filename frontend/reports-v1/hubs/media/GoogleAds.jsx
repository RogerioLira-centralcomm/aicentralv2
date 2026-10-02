import React, {useMemo, useState} from 'react';
import {ArrowRight, Download01, Copy01, Zap} from '@untitledui/icons';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {ReportsNativeSelect} from '../../ReportsNativeSelect.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {dayLabel, friendlyAgo, formatRange, toIsoDay} from '../../friendlyDates.js';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {Chart} from '../../shell/media.jsx';
import {DataTable, EmptyState, ErrorState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {MediaPerformance} from './MediaPerformance.jsx';
import {GoalDrawer, GoalsSection, OBJECTIVES, PacingBar} from './GoogleAdsGoals.jsx';
import {currency, number, percent} from '../shared.jsx';
import {ActionStatus, ActionToasts, ActionsView, ApplyDialog, useGoogleAdsActions} from './GoogleAdsActions.jsx';

const VIEWS = [['overview', 'Resumo e ações'], ['actions', 'Ações'], ['search_terms', 'Termos de pesquisa'], ['keywords', 'Palavras-chave'], ['negatives', 'Palavras negativas'], ['campaigns', 'Campanhas'], ['details', 'Grupos, páginas e dispositivos']];
const SEVERITY = {high: ['Alta', 'error'], medium: ['Média', 'warning'], low: ['Baixa', 'low']};
const TERM_ACTION = {negate: ['Negativar', 'error'], add_keyword: ['Virar palavra-chave', 'success'], review: ['Revisar', 'warning'], covered: ['Já negativado', 'gray'], excluded: ['Excluído no Google Ads', 'gray'], added: ['Já é palavra-chave', 'gray'], keep: ['Manter', 'gray']};
const MATCH = {EXACT: 'Exata', PHRASE: 'Frase', BROAD: 'Ampla'};
const LEVEL = {campaign: 'Campanha', ad_group: 'Grupo de anúncios', shared_list: 'Lista compartilhada'};
const BIDDING = {MAXIMIZE_CONVERSIONS: 'Maximizar conversões', MAXIMIZE_CONVERSION_VALUE: 'Maximizar valor', TARGET_CPA: 'CPA desejado', TARGET_ROAS: 'ROAS desejado', MANUAL_CPC: 'CPC manual', TARGET_SPEND: 'Maximizar cliques', TARGET_IMPRESSION_SHARE: 'Parcela de impressões'};
const STATUS = {ENABLED: ['Ativa', 'success'], PAUSED: ['Pausada', 'gray'], REMOVED: ['Removida', 'error']};
const DATASET = {campaign_metrics: 'campanhas', campaign_settings: 'configurações', ad_group_metrics: 'grupos', device_metrics: 'dispositivos', landing_page_metrics: 'páginas de destino', keyword_metrics: 'palavras-chave', search_term_metrics: 'termos de pesquisa', negative_keywords: 'negativas'};
const badge = ([label, tone]) => <span className={`rs-badge is-${tone}`}>{label}</span>;
const COMPARE = {previous: 'vs período anterior', year: 'vs mesmo período do ano anterior'};
const change = (now, before) => before ? (Number(now || 0) - Number(before)) * 100 / Number(before) : null;
const LIVE = ['approved', 'sent', 'applied'];
// A recommendation is settled once its change is waiting, being applied or applied; anything else can be approved again.
const liveAction = (actions, item) => actions.byRecommendation.get(item.id) || item.queued || null;
const proposalOf = item => ({...item.proposal, recommendation_id: item.id});

/** CSV that Google Ads Editor imports directly (Conta → Importar → Colar/arquivo). */
function editorCsv(rows, kind, match) {
  const quote = value => `"${String(value ?? '').replaceAll('"', '""')}"`;
  const type = kind === 'negate' ? `Campaign Negative ${match === 'PHRASE' ? 'Phrase' : 'Exact'}` : 'Exact';
  const lines = [['Campaign', 'Ad Group', 'Keyword', 'Criterion Type'].map(quote).join(',')];
  rows.forEach(row => lines.push([row.campaign_name, kind === 'negate' ? '' : row.ad_group_name, row.search_term, type].map(quote).join(',')));
  return `﻿${lines.join('\r\n')}`;
}
function download(text, name) {
  const url = URL.createObjectURL(new Blob([text], {type: 'text/csv;charset=utf-8'}));
  const link = Object.assign(document.createElement('a'), {href: url, download: name});
  document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
}

/** Health of each Google Ads account: last run, and datasets that came back incomplete. */
function AccountHealth({accounts}) {
  if (!accounts.length) return null;
  return <ul className="ga-health">{accounts.map(account => {
    const age = account.last_run_at ? (Date.now() - Date.parse(account.last_run_at)) / 36e5 : null;
    const tone = age == null ? 'warning' : age > 48 ? 'error' : 'success';
    const problems = (account.datasets || []).filter(item => ['truncated', 'error', 'skipped'].includes(item.status));
    return <li key={account.id}>
      <span className={`rs-dot is-${tone}`} aria-hidden="true"/>
      <span><strong>{account.name}</strong><small>{account.external_id} · {account.last_run_at ? `última coleta ${friendlyAgo(account.last_run_at)}` : 'nenhuma coleta recebida'}{account.timed_out ? ' · terminou por tempo' : ''}</small></span>
      {problems.length > 0 && <span className="ga-health__issues">{problems.map(item => <span key={item.name} className="rs-badge is-warning">{DATASET[item.name] || item.name}: {item.status === 'truncated' ? 'truncado' : item.status === 'skipped' ? 'não rodou' : 'erro'}</span>)}</span>}
    </li>;
  })}</ul>;
}

/** The change a recommendation proposes: approve it, or follow the one already approved. */
function Proposal({item, actions, onApply}) {
  if (!item.proposal) return null;
  const action = liveAction(actions, item);
  return <div className="gaa-proposal">
    <span className="gaa-proposal__label"><Zap size={14} aria-hidden="true"/>{item.proposal.label}</span>
    {action ? <ActionStatus action={action} actions={actions} onRetry={() => onApply([proposalOf(item)])}/>
      : actions.canEdit && <ReportsActionButton color="secondary" size="sm" onClick={() => onApply([proposalOf(item)])}>Aplicar no Google Ads</ReportsActionButton>}
  </div>;
}

function Recommendations({items, money, onOpen, rules, actions, onApply}) {
  const [showRules, setShowRules] = useState(false);
  if (!items.length) return <EmptyState title="Nenhuma ação pendente" description="As regras não encontraram desperdício, conflito ou oportunidade com os dados deste período."/>;
  return <>
    <ol className="ga-actions">{items.map((item, index) => <li key={item.id}>
      <span className="ga-actions__order">{index + 1}</span>
      <div className="ga-actions__body">
        <div className="ga-actions__head">{badge(SEVERITY[item.severity])}<strong>{item.title}</strong>
          <span className="ga-actions__object">{item.object.label}{item.object.campaign ? ` · ${item.object.campaign}` : ''}{item.object.ad_group ? ` › ${item.object.ad_group}` : ''}</span></div>
        <p>{item.summary} <b>{item.action}</b></p>
        <Proposal item={item} actions={actions} onApply={onApply}/>
      </div>
      <div className="ga-actions__impact">
        {item.impact.kind === 'cost' && item.impact.value > 0 && <><strong>{money(item.impact.value)}</strong><small>em jogo</small></>}
        {item.impact.kind === 'conversions' && <><strong>{number(item.impact.value)}</strong><small>conversões</small></>}
        {item.link && item.link.tab !== 'overview' && <ReportsActionButton color="link-color" size="sm" className="rs-link-button" onClick={() => onOpen(item.link)}>Abrir<ArrowRight size={14} aria-hidden="true"/></ReportsActionButton>}
      </div>
    </li>)}</ol>
    <ReportsActionButton color="link-color" size="sm" className="rs-link-button ga-rules-toggle" aria-expanded={showRules} onClick={() => setShowRules(value => !value)}>{showRules ? 'Ocultar critérios' : 'Como decidimos'}</ReportsActionButton>
    {showRules && <dl className="ga-rules">{rules.map(rule => <div key={rule.rule}><dt>{badge(SEVERITY[rule.severity])} {rule.title}</dt><dd>{rule.when}</dd></div>)}</dl>}
  </>;
}

function Overview({body, money, onOpen, onEditGoal, actions, onApply}) {
  const pending = body.recommendations.filter(item => item.proposal && !LIVE.includes(liveAction(actions, item)?.status));
  const {totals, previous} = body;
  const label = COMPARE[body.compare?.mode] || COMPARE.previous;
  // Each day is compared with the day at the same distance from the start of the comparison window.
  const offset = Math.round((Date.parse(body.period.start) - Date.parse(body.compare.start)) / 864e5);
  const shift = day => new Date(Date.parse(`${toIsoDay(day)}T12:00:00Z`) - offset * 864e5).toISOString().slice(0, 10);
  const before = new Map((body.previous_daily || []).map(item => [toIsoDay(item.date), item]));
  const series = key => [{name: formatRange(body.period.start, body.period.end), data: body.daily.map(item => Number(item[key] || 0))},
    {name: formatRange(body.compare.start, body.compare.end), data: body.daily.map(item => Number(before.get(shift(item.date))?.[key] || 0))}];
  return <div className="rs-stack">
    <MetricGroup label="Resumo do Google Ads" changeLabel={label} items={[
      {label: 'Investimento', value: money(totals.cost), change: change(totals.cost, previous.cost)},
      {label: 'Conversões', value: number(totals.conversions), change: change(totals.conversions, previous.conversions)},
      {label: 'Custo por conversão', value: totals.cpa != null ? money(totals.cpa) : '—', change: change(totals.cpa, previous.cpa), inverse: true},
      {label: 'Valor das conversões', value: totals.conversion_value ? money(totals.conversion_value) : '—', detail: totals.roas ? `ROAS ${totals.roas.toLocaleString('pt-BR')}` : 'Sem valor informado'},
      {label: 'Cliques', value: number(totals.clicks), detail: `CTR ${totals.ctr != null ? `${totals.ctr.toLocaleString('pt-BR')}%` : '—'} · CPC ${totals.cpc != null ? money(totals.cpc) : '—'}`},
    ]}/>
    <Section title="Próximos passos" description="Em ordem de execução: o que trava a conta primeiro, depois metas e o maior impacto em reais. As que têm mudança pronta podem ser aplicadas direto no Google Ads."
      action={actions.canEdit && pending.length > 1 && <ReportsActionButton color="primary" size="sm" onClick={() => onApply(pending.map(proposalOf))}><Zap size={16} aria-hidden="true"/>Aplicar {pending.length} mudanças</ReportsActionButton>}>
      <Recommendations items={body.recommendations} money={money} onOpen={onOpen} rules={body.rules} actions={actions} onApply={onApply}/>
    </Section>
    {body.goals_ready && <GoalsSection campaigns={body.campaigns} money={money} onEdit={onEditGoal}/>}
    <div className="rs-grid rs-grid--2">
      <Section title="Investimento por dia" description={`Período atual ${label.replace('vs ', 'e ')}`}>
        <Chart type="area" height={220} labels={body.daily.map(item => dayLabel(item.date))} series={series('cost')}/>
      </Section>
      <Section title="Conversões por dia" description="Conversões informadas pelo Google Ads">
        <Chart type="area" height={220} labels={body.daily.map(item => dayLabel(item.date))} series={series('conversions')}/>
      </Section>
    </div>
    <Section title="Saúde da coleta" description="Cada execução diária relê os últimos 14 dias e busca mais 45 dias do passado, até 13 meses de histórico">
      <AccountHealth accounts={body.accounts}/>
    </Section>
  </div>;
}

const delta = (now, before, inverse = false) => {
  const value = change(now, before);
  if (value == null || !Number.isFinite(value)) return null;
  const good = (value >= 0) !== inverse;
  return <small className={`rs-cell-sub ${good ? 'ga-up' : 'ga-down'}`}>{value >= 0 ? '+' : ''}{value.toLocaleString('pt-BR', {maximumFractionDigits: 0})}%</small>;
};

function Campaigns({body, money, onEditGoal}) {
  return <Section title="Campanhas" description={`Configuração do Google Ads, meta da equipe e resultado do período (variação ${COMPARE[body.compare?.mode] || COMPARE.previous})`}>
    <DataTable label="Campanhas" rows={body.campaigns} rowKey={row => `${row.account_id}:${row.campaign_external_id}`} initialSort={{key: 'cost', dir: 'desc'}} columns={[
      {key: 'campaign_name', label: 'Campanha', render: row => <span className="ga-camp"><strong>{row.campaign_name}</strong><small className="rs-cell-sub">{row.status && row.status !== 'ENABLED' ? `${(STATUS[row.status] || [row.status])[0]} · ` : ''}{BIDDING[row.bidding_strategy_type] || row.bidding_strategy_type || '—'}</small></span>},
      {key: 'budget', label: 'Orçamento/dia', numeric: true, render: row => row.budget != null ? <>{money(row.budget)}<small className={`rs-cell-sub${row.budget_usage >= 95 ? ' ga-strong' : ''}`}>{row.budget_usage != null ? `uso ${row.budget_usage.toLocaleString('pt-BR')}%` : ''}{row.budget_shared ? ' · compartilhado' : ''}</small></> : '—'},
      {key: 'pacing', label: 'Ritmo do mês', sortable: false, render: row => <PacingBar campaign={row} money={money}/>},
      {key: 'cost', label: 'Investimento', numeric: true, render: row => <>{money(row.cost)}{delta(row.cost, row.previous?.cost)}</>},
      {key: 'conversions', label: 'Conversões', numeric: true, render: row => <>{number(row.conversions)}{delta(row.conversions, row.previous?.conversions)}</>},
      {key: 'cpa', label: 'CPA', numeric: true, sort: row => row.cpa ?? Infinity, render: row => <>{row.cpa != null ? money(row.cpa) : '—'}{row.goal?.target_cpa != null ? <small className="rs-cell-sub">meta {money(row.goal.target_cpa)}</small> : delta(row.cpa, row.previous?.cpa, true)}</>},
      {key: 'roas', label: 'ROAS', numeric: true, sort: row => row.roas || 0, render: row => row.roas != null ? row.roas.toLocaleString('pt-BR') : '—'},
      {key: 'goal', label: 'Meta', sortable: false, render: row => row.campaign_id && body.goals_ready ? <ReportsActionButton color="link-color" size="sm" className="rs-link-button" onClick={() => onEditGoal(row)}>{row.goal ? (OBJECTIVES.find(([key]) => key === (row.goal.objective || ''))?.[1] || 'Editar') : 'Definir'}</ReportsActionButton> : '—'},
    ]}/>
  </Section>;
}

function SearchTerms({period, initialFilter, actions, onApply}) {
  const [state, retry] = useApi(apiUrl('/google-ads/search-terms', {start_date: period.start, end_date: period.end}));
  const [filter, setFilter] = useState(initialFilter || 'negate');
  const [match, setMatch] = useState('EXACT');
  const [selected, setSelected] = useState(() => new Set());
  const terms = state.body?.terms || [];
  const counts = useMemo(() => terms.reduce((acc, row) => ({...acc, [row.action]: (acc[row.action] || 0) + 1}), {}), [terms]);
  const visible = filter === 'all' ? terms : terms.filter(row => row.action === filter);
  const money = value => currency(value, state.body?.currency);
  const keyOf = row => `${row.account_id}:${row.ad_group_external_id}:${row.term_hash}`;
  const chosen = visible.filter(row => selected.has(keyOf(row)));
  const exportRows = chosen.length ? chosen : visible;
  const exportable = filter === 'negate' || filter === 'add_keyword';
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <LoadingState rows={8}/>;
  if (!terms.length) return <EmptyState title="Sem termos de pesquisa no período" description="Os termos chegam pelo script do Google Ads. Confira a coleta no Resumo."/>;
  const toggle = row => setSelected(current => {const next = new Set(current); next.has(keyOf(row)) ? next.delete(keyOf(row)) : next.add(keyOf(row)); return next;});
  const waste = visible.filter(row => row.action === 'negate').reduce((sum, row) => sum + Number(row.cost || 0), 0);
  // Same ids as the recommendations, so a term approved here also shows as approved in Resumo e ações.
  const recommendationId = row => `${row.action === 'add_keyword' ? 'add_keyword' : 'negative_candidate'}:${row.account_id}:${row.ad_group_external_id}:${row.term_hash}`;
  const applicable = exportRows.filter(row => ['negate', 'add_keyword'].includes(row.action) && !LIVE.includes(actions.byRecommendation.get(recommendationId(row))?.status));
  const proposals = () => applicable.map(row => row.action === 'negate'
    ? {op: 'negative.add', account_id: row.account_id, target: {level: 'campaign', campaign_id: row.campaign_external_id},
      params: {text: row.search_term, match_type: match}, label: `Negativar ${match === 'EXACT' ? `[${row.search_term}]` : `"${row.search_term}"`} em “${row.campaign_name}”`,
      recommendation_id: recommendationId(row)}
    : {op: 'keyword.add', account_id: row.account_id, target: {ad_group_id: row.ad_group_external_id, campaign_id: row.campaign_external_id},
      params: {text: row.search_term, match_type: 'EXACT'}, label: `Adicionar [${row.search_term}] em “${row.ad_group_name}”`, recommendation_id: recommendationId(row)});
  return <Section title="Termos de pesquisa" description={`${terms.length} termos com mais investimento no período${terms.length >= state.body.limit ? ` (os ${state.body.limit} primeiros)` : ''}${state.body.negatives_known ? '' : ' · negativas ainda não lidas: termos sem conversão ficam em Revisar'}`}
    action={exportable && <div className="rs-actions">
      {filter === 'negate' && <ReportsNativeSelect aria-label="Correspondência da negativa" value={match} onChange={event => setMatch(event.target.value)}><option value="EXACT">Negativa exata</option><option value="PHRASE">Negativa de frase</option></ReportsNativeSelect>}
      <ReportsActionButton color="secondary" size="sm" onClick={() => navigator.clipboard?.writeText(exportRows.map(row => filter === 'negate' && match === 'EXACT' ? `[${row.search_term}]` : filter === 'negate' ? `"${row.search_term}"` : `[${row.search_term}]`).join('\n'))}><Copy01 size={16} aria-hidden="true"/>Copiar</ReportsActionButton>
      <ReportsActionButton color="secondary" size="sm" onClick={() => download(editorCsv(exportRows, filter, match), `google-ads-${filter === 'negate' ? 'negativas' : 'palavras-chave'}-${period.end}.csv`)}><Download01 size={16} aria-hidden="true"/>Exportar para o Editor ({exportRows.length})</ReportsActionButton>
      {actions.canEdit && <ReportsActionButton color="primary" size="sm" isDisabled={!applicable.length} onClick={() => onApply(proposals())}><Zap size={16} aria-hidden="true"/>{filter === 'negate' ? 'Negativar' : 'Adicionar'} no Google Ads ({applicable.length})</ReportsActionButton>}
    </div>}>
    <div className="rs-segmented ga-filter" role="group" aria-label="Ação">
      {[['negate', 'Negativar'], ['add_keyword', 'Virar palavra-chave'], ['review', 'Revisar'], ['covered', 'Já negativados'], ['all', 'Todos']].filter(([key]) => key === 'all' || counts[key] || key === filter).map(([key, label]) =>
        <button type="button" key={key} aria-pressed={filter === key} onClick={() => {setFilter(key); setSelected(new Set());}}>{label} · {key === 'all' ? terms.length : counts[key] || 0}</button>)}
    </div>
    {filter === 'negate' && waste > 0 && <p className="ga-note">{money(waste)} gastos nestes termos sem nenhuma conversão. Selecione as linhas e negative direto no Google Ads (próxima execução do script de Ações) ou exporte para o Editor.</p>}
    <DataTable label="Termos de pesquisa" rows={visible} rowKey={keyOf} initialSort={{key: 'cost', dir: 'desc'}} empty={<p className="rs-muted">Nenhum termo nesta ação.</p>} columns={[
      ...(exportable ? [{key: 'pick', label: '', sortable: false, render: row => <input type="checkbox" aria-label={`Selecionar ${row.search_term}`} checked={selected.has(keyOf(row))} onChange={() => toggle(row)}/>}] : []),
      {key: 'action', label: 'Ação', sortable: false, render: row => {
        const applied = actions.byRecommendation.get(recommendationId(row));
        return applied ? <ActionStatus action={applied} actions={actions}/> : badge(TERM_ACTION[row.action] || [row.action, 'gray']);
      }},
      {key: 'search_term', label: 'Termo pesquisado', render: row => <><strong>{row.search_term}</strong><small className="rs-cell-sub">{row.campaign_name} › {row.ad_group_name}</small></>},
      {key: 'clicks', label: 'Cliques', numeric: true, render: row => number(row.clicks)},
      {key: 'cost', label: 'Custo', numeric: true, render: row => money(row.cost)},
      {key: 'conversions', label: 'Conversões', numeric: true, render: row => number(row.conversions)},
      {key: 'cpa', label: 'CPA', numeric: true, sort: row => row.cpa ?? Infinity, render: row => row.cpa != null ? money(row.cpa) : '—'},
      {key: 'ctr', label: 'CTR', numeric: true, sort: row => row.ctr || 0, render: row => row.ctr != null ? `${row.ctr.toLocaleString('pt-BR')}%` : '—'},
    ]}/>
  </Section>;
}

function Keywords({period}) {
  const [state, retry] = useApi(apiUrl('/google-ads/keywords', {start_date: period.start, end_date: period.end}));
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <LoadingState rows={8}/>;
  const money = value => currency(value, state.body.currency);
  return <Section title="Palavras-chave" description="Índice de Qualidade do último envio e resultado do período">
    <DataTable label="Palavras-chave" rows={state.body.keywords} rowKey={row => `${row.account_id}:${row.ad_group_external_id}:${row.criterion_external_id}`} initialSort={{key: 'cost', dir: 'desc'}}
      empty={<EmptyState title="Sem palavras-chave no período" description="Campanhas de Performance Max e Display não têm palavras-chave."/>} columns={[
        {key: 'keyword_text', label: 'Palavra-chave', render: row => <><strong>{row.match_type === 'EXACT' ? `[${row.keyword_text}]` : row.match_type === 'PHRASE' ? `"${row.keyword_text}"` : row.keyword_text}</strong><small className="rs-cell-sub">{MATCH[row.match_type]} · {row.campaign_name} › {row.ad_group_name}</small></>},
        {key: 'quality_score', label: 'Índice de Qualidade', numeric: true, sort: row => row.quality_score || 0, render: row => row.quality_score ? <span className={`rs-badge is-${row.quality_score <= 4 ? 'error' : row.quality_score <= 6 ? 'warning' : 'success'}`}>{row.quality_score}/10</span> : '—'},
        {key: 'clicks', label: 'Cliques', numeric: true, render: row => number(row.clicks)},
        {key: 'cost', label: 'Custo', numeric: true, render: row => money(row.cost)},
        {key: 'conversions', label: 'Conversões', numeric: true, render: row => Number(row.conversions) === 0 && row.clicks >= 30 ? <span className="ga-strong">0</span> : number(row.conversions)},
        {key: 'cpa', label: 'CPA', numeric: true, sort: row => row.cpa ?? Infinity, render: row => row.cpa != null ? money(row.cpa) : '—'},
        {key: 'ctr', label: 'CTR', numeric: true, sort: row => row.ctr || 0, render: row => row.ctr != null ? `${row.ctr.toLocaleString('pt-BR')}%` : '—'},
        {key: 'cpc', label: 'CPC', numeric: true, sort: row => row.cpc || 0, render: row => row.cpc != null ? money(row.cpc) : '—'},
      ]}/>
  </Section>;
}

function Negatives({period}) {
  const [state, retry] = useApi(apiUrl('/google-ads/negatives', {start_date: period.start, end_date: period.end}));
  const [scope, setScope] = useState('active');
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <LoadingState rows={8}/>;
  const rows = state.body.negatives;
  const active = rows.filter(row => !row.removed_at);
  const removed = rows.filter(row => row.removed_at);
  const byLevel = level => active.filter(row => row.level === level).length;
  const visible = scope === 'active' ? active : scope === 'conflicts' ? active.filter(row => row.blocks_keyword) : removed;
  return <div className="rs-stack">
    <MetricGroup label="Palavras negativas" items={[
      {label: 'Negativas ativas', value: number(active.length)},
      {label: 'Em listas compartilhadas', value: number(byLevel('shared_list')), detail: (count => `${count} ${count === 1 ? 'lista' : 'listas'}`)(new Set(active.filter(row => row.shared_set_name).map(row => row.shared_set_name)).size)},
      {label: 'Em campanhas e grupos', value: number(byLevel('campaign') + byLevel('ad_group'))},
      {label: 'Bloqueando palavra-chave', value: number(state.body.conflicts.length), detail: state.body.conflicts.length ? 'Revise primeiro' : 'Nenhum conflito'},
    ]}/>
    <Section title="Negativas" description={`Inventário do último envio completo · removidas nos últimos ${state.body.removed_days} dias ficam registradas`}
      action={<div className="rs-segmented" role="group" aria-label="Situação">
        {[['active', `Ativas · ${active.length}`], ['conflicts', `Conflitos · ${state.body.conflicts.length}`], ['removed', `Removidas · ${removed.length}`]].map(([key, label]) => <button type="button" key={key} aria-pressed={scope === key} onClick={() => setScope(key)}>{label}</button>)}
      </div>}>
      {scope === 'conflicts' && state.body.conflicts.length > 0 && <ul className="ga-conflicts">{state.body.conflicts.map((item, index) => <li key={index}><strong>{item.keyword}</strong> <span>{item.campaign_name} › {item.ad_group_name}</span></li>)}</ul>}
      <DataTable label="Negativas" rows={visible} rowKey={row => row.id} empty={<p className="rs-muted">{scope === 'active' ? 'Nenhuma negativa ativa recebida. Elas chegam no fim de cada execução completa do script.' : 'Nada aqui.'}</p>} columns={[
        {key: 'keyword_text', label: 'Negativa', render: row => <><strong>{row.match_type === 'EXACT' ? `[${row.keyword_text}]` : row.match_type === 'PHRASE' ? `"${row.keyword_text}"` : row.keyword_text}</strong>{row.blocks_keyword && <small className="rs-cell-sub ga-strong">bloqueia palavra-chave ativa</small>}</>},
        {key: 'match_type', label: 'Correspondência', render: row => MATCH[row.match_type] || row.match_type},
        {key: 'level', label: 'Nível', render: row => LEVEL[row.level] || row.level},
        {key: 'where', label: 'Onde', sort: row => row.shared_set_name || row.campaign_name || '', render: row => row.level === 'shared_list' ? <>{row.shared_set_name}<small className="rs-cell-sub">{(row.attached_campaign_ids || []).length} campanhas</small></> : <>{row.campaign_name}{row.ad_group_name && <small className="rs-cell-sub">{row.ad_group_name}</small>}</>},
        {key: 'last_seen_at', label: scope === 'removed' ? 'Removida' : 'Visto', render: row => friendlyAgo(row.removed_at || row.last_seen_at)},
      ]}/>
    </Section>
  </div>;
}

/** "O Google Ads está bem aproveitado?" — the engine v2 data as an optimized Google Ads report. */
export function GoogleAds({data}) {
  const {period} = useReportsContext();
  const initial = new URLSearchParams(location.search);
  const [view, setView] = useState(VIEWS.some(([key]) => key === initial.get('view')) ? initial.get('view') : 'overview');
  const [termFilter, setTermFilter] = useState(initial.get('filter') || '');
  const [compare, setCompare] = useState(initial.get('compare') === 'year' ? 'year' : 'previous');
  const [editing, setEditing] = useState(null);
  const [applying, setApplying] = useState(null);
  const actions = useGoogleAdsActions(data);
  const [state, retry] = useApi(apiUrl('/google-ads/summary', {start_date: period.start, end_date: period.end, compare}));
  const changeCompare = value => {
    setCompare(value);
    const url = new URL(location.href); value === 'previous' ? url.searchParams.delete('compare') : url.searchParams.set('compare', value);
    history.replaceState(history.state, '', url);
  };
  const go = (next, filter = '') => {
    setView(next); setTermFilter(filter);
    const url = new URL(location.href); url.searchParams.set('view', next); filter ? url.searchParams.set('filter', filter) : url.searchParams.delete('filter');
    history.replaceState(history.state, '', url);
  };
  const body = state.body;
  const money = value => currency(value, body?.currency);
  const hasAccount = data.accounts.some(item => item.platform === 'google_ads');
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !body) return <div className="rs-stack"><LoadingState rows={2}/><LoadingState rows={6}/></div>;
  if (!body.ready || (!body.accounts.length && !hasAccount)) return <EmptyState title="Google Ads ainda não conectado"
    description="Gere o script do Google Ads em Mídia → Dados e programe-o para rodar todos os dias. Esta área mostra termos, negativas, palavras-chave e as ações recomendadas."
    action={<ReportsActionButton color="primary" size="sm" href={reportUrl('media/data')}>Conectar Google Ads</ReportsActionButton>}/>;
  const counts = {search_terms: body.counts?.negate || 0, overview: body.recommendations.filter(item => item.severity !== 'low').length, actions: actions.waiting};
  return <div className="rs-stack">
    <div className="ga-bar">
      <nav className="ga-views" aria-label="Google Ads">{VIEWS.map(([key, label]) => <button type="button" key={key} aria-current={view === key ? 'page' : undefined} onClick={() => go(key)}>{label}{counts[key] ? <span>{counts[key]}</span> : null}</button>)}</nav>
      {['overview', 'campaigns'].includes(view) && <label className="ga-compare"><span>Comparar com</span><ReportsNativeSelect value={compare} onChange={event => changeCompare(event.target.value)}>
        <option value="previous">Período anterior</option><option value="year">Mesmo período do ano anterior</option></ReportsNativeSelect></label>}
    </div>
    {view === 'overview' && <Overview body={body} money={money} onOpen={link => go(link.tab, link.filter || '')} onEditGoal={setEditing} actions={actions} onApply={setApplying}/>}
    {view === 'actions' && <ActionsView actions={actions}/>}
    {view === 'search_terms' && <SearchTerms key={termFilter} period={period} initialFilter={termFilter} actions={actions} onApply={setApplying}/>}
    {view === 'keywords' && <Keywords period={period}/>}
    {view === 'negatives' && <Negatives period={period}/>}
    {view === 'campaigns' && <Campaigns body={body} money={money} onEditGoal={setEditing}/>}
    {editing && <GoalDrawer key={editing.campaign_external_id} campaign={editing} data={data} money={money} onClose={() => setEditing(null)} onSaved={() => {setEditing(null); retry();}}/>}
    {view === 'details' && <MediaPerformance views={['ad_groups', 'landing_pages', 'devices']} hideSettings/>}
    {applying && <ApplyDialog items={applying} actions={actions} onClose={() => setApplying(null)}/>}
    <ActionToasts actions={actions}/>
  </div>;
}
