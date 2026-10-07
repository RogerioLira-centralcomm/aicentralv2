import {ReportsActionButton} from './ReportsActionButton.jsx';
import {CaduTabs} from '../cadu-design-system/components/CaduTabs.jsx';
import React, {useCallback, useEffect, useState} from 'react';
import {AlertCircle, AlertTriangle, ArrowDown, ArrowUp, CheckCircle, Download01, InfoCircle, SearchLg, XClose} from '@untitledui/icons';
import {Empty, integer, json, reportUrl} from './reportsCommon.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {Table} from '../cadu-design-system/untitled-kit/table.tsx';
import './alerts-center.css';
import {apiUrl, useApi} from './shell/useApi.js';
import {useReportsContext} from './shell/context.js';
import {customerParam} from './shell/customerScope.js';

const SEVERITY = {high: 'Alta', medium: 'Média', low: 'Baixa'};
const STATUS = {open: 'Ativo', acknowledged: 'Reconhecido', investigating: 'Em investigação', silenced: 'Silenciado', resolved: 'Resolvido'};
const CHANNEL = {site: 'Site', journey: 'Jornada', google_ads: 'Google Ads', meta: 'Meta Ads', reports: 'Relatórios'};
const SEVERITY_COLOR = {high: 'error', medium: 'warning', low: 'brand'};
const STATUS_COLOR = {open: 'error', acknowledged: 'orange', investigating: 'warning', silenced: 'gray', resolved: 'success'};
const HEALTH = {ok: ['Saudável', 'success'], warning: ['Atenção', 'warning'], down: ['Fora do ar', 'error'], unknown: ['Sem leitura', 'gray']};
const dash = '—';
const when = value => value ? new Date(value).toLocaleString('pt-BR', {timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short'}) : dash;
const ago = value => {
  if (!value) return dash;
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60000));
  if (minutes < 1) return 'agora';
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `há ${hours} ${hours === 1 ? 'hora' : 'horas'}`;
  const days = Math.round(hours / 24);
  return `há ${days} ${days === 1 ? 'dia' : 'dias'}`;
};
const money = (micros, currency) => micros == null ? dash : new Intl.NumberFormat('pt-BR', {style: 'currency', currency: currency || 'BRL'}).format(micros / 1_000_000);
const percent = value => `${Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;
const evidenceValue = item => item.value == null ? dash : item.unit === 'percent' ? percent(item.value)
  : item.unit === 'count' ? integer(item.value) : item.unit === 'money' ? money(item.value, item.currency) : String(item.value);
const impactValue = impact => !impact || impact.value == null ? dash : impact.unit === 'percent' ? percent(impact.value).replace(/^-/, '−')
  : impact.unit === 'count' ? integer(impact.value) : String(impact.value);
const initials = name => name ? name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0].toUpperCase()).join('') : '';
const EVENT_LABEL = {opened: 'Alerta aberto', acknowledged: 'Reconhecido', investigating: 'Em investigação', assigned: 'Assumido', unassigned: 'Liberado', silenced: 'Silenciado',
  unsilenced: 'Silêncio removido', resolved: 'Resolvido', notified: 'E-mail enviado', notification_skipped: 'E-mail não enviado', notification_failed: 'Falha ao enviar e-mail'};
const SKIP_REASON = {disabled: 'envio de e-mail desativado', cooldown: 'já avisado nas últimas 24 h', low_severity: 'prioridade baixa', no_recipients: 'sem destinatários',
  flow_monitor: 'a queda já é avisada pelo monitor de páginas'};
const csrfHeaders = data => ({'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf});

function SeverityIcon({severity, kind}) {
  const Icon = kind === 'opportunity' ? InfoCircle : severity === 'high' ? AlertCircle : AlertTriangle;
  return <span className={`al-sev-icon is-${severity}`} aria-hidden="true"><Icon width={18} height={18}/></span>;
}

function StatusBadge({alert}) {
  return <BadgeWithDot size="sm" color={STATUS_COLOR[alert.status]}>{STATUS[alert.status]}</BadgeWithDot>;
}

function SeverityBadge({severity}) {
  return <Badge size="sm" color={SEVERITY_COLOR[severity]}>{SEVERITY[severity]}</Badge>;
}

function Delta({value, unit = '', worseWhenUp = false, suffix}) {
  if (value == null) return <span className="al-delta is-none">{dash}</span>;
  if (value === 0) return <span className="al-delta is-neutral">sem variação{suffix ? ` ${suffix}` : ''}</span>;
  const bad = worseWhenUp ? value > 0 : value < 0;
  const Arrow = value > 0 ? ArrowUp : ArrowDown;
  return <span className={`al-delta ${bad ? 'is-bad' : 'is-good'}`}><Arrow width={12} height={12} aria-hidden="true"/>{Math.abs(value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}{unit}{suffix && <em>{suffix}</em>}</span>;
}

function Kpis({summary}) {
  if (!summary) return <div className="al-kpis" aria-busy="true"><div className="al-kpi is-loading"/></div>;
  return <section className="al-kpis" aria-label="Resumo dos alertas">
    <div className="al-kpi"><span className="al-kpi__icon is-high"><AlertCircle width={20} height={20} aria-hidden="true"/></span>
      <div><b>{integer(summary.active)}</b><span>Ocorrências ativas</span><Delta value={summary.opened_delta} worseWhenUp suffix="vs. período anterior"/></div></div>
    <div className="al-kpi"><span className="al-kpi__icon is-medium"><AlertTriangle width={20} height={20} aria-hidden="true"/></span>
      <div><b>{integer(summary.investigating)}</b><span>Em investigação</span></div></div>
    <div className="al-kpi"><span className="al-kpi__icon is-ok"><CheckCircle width={20} height={20} aria-hidden="true"/></span>
      <div><b>{integer(summary.resolved_today)}</b><span>Resolvidas hoje</span><Delta value={summary.resolved_today_change} unit="%" suffix="vs. ontem"/></div></div>
    <div className="al-kpi"><span className="al-kpi__icon is-info"><InfoCircle width={20} height={20} aria-hidden="true"/></span>
      <div><b>{summary.uptime == null ? dash : percent(summary.uptime)}</b><span>Uptime dos sites</span>{summary.uptime_change != null && <Delta value={summary.uptime_change} unit=" pt"/>}</div></div>
    {summary.estimated_impact != null && <div className="al-kpi"><span className="al-kpi__icon is-info"><InfoCircle width={20} height={20} aria-hidden="true"/></span>
      <div><b>{money(summary.estimated_impact.micros, summary.estimated_impact.currency)}</b><span>Impacto estimado</span><small>últimos 7 dias</small></div></div>}
  </section>;
}

function History({alertId, client}) {
  const [events, setEvents] = useState(null);
  useEffect(() => {
    let active = true;
    json(`/connect/api/v2/reports/alerts/${alertId}/events`).then(body => { if (active) setEvents(body.events); }).catch(() => { if (active) setEvents([]); });
    return () => { active = false; };
  }, [alertId, client]);
  if (!events) return <p className="alerts-note" role="status">Carregando histórico…</p>;
  return <ol className="alerts-history" aria-label="Histórico do alerta">{events.map((item, index) => <li key={index}>
    <b>{EVENT_LABEL[item.kind] || item.kind}</b>{item.kind === 'resolved' ? ` · ${item.detail?.resolution === 'manual' ? 'manualmente' : 'automaticamente'}` : ''}
    {item.kind === 'notification_skipped' && item.detail?.reason ? ` · ${SKIP_REASON[item.detail.reason] || item.detail.reason}` : ''}
    {item.kind === 'silenced' && item.detail?.permanent ? ' · sem prazo' : item.kind === 'silenced' && item.detail?.hours ? ` · por ${item.detail.hours === 168 ? '7 dias' : `${item.detail.hours} h`}` : ''}
    {item.actor_name ? ` · ${item.actor_name}` : ''}<small>{when(item.created_at)}</small></li>)}</ol>;
}

const PANEL_TABS = [{id: 'overview', label: 'Visão geral'}, {id: 'evidence', label: 'Evidências'}, {id: 'causes', label: 'Possíveis causas'},
  {id: 'recommendations', label: 'Recomendações'}, {id: 'history', label: 'Histórico'}];

function TextList({items, empty}) {
  if (!items?.length) return <p className="alerts-note">{empty}</p>;
  return <ul className="al-list">{items.map((item, index) => <li key={index}>{typeof item === 'string' ? item : item.text || item.title}</li>)}</ul>;
}

function AlertPanel({alert, userId, choices, busy, onAct, onClose, client}) {
  const [tab, setTab] = useState('overview');
  const [hours, setHours] = useState(String(choices[1] || choices[0]));
  useEffect(() => setTab('overview'), [alert.id]);
  const live = alert.status !== 'resolved';
  const mine = alert.assigned_to === userId;
  return <aside className="al-panel" aria-label={`Detalhes: ${alert.title}`}>
    <header className="al-panel__head">
      <SeverityIcon severity={alert.severity} kind={alert.kind}/>
      <div><h2>{alert.title}</h2><p>{alert.page_path || alert.site_label || CHANNEL[alert.channel]}</p>
        <span className="al-panel__badges"><SeverityBadge severity={alert.severity}/><StatusBadge alert={alert}/></span></div>
      <ReportsActionButton color="tertiary" size="sm" aria-label="Fechar detalhes" onClick={onClose}><XClose width={16} height={16} aria-hidden="true"/></ReportsActionButton>
    </header>
    <CaduTabs label="Seções do alerta" value={tab} onChange={setTab} items={PANEL_TABS}/>
    <div className="al-panel__body">
      {tab === 'overview' && <>
        <p>{alert.summary}</p>
        {alert.evidence.length > 0 && <dl className="al-cards">{alert.evidence.slice(0, 3).map((item, index) => <div key={index}><dt>{item.label}</dt><dd>{evidenceValue(item)}</dd></div>)}</dl>}
        <p className="alerts-meta">Detectado em {when(alert.first_seen_at)} · {integer(alert.occurrences)} {alert.occurrences === 1 ? 'verificação' : 'verificações'}
          {alert.site_label ? ` · ${alert.site_label}` : ''}{alert.assigned_name ? ` · responsável: ${alert.assigned_name}` : ' · sem responsável'}
          {alert.status === 'silenced' ? ` · ${alert.silenced_until ? `silenciado até ${when(alert.silenced_until)}` : 'silenciado sem prazo'}` : ''}
          {alert.status === 'resolved' ? ` · resolvido ${alert.resolution === 'auto' ? 'automaticamente' : 'manualmente'} em ${when(alert.resolved_at)}` : ''}</p>
      </>}
      {tab === 'evidence' && <dl className="alerts-evidence">{alert.evidence.map((item, index) => <div key={index}><dt>{item.label}</dt><dd>{evidenceValue(item)}</dd></div>)}</dl>}
      {tab === 'causes' && <TextList items={alert.causes} empty="Ainda não há causas calculadas para este alerta. Elas aparecem quando o sistema cruza a ocorrência com mudanças no mesmo período."/>}
      {tab === 'recommendations' && <TextList items={alert.recommendations} empty="Este alerta ainda não tem recomendações."/>}
      {tab === 'history' && <History alertId={alert.id} client={client}/>}
    </div>
    {live && <div className="al-panel__tools">
      <ReportsActionButton color="secondary" size="sm" disabled={busy} onClick={() => onAct([alert.id], 'assign', {assign: !mine})}>{mine ? 'Liberar' : 'Assumir'}</ReportsActionButton>
      {alert.status !== 'silenced' ? <span className="alerts-snooze"><ReportsNativeSelect value={hours} onChange={event => setHours(event.target.value)} aria-label="Duração do silêncio">
        {choices.map(item => <option key={item} value={item}>{item === 168 ? '7 dias' : item === 24 ? '24 horas' : `${item} hora`}</option>)}<option value="permanent">Sem prazo</option></ReportsNativeSelect>
        <ReportsActionButton color="secondary" size="sm" disabled={busy} onClick={() => onAct([alert.id], 'silence', hours === 'permanent' ? {permanent: true} : {hours: Number(hours)})}>Silenciar</ReportsActionButton></span>
        : <ReportsActionButton color="secondary" size="sm" disabled={busy} onClick={() => onAct([alert.id], 'unsilence', {})}>Remover silêncio</ReportsActionButton>}
    </div>}
    <footer className="al-panel__foot">
      {alert.page_path
        ? <ReportsActionButton color="secondary" href={reportUrl('pages', {site_id: alert.site_id, path: alert.page_path})}>Ver em Site &amp; Jornada</ReportsActionButton>
        : alert.site_id && <ReportsActionButton color="secondary" href={reportUrl('supertag', {scope_site: alert.site_id})}>Ver coleta do site</ReportsActionButton>}
      {live && alert.status !== 'investigating' && alert.status !== 'silenced' && <ReportsActionButton color="secondary" disabled={busy} onClick={() => onAct([alert.id], alert.status === 'open' || alert.status === 'acknowledged' ? 'investigate' : 'acknowledge', {})}>Em investigação</ReportsActionButton>}
      {live && <ReportsActionButton color="primary" disabled={busy} onClick={() => onAct([alert.id], 'resolve', {})}>Marcar como resolvido</ReportsActionButton>}
    </footer>
  </aside>;
}

const GADS_SEVERITY = {high: ['Alta', 'error'], medium: ['Média', 'warning']};

/** Google Ads findings computed from the data the script sends; each one opens the object in Mídia → Google Ads. */
function GoogleAdsAlerts() {
  const {period} = useReportsContext();
  const [state] = useApi(apiUrl('/google-ads/summary', {start_date: period.start, end_date: period.end}));
  const items = (state.body?.recommendations || []).filter(item => item.severity !== 'low');
  if (!state.body?.ready || !items.length) return null;
  const href = link => reportUrl('media/google-ads', {view: link?.tab || 'overview', filter: link?.filter || ''});
  return <article className="reports-panel alerts-gads"><div className="reports-panel-head"><h2>Google Ads</h2><span>{items.length} {items.length === 1 ? 'ação' : 'ações'} de prioridade alta ou média</span></div>
    <ul className="rs-list">{items.slice(0, 6).map(item => <li key={item.id}>
      <span className={`rs-badge is-${GADS_SEVERITY[item.severity][1]}`}>{GADS_SEVERITY[item.severity][0]}</span>
      <span className="rs-list__copy"><strong>{item.title}: {item.object.label}</strong><small>{item.object.campaign ? `${item.object.campaign} · ` : ''}{item.summary}</small></span>
      <ReportsActionButton color="link-color" size="sm" className="reports-inline-link" href={href(item.link)}>Abrir</ReportsActionButton>
    </li>)}</ul>
    {items.length > 6 && <ReportsActionButton color="link-color" size="sm" className="reports-inline-link" href={reportUrl('media/google-ads')}>Ver as {items.length} ações</ReportsActionButton>}
  </article>;
}

const STATUS_FILTERS = [['active', 'Todos os status'], ['investigating', 'Em investigação'], ['resolved', 'Resolvidos']];

/** One list of alerts (occurrences or opportunities) with search, filters, paging, bulk actions and the detail panel. */
function AlertsList({kind, data, onChanged}) {
  const client = data.client.client_id;
  const customer_id = customerParam();
  const [filters, setFilters] = useState({q: '', channel: '', severity: '', status: 'active'});
  const [search, setSearch] = useState('');
  const [state, setState] = useState({loading: true, error: '', body: null});
  const [selected, setSelected] = useState(() => new Set());
  const [openId, setOpenId] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const query = {kind, customer_id, q: filters.q, channel: filters.channel, severity: filters.severity, status: filters.status};
  const load = useCallback(() => json(apiUrl('/alerts', {...query, per_page: 200}))
    .then(body => setState({loading: false, error: '', body})).catch(failure => setState({loading: false, error: failure.message, body: null})),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [client, kind, customer_id, filters]);
  useEffect(() => { setState(current => ({...current, loading: true})); load(); }, [load]);
  useEffect(() => { const timer = setTimeout(() => setFilters(current => current.q === search.trim() ? current : {...current, q: search.trim()}), 300); return () => clearTimeout(timer); }, [search]);
  useEffect(() => { setSelected(new Set()); }, [kind, filters]);
  const change = patch => setFilters(current => ({...current, ...patch}));
  const body = state.body;
  const rows = body?.alerts || [];
  const open = rows.find(item => item.id === openId);
  const act = async (ids, action, extra) => {
    setBusy(true); setNotice('');
    try {
      if (ids.length === 1) {
        await json(`/connect/api/v2/reports/alerts/${ids[0]}/${action}`, {method: 'POST', headers: csrfHeaders(data), body: JSON.stringify({...extra})});
      } else {
        const result = await json('/connect/api/v2/reports/alerts/bulk', {method: 'POST', headers: csrfHeaders(data), body: JSON.stringify({ids, action})});
        setNotice(`${result.done} ${result.done === 1 ? 'alerta atualizado' : 'alertas atualizados'}${result.skipped ? `, ${result.skipped} ignorados (já resolvidos ou fora deste estado)` : ''}.`);
        setSelected(new Set());
      }
      await load(); onChanged();
    } catch (failure) { setState(current => ({...current, error: failure.message})); }
    setBusy(false);
  };
  const exportUrl = apiUrl('/alerts/export', query);
  const noun = kind === 'opportunity' ? 'oportunidade' : 'ocorrência';
  return <div className={`al-main${open ? ' has-panel' : ''}`}>
    <section className="al-list-wrap" aria-label={kind === 'opportunity' ? 'Oportunidades' : 'Ocorrências'}>
      <div className="al-toolbar">
        <CaduInput className="al-search" size="sm" type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Buscar alertas…" aria-label="Buscar alertas"
          leading={<SearchLg width={16} height={16} aria-hidden="true"/>}/>
        <ReportsNativeSelect value={filters.channel} onChange={event => change({channel: event.target.value})} aria-label="Canal"><option value="">Todos os canais</option>
          {Object.entries(CHANNEL).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</ReportsNativeSelect>
        <ReportsNativeSelect value={filters.severity} onChange={event => change({severity: event.target.value})} aria-label="Severidade"><option value="">Todas as severidades</option>
          {Object.entries(SEVERITY).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</ReportsNativeSelect>
        <ReportsNativeSelect value={filters.status} onChange={event => change({status: event.target.value})} aria-label="Status">
          {STATUS_FILTERS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</ReportsNativeSelect>
        <ReportsActionButton color="secondary" size="sm" href={exportUrl}><Download01 width={16} height={16} aria-hidden="true"/> Exportar</ReportsActionButton>
      </div>
      {selected.size > 0 && <div className="al-bulk" role="region" aria-label="Ações em lote"><b>{selected.size} {selected.size === 1 ? 'selecionado' : 'selecionados'}</b>
        <ReportsActionButton color="secondary" size="sm" disabled={busy} onClick={() => act([...selected], 'acknowledge', {})}>Reconhecer</ReportsActionButton>
        <ReportsActionButton color="secondary" size="sm" disabled={busy} onClick={() => act([...selected], 'investigate', {})}>Em investigação</ReportsActionButton>
        <ReportsActionButton color="primary" size="sm" disabled={busy} onClick={() => act([...selected], 'resolve', {})}>Marcar como resolvido</ReportsActionButton></div>}
      {notice && <p className="alerts-note" role="status">{notice}</p>}
      {state.error && <div className="reports-error" role="alert">{state.error}</div>}
      {state.loading && !body && <div className="reports-loading" role="status">Carregando alertas…</div>}
      {body && !rows.length && <Empty message={filters.q || filters.channel || filters.severity || filters.status !== 'active'
        ? `Nenhuma ${noun} com estes filtros.` : kind === 'opportunity' ? 'Nenhuma oportunidade no momento.' : 'Nenhuma ocorrência ativa. O monitor confirma cada problema antes de avisar.'}/>}
      {rows.length > 0 && <div className="al-table-wrap">
        <Table aria-label={noun === 'oportunidade' ? 'Oportunidades' : 'Ocorrências'} size="sm" selectionMode="multiple" selectionBehavior="toggle" selectedKeys={selected}
          disabledKeys={rows.filter(item => item.status === 'resolved').map(item => item.id)}
          onSelectionChange={keys => setSelected(keys === 'all' ? new Set(rows.filter(item => item.status !== 'resolved').map(item => item.id)) : new Set(keys))}
          onRowAction={key => setOpenId(current => current === key ? '' : String(key))}>
          <Table.Header>
            <Table.Head id="alert" isRowHeader label="Alerta"/><Table.Head id="channel" label="Canal"/><Table.Head id="severity" label="Severidade"/>
            <Table.Head id="impact" label="Impacto"/><Table.Head id="last" label="Última ocorrência"/><Table.Head id="status" label="Status"/><Table.Head id="owner" label="Responsável"/>
          </Table.Header>
          <Table.Body>{rows.map(alert => <Table.Row key={alert.id} id={alert.id} className={openId === alert.id ? 'al-row is-open' : 'al-row'}>
            <Table.Cell><span className="al-title"><SeverityIcon severity={alert.severity} kind={alert.kind}/><span><b>{alert.title}</b><small>{alert.page_path || alert.summary}</small></span></span></Table.Cell>
            <Table.Cell>{CHANNEL[alert.channel]}</Table.Cell>
            <Table.Cell><SeverityBadge severity={alert.severity}/></Table.Cell>
            <Table.Cell className="al-impact">{alert.impact ? <><b className={alert.impact.unit === 'percent' && Number(alert.impact.value) < 0 ? 'is-bad' : ''}>{impactValue(alert.impact)}</b><small>{alert.impact.label}</small></> : dash}</Table.Cell>
            <Table.Cell className="al-when">{ago(alert.last_seen_at)}</Table.Cell>
            <Table.Cell><StatusBadge alert={alert}/></Table.Cell>
            <Table.Cell>{alert.assigned_name ? <span className="al-owner"><i aria-hidden="true">{initials(alert.assigned_name)}</i>{alert.assigned_name.split(' ')[0]}</span> : dash}</Table.Cell>
          </Table.Row>)}</Table.Body>
        </Table></div>}
      {body && rows.length > 0 && <p className="alerts-note">{body.total > rows.length ? `Mostrando os ${integer(rows.length)} mais recentes de ${integer(body.total)}. Use os filtros para refinar.` : `${integer(body.total)} ${body.total === 1 ? noun : noun === 'ocorrência' ? 'ocorrências' : 'oportunidades'}`}</p>}
      {kind === 'incident' && filters.status === 'active' && <GoogleAdsAlerts/>}
    </section>
    {open && <AlertPanel alert={open} userId={body.user_id} choices={body.silence_choices} busy={busy} onAct={act} onClose={() => setOpenId('')} client={client}/>}
  </div>;
}

function MonitorsList({client}) {
  const [state] = useApi(apiUrl('/alerts/monitors'));
  const body = state.body;
  return <div className="al-monitors">
    {state.error && <div className="reports-error" role="alert">{state.error}</div>}
    {state.loading && !body && <div className="reports-loading" role="status">Carregando monitores…</div>}
    {body && !body.monitors.length && <Empty message="Nenhum monitor ativo. Publique um fluxo com monitoramento de páginas ou instale a Super Tag em um site."/>}
    {body?.monitors.length > 0 && <div className="al-table-wrap">
      <Table aria-label="Monitores" size="sm">
        <Table.Header><Table.Head id="monitor" isRowHeader label="Monitor"/><Table.Head id="type" label="Tipo"/><Table.Head id="health" label="Situação"/>
          <Table.Head id="last" label="Última leitura"/><Table.Head id="detail" label="Detalhe"/></Table.Header>
        <Table.Body>{body.monitors.map(item => <Table.Row key={`${item.kind}-${item.id}`} id={`${item.kind}-${item.id}`}>
          <Table.Cell><span className="al-title"><span><b>{item.name}</b><small>{item.target}</small></span></span></Table.Cell>
          <Table.Cell>{item.kind === 'url' ? 'Páginas do fluxo' : 'Coleta da Super Tag'}</Table.Cell>
          <Table.Cell><BadgeWithDot size="sm" color={HEALTH[item.health][1]}>{HEALTH[item.health][0]}</BadgeWithDot></Table.Cell>
          <Table.Cell className="al-when">{ago(item.last_checked_at)}</Table.Cell>
          <Table.Cell>{item.kind === 'url' ? `verifica a cada ${item.every_minutes} min${item.down_since ? ` · fora do ar desde ${when(item.down_since)}` : ''}` : `${integer(item.events_24h)} eventos em 24 h`}</Table.Cell>
        </Table.Row>)}</Table.Body>
      </Table></div>}
    {body && <article className="reports-panel alerts-rules"><div className="reports-panel-head"><h2>Quando um alerta abre</h2><span>{body.emails_enabled ? 'E-mail ativado neste ambiente' : 'E-mail desativado neste ambiente'}</span></div>
      <ul>{body.rules.map(rule => <li key={rule.rule}><b>{rule.title}.</b> {rule.when}</li>)}</ul>
      <p className="alerts-note">Um alerta só abre depois da confirmação da regra, é atualizado em vez de duplicado, fecha sozinho quando o problema acaba e pode ser silenciado. Os alertas não alteram nada no seu site nem no Google Ads.</p></article>}
  </div>;
}

export function AlertsCenter({data}) {
  const client = data.client.client_id;
  const [tab, setTab] = useState('incident');
  const [summary, setSummary] = useState(null);
  const loadSummary = useCallback(() => json(apiUrl('/alerts/summary')).then(setSummary).catch(() => setSummary(null)), [client]);
  useEffect(() => { loadSummary(); }, [loadSummary]);
  const tabs = summary?.tabs;
  return <div className="alerts-center">
    <CaduTabs label="Central de alertas" value={tab} onChange={setTab} items={[
      {id: 'incident', label: 'Ocorrências', count: tabs?.incidents ?? ''}, {id: 'monitors', label: 'Monitores', count: tabs?.monitors ?? ''},
      {id: 'opportunity', label: 'Oportunidades', count: tabs?.opportunities ?? ''}]}/>
    <Kpis summary={summary}/>
    {tab === 'monitors' ? <MonitorsList client={client}/> : <AlertsList key={tab} kind={tab} data={data} onChanged={loadSummary}/>}
  </div>;
}
