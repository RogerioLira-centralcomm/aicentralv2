import React, {useState} from 'react';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {DataTable, EmptyState, ErrorState, LoadingState, Section} from '../../shell/primitives.jsx';
import {currency, number, percent} from '../shared.jsx';

const VIEWS = [['ad_groups', 'Grupos de anúncios'], ['keywords', 'Palavras-chave'], ['search_terms', 'Termos de pesquisa'], ['landing_pages', 'Páginas de destino'], ['devices', 'Dispositivos']];
const DEVICE = {MOBILE: 'Celular', DESKTOP: 'Computador', TABLET: 'Tablet', CONNECTED_TV: 'TV conectada', OTHER: 'Outro'};
const MATCH = {EXACT: 'Exata', PHRASE: 'Frase', BROAD: 'Ampla'};
const STATUS = {ENABLED: ['Ativo', 'success'], PAUSED: ['Pausado', 'gray'], REMOVED: ['Removido', 'error'], ADDED: ['Adicionado', 'success'], EXCLUDED: ['Negativado', 'gray'], NONE: ['—', 'gray']};
const BIDDING = {MAXIMIZE_CONVERSIONS: 'Maximizar conversões', MAXIMIZE_CONVERSION_VALUE: 'Maximizar valor', TARGET_CPA: 'CPA desejado', TARGET_ROAS: 'ROAS desejado', MANUAL_CPC: 'CPC manual', TARGET_SPEND: 'Maximizar cliques', TARGET_IMPRESSION_SHARE: 'Parcela de impressões'};
const status = value => {const [label, tone] = STATUS[value] || [value || '—', 'gray']; return label === '—' ? '—' : <span className={`rs-badge is-${tone}`}>{label}</span>;};

/** "O que está funcionando dentro das campanhas?" — the Google Ads detail the engine already collects every day. */
export function MediaPerformance({views: allowed, hideSettings = false} = {}) {
  const views = allowed ? VIEWS.filter(([key]) => allowed.includes(key)) : VIEWS;
  const {period} = useReportsContext();
  const [state, retry] = useApi(apiUrl('/media/performance', {start_date: period.start, end_date: period.end}));
  const [view, setView] = useState(views[0][0]);
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <LoadingState rows={8}/>;
  const body = state.body;
  if (!body.has_data && !body.settings.length) return <EmptyState title="Sem detalhe do Google Ads neste período"
    description="Grupos, palavras-chave, termos e dispositivos chegam pelo script do Google Ads (motor v2). Confira a integração ou escolha outro período."
    action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('media/data')}>Ver integração</ReportsActionButton>}/>;
  const money = micros => micros == null ? '—' : currency(micros / 1e6, body.currency);
  const metrics = [
    {key: 'cost_micros', label: 'Investimento', numeric: true, render: row => money(row.cost_micros)},
    {key: 'impressions', label: 'Impressões', numeric: true, render: row => number(row.impressions)},
    {key: 'clicks', label: 'Cliques', numeric: true, render: row => number(row.clicks)},
    {key: 'ctr', label: 'CTR', numeric: true, sort: row => row.impressions ? row.clicks / row.impressions : 0, render: row => percent(row.clicks, row.impressions)},
    {key: 'conversions', label: 'Conversões', numeric: true, sort: row => Number(row.conversions || 0), render: row => number(row.conversions)},
    {key: 'cpa', label: 'CPA', numeric: true, sort: row => Number(row.conversions) ? row.cost_micros / row.conversions : Infinity, render: row => Number(row.conversions) && row.cost_micros != null ? money(row.cost_micros / Number(row.conversions)) : '—'},
  ];
  const lead = {
    ad_groups: [{key: 'ad_group_name', label: 'Grupo', render: row => <><strong>{row.ad_group_name}</strong><small className="rs-cell-sub">{row.campaign_name}</small></>}, {key: 'status', label: 'Status', sortable: false, render: row => status(row.status)}],
    keywords: [{key: 'keyword_text', label: 'Palavra-chave', render: row => <><strong>{row.keyword_text}</strong><small className="rs-cell-sub">{MATCH[row.match_type] || row.match_type} · {row.ad_group_name}</small></>}, {key: 'quality_score', label: 'Índice de qualidade', numeric: true, sort: row => row.quality_score || 0, render: row => row.quality_score ? `${row.quality_score}/10` : '—'}],
    search_terms: [{key: 'search_term', label: 'Termo pesquisado'}, {key: 'status', label: 'Situação', sortable: false, render: row => status(row.status)}],
    landing_pages: [{key: 'page_path', label: 'Página', render: row => <><strong className="rs-path">{row.page_path}</strong><small className="rs-cell-sub">{row.page_host} · {row.campaigns} {row.campaigns === 1 ? 'campanha' : 'campanhas'}</small></>}],
    devices: [{key: 'device', label: 'Dispositivo', render: row => DEVICE[row.device] || row.device}],
  }[view];
  return <div className="rs-stack">
    <Section title={hideSettings ? 'Grupos, páginas e dispositivos' : 'Detalhe do Google Ads'} description="Ordenado por investimento no período; clique no cabeçalho para reordenar"
      action={<div className="rs-segmented" role="group" aria-label="Detalhe">{views.map(([key, label]) => <button type="button" key={key} aria-pressed={view === key} onClick={() => setView(key)}>{label}</button>)}</div>}>
      <DataTable key={view} label={VIEWS.find(([key]) => key === view)[1]} rows={body[view] || []} rowKey={(row, index) => index}
        empty={<p className="rs-muted">Sem dados desta visão no período.</p>} columns={[...lead, ...metrics]}/>
    </Section>
    {!hideSettings && body.settings.length > 0 && <Section title="Configuração das campanhas" description="Orçamento diário e estratégia de lance no último envio do script">
      <DataTable label="Configuração das campanhas" rows={body.settings} rowKey={(row, index) => index} limit={20} columns={[
        {key: 'campaign_name', label: 'Campanha'},
        {key: 'status', label: 'Status', sortable: false, render: row => status(row.status)},
        {key: 'bidding_strategy_type', label: 'Lance', render: row => BIDDING[row.bidding_strategy_type] || row.bidding_strategy_type || '—'},
        {key: 'budget_micros', label: 'Orçamento diário', numeric: true, sort: row => Number(row.budget_micros || 0), render: row => row.budget_micros == null ? '—' : `${currency(row.budget_micros / 1e6, row.currency)}${row.budget_shared ? ' · compartilhado' : ''}`},
      ]}/>
    </Section>}
  </div>;
}
