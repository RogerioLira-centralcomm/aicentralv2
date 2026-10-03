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
// The header's source/campaign choice travels with every Google Ads request.
const narrow = scope => ({scope_account: scope.account, scope_campaign: scope.campaign});
const ACTION_ORDER = ['negate', 'add_keyword', 'review', 'covered', 'excluded', 'added', 'keep'];
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

const SHOWN = 6;

/** One recommendation as a card: what is wrong, what to do, and the change ready to apply. Impact in money only. */
function ActionCard({item, money, onOpen, actions, onApply}) {
  const [label, tone] = SEVERITY[item.severity];
  const open = item.link && item.link.tab !== 'overview' ? item.link : null;
  return <article className={`ga-card is-${tone}`}>
    <header className="ga-card__head">{badge([label, tone])}
      {item.impact.kind === 'cost' && item.impact.value > 0 && <span className="ga-card__impact">{money(item.impact.value)} em jogo</span>}</header>
    <h3>{item.title}</h3>
    <p className="ga-card__object">{item.object.label}{item.object.campaign ? ` · ${item.object.campaign}` : ''}{item.object.ad_group ? ` › ${item.object.ad_group}` : ''}</p>
    <p>{item.summary} <b>{item.action}</b></p>
    <footer className="ga-card__foot">
      <Proposal item={item} actions={actions} onApply={onApply}/>
      {open && <ReportsActionButton color="link-color" size="sm" className="rs-link-button" onClick={() => onOpen(open)}>Abrir<ArrowRight size={14} aria-hidden="true"/></ReportsActionButton>}
    </footer>
  </article>;
}

function ActionCenter({items, money, onOpen, rules, actions, onApply, onSeeAll}) {
  const [showRules, setShowRules] = useState(false);
  const [all, setAll] = useState(false);
  const pending = items.filter(item => item.proposal && !LIVE.includes(liveAction(actions, item)?.status));
  const count = severity => items.filter(item => item.severity === severity).length;
  const waiting = actions.waiting;
  const visible = all ? items : items.slice(0, SHOWN);
  return <Section title="Central de ações" description="O que travar ou desperdiçar verba vem primeiro, depois metas e oportunidades. As que têm mudança pronta podem ser aplicadas direto no Google Ads."
    action={<div className="rs-actions">
      {waiting > 0 && <ReportsActionButton color="secondary" size="sm" onClick={onSeeAll}>Fila de ações · {waiting}</ReportsActionButton>}
      {actions.canEdit && pending.length > 1 && <ReportsActionButton color="primary" size="sm" onClick={() => onApply(pending.map(proposalOf))} iconLeading={Zap}>Aplicar {pending.length} mudanças</ReportsActionButton>}
    </div>}>
    {!items.length ? <EmptyState title="Nenhuma ação pendente" description="As regras não encontraram desperdício, conflito ou oportunidade com os dados deste período."/> : <>
      <ul className="ga-center__summary" aria-label="Resumo por prioridade">
        {['high', 'medium', 'low'].map(severity => <li key={severity} className={`is-${SEVERITY[severity][1]}`}><strong>{count(severity)}</strong><span>prioridade {SEVERITY[severity][0].toLowerCase()}</span></li>)}
        <li><strong>{pending.length}</strong><span>com mudança pronta</span></li>
      </ul>
      <div className="ga-cards">{visible.map(item => <ActionCard key={item.id} item={item} money={money} onOpen={onOpen} actions={actions} onApply={onApply}/>)}</div>
      <div className="ga-center__more">
        {items.length > SHOWN && <ReportsActionButton color="link-color" size="sm" className="rs-link-button" aria-expanded={all} onClick={() => setAll(value => !value)}>{all ? 'Mostrar menos' : `Ver as ${items.length - SHOWN} restantes`}</ReportsActionButton>}
        <ReportsActionButton color="link-color" size="sm" className="rs-link-button" aria-expanded={showRules} onClick={() => setShowRules(value => !value)}>{showRules ? 'Ocultar critérios' : 'Como decidimos'}</ReportsActionButton>
      </div>
      {showRules && <dl className="ga-rules">{rules.map(rule => <div key={rule.rule}><dt>{badge(SEVERITY[rule.severity])} {rule.title}</dt><dd>{rule.when}</dd></div>)}</dl>}
    </>}
  </Section>;
}

