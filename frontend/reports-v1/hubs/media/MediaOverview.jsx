import React from 'react';
import {ArrowRight} from '@untitledui/icons';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {useReportsContext} from '../../shell/context.js';
import {platformName} from '../../shell/media.jsx';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {TrendGrid, daySeries} from '../../shell/TrendGrid.jsx';
import {AppLink, DataTable, EmptyState, ErrorState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {compact, compactCurrency, currency, number, percent, useMedia} from '../shared.jsx';

const STATUS = {ENABLED: 'Ativa', PAUSED: 'Pausada', REMOVED: 'Removida', active: 'Ativa', paused: 'Pausada', disabled: 'Desativada'};

/** "Como está minha operação de mídia?" — totals, the daily curve, channels and the campaigns to open next. */
export function MediaOverview({data}) {
  const {period, scope} = useReportsContext();
  const media = useMedia(period, scope);
  // Same comparison the Visão geral uses: the previous window of equal length, daily, for the dashed line.
  const [compare] = useApi(apiUrl('/overview/compare', {start_date: period.start, end_date: period.end, account_id: scope.account, campaign_id: scope.campaign}));
  if (media.loading) return <div className="rs-stack"><LoadingState rows={2}/><LoadingState rows={6}/></div>;
  if (media.error) return <ErrorState message={media.error} onRetry={media.retry}/>;
  const summary = media.summary;
  if (!summary) return <EmptyState title="Nenhum dado de mídia neste período"
    description={media.conflicts ? 'Há valores importados aguardando revisão; eles entram aqui depois de confirmados.' : 'Conecte o Google Ads, envie um arquivo ou escolha outro período para ver investimento, alcance e resultado.'}
    action={<div className="rs-actions"><ReportsActionButton color="primary" size="sm" href={reportUrl('media/data')}>Conectar fonte</ReportsActionButton><ReportsActionButton color="secondary" size="sm" href={reportUrl('imports')}>Enviar arquivo</ReportsActionButton></div>}/>;
  const {totals} = summary;
  const money = value => currency(value, summary.currency);
  const campaigns = data.campaigns.filter(item => ['ENABLED', 'active'].includes(item.status)
    && (!scope.account || String(item.account_id) === scope.account) && (!scope.campaign || String(item.id) === scope.campaign)).slice(0, 6);
  const previous = compare.body?.previous_daily?.media || [];
  const trend = [
    {key: 'cost', title: 'Investimento por dia', field: 'cost', format: money, total: compactCurrency(totals.cost, summary.currency), skip: totals.cost == null},
    {key: 'impressions', title: 'Impressões por dia', field: 'impressions', format: number, total: compact(totals.impressions)},
    {key: 'clicks', title: 'Cliques por dia', field: 'clicks', format: number, total: compact(totals.clicks)},
    {key: 'conversions', title: 'Conversões por dia', field: 'conversions', format: number, total: number(totals.conversions)},
  ].filter(item => !item.skip).map(item => ({...item, points: daySeries(period.start, period.end, summary.days, item.field),
    previous: previous.map(row => row[item.field] == null ? null : Number(row[item.field]))}));
  return <div className="rs-stack">
    <MetricGroup label="Resumo de mídia" items={[
      {label: 'Investimento', value: compactCurrency(totals.cost, summary.currency), detail: summary.origin},
      {label: 'Impressões', value: compact(totals.impressions)},
      {label: 'Cliques', value: compact(totals.clicks), detail: `CTR ${percent(totals.clicks, totals.impressions)}`},
      {label: 'Conversões', value: number(totals.conversions), detail: summary.confirmed ? `${number(summary.confirmed)} confirmadas no CRM` : 'Informadas pela plataforma'},
      {label: 'CPA', value: totals.cost != null && totals.conversions ? money(totals.cost / totals.conversions) : '—', detail: 'Investimento por conversão'},
    ]}/>
    <TrendGrid title="Tendência diária das campanhas" description="Contra o período anterior de mesma duração" charts={trend} columns={trend.length === 4 ? 2 : 3}/>
    <Section title="Canais" description="Resultado por plataforma no período">
      <DataTable label="Canais" rows={summary.platforms} rowKey={row => row.platform} initialSort={{key: 'cost', dir: 'desc'}} columns={[
        {key: 'label', label: 'Canal'},
        {key: 'cost', label: 'Investimento', numeric: true, render: row => money(row.cost)},
        {key: 'impressions', label: 'Impressões', numeric: true, render: row => number(row.impressions)},
        {key: 'clicks', label: 'Cliques', numeric: true, render: row => number(row.clicks)},
        {key: 'ctr', label: 'CTR', numeric: true, sort: row => row.impressions ? row.clicks / row.impressions : 0, render: row => percent(row.clicks, row.impressions)},
        {key: 'conversions', label: 'Conversões', numeric: true, render: row => number(row.conversions)},
      ]}/>
    </Section>
    <Section title="Campanhas ativas" description={`${campaigns.length} de ${data.campaigns.length} cadastradas`}
      action={<AppLink className="rs-link" href={reportUrl('media/campaigns')}>Todas as campanhas<ArrowRight size={14} aria-hidden="true"/></AppLink>}>
      <DataTable label="Campanhas ativas" rows={campaigns} rowKey={row => row.id}
        empty={<p className="rs-muted">Nenhuma campanha ativa. Cadastre ou reative campanhas em Mídia → Campanhas.</p>} columns={[
          {key: 'name', label: 'Campanha', render: row => <AppLink href={reportUrl('campaigns', {campaign_id: row.id})}>{row.name}</AppLink>},
          {key: 'account_name', label: 'Conta'},
          {key: 'platform', label: 'Canal', render: row => platformName(row.platform)},
          {key: 'status', label: 'Status', render: row => <span className="rs-badge is-success">{STATUS[row.status] || row.status}</span>},
          {key: 'creative', label: '', sortable: false, render: row => <AppLink className="rs-link" href={reportUrl('media/creatives', {campaign: row.id})}>Criar criativo</AppLink>},
        ]}/>
    </Section>
  </div>;
}
