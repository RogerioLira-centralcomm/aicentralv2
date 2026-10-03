import {dayLabel} from '../../friendlyDates.js';
import React, {useState} from 'react';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {ReportsConfirmDialog} from '../../ReportsConfirmDialog.jsx';
import {json, reportUrl} from '../../reportsCommon.jsx';
import {friendlyDateTime} from '../../friendlyDates.js';
import {useReportsContext} from '../../shell/context.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {Chart} from '../../shell/media.jsx';
import {AppLink, DataTable, EmptyState, ErrorState, LoadingState, MetricGroup, Section} from '../../shell/primitives.jsx';
import {number, percent} from '../shared.jsx';

const KIND = {conversion: 'Conversão', form_submit: 'Formulário enviado', whatsapp_click: 'WhatsApp'};
const CRM = {lead: 'Leads', qualified_lead: 'Leads qualificados', sale: 'Vendas'};
const CONFIRMATION = {rule: 'Página de obrigado ou regra', conversion: 'Conversão registrada pelo site', valid_submit: 'Formulário válido'};
const STEP = {page_view: 'Página', form_submit: 'Formulário', conversion: 'Conversão'};

/** Conversions as the site observed them (type, page, origin), next to what the CRM confirmed. Connects media and behaviour. */
export function Conversions() {
  const {period, scope} = useReportsContext();
  const range = {start_date: period.start, end_date: period.end, site_id: scope.site || undefined};
  const [state, retry] = useApi(apiUrl('/journey/conversions', range));
  const [leadsState, retryLeads] = useApi(apiUrl('/supertag/leads', range));
  const [groupsState] = useApi(apiUrl('/journey/conversion-groups', range));
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <div className="rs-stack"><LoadingState rows={2}/><LoadingState rows={6}/></div>;
  const body = state.body;
  const totals = body.totals;
  const confirmed = body.confirmed || [];
  const crmTotal = confirmed.reduce((sum, item) => sum + Number(item.total), 0);
  const leads = leadsState.body?.leads || [];
  if (!body.groups.length && !crmTotal && !leads.length && !leadsState.loading) return <EmptyState title="Nenhuma conversão no período"
    description="Com a Super Tag instalada, páginas de obrigado (caminho com obrigad, thank, sucesso ou confirmac) já contam como conversão. Para contar outra página, um formulário válido ou um evento, crie a regra nas Configurações da Super Tag. Também dá para conectar o CRM."
    action={<div className="rs-actions"><ReportsActionButton color="primary" size="sm" href={reportUrl('supertag')}>Regras de conversão</ReportsActionButton><ReportsActionButton color="secondary" size="sm" href={reportUrl('events')}>Ver eventos</ReportsActionButton></div>}/>;
  const originSessions = body.origins.reduce((sum, item) => sum + item.sessions, 0);
  // Organic search reads per engine, so Google and Bing conversion rates can be compared.
  const originRows = body.origins.flatMap(item => item.engines?.length ? item.engines.map(engine => ({...engine, platform: `${item.platform}:${engine.engine}`, label: `${engine.label} · busca orgânica`})) : [item]);
  const leadTotals = leadsState.body?.totals;
  return <div className="rs-stack">
    <MetricGroup label="Resumo de conversões" items={[
      {label: 'Conversões', value: number(totals.conversion), detail: 'Observadas no site'},
      {label: 'Leads', value: leadTotals ? number(leadTotals.leads) : '—', detail: leadTotals ? `${number(leadTotals.confirmed)} confirmados · ${number(leadTotals.pending)} pendentes` : 'Quem enviou formulário'},
      {label: 'Formulários enviados', value: number(totals.form_submit)},
      {label: 'Cliques no WhatsApp', value: number(totals.whatsapp_click)},
      {label: 'Confirmadas no CRM', value: number(crmTotal), detail: confirmed.length ? confirmed.map(item => `${number(item.total)} ${CRM[item.kind]?.toLowerCase() || item.kind}`).join(' · ') : 'Sem webhook de conversões'},
    ]}/>
    <LeadsSection state={leadsState} retry={retryLeads}/>
    {body.daily.length > 1 && <Section title="Conversões por dia" description="Conversões observadas pela Super Tag">
      <Chart type="bar" height={220} labels={body.daily.map(item => dayLabel(item.day))} values={body.daily.map(item => Number(item.conversions))}/>
    </Section>}
    <ConversionGroups state={groupsState}/>
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
      <DataTable label="Conversão por origem" rows={originRows} rowKey={row => row.platform} initialSort={{key: 'converted', dir: 'desc'}} columns={[
        {key: 'label', label: 'Origem'},
        {key: 'sessions', label: 'Sessões', numeric: true, render: row => number(row.sessions)},
        {key: 'share', label: 'Das visitas', numeric: true, sort: row => row.sessions, render: row => percent(row.sessions, originSessions)},
        {key: 'converted', label: 'Converteram', numeric: true, render: row => number(row.converted)},
        {key: 'rate', label: 'Taxa', numeric: true, sort: row => row.sessions ? row.converted / row.sessions : 0, render: row => percent(row.converted, row.sessions)},
      ]}/>
    </Section>
  </div>;
}