/** Period comparison lives next to the numbers it changes, not in the tab bar. */
function CompareSelect({value, onChange}) {
  return <label className="ga-compare"><span>Comparar com</span><ReportsNativeSelect value={value} onChange={event => onChange(event.target.value)}>
    <option value="previous">Período anterior</option><option value="year">Mesmo período do ano anterior</option></ReportsNativeSelect></label>;
}

function Overview({body, money, onOpen, onEditGoal, actions, onApply, compare, onCompare}) {
  const {totals, previous} = body;
  const label = COMPARE[body.compare?.mode] || COMPARE.previous;
  // Each day is compared with the day at the same distance from the start of the comparison window.
  const offset = Math.round((Date.parse(body.period.start) - Date.parse(body.compare.start)) / 864e5);
  const shift = day => new Date(Date.parse(`${toIsoDay(day)}T12:00:00Z`) - offset * 864e5).toISOString().slice(0, 10);
  const before = new Map((body.previous_daily || []).map(item => [toIsoDay(item.date), item]));
  const series = key => [{name: formatRange(body.period.start, body.period.end), data: body.daily.map(item => Number(item[key] || 0))},
    {name: formatRange(body.compare.start, body.compare.end), data: body.daily.map(item => Number(before.get(shift(item.date))?.[key] || 0))}];
  return <div className="rs-stack">
    <div className="ga-head"><h2>Resumo do período</h2><CompareSelect value={compare} onChange={onCompare}/></div>
    <MetricGroup label="Resumo do Google Ads" changeLabel={label} items={[
      {label: 'Investimento', value: money(totals.cost), change: change(totals.cost, previous.cost)},
      {label: 'Conversões', value: number(totals.conversions), change: change(totals.conversions, previous.conversions)},
      {label: 'Custo por conversão', value: totals.cpa != null ? money(totals.cpa) : '—', change: change(totals.cpa, previous.cpa), inverse: true},
      {label: 'Valor das conversões', value: totals.conversion_value ? money(totals.conversion_value) : '—', detail: totals.roas ? `ROAS ${totals.roas.toLocaleString('pt-BR')}` : 'Sem valor informado'},
      {label: 'Cliques', value: number(totals.clicks), detail: `CTR ${totals.ctr != null ? `${totals.ctr.toLocaleString('pt-BR')}%` : '—'} · CPC ${totals.cpc != null ? money(totals.cpc) : '—'}`},
    ]}/>
    <ActionCenter items={body.recommendations} money={money} onOpen={onOpen} rules={body.rules} actions={actions} onApply={onApply} onSeeAll={() => onOpen({tab: 'actions'})}/>
    {body.goals_ready && <GoalsSection campaigns={body.campaigns} money={money} onEdit={onEditGoal}/>}
    <div className="rs-grid rs-grid--3">
      <Section title="Investimento" description="Gasto diário"><Chart type="area" height={200} labels={body.daily.map(item => dayLabel(item.date))} series={series('cost')}/></Section>
      <Section title="Conversões" description="Informadas pelo Google Ads"><Chart type="area" height={200} labels={body.daily.map(item => dayLabel(item.date))} series={series('conversions')}/></Section>
      <Section title="Impressões" description="Quantas vezes os anúncios apareceram"><Chart type="area" height={200} labels={body.daily.map(item => dayLabel(item.date))} series={series('impressions')}/></Section>
      <Section title="Cliques" description="Cliques nos anúncios"><Chart type="area" height={200} labels={body.daily.map(item => dayLabel(item.date))} series={series('clicks')}/></Section>
      <Section title="CTR" description="Cliques ÷ impressões, em %"><Chart type="area" height={200} labels={body.daily.map(item => dayLabel(item.date))} series={series('ctr')}/></Section>
      <Section title="CPC médio" description="Custo por clique"><Chart type="area" height={200} labels={body.daily.map(item => dayLabel(item.date))} series={series('cpc')}/></Section>
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

function Campaigns({body, money, onEditGoal, compare, onCompare}) {
  return <Section title="Campanhas" action={<CompareSelect value={compare} onChange={onCompare}/>} description={`Configuração do Google Ads, meta da equipe e resultado do período (variação ${COMPARE[body.compare?.mode] || COMPARE.previous})`}>
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
  const {scope: media} = useReportsContext();
  const [state, retry] = useApi(apiUrl('/google-ads/search-terms', {start_date: period.start, end_date: period.end, ...narrow(media)}));
  const [filter, setFilter] = useState(initialFilter || 'all');
  const [match, setMatch] = useState('EXACT');
  const [selected, setSelected] = useState(() => new Set());
  const terms = state.body?.terms || [];
  const counts = useMemo(() => terms.reduce((acc, row) => ({...acc, [row.action]: (acc[row.action] || 0) + 1}), {}), [terms]);
  const visible = filter === 'all' ? terms : terms.filter(row => row.action === filter);
  const money = value => currency(value, state.body?.currency);
  const keyOf = row => `${row.account_id}:${row.ad_group_external_id}:${row.term_hash}`;
  const pickable = row => row.action === 'negate' || row.action === 'add_keyword';
  const chosen = visible.filter(row => selected.has(keyOf(row)));
  // In "Todos" the toolbar follows the selection: negatives unless only keyword candidates are marked.
  const mode = filter === 'negate' || filter === 'add_keyword' ? filter : chosen.length && chosen.every(row => row.action === 'add_keyword') ? 'add_keyword' : 'negate';
  const exportRows = (chosen.length ? chosen : visible).filter(row => row.action === mode);
  const exportable = visible.some(pickable);
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <LoadingState rows={8}/>;
  if (!terms.length) return <EmptyState title="Sem termos de pesquisa no período" description="Os termos chegam pelo script do Google Ads. Confira a coleta no Resumo."/>;
  const toggle = row => setSelected(current => {const next = new Set(current); next.has(keyOf(row)) ? next.delete(keyOf(row)) : next.add(keyOf(row)); return next;});
  const pickableRows = visible.filter(pickable);
  const allPicked = pickableRows.length > 0 && pickableRows.every(row => selected.has(keyOf(row)));
  const toggleAll = () => setSelected(allPicked ? new Set() : new Set(pickableRows.map(keyOf)));
  const waste = visible.filter(row => row.action === 'negate').reduce((sum, row) => sum + Number(row.cost || 0), 0);
  // Same ids as the recommendations, so a term approved here also shows as approved in Resumo e ações.
  const recommendationId = row => `${row.action === 'add_keyword' ? 'add_keyword' : 'negative_candidate'}:${row.account_id}:${row.ad_group_external_id}:${row.term_hash}`;
  const applicable = (chosen.length ? chosen : exportRows).filter(row => pickable(row) && !LIVE.includes(actions.byRecommendation.get(recommendationId(row))?.status));
  const proposals = () => applicable.map(row => row.action === 'negate'
    ? {op: 'negative.add', account_id: row.account_id, target: {level: 'campaign', campaign_id: row.campaign_external_id},
      params: {text: row.search_term, match_type: match}, label: `Negativar ${match === 'EXACT' ? `[${row.search_term}]` : `"${row.search_term}"`} em “${row.campaign_name}”`,
      recommendation_id: recommendationId(row)}
    : {op: 'keyword.add', account_id: row.account_id, target: {ad_group_id: row.ad_group_external_id, campaign_id: row.campaign_external_id},
      params: {text: row.search_term, match_type: 'EXACT'}, label: `Adicionar [${row.search_term}] em “${row.ad_group_name}”`, recommendation_id: recommendationId(row)});
  return <Section title="Termos de pesquisa" description={`${terms.length} termos com mais investimento no período${terms.length >= state.body.limit ? ` (os ${state.body.limit} primeiros)` : ''}${state.body.negatives_known ? '' : ' · negativas ainda não lidas: termos sem conversão ficam em Revisar'}`}
    action={exportable && <div className="rs-actions">
      {mode === 'negate' && <ReportsNativeSelect aria-label="Correspondência da negativa" value={match} onChange={event => setMatch(event.target.value)}><option value="EXACT">Negativa exata</option><option value="PHRASE">Negativa de frase</option></ReportsNativeSelect>}
      <ReportsActionButton color="secondary" size="sm" onClick={() => navigator.clipboard?.writeText(exportRows.map(row => mode === 'negate' && match === 'EXACT' ? `[${row.search_term}]` : mode === 'negate' ? `"${row.search_term}"` : `[${row.search_term}]`).join('\n'))} iconLeading={Copy01}>Copiar</ReportsActionButton>
      <ReportsActionButton color="secondary" size="sm" onClick={() => download(editorCsv(exportRows, mode, match), `google-ads-${mode === 'negate' ? 'negativas' : 'palavras-chave'}-${period.end}.csv`)} iconLeading={Download01}>Exportar para o Editor ({exportRows.length})</ReportsActionButton>
      {actions.canEdit && <ReportsActionButton color="primary" size="sm" isDisabled={!applicable.length} onClick={() => onApply(proposals())} iconLeading={Zap}>{chosen.length && chosen.some(row => row.action === 'negate') && chosen.some(row => row.action === 'add_keyword') ? 'Aplicar' : mode === 'negate' ? 'Negativar' : 'Adicionar'} no Google Ads ({applicable.length})</ReportsActionButton>}
    </div>}>
    <div className="rs-segmented ga-filter" role="group" aria-label="Ação">
      {[['negate', 'Negativar'], ['add_keyword', 'Virar palavra-chave'], ['review', 'Revisar'], ['covered', 'Já negativados'], ['excluded', 'Excluídos'], ['added', 'Já são palavras-chave'], ['keep', 'Manter'], ['all', 'Todos']].map(([key, label]) =>
        <button type="button" key={key} aria-pressed={filter === key} onClick={() => {setFilter(key); setSelected(new Set());}}>{label} · {key === 'all' ? terms.length : counts[key] || 0}</button>)}
    </div>
    {filter === 'negate' && waste > 0 && <p className="ga-note">{money(waste)} gastos nestes termos sem nenhuma conversão. Selecione as linhas e negative direto no Google Ads (próxima execução do script de Ações) ou exporte para o Editor.</p>}
    <DataTable label="Termos de pesquisa" rows={visible} rowKey={keyOf} initialSort={{key: 'action', dir: 'asc'}} empty={<p className="rs-muted">Nenhum termo nesta ação.</p>} columns={[
      ...(exportable ? [{key: 'pick', label: <input type="checkbox" aria-label="Selecionar todos" checked={allPicked} onChange={toggleAll}/>, sortable: false, render: row => pickable(row) ? <input type="checkbox" aria-label={`Selecionar ${row.search_term}`} checked={selected.has(keyOf(row))} onChange={() => toggle(row)}/> : null}] : []),
      // Action first (what to do), then the most expensive term inside each action.
      {key: 'action', label: 'Ação', sort: row => `${ACTION_ORDER.indexOf(row.action) < 0 ? 9 : ACTION_ORDER.indexOf(row.action)}:${String(1e12 - Math.round(Number(row.cost || 0) * 100)).padStart(13, '0')}`, render: row => {
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
  const [state, retry] = useApi(apiUrl('/google-ads/keywords', {start_date: period.start, end_date: period.end, ...narrow(useReportsContext().scope)}));
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

const NEG_GROUP = {remove: ['Pode remover', 'error'], review: ['Revisar', 'warning'], keep: ['Manter', 'success']};
const negativeLabel = row => row.match_type === 'EXACT' ? `[${row.keyword_text}]` : row.match_type === 'PHRASE' ? `"${row.keyword_text}"` : row.keyword_text;
const removalId = row => `negative_remove:${row.account_id}:${row.id}`;
/** What the agent said wins only when it is sure; a doubtful "remove" on a keeper just asks for a look. */
function finalVerdict(row, review, minimum) {
  if (!review || row.verdict === 'remove') return row.verdict;
  if (review.confidence >= minimum) return review.verdict;
  return row.verdict === 'keep' && review.verdict === 'remove' ? 'review' : row.verdict;
}

function Negatives({period, actions, onApply}) {
  const query = {start_date: period.start, end_date: period.end, ...narrow(useReportsContext().scope)};
  const [state, retry] = useApi(apiUrl('/google-ads/negatives', query));
  const [scope, setScope] = useState('');
  const [selected, setSelected] = useState(() => new Set());
  const [reviews, setReviews] = useState(null);
  const [review, setReview] = useState({busy: false, error: ''});
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <LoadingState rows={8}/>;
  const rows = state.body.negatives;
  const minimum = reviews?.minimum ?? 0.7;
  const active = rows.filter(row => !row.removed_at).map(row => ({...row, final: finalVerdict(row, reviews?.items[row.id], minimum)}));
  const removed = rows.filter(row => row.removed_at);
  const count = key => active.filter(row => row.final === key).length;
  const byLevel = level => active.filter(row => row.level === level).length;
  const current = scope || (count('remove') ? 'remove' : 'all');
  const visible = current === 'all' ? active : current === 'removed' ? removed : active.filter(row => row.final === current);
  const canPick = actions.canEdit && current !== 'removed';
  const chosen = visible.filter(row => selected.has(row.id));
  const applicable = chosen.filter(row => !LIVE.includes(actions.byRecommendation.get(removalId(row))?.status));
  const choose = key => {setScope(key); setSelected(new Set());};
  const toggle = row => setSelected(prev => {const next = new Set(prev); next.has(row.id) ? next.delete(row.id) : next.add(row.id); return next;});
  const suggested = visible.filter(row => row.final === 'remove' && !LIVE.includes(actions.byRecommendation.get(removalId(row))?.status));
  const runReview = async () => {
    setReview({busy: true, error: ''});
    try {
      const result = await actions.post(`/google-ads/negatives/review?${new URLSearchParams(query)}`);
      setReviews({items: result.reviews, minimum: result.ai_confidence});
      setReview({busy: false, error: ''});
    } catch (failure) {setReview({busy: false, error: failure.message});}
  };
  const proposals = () => applicable.map(row => ({...row.proposal, recommendation_id: removalId(row)}));
  return <div className="rs-stack">
    <MetricGroup label="Palavras negativas" items={[
      {label: 'Negativas ativas', value: number(active.length), detail: `${number(byLevel('shared_list'))} em listas · ${number(byLevel('campaign') + byLevel('ad_group'))} em campanhas e grupos`},
      {label: 'Pode remover', value: number(count('remove')), detail: count('remove') ? 'Conflitos e duplicadas' : 'Nada a limpar'},
      {label: 'Para revisar', value: number(count('review')), detail: reviews ? 'Com a revisão da IA' : 'Peça a revisão da IA'},
      {label: 'Bloqueando palavra-chave', value: number(state.body.conflicts.length), detail: state.body.conflicts.length ? 'Revise primeiro' : 'Nenhum conflito'},
    ]}/>
    <Section title="Negativas" description={`Score de utilidade de 0 a 100, calculado com palavras-chave, termos de pesquisa e duplicidade · removidas nos últimos ${state.body.removed_days} dias ficam registradas`}
      action={<div className="rs-actions">
        {actions.canEdit && <ReportsActionButton color="secondary" size="sm" isDisabled={review.busy || !active.length} onClick={runReview}>{review.busy ? 'Revisando…' : reviews ? 'Revisar de novo com IA' : 'Revisar com IA'}</ReportsActionButton>}
        {canPick && <ReportsActionButton color="secondary" size="sm" isDisabled={!suggested.length} onClick={() => setSelected(new Set(suggested.map(row => row.id)))}>Selecionar sugeridas ({suggested.length})</ReportsActionButton>}
        {canPick && <ReportsActionButton color="primary" size="sm" isDisabled={!applicable.length} onClick={() => onApply(proposals())} iconLeading={Zap}>Remover no Google Ads ({applicable.length})</ReportsActionButton>}
      </div>}>
      <div className="rs-segmented ga-filter" role="group" aria-label="Grupo">
        {[['remove', `Pode remover · ${count('remove')}`], ['review', `Revisar · ${count('review')}`], ['keep', `Manter · ${count('keep')}`], ['all', `Todas · ${active.length}`], ['removed', `Removidas · ${removed.length}`]].map(([key, label]) =>
          <button type="button" key={key} aria-pressed={current === key} onClick={() => choose(key)}>{label}</button>)}
      </div>
      {review.error && <p className="ga-note" role="alert">{review.error}</p>}
      {reviews && <p className="ga-note">A IA revisou {Object.keys(reviews.items).length} negativas e só muda o grupo quando tem {Math.round(minimum * 100)}% de confiança ou mais. Nada é removido sem a sua aprovação.</p>}
      {current === 'remove' && count('remove') > 0 && <p className="ga-note">Estas negativas não protegem o orçamento: bloqueiam palavra-chave ativa ou já estão cobertas por outra. Selecione e remova pela fila de Ações (aplica na próxima execução do script).</p>}
      <DataTable label="Negativas" rows={visible} rowKey={row => row.id} initialSort={current === 'removed' ? undefined : {key: 'score', dir: 'asc'}}
        empty={<p className="rs-muted">{current === 'removed' ? 'Nada removido no período.' : current === 'all' ? 'Nenhuma negativa ativa recebida. Elas chegam no fim de cada execução completa do script.' : 'Nenhuma negativa neste grupo.'}</p>} columns={[
        ...(canPick ? [{key: 'pick', label: '', sortable: false, render: row => <input type="checkbox" aria-label={`Selecionar ${negativeLabel(row)}`} checked={selected.has(row.id)} onChange={() => toggle(row)}/>}] : []),
        ...(current === 'removed' ? [] : [{key: 'final', label: 'Sugestão', sortable: false, render: row => {
          const applied = actions.byRecommendation.get(removalId(row));
          return applied ? <ActionStatus action={applied} actions={actions}/> : badge(NEG_GROUP[row.final]);
        }}, {key: 'score', label: 'Score', numeric: true, render: row => <span className={`rs-badge is-${row.final === 'remove' ? 'error' : row.final === 'review' ? 'warning' : 'success'}`} title="Quanto vale manter esta negativa: baixo, pode sair; alto, está protegendo o orçamento.">{row.score}</span>}]),
        {key: 'keyword_text', label: 'Negativa', render: row => {
          const ai = reviews?.items[row.id];
          return <><strong>{negativeLabel(row)}</strong>
            {row.blocks_keyword && <small className="rs-cell-sub ga-strong">bloqueia palavra-chave ativa</small>}
            {!row.removed_at && row.reasons?.[0] && <small className="rs-cell-sub">{row.reasons[0]}</small>}
            {ai && <small className="rs-cell-sub">IA · {NEG_GROUP[ai.verdict][0]} ({Math.round(ai.confidence * 100)}%): {ai.reason}</small>}</>;
        }},
        {key: 'match_type', label: 'Correspondência', render: row => MATCH[row.match_type] || row.match_type},
        {key: 'level', label: 'Nível', render: row => LEVEL[row.level] || row.level},
        {key: 'where', label: 'Onde', sort: row => row.shared_set_name || row.campaign_name || '', render: row => row.level === 'shared_list' ? <>{row.shared_set_name}<small className="rs-cell-sub">{(row.attached_campaign_ids || []).length} campanhas</small></> : <>{row.campaign_name}{row.ad_group_name && <small className="rs-cell-sub">{row.ad_group_name}</small>}</>},
        {key: 'last_seen_at', label: current === 'removed' ? 'Removida' : 'Visto', render: row => friendlyAgo(row.removed_at || row.last_seen_at)},
      ]}/>
    </Section>
  </div>;
}

/** "O Google Ads está bem aproveitado?" — the engine v2 data as an optimized Google Ads report. */
export function GoogleAds({data}) {
  const {period, scope} = useReportsContext();
  const initial = new URLSearchParams(location.search);
  const [view, setView] = useState(VIEWS.some(([key]) => key === initial.get('view')) ? initial.get('view') : 'overview');
  const [termFilter, setTermFilter] = useState(initial.get('filter') || '');
  const [compare, setCompare] = useState(initial.get('compare') === 'year' ? 'year' : 'previous');
  const [editing, setEditing] = useState(null);
  const [applying, setApplying] = useState(null);
  const actions = useGoogleAdsActions(data);
  const [state, retry] = useApi(apiUrl('/google-ads/summary', {start_date: period.start, end_date: period.end, compare, ...narrow(scope)}));
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
    action={<ReportsActionButton color="primary" size="sm" href={reportUrl('data-sources/connect')}>Conectar Google Ads</ReportsActionButton>}/>;
  const counts = {search_terms: body.counts?.negate || 0, overview: body.recommendations.filter(item => item.severity !== 'low').length, actions: actions.waiting};
  return <div className="rs-stack">
    <div className="ga-bar">
      <nav className="ga-views" aria-label="Google Ads">{VIEWS.map(([key, label]) => <button type="button" key={key} aria-current={view === key ? 'page' : undefined} onClick={() => go(key)}>{label}{counts[key] ? <span>{counts[key]}</span> : null}</button>)}</nav>
    </div>
    {view === 'overview' && <Overview body={body} money={money} onOpen={link => go(link.tab, link.filter || '')} onEditGoal={setEditing} actions={actions} onApply={setApplying} compare={compare} onCompare={changeCompare}/>}
    {view === 'actions' && <ActionsView actions={actions}/>}
    {view === 'search_terms' && <SearchTerms key={termFilter} period={period} initialFilter={termFilter} actions={actions} onApply={setApplying}/>}
    {view === 'keywords' && <Keywords period={period}/>}
    {view === 'negatives' && <Negatives period={period} actions={actions} onApply={setApplying}/>}
    {view === 'campaigns' && <Campaigns body={body} money={money} onEditGoal={setEditing} compare={compare} onCompare={changeCompare}/>}
    {editing && <GoalDrawer key={editing.campaign_external_id} campaign={editing} data={data} money={money} onClose={() => setEditing(null)} onSaved={() => {setEditing(null); retry();}}/>}
    {view === 'details' && <MediaPerformance views={['ad_groups', 'landing_pages', 'devices']} hideSettings/>}
    {applying && <ApplyDialog items={applying} actions={actions} onClose={() => setApplying(null)}/>}
    <ActionToasts actions={actions}/>
  </div>;
}
