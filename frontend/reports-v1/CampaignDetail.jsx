import React, {useEffect, useState} from 'react';
import {ArrowLeft, ArrowUpRight, SearchLg} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsTabs} from './ReportsTabs.jsx';
import {FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import {Alert, Callout, Card, DataTable as Table, EmptyNote, Stats} from './ReportsBlocks.jsx';
import {CAMPAIGN_STATUS, channelLabel} from './ClientsAccounts.jsx';
import {Chart, amount, money, platformName} from './shell/media.jsx';
import {decimal, integer, json, reportUrl, shortDate} from './reportsCommon.jsx';

const API = '/connect/api/v2/reports';
const TABS = [['overview', 'Visão geral'], ['performance', 'Performance'], ['channels', 'Canais'], ['pages', 'Páginas'], ['forms', 'Formulários'], ['leads', 'Leads'],
  ['conversions', 'Conversões'], ['reports', 'Relatórios'], ['imports', 'Dados de origem'], ['settings', 'Configurações']];
const METRIC_LABELS = {impressions: 'Impressões', clicks: 'Cliques', cost: 'Investimento', conversions: 'Conversões', conversion_value: 'Valor de conversão'};
const CRM_STEPS = {lead: 'Lead', qualified_lead: 'Lead qualificado', sale: 'Venda'};
const money_ = key => key === 'cost' || key === 'conversion_value';

function Toolbar({query, setQuery, placeholder, sources, source, setSource, metric, setMetric}) {
  return <div className="flex flex-wrap items-center gap-3 border-b border-secondary px-6 py-3">
    <div className="w-full max-w-80"><ReportsFieldInput size="sm" type="search" aria-label={placeholder} placeholder={placeholder} value={query} onChange={event => setQuery(event.target.value)}
      leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>}/></div>
    {sources?.length > 0 && <div className="w-48"><ReportsNativeSelect size="sm" aria-label="Origem" value={source} onChange={event => setSource(event.target.value)}>
      <option value="all">Todas as origens</option>{sources.map(item => <option key={item} value={item}>{item}</option>)}</ReportsNativeSelect></div>}
    {setMetric && <div className="w-48"><ReportsNativeSelect size="sm" aria-label="Métrica" value={metric} onChange={event => setMetric(event.target.value)}>
      <option value="all">Todas as métricas</option>{Object.entries(METRIC_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</ReportsNativeSelect></div>}
  </div>;
}

/** One media campaign: performance, traffic it brings, what happens on the site and the CRM, sources and settings. */
export function CampaignDetail({data, detail, error, tab, setTab, close, filters, refreshRevision, save, busy, updateDetail}) {
  const [channelData, setChannelData] = useState(null);
  const [flowData, setFlowData] = useState(null);
  const [analysisError, setAnalysisError] = useState('');
  const [query, setQuery] = useState('');
  const [source, setSource] = useState('all');
  const [metric, setMetric] = useState('all');
  const campaignId = detail?.campaign?.id;
  useEffect(() => {
    if (!campaignId) return undefined;
    let active = true;
    const params = new URLSearchParams({client_id: String(data.client.client_id), campaign_id: String(campaignId), days: filters.period, start_date: filters.startDate, end_date: filters.endDate});
    Promise.all([json(`${API}/metrics?${params}`), json(`${API}/flow?${params}`)])
      .then(([metrics, flow]) => {if (active) {setChannelData(metrics); setFlowData(flow); setAnalysisError('');}})
      .catch(failure => {if (active) setAnalysisError(failure.message);});
    return () => {active = false;};
  }, [campaignId, data.client.client_id, filters.period, filters.startDate, filters.endDate, refreshRevision]);
  useEffect(() => {setQuery(''); setSource('all'); setMetric('all');}, [tab]);

  const back = <div><Button size="sm" color="link-gray" iconLeading={ArrowLeft} onPress={close}>Campanhas</Button></div>;
  if (error) return <div className="untitled-scope flex flex-col gap-6">{back}<Alert>{error}</Alert></div>;
  if (!detail) return <div className="untitled-scope flex flex-col gap-6">{back}<Card><p className="text-sm text-tertiary">Carregando a campanha…</p></Card></div>;

  const campaign = detail.campaign;
  const period = `${shortDate(filters.startDate)} – ${shortDate(filters.endDate)}`;
  const inPeriod = item => item.metric_date >= filters.startDate && item.metric_date <= filters.endDate;
  const latest = (detail.metric_totals || []).reduce((value, item) => !value || item.latest_date > value ? item.latest_date : value, '');
  const imported = key => detail.metrics.filter(item => item.metric_key === key && inPeriod(item) && item.value_numeric != null).reduce((sum, item) => sum + Number(item.value_numeric || 0), 0);
  const events = flowData?.events || [];
  const channelEvents = Object.values(events.reduce((map, item) => {
    const key = item.source_label || 'Origem direta';
    map[key] = map[key] || {source_label: key, total: 0, mapped: 0};
    map[key].total += Number(item.total || 0); map[key].mapped += Number(item.mapped || 0);
    return map;
  }, {}));
  const channelTotal = channelEvents.reduce((sum, item) => sum + item.total, 0);
  const forms = events.filter(item => item.event_kind === 'form_submit');
  const conversions = events.filter(item => item.event_kind === 'conversion');
  const assists = events.filter(item => ['form_submit', 'whatsapp_click'].includes(item.event_kind));
  const confirmed = flowData?.confirmed || [];
  const ingested = (channelData?.days || []).flatMap(item => [
    {metric_date: item.date, metric_key: 'impressions', value_numeric: item.impressions, source: 'google_ads_script'},
    {metric_date: item.date, metric_key: 'clicks', value_numeric: item.clicks, source: 'google_ads_script'},
    {metric_date: item.date, metric_key: 'cost', value_numeric: item.cost_micros == null ? null : Number(item.cost_micros) / 1_000_000, currency: channelData.currency, source: 'google_ads_script'},
    {metric_date: item.date, metric_key: 'conversions', value_numeric: item.conversions, source: 'google_ads_script'},
  ]).filter(item => item.value_numeric != null);
  const importedDaily = detail.metrics.filter(item => item.value_numeric != null && inPeriod(item));
  const dimensional = (detail.metric_observations || []).filter(inPeriod);
  const needle = query.trim().toLocaleLowerCase('pt-BR');
  const hit = value => !needle || String(value || '').toLocaleLowerCase('pt-BR').includes(needle);
  const bySource = item => source === 'all' || item.source_label === source;
  const sourcesOf = list => [...new Set(list.map(item => item.source_label))];
  const toolbar = props => <Toolbar query={query} setQuery={setQuery} source={source} setSource={setSource} metric={metric} {...props}/>;
  const [statusLabel, statusColor] = CAMPAIGN_STATUS[campaign.status] || [campaign.status || 'Ativa', 'gray'];
  const chart = <Chart type="area" labels={(channelData?.days || []).map(item => shortDate(item.date))} values={(channelData?.days || []).map(item => item.impressions)}/>;
  const eventColumns = [['Evento', row => <span className="font-medium text-primary">{row.event_name}</span>], ['Página', row => <span className="font-mono text-xs">{row.page_path}</span>],
    ['Origem', row => row.source_label], ['Ocorrências', row => integer(row.total), 'right'], ['Em etapas', row => integer(row.mapped), 'right']];
  const crmTable = <Table minWidth={360} rowKey={row => row.conversion_kind} rows={confirmed} columns={[['Etapa', row => CRM_STEPS[row.conversion_kind] || row.conversion_kind], ['Confirmações', row => integer(row.total), 'right']]}/>;

  return <div className="untitled-scope flex flex-col gap-6">
    {back}
    <section className="flex flex-wrap items-start justify-between gap-4 rounded-xl bg-primary px-6 py-5 shadow-xs ring-1 ring-secondary">
      <div className="flex min-w-0 items-start gap-4">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-primary ring-1 ring-secondary [&_img]:size-6 [&_svg]:h-5 [&_svg]:w-8"><FlowPlatformLogo platform={campaign.platform}/></span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2"><h2 className="text-xl font-semibold text-primary">{campaign.name}</h2><BadgeWithDot type="pill-color" size="sm" color={statusColor}>{statusLabel}</BadgeWithDot></div>
          <p className="mt-0.5 text-sm text-tertiary">{platformName(campaign.platform)} · {campaign.account_name || 'Campanha manual'}{campaign.external_id ? <> · ID <span className="font-mono">{campaign.external_id}</span></> : ''}{channelLabel(campaign.channel_type || campaign.objective) ? ` · ${channelLabel(campaign.channel_type || campaign.objective)}` : ''}</p>
          <p className="mt-1 text-xs text-quaternary">Criada em {shortDate(campaign.created_at)} · atualizada em {shortDate(campaign.updated_at)} · período {period}</p>
        </div>
      </div>
      <div className="flex shrink-0 gap-3">
        <Button size="md" color="secondary" href={reportUrl('media/creatives', {campaign: campaign.id})}>Criar criativo</Button>
        <Button size="md" color="secondary" href={reportUrl('imports')}>Importar dados</Button>
      </div>
    </section>
    <ReportsTabs label="Seções da campanha" items={TABS.map(([id, label]) => ({id, label}))} value={tab} onChange={setTab}/>
    {analysisError && <Alert>Não foi possível carregar os dados desta campanha: {analysisError}</Alert>}

    {tab === 'overview' && <>
      <Stats items={[['Impressões', integer(channelData?.totals?.impressions ?? imported('impressions')), `${period} · mídia`], ['Cliques', integer(channelData?.totals?.clicks ?? imported('clicks')), `${period} · mídia`],
        ['Conversões', decimal(channelData?.totals?.conversions ?? imported('conversions')), 'Reportadas pela plataforma'], ['Último dado', shortDate(latest), 'Mais recente entre as métricas']]}/>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Impressões no período" description={period}>{chart}</Card>
        <Card flush title="Dados personalizados" badge={<Badge type="pill-color" size="sm" color="gray">{detail.custom_values.length}</Badge>} description="Campos extras dos arquivos importados.">
          {detail.custom_values.length ? <ul>{detail.custom_values.slice(0, 8).map((item, index) => <li key={`${item.metric_key}:${item.metric_date}:${index}`} className="flex items-center justify-between gap-3 border-b border-secondary px-6 py-3 last:border-b-0">
            <div className="min-w-0"><p className="truncate text-sm font-medium text-primary">{item.metric_label} <span className="font-normal text-tertiary">· {item.channel}</span></p><p className="font-mono text-xs text-tertiary">{item.metric_key} · {shortDate(item.metric_date)}</p></div>
            <span className="text-sm font-semibold text-primary tabular-nums">{item.value_numeric} <span className="text-xs font-normal text-tertiary">{item.currency || item.unit}</span></span>
          </li>)}</ul> : <EmptyNote title="Nenhum dado extra">Campos adicionais importados aparecem aqui.</EmptyNote>}
        </Card>
      </div>
    </>}

    {tab === 'performance' && (() => {
      const all = [...ingested, ...importedDaily];
      const rows = all.filter(item => (source === 'all' || (item.source === 'google_ads_script' ? 'Google Ads' : 'Importação') === source) && (metric === 'all' || item.metric_key === metric)
        && hit(`${METRIC_LABELS[item.metric_key] || item.metric_key} ${item.metric_date} ${item.currency || ''} ${item.source || ''}`));
      const dims = dimensional.filter(item => (metric === 'all' || item.metric_key === metric) && hit(`${METRIC_LABELS[item.metric_key] || item.metric_key} ${item.metric_date} ${Object.values(item.dimensions || {}).map(value => `${value.label} ${value.value}`).join(' ')}`));
      const value = item => money_(item.metric_key) ? amount(item.value_numeric, item.currency) : integer(item.value_numeric);
      return <>
        <Stats items={[['Impressões', integer(channelData?.totals?.impressions), period], ['Cliques', integer(channelData?.totals?.clicks), period],
          ['Investimento', money(channelData?.totals?.cost_micros, channelData?.currency), 'Moeda da conta'], ['Conversões da plataforma', decimal(channelData?.totals?.conversions), 'Enviadas pela plataforma']]}/>
        <Card title="Impressões por dia" description={`${period} · Google Ads Script`}>{chart}</Card>
        <Card flush title="Métricas por data" badge={<Badge type="pill-color" size="sm" color="gray">{rows.length}</Badge>} description="Valores mantidos por origem e unidade, sem misturar fontes.">
          {toolbar({placeholder: 'Data, origem ou métrica', sources: ['Google Ads', 'Importação'], setMetric})}
          {rows.length ? <Table rowKey={(row, index) => `${row.metric_date}:${row.metric_key}:${index}`} rows={rows} columns={[['Data', row => shortDate(row.metric_date)], ['Métrica', row => METRIC_LABELS[row.metric_key] || row.metric_key],
            ['Valor', value, 'right'], ['Moeda', row => row.currency || '—'],
            ['Fonte', row => row.source === 'google_ads_script' ? 'Google Ads' : row.version_count > 1 ? <Badge type="pill-color" size="sm" color="warning">Revisar divergência</Badge> : 'Importação']]}/>
            : <EmptyNote title={all.length ? 'Nada corresponde aos filtros' : 'Sem dados de performance no período'}/>}
        </Card>
        <Card flush title="Por anúncio e dimensão" badge={<Badge type="pill-color" size="sm" color="gray">{dims.length}</Badge>} description="Valores do export apresentados sem somar entre dimensões.">
          {toolbar({placeholder: 'Anúncio, dimensão ou métrica', sources: [], setMetric})}
          {dims.length ? <Table rowKey={(row, index) => `${row.metric_date}:${row.metric_key}:${index}`} rows={dims.slice(0, 500)} columns={[['Data', row => shortDate(row.metric_date)], ['Métrica', row => METRIC_LABELS[row.metric_key] || row.metric_key],
            ['Valor', value, 'right'], ['Dimensões', row => Object.values(row.dimensions || {}).map(item => `${item.label}: ${item.value}`).join(' · ') || 'Campanha']]}/>
            : <EmptyNote title={dimensional.length ? 'Nada corresponde aos filtros' : 'Sem detalhe por anúncio'}>{dimensional.length ? null : 'Aparece quando o export traz essa dimensão.'}</EmptyNote>}
        </Card>
      </>;
    })()}

    {tab === 'channels' && (() => {
      const rows = channelEvents.filter(item => bySource(item) && hit(item.source_label));
      return <>
        <Stats items={[['Plataforma', platformName(campaign.platform), channelLabel(campaign.channel_type || campaign.objective) || 'Canal não informado'], ['Origens atribuídas', integer(channelEvents.length), 'UTM ou domínio de referência'],
          ['Eventos atribuídos', integer(channelTotal), period]]}/>
        <Card flush title="Origem do tráfego" badge={<Badge type="pill-color" size="sm" color="gray">{rows.length}</Badge>} description={`Eventos da Super Tag atribuídos a esta campanha · ${period}`}>
          {toolbar({placeholder: 'Origem, UTM ou domínio', sources: sourcesOf(channelEvents)})}
          {rows.length ? <Table minWidth={560} rowKey={row => row.source_label} rows={rows} columns={[['Origem', row => <span className="font-medium text-primary">{row.source_label}</span>], ['Eventos', row => integer(row.total), 'right'],
            ['Em etapas', row => integer(row.mapped), 'right'], ['Participação', row => channelTotal ? `${Math.round(row.total / channelTotal * 100)}%` : '—', 'right']]}/>
            : <EmptyNote title={channelEvents.length ? 'Nada corresponde aos filtros' : 'Sem eventos atribuídos no período'}/>}
        </Card>
      </>;
    })()}

    {tab === 'pages' && (() => {
      const all = flowData?.activity || [];
      const rows = all.filter(item => hit(item.page_path));
      return <Card flush title="Páginas" badge={<Badge type="pill-color" size="sm" color="gray">{rows.length}</Badge>} description={`Atividade por URL · ${period}`}>
        {toolbar({placeholder: 'Caminho ou URL'})}
        {rows.length ? <Table rowKey={row => `${row.tag_id}:${row.page_path}`} rows={rows} columns={[['Página', row => <span className="font-mono text-xs text-primary">{row.page_path}</span>], ['Visitas', row => integer(row.views), 'right'],
          ['Visitantes', row => integer(row.visitors), 'right'], ['Formulários', row => integer(row.form_submissions), 'right'], ['Conversões', row => integer(row.conversions), 'right']]}/>
          : <EmptyNote title={all.length ? 'Nada corresponde à busca' : 'Nenhuma página com visitas da campanha'}>{all.length ? null : 'Aparecem quando a Super Tag recebe visitas atribuídas a esta campanha.'}</EmptyNote>}
      </Card>;
    })()}

    {tab === 'forms' && (() => {
      const rows = forms.filter(item => bySource(item) && hit(`${item.event_name} ${item.page_path} ${item.source_label}`));
      return <Card flush title="Formulários" badge={<Badge type="pill-color" size="sm" color="gray">{rows.length}</Badge>} description="Somente contagens; o que foi digitado não é armazenado.">
        {toolbar({placeholder: 'Evento, página ou origem', sources: sourcesOf(forms)})}
        {rows.length ? <Table rowKey={(row, index) => `${row.event_name}:${row.page_path}:${index}`} rows={rows} columns={eventColumns}/>
          : <EmptyNote title={forms.length ? 'Nada corresponde aos filtros' : 'Nenhum envio no período'}/>}
      </Card>;
    })()}

    {tab === 'leads' && <>
      <Stats items={[['Leads', integer(confirmed.find(item => item.conversion_kind === 'lead')?.total), 'Confirmados pelo CRM'], ['Qualificados', integer(confirmed.find(item => item.conversion_kind === 'qualified_lead')?.total), 'Confirmados pelo CRM'],
        ['Vendas', integer(confirmed.find(item => item.conversion_kind === 'sale')?.total), 'Confirmadas pelo CRM']]}/>
      <Card flush title="Confirmações recebidas" description={`CRM · ${period} · somente totais; dados pessoais ficam no CRM.`}>
        {confirmed.length ? crmTable : <EmptyNote title="Nenhuma confirmação">Conecte o CRM em Mídia › Dados para receber leads e vendas confirmados.</EmptyNote>}
      </Card>
    </>}

    {tab === 'conversions' && (() => {
      const rows = conversions.filter(item => bySource(item) && hit(`${item.event_name} ${item.page_path} ${item.source_label}`));
      const sum = kind => assists.filter(item => item.event_kind === kind).reduce((total, item) => total + Number(item.total || 0), 0);
      return <>
        <Stats items={[['Na plataforma', decimal(channelData?.totals?.conversions), 'Reportadas pela conta de mídia'], ['No site', integer(channelData?.observed_conversions), 'Eventos de conversão da Super Tag'],
          ['No CRM', integer(channelData?.confirmed_conversions), 'Leads, qualificados e vendas']]}/>
        <Callout>Plataforma, site e CRM medem de jeitos diferentes. Os totais ficam separados para comparação e nunca são somados.</Callout>
        <Card flush title="Conversões observadas no site" badge={<Badge type="pill-color" size="sm" color="gray">{rows.length}</Badge>} description={`Eventos da Super Tag · ${period}`}>
          {toolbar({placeholder: 'Conversão, página ou origem', sources: sourcesOf(conversions)})}
          {rows.length ? <Table rowKey={(row, index) => `${row.event_name}:${row.page_path}:${index}`} rows={rows} columns={eventColumns}/>
            : <EmptyNote title="Nenhuma conversão no período">Configure uma etapa de conversão em Fluxos ou chame trackConversion no site depois da ação confirmada.</EmptyNote>}
        </Card>
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Ações antes da conversão" description="Formulários e cliques no WhatsApp atribuídos à campanha, sem somar às conversões.">
            <dl className="grid grid-cols-2 gap-4">{[['Formulários', sum('form_submit')], ['WhatsApp', sum('whatsapp_click')]].map(([label, value]) => <div key={label}>
              <dt className="text-sm text-tertiary">{label}</dt><dd className="text-display-xs font-semibold text-primary tabular-nums">{integer(value)}</dd></div>)}</dl>
          </Card>
          <Card flush title="Etapas confirmadas pelo CRM" description="Fonte independente, agregada.">{confirmed.length ? crmTable : <EmptyNote title="Nenhuma confirmação do CRM"/>}</Card>
        </div>
      </>;
    })()}

    {tab === 'reports' && <Card flush title="Relatórios associados" badge={<Badge type="pill-color" size="sm" color="gray">{detail.reports.length}</Badge>}>
      {detail.reports.length ? <ul>{detail.reports.map(item => <li key={item.id} className="flex items-center justify-between gap-3 border-b border-secondary px-6 py-3 last:border-b-0">
        <div><p className="text-sm font-medium text-primary">{item.campaign_name}</p><p className="text-xs text-tertiary">Versão {item.revision} · {shortDate(item.updated_at)}</p></div>
        <Button size="sm" color="secondary" href={reportUrl('reports')} iconTrailing={ArrowUpRight}>Abrir</Button>
      </li>)}</ul> : <EmptyNote title="Nenhum relatório associado">Crie um relatório em Relatórios e escolha esta campanha.</EmptyNote>}
    </Card>}

    {tab === 'imports' && <div className="grid gap-6 lg:grid-cols-2">
      <Card flush title="Arquivos de origem" badge={<Badge type="pill-color" size="sm" color="gray">{detail.imports.length}</Badge>} actions={<Button size="sm" color="secondary" href={reportUrl('imports')} iconTrailing={ArrowUpRight}>Importações</Button>}>
        {detail.imports.length ? <ul>{detail.imports.map(item => <li key={item.id} className="border-b border-secondary px-6 py-3 last:border-b-0">
          <p className="truncate text-sm font-medium text-primary">{item.original_name}</p><p className="text-xs text-tertiary">{item.file_kind} · {integer(item.observations)} métricas · {shortDate(item.created_at)}</p>
        </li>)}</ul> : <EmptyNote title="Nenhum arquivo importado"/>}
      </Card>
      <Card flush title="Totais por intervalo" badge={<Badge type="pill-color" size="sm" color="gray">{detail.range_snapshots.length}</Badge>} description="Ficam separados dos dados diários.">
        {detail.range_snapshots.length ? <ul>{detail.range_snapshots.map(item => <li key={item.id} className="border-b border-secondary px-6 py-3 last:border-b-0">
          <p className="text-sm font-medium text-primary">{shortDate(item.period_start)} – {shortDate(item.period_end)} <span className="font-normal text-tertiary">· {item.original_name}</span></p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">{item.metrics.map(entry => <Badge key={entry.metric_key} type="color" size="sm" color="gray">{entry.metric_label}: {entry.value_numeric} {entry.currency || entry.unit}</Badge>)}</div>
        </li>)}</ul> : <EmptyNote title="Nenhum total de intervalo"/>}
      </Card>
    </div>}

    {tab === 'settings' && <Settings data={data} campaign={campaign} statusLabel={statusLabel} save={save} busy={busy} updateDetail={updateDetail}/>}
  </div>;
}

function Settings({data, campaign, statusLabel, save, busy, updateDetail}) {
  const [form, setForm] = useState({});
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    setForm({account_id: campaign.account_id || '', external_id: campaign.external_id || '', name: campaign.name || '', objective: campaign.objective || '', channel_type: campaign.channel_type || ''});
    setNotice('');
  }, [campaign.id, campaign.name, campaign.objective, campaign.channel_type]);
  const submit = async event => {
    event.preventDefault();
    try {
      await save(`/campaigns/${campaign.id}`, form, true, 'PATCH');
      updateDetail(await json(`${API}/campaigns/${campaign.id}?client_id=${data.client.client_id}`));
      setNotice('Campanha atualizada.'); setError('');
    } catch (failure) {setError(failure.message); setNotice('');}
  };
  const facts = [['Plataforma', platformName(campaign.platform)], ['Conta anunciante', campaign.account_name || '—'], ['ID da conta', campaign.account_external_id, true],
    ['ID da campanha', campaign.external_id, true], ['Status na plataforma', statusLabel], ['Última atualização', shortDate(campaign.updated_at)]];
  return <div className="grid items-start gap-6 lg:grid-cols-2">
    <Card title="Identificação" description="Como a campanha aparece na conta de mídia.">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4">{facts.map(([label, value, mono]) => <div key={label} className="min-w-0">
        <dt className="text-xs font-medium text-tertiary">{label}</dt><dd className={`mt-0.5 truncate text-sm text-primary ${mono ? 'font-mono' : 'font-medium'}`}>{value || '—'}</dd>
      </div>)}</dl>
    </Card>
    <Card title="Classificação no Reports" description="Nome e contexto usados nos relatórios.">
      {data.client.role === 'viewer' ? <p className="text-sm text-tertiary">Seu acesso permite consultar a campanha, sem editar.</p> : <form className="flex flex-col gap-5" onSubmit={submit}>
        {error && <Alert>{error}</Alert>}
        {!campaign.account_id && <div className="grid gap-4 sm:grid-cols-2">
          <ReportsNativeSelect label="Conta de mídia" hint="Opcional. Conecta a campanha manual." value={form.account_id || ''} onChange={event => setForm({...form, account_id: event.target.value})}>
            <option value="">Manter manual</option>{data.accounts.filter(item => item.account_kind === 'advertiser' && item.customer_id === campaign.customer_id).map(item => <option value={item.id} key={item.id}>{item.name}</option>)}
          </ReportsNativeSelect>
          {form.account_id && <ReportsFieldInput label="ID da campanha na plataforma" required className="font-mono" value={form.external_id || ''} onChange={event => setForm({...form, external_id: event.target.value})}/>}
        </div>}
        <ReportsFieldInput label="Nome" required maxLength={240} value={form.name || ''} onChange={event => setForm({...form, name: event.target.value})}/>
        <div className="grid gap-4 sm:grid-cols-2">
          <ReportsFieldInput label="Objetivo" maxLength={160} value={form.objective || ''} onChange={event => setForm({...form, objective: event.target.value})} placeholder="Ex.: leads"/>
          <ReportsFieldInput label="Tipo de canal" maxLength={64} value={form.channel_type || ''} onChange={event => setForm({...form, channel_type: event.target.value})} placeholder="Ex.: pesquisa, social"/>
        </div>
        <div className="flex items-center justify-end gap-3 border-t border-secondary pt-4">
          {notice && <span role="status" className="text-sm text-success-primary">{notice}</span>}
          <Button type="submit" size="md" color="primary" isDisabled={busy} isLoading={busy}>Salvar alterações</Button>
        </div>
      </form>}
    </Card>
  </div>;
}
