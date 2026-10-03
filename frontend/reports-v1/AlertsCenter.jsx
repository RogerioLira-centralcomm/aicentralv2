import {ReportsActionButton} from './ReportsActionButton.jsx';
import {CaduTabs} from '../cadu-design-system/components/CaduTabs.jsx';
import React, {useCallback, useEffect, useState} from 'react';
import {Empty, integer, json, reportUrl} from './reportsCommon.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import './alerts-center.css';
import {apiUrl, useApi} from './shell/useApi.js';
import {useReportsContext} from './shell/context.js';

const SEVERITY = {high: 'Prioridade alta', medium: 'Prioridade média', low: 'Prioridade baixa'};
const dash = '—';
const when = value => value ? new Date(value).toLocaleString('pt-BR', {timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short'}) : dash;
const money = (micros, currency) => micros == null ? dash : new Intl.NumberFormat('pt-BR', {style: 'currency', currency: currency || 'BRL'}).format(micros / 1_000_000);
const evidenceValue = item => item.value == null ? dash : item.unit === 'percent' ? `${Number(item.value).toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`
  : item.unit === 'count' ? integer(item.value) : item.unit === 'money' ? money(item.value, item.currency) : String(item.value);
const EVENT_LABEL = {opened: 'Alerta aberto', acknowledged: 'Reconhecido', assigned: 'Assumido', unassigned: 'Liberado', silenced: 'Silenciado', unsilenced: 'Silêncio removido',
  resolved: 'Resolvido automaticamente', notified: 'E-mail enviado', notification_skipped: 'E-mail não enviado', notification_failed: 'Falha ao enviar e-mail'};
const SKIP_REASON = {disabled: 'envio de e-mail desativado', cooldown: 'já avisado nas últimas 24 h', low_severity: 'prioridade baixa', no_recipients: 'sem destinatários'};

function statusText(alert) {
  if (alert.status === 'resolved') return `Resolvido ${alert.resolution === 'auto' ? 'automaticamente' : ''} em ${when(alert.resolved_at)}`;
  if (alert.status === 'silenced') return alert.silenced_until ? `Silenciado até ${when(alert.silenced_until)}` : 'Silenciado sem prazo';
  if (alert.status === 'acknowledged') return `Reconhecido em ${when(alert.acknowledged_at)}`;
  return 'Aberto';
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
    <b>{EVENT_LABEL[item.kind] || item.kind}</b>{item.kind === 'notification_skipped' && item.detail?.reason ? ` · ${SKIP_REASON[item.detail.reason] || item.detail.reason}` : ''}
    {item.kind === 'silenced' && item.detail?.permanent ? ' · sem prazo' : item.kind === 'silenced' && item.detail?.hours ? ` · por ${item.detail.hours === 168 ? '7 dias' : `${item.detail.hours} h`}` : ''}
    {item.actor_name ? ` · ${item.actor_name}` : ''}<small>{when(item.created_at)}</small></li>)}</ol>;
}

