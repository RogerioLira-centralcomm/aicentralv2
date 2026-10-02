import {dayLabel} from '../../friendlyDates.js';
import React from 'react';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {friendlyDateTime} from '../../friendlyDates.js';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {Chart} from '../../shell/media.jsx';
import {DataTable, EmptyState, ErrorState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {number, percent} from '../shared.jsx';

const KIND = {conversion: 'Conversão', form_submit: 'Formulário enviado', whatsapp_click: 'WhatsApp'};
const CRM = {lead: 'Leads', qualified_lead: 'Leads qualificados', sale: 'Vendas'};

/** Conversions as the site observed them (type, page, origin), next to what the CRM confirmed. Connects media and behaviour. */
export function Conversions() {
  const {period} = useReportsContext();
  const [state, retry] = useApi(apiUrl('/journey/conversions', {start_date: period.start, end_date: period.end}));
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <div className="rs-stack"><LoadingState rows={2}/><LoadingState rows={6}/></div>;
  const body = state.body;
  const totals = body.totals;
  const confirmed = body.confirmed || [];
  const crmTotal = confirmed.reduce((sum, item) => sum + Number(item.total), 0);
  if (!body.groups.length && !crmTotal) return <EmptyState title="Nenhuma conversão no período"
    description="Marque a página de obrigado como conversão em um fluxo, envie eventos personalizados ou conecte o CRM para ver conversões aqui."
    action={<div className="rs-actions"><ReportsActionButton color="primary" size="sm" href={reportUrl('flows')}>Abrir Fluxos</ReportsActionButton><ReportsActionButton color="secondary" size="sm" href={reportUrl('events')}>Ver eventos</ReportsActionButton></div>}/>;
  const originSessions = body.origins.reduce((sum, item) => sum + item.sessions, 0);
  return <div className="rs-stack">
    <MetricGroup label="Resumo de conversões" items={[
      {label: 'Conversões', value: number(totals.conversion), detail: 'Observadas no site'},
      {label: 'Formulários enviados', value: number(totals.form_submit)},
      {label: 'Cliques no WhatsApp', value: number(totals.whatsapp_click)},
      {label: 'Confirmadas no CRM', value: number(crmTotal), detail: confirmed.length ? confirmed.map(item => `${number(item.total)} ${CRM[item.kind]?.toLowerCase() || item.kind}`).join(' · ') : 'Sem webhook de conversões'},
    ]}/>
    {body.daily.length > 1 && <Section title="Conversões por dia" description="Conversões observadas pela Super Tag">
      <Chart type="bar" height={220} labels={body.daily.map(item => dayLabel(item.day))} values={body.daily.map(item => Number(item.conversions))}/>
    </Section>}
    <Section title="Onde acontecem" description="Por tipo, nome do evento e página">
      <DataTable label="Conversões por página" rows={body.groups} rowKey={row => `${row.kind}${row.name}${row.host}${row.path}`} initialSort={{key: 'total', dir: 'desc'}}
        empty={<p className="rs-muted">Nenhum evento de conversão no site neste período.</p>} columns={[
          {key: 'kind', label: 'Tipo', render: row => KIND[row.kind] || row.kind},
          {key: 'name', label: 'Evento', render: row => row.name === row.kind ? '—' : row.name},
          {key: 'path', label: 'Página', render: row => <span className="rs-path" title={`${row.host}${row.path}`}>{row.path}</span>},
          {key: 'total', label: 'Quantidade', numeric: true, render: row => number(row.total)},
          {key: 'sessions', label: 'Sessões', numeric: true, render: row => number(row.sessions)},
          {key: 'last_at', label: 'Última', render: row => friendlyDateTime(row.last_at)},
        ]}/>
    </Section>
    <Section title="Origem das sessões que convertem" description="Primeiro contato da sessão e taxa de conversão">
      <DataTable label="Conversão por origem" rows={body.origins} rowKey={row => row.platform} initialSort={{key: 'converted', dir: 'desc'}} columns={[
        {key: 'label', label: 'Origem'},
        {key: 'sessions', label: 'Sessões', numeric: true, render: row => number(row.sessions)},
        {key: 'share', label: 'Das visitas', numeric: true, sort: row => row.sessions, render: row => percent(row.sessions, originSessions)},
        {key: 'converted', label: 'Converteram', numeric: true, render: row => number(row.converted)},
        {key: 'rate', label: 'Taxa', numeric: true, sort: row => row.sessions ? row.converted / row.sessions : 0, render: row => percent(row.converted, row.sessions)},
      ]}/>
    </Section>
  </div>;
}