// Conversion pages grouped on their own: URLs that differ only by an id are one group.
function ConversionGroups({state}) {
  const groups = state.body?.groups || [];
  if (state.error || !groups.length) return null;
  const {totals} = state.body;
  return <Section title="Grupos de conversão" description={`${totals.groups} ${totals.groups === 1 ? 'grupo' : 'grupos'} de páginas e eventos${totals.merged ? ` · ${totals.merged} reúnem várias URLs` : ''}`}>
    <DataTable label="Grupos de conversão" rows={groups} rowKey={row => `${row.site_id}${row.kind}${row.name}${row.pattern}`} initialSort={{key: 'conversions', dir: 'desc'}} columns={[
      {key: 'pattern', label: 'Grupo', render: row => <><span className="rs-path" title={`${row.host}${row.pattern}`}>{row.pattern}</span>
        <small className="rs-cell-sub">{KIND[row.kind] || row.kind}{row.name ? ` · ${row.name}` : ''}{row.grouped ? ` · ${row.pages} URLs` : ''}</small></>},
      {key: 'conversions', label: 'Conversões', numeric: true, render: row => number(row.conversions)},
      {key: 'sessions', label: 'Sessões', numeric: true, render: row => number(row.sessions)},
      {key: 'share', label: 'Participação', numeric: true, render: row => `${Number(row.share).toLocaleString('pt-BR', {maximumFractionDigits: 0})}%`},
      {key: 'origins', label: 'Origem principal', sortable: false, render: row => row.origins.length ? <span title={row.origins.map(item => `${item.label}: ${number(item.sessions)} sessões`).join('\n')}>{row.origins[0].label} <span className="rs-muted">{Number(row.origins[0].share).toLocaleString('pt-BR', {maximumFractionDigits: 0})}%</span></span> : '—'},
      {key: 'from_pages', label: 'Vêm de', sortable: false, render: row => row.from_pages.length ? <span className="rs-path" title={row.from_pages.map(item => `${item.pattern}: ${number(item.sessions)} sessões`).join('\n')}>{row.from_pages[0].pattern}</span> : '—'},
      {key: 'flow', label: <span className="sr-only">Ação</span>, sortable: false, render: row => {
        const from = row.from_pages[0]?.pattern;
        return from && !from.includes('*') && row.example_path && !row.grouped ? <AppLink className="rs-link" href={reportUrl('flows', {site_host: row.host, caminho: JSON.stringify([from, row.example_path])})}>Criar fluxo<span className="sr-only"> a partir deste caminho</span></AppLink> : null;
      }},
    ]}/>
  </Section>;
}

const origin = lead => lead.utm_source ? `${lead.utm_source}${lead.utm_medium ? ` / ${lead.utm_medium}` : ''}` : lead.referrer_host || 'Direto';