function AlertCard({alert, userId, choices, busy, onAct, client}) {
  const [hours, setHours] = useState(String(choices[1] || choices[0]));
  const [history, setHistory] = useState(false);
  const live = alert.status !== 'resolved';
  const mine = alert.assigned_to === userId;
  return <li className={`alerts-card is-${alert.severity}${live ? '' : ' is-resolved'}`}>
    <header><span className="alerts-badge">{SEVERITY[alert.severity]}</span><h3>{alert.title}</h3><span className="alerts-status">{statusText(alert)}</span></header>
    <p>{alert.summary}</p>
    <dl className="alerts-evidence">{alert.evidence.map((item, index) => <div key={index}><dt>{item.label}</dt><dd>{evidenceValue(item)}</dd></div>)}</dl>
    <p className="alerts-meta">{alert.site_label} · {alert.allowed_host} · visto pela primeira vez em {when(alert.first_seen_at)} · {integer(alert.occurrences)} {alert.occurrences === 1 ? 'verificação' : 'verificações'}
      {alert.assigned_name ? ` · responsável: ${alert.assigned_name}` : ' · sem responsável'}</p>
    <div className="alerts-actions">
      {live && alert.status === 'open' && <ReportsActionButton color="secondary" size="sm" disabled={busy} onClick={() => onAct(alert, 'acknowledge', {})}>Reconhecer</ReportsActionButton>}
      {live && <ReportsActionButton color="secondary" size="sm" disabled={busy} onClick={() => onAct(alert, 'assign', {assign: !mine})}>{mine ? 'Liberar' : 'Assumir'}</ReportsActionButton>}
      {live && alert.status !== 'silenced' && <span className="alerts-snooze"><ReportsNativeSelect value={hours} onChange={event => setHours(event.target.value)} aria-label="Duração do silêncio">
        {choices.map(item => <option key={item} value={item}>{item === 168 ? '7 dias' : item === 24 ? '24 horas' : `${item} hora`}</option>)}<option value="permanent">Sem prazo</option></ReportsNativeSelect>
        <ReportsActionButton color="secondary" size="sm" disabled={busy} onClick={() => onAct(alert, 'silence', hours === 'permanent' ? {permanent: true} : {hours: Number(hours)})}>Silenciar</ReportsActionButton></span>}
      {live && alert.status === 'silenced' && <ReportsActionButton color="secondary" size="sm" disabled={busy} onClick={() => onAct(alert, 'unsilence', {})}>Remover silêncio</ReportsActionButton>}
      {alert.page_path && <ReportsActionButton color="link-color" size="sm" className="reports-inline-link" href={reportUrl('pages', {site_id: alert.site_id, path: alert.page_path})}>Ver página</ReportsActionButton>}
      {alert.page_path && <ReportsActionButton color="link-color" size="sm" className="reports-inline-link" href={reportUrl('journey/navigation')}>Ver navegação</ReportsActionButton>}
      <ReportsActionButton color="link-color" size="sm" className="reports-inline-link" href={reportUrl('supertag', {scope_site: alert.site_id})}>Ver coleta do site</ReportsActionButton>
      <ReportsActionButton color="link-color" size="sm" className="alerts-link" aria-expanded={history} onClick={() => setHistory(value => !value)}>{history ? 'Ocultar histórico' : 'Histórico'}</ReportsActionButton>
    </div>
    {history && <History alertId={alert.id} client={client}/>}
  </li>;
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

export function AlertsCenter({data}) {
  const client = data.client.client_id;
  const [status, setStatus] = useState('active');
  const [state, setState] = useState({loading: true, error: '', body: null});
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => json(`/connect/api/v2/reports/alerts?status=${status}`)
    .then(body => setState({loading: false, error: '', body})).catch(failure => setState({loading: false, error: failure.message, body: null})), [client, status]);
  useEffect(() => { setState(current => ({...current, loading: true})); load(); }, [load]);
  const act = async (alert, action, body) => {
    setBusy(true);
    try {
      await json(`/connect/api/v2/reports/alerts/${alert.id}/${action}`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({...body})});
      await load();
    } catch (failure) { setState(current => ({...current, error: failure.message})); }
    setBusy(false);
  };
  const body = state.body;
  return <div className="alerts-center">
    <CaduTabs label="Estado dos alertas" value={status} onChange={setStatus} items={[{id: 'active', label: 'Ativos'}, {id: 'resolved', label: 'Resolvidos'}]}/>
    {state.error && <div className="reports-error" role="alert">{state.error}</div>}
    {status === 'active' && <GoogleAdsAlerts/>}
    {state.loading && !body && <div className="reports-loading" role="status">Carregando alertas…</div>}
    {body && !body.alerts.length && <Empty message={status === 'active' ? 'Nenhum alerta ativo. O monitor confirma cada problema antes de avisar.' : 'Nenhum alerta resolvido ainda.'}/>}
    {body?.alerts.length > 0 && <ul className="alerts-list">{body.alerts.map(alert => <AlertCard key={alert.id} alert={alert} userId={body.user_id} choices={body.silence_choices} busy={busy} onAct={act} client={client}/>)}</ul>}
    {body && <article className="reports-panel alerts-rules"><div className="reports-panel-head"><h2>Quando um alerta abre</h2><span>{body.emails_enabled ? 'E-mail ativado neste ambiente' : 'E-mail desativado neste ambiente'}</span></div>
      <ul>{body.rules.map(rule => <li key={rule.rule}><b>{rule.title}.</b> {rule.when}</li>)}</ul>
      <p className="alerts-note">Um alerta só abre depois da confirmação da regra, é atualizado em vez de duplicado, fecha sozinho quando o problema acaba e pode ser silenciado. Os alertas não alteram nada no seu site nem no Google Ads.</p></article>}
  </div>;
}