/** Who converted: the contact each valid form sent, its session origin and the pages visited before. */
function LeadsSection({state, retry}) {
  const [revealed, setRevealed] = useState({});
  const [journeyFor, setJourneyFor] = useState('');
  const [removing, setRemoving] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (state.error) return <Section title="Quem converteu"><ErrorState message={state.error} onRetry={retry}/></Section>;
  if (state.loading && !state.body) return <Section title="Quem converteu"><LoadingState rows={3}/></Section>;
  const body = state.body;
  if (!body) return null;
  const description = 'Contatos de formulários válidos e de identify(). Confirmado quando a conversão da mesma sessão chega em até 30 minutos.';
  if (!body.ready) return <Section title="Quem converteu" description={description}><p className="rs-muted">A tabela de contatos ainda não foi criada neste ambiente (migração pendente).</p></Section>;
  const reveal = async lead => {
    setError('');
    try {const contact = await json(apiUrl(`/supertag/leads/${lead.id}/contact`)); setRevealed(current => ({...current, [lead.id]: contact}));}
    catch (failure) {setError(failure.message);}
  };
  const remove = async () => {
    setBusy(true); setError('');
    try {
      await json(apiUrl(`/supertag/leads/${removing.id}`), {method: 'DELETE', headers: {'X-CSRF-Token': body.csrf || ''}});
      setRemoving(null); retry();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const selected = body.leads.find(item => item.id === journeyFor);
  return <Section title="Quem converteu" description={description}>
    {error && <div className="rs-error" role="alert"><div><strong>Não foi possível concluir</strong><p>{error}</p></div></div>}
    <DataTable label="Quem converteu" rows={body.leads} rowKey={row => row.id} initialSort={{key: 'submitted_at', dir: 'desc'}}
      empty={<p className="rs-muted">Nenhum contato neste período. Formulários válidos enviam nome, e-mail e telefone automaticamente; campos extras são escolhidos nas Configurações da Super Tag.</p>}
      columns={[
        {key: 'submitted_at', label: 'Data e hora', render: row => friendlyDateTime(row.submitted_at)},
        {key: 'name', label: 'Nome', render: row => (revealed[row.id]?.name ?? row.name) || <span className="rs-muted">—</span>},
        {key: 'contact', label: 'Contato', sortable: false, render: row => {
          const full = revealed[row.id];
          const email = full ? full.email : row.email, phone = full ? full.phone : row.phone;
          return <span className="flex flex-col gap-0.5">
            {email && <span>{email}</span>}{phone && <span>{phone}</span>}{!email && !phone && <span className="rs-muted">—</span>}
            {body.can_reveal && !full && (row.email || row.phone) && <button type="button" className="text-left text-xs font-semibold text-brand-secondary" onClick={() => reveal(row)}>Revelar</button>}
          </span>;
        }},
        {key: 'fields', label: 'Campos extras', sortable: false, render: row => {
          const fields = revealed[row.id]?.fields || row.fields || {};
          const entries = Object.entries(fields);
          return entries.length ? <span className="flex flex-col gap-0.5 text-xs">{entries.map(([key, value]) => <span key={key}><strong>{key}:</strong> {value}</span>)}</span> : <span className="rs-muted">—</span>;
        }},
        {key: 'page_path', label: 'Página do formulário', render: row => <span className="rs-path" title={`${row.host}${row.page_path}`}>{row.source === 'identify' ? `${row.page_path} · identify` : row.page_path}</span>},
        {key: 'status', label: 'Status', render: row => row.status === 'confirmed'
          ? <span title={CONFIRMATION[row.confirmation] || ''}>Confirmado</span> : <span className="rs-muted" title="Sem conversão da mesma sessão em até 30 min">Pendente</span>},
        {key: 'origin', label: 'Origem da sessão', sort: origin, render: origin},
        {key: 'campaign', label: 'Campanha', render: row => row.campaign || <span className="rs-muted">—</span>},
        {key: 'actions', label: '', sortable: false, render: row => <span className="flex gap-3 whitespace-nowrap">
          <button type="button" className="text-xs font-semibold text-brand-secondary" aria-expanded={journeyFor === row.id} onClick={() => setJourneyFor(current => current === row.id ? '' : row.id)}>{journeyFor === row.id ? 'Ocultar jornada' : 'Ver jornada'}</button>
          {body.can_reveal && <button type="button" className="text-xs font-semibold text-error-primary" onClick={() => setRemoving(row)}>Apagar</button>}
        </span>},
      ]}/>
    {selected && <div className="rs-card mt-3 p-4" aria-live="polite">
      <p className="text-sm font-semibold text-primary">Jornada da sessão · {selected.host}</p>
      {selected.journey.length ? <ol className="mt-2 flex flex-col gap-1 text-sm">{selected.journey.map((step, index) => <li key={index} className="flex gap-3">
        <span className="w-28 shrink-0 text-xs text-tertiary">{friendlyDateTime(step.at)}</span>
        <span className="w-24 shrink-0 text-xs font-semibold">{STEP[step.kind] || step.kind}</span>
        <span className="rs-path">{step.path}{step.kind === 'conversion' && step.name ? ` · ${step.name}` : ''}</span>
      </li>)}</ol> : <p className="rs-muted mt-2">Os eventos desta sessão já expiraram ou ainda não chegaram.</p>}
    </div>}
    <ReportsConfirmDialog open={Boolean(removing)} title="Apagar contato" description="O contato e os campos deste envio são apagados de vez. A conversão continua contada." confirmLabel="Apagar contato" busy={busy}
      onCancel={() => setRemoving(null)} onConfirm={remove}/>
  </Section>;
}
