import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Bell01, Clock, ReverseLeft, XClose, Zap} from '@untitledui/icons';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {ReportsConfirmDialog} from '../../ReportsConfirmDialog.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {friendlyAgo, friendlyDateTime} from '../../friendlyDates.js';
import {apiUrl} from '../../shell/useApi.js';
import {json} from '../../reportsCommon.jsx';
import {EmptyState, ErrorState, LoadingState, Section} from '../../shell/primitives.jsx';
import './google-ads-actions.css';

const OPEN = ['approved', 'sent'];
const STATE = {
  approved: ['Agendada', 'low'], sent: ['Aplicando agora', 'warning'], applied: ['Aplicada', 'success'], failed: ['Falhou', 'error'],
  skipped: ['Não aplicada', 'gray'], expired: ['Venceu', 'gray'], cancelled: ['Cancelada', 'gray'],
};
const NOTIFY_KEY = 'cadu.gads.actions.notify';
const badge = ([label, tone]) => <span className={`rs-badge is-${tone}`}>{label}</span>;

/** "mm:ss" (or "h h mm min") until a moment; the server clock offset keeps every browser on the same countdown. */
function remaining(target, offset) {
  if (!target) return null;
  const ms = Date.parse(target) - (Date.now() + offset);
  if (ms <= 0) return 'a qualquer momento';
  const total = Math.round(ms / 1000);
  const hours = Math.floor(total / 3600), minutes = Math.floor((total % 3600) / 60), seconds = total % 60;
  return hours ? `${hours} h ${String(minutes).padStart(2, '0')} min` : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export function Countdown({to, offset = 0}) {
  const [, tick] = useState(0);
  useEffect(() => {
    if (!to) return undefined;
    const timer = window.setInterval(() => tick(value => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [to]);
  const text = remaining(to, offset);
  return text ? <time className="gaa-countdown" dateTime={to} title={friendlyDateTime(to)}>{text}</time> : null;
}

function readNotify() {
  try {return localStorage.getItem(NOTIFY_KEY) === '1';} catch {return false;}
}

/**
 * Live state of the Ações queue for the whole Google Ads area: polls while something is waiting, and announces each
 * change the script applied (toast on screen, browser notification when the person turned it on).
 */
export function useGoogleAdsActions(data) {
  const [state, setState] = useState({loading: true, error: '', body: null});
  const [toasts, setToasts] = useState([]);
  const [notify, setNotify] = useState(readNotify);
  const offset = useRef(0);
  const known = useRef(null);
  const notifyRef = useRef(notify);
  notifyRef.current = notify;

  const announce = useCallback((title, detail, tone) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts(current => [...current.slice(-3), {id, title, detail, tone}]);
    window.setTimeout(() => setToasts(current => current.filter(item => item.id !== id)), 9000);
    if (notifyRef.current && typeof Notification !== 'undefined' && Notification.permission === 'granted' && document.visibilityState !== 'visible') {
      try {new Notification(`Google Ads · ${title}`, {body: detail, tag: id});} catch { /* Some browsers only allow notifications from a service worker. */ }
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const body = await json(apiUrl('/google-ads/actions'));
      offset.current = body.server_time ? Date.parse(body.server_time) - Date.now() : 0;
      const previous = known.current;
      known.current = new Map(body.actions.map(item => [item.id, item.status]));
      if (previous) {
        body.actions.forEach(item => {
          const before = previous.get(item.id);
          if (!before || before === item.status || !OPEN.includes(before)) return;
          const message = item.result?.message || '';
          if (item.status === 'applied') announce('Mudança aplicada', `${item.label}${message ? ` · ${message}` : ''}`, 'success');
          else if (item.status === 'failed') announce('Mudança falhou', `${item.label} · ${message}`, 'error');
          else if (item.status === 'skipped') announce('Mudança não aplicada', `${item.label} · ${message}`, 'warning');
          else if (item.status === 'expired') announce('Aprovação venceu', item.label, 'warning');
        });
      }
      setState({loading: false, error: '', body});
    } catch (failure) {
      setState(current => ({...current, loading: false, error: failure.message}));
    }
  }, [announce]);

  const waiting = (state.body?.actions || []).filter(item => OPEN.includes(item.status)).length;
  useEffect(() => {load();}, [load, data.client.client_id]);
  // Faster while something waits for the script, so "aplicada" shows up within half a minute of the run.
  useEffect(() => {
    const timer = window.setInterval(() => {if (document.visibilityState === 'visible' || waiting) load();}, waiting ? 30000 : 120000);
    return () => window.clearInterval(timer);
  }, [load, waiting]);

  const post = useCallback(async (path, body = {}) => {
    const result = await json(apiUrl(path), {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf},
      body: JSON.stringify(body)});
    await load();
    return result;
  }, [data.csrf, load]);

  const toggleNotify = useCallback(async () => {
    let next = !notify;
    if (next && typeof Notification !== 'undefined' && Notification.permission === 'default') next = (await Notification.requestPermission()) === 'granted';
    if (next && typeof Notification !== 'undefined' && Notification.permission === 'denied') next = false;
    try {localStorage.setItem(NOTIFY_KEY, next ? '1' : '0');} catch { /* Private windows: the choice lasts for this page only. */ }
    setNotify(next);
  }, [notify]);

  const byRecommendation = useMemo(() => {
    const map = new Map();
    (state.body?.actions || []).forEach(item => {if (item.recommendation_id && !map.has(item.recommendation_id)) map.set(item.recommendation_id, item);});
    return map;
  }, [state.body]);
  const accounts = useMemo(() => new Map((state.body?.accounts || []).map(item => [item.account_id, item])), [state.body]);

  return {state, reload: load, post, toasts, dismiss: id => setToasts(current => current.filter(item => item.id !== id)), announce,
    notify, toggleNotify, waiting, byRecommendation, accounts, offset: offset.current, canEdit: data.client.role !== 'viewer'};
}

export function ActionToasts({actions}) {
  if (!actions.toasts.length) return null;
  return <div className="gaa-toasts" aria-live="polite">{actions.toasts.map(item => <div key={item.id} className={`gaa-toast is-${item.tone}`} role="status">
    <span><strong>{item.title}</strong><small>{item.detail}</small></span>
    <button type="button" aria-label="Fechar aviso" onClick={() => actions.dismiss(item.id)}><XClose size={16} aria-hidden="true"/></button>
  </div>)}</div>;
}

/** When the next run of an account's Ações script is expected, in words that explain the hourly limit. */
function whenText(account, offset) {
  if (!account?.has_key) return {ready: false, text: 'O script de Ações não está instalado nesta conta. A mudança fica na fila por 24 h, esperando a instalação.'};
  if (!account.last_poll_at) return {ready: false, text: 'O script de Ações desta conta ainda não rodou. Agende-o de hora em hora no Google Ads; a mudança fica na fila por 24 h.'};
  if (!account.next_run_at) return {ready: false, text: `O script de Ações não roda desde ${friendlyDateTime(account.last_poll_at)}. Confira a programação no Google Ads.`};
  const writesOff = account.allow_writes === false ? ' A escrita está desligada no script (allowWrites: false): ele só vai simular.' : '';
  return {ready: true, text: <>Aplicada na próxima execução do script de Ações, em <Countdown to={account.next_run_at} offset={offset}/>. O Google Ads só roda scripts de hora em hora; até lá você pode cancelar.{writesOff}</>};
}

/** Approve one or many proposed changes, saying exactly what changes and when. */
export function ApplyDialog({items, actions, onClose}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (!items?.length) return null;
  const account = actions.accounts.get(items[0].account_id);
  const when = whenText(account, actions.offset);
  const confirm = async () => {
    setBusy(true); setError('');
    try {
      const result = await actions.post('/google-ads/actions', {items: items.map(item => ({op: item.op, account_id: item.account_id, target: item.target,
        params: item.params, expect: item.expect, label: item.label, recommendation_id: item.recommendation_id}))});
      const queued = result.created.filter(item => !item.duplicate).length;
      const limited = result.created.filter(item => item.note).length;
      actions.announce(queued === 1 ? 'Mudança agendada' : `${queued} mudanças agendadas`,
        `${limited ? `${limited} ajustada(s) ao teto de variação. ` : ''}Aplicação na próxima execução do script de Ações.`, 'info');
      onClose();
    } catch (failure) {setError(failure.message); setBusy(false);}
  };
  const description = <span className="gaa-dialog">
    {/* The dialog renders the description inside a <p>, so the list is made of spans. */}
    {items.length === 1 ? <strong>{items[0].label}</strong> : <span className="gaa-dialog__list">{items.slice(0, 12).map((item, index) => <span key={index}>{item.label}</span>)}{items.length > 12 && <span>e mais {items.length - 12}…</span>}</span>}
    <span className="gaa-dialog__when"><Clock size={16} aria-hidden="true"/><span>{when.text}</span></span>
    {error && <span className="gaa-dialog__error" role="alert">{error}</span>}
  </span>;
  return <ReportsConfirmDialog open tone="primary" busy={busy} title={items.length === 1 ? 'Aplicar no Google Ads?' : `Aplicar ${items.length} mudanças no Google Ads?`}
    description={description} confirmLabel={when.ready ? 'Aprovar e agendar' : 'Agendar mesmo assim'} onCancel={onClose} onConfirm={confirm}/>;
}

/** Status of the change attached to a recommendation, with what can still be done about it. */
export function ActionStatus({action, actions, onRetry}) {
  const [busy, setBusy] = useState(false);
  const run = async path => {
    setBusy(true);
    try {await actions.post(path);} catch (failure) {actions.announce('Não foi possível', failure.message, 'error');} finally {setBusy(false);}
  };
  const account = actions.accounts.get(action.account_id);
  const message = action.result?.message;
  return <span className="gaa-status">
    {badge(STATE[action.status] || [action.status, 'gray'])}
    {action.status === 'approved' && <small>{account?.next_run_at ? <>aplica em <Countdown to={account.next_run_at} offset={actions.offset}/></> : 'aguardando o script de Ações'}{action.result?.simulated ? ' · última execução só simulou' : ''}</small>}
    {action.status === 'sent' && <small>o script está aplicando</small>}
    {action.status === 'applied' && <small>{friendlyAgo(action.finished_at)}{action.undo_of ? ' · desfazer' : ''}</small>}
    {['failed', 'skipped'].includes(action.status) && message && <small title={message}>{message}</small>}
    {actions.canEdit && action.can_cancel && <ReportsActionButton color="link-gray" size="sm" isDisabled={busy} onClick={() => run(`/google-ads/actions/${action.id}/cancel`)}>Cancelar</ReportsActionButton>}
    {actions.canEdit && action.can_undo && <ReportsActionButton color="link-color" size="sm" isDisabled={busy} onClick={() => run(`/google-ads/actions/${action.id}/undo`)}><ReverseLeft size={14} aria-hidden="true"/>Desfazer</ReportsActionButton>}
    {actions.canEdit && onRetry && ['failed', 'expired', 'cancelled', 'skipped'].includes(action.status) && <ReportsActionButton color="link-color" size="sm" onClick={onRetry}>Tentar de novo</ReportsActionButton>}
  </span>;
}

/** One card per Google Ads account: is the Ações script installed, when did it last check, when is the next run. */
function Agents({body, actions}) {
  return <ul className="gaa-agents">{body.accounts.map(account => {
    const tone = !account.has_key ? 'gray' : !account.last_poll_at ? 'warning' : account.next_run_at ? 'success' : 'error';
    return <li key={account.account_id}>
      <span className={`rs-dot is-${tone}`} aria-hidden="true"/>
      <span className="gaa-agents__name"><strong>{account.name}</strong><small>{account.external_id}</small></span>
      {!account.has_key ? <span className="gaa-agents__info">Script de Ações não instalado
        <ReportsActionButton color="link-color" size="sm" href={reportUrl('data-sources/connect')}>Gerar scripts</ReportsActionButton></span>
        : !account.last_poll_at ? <span className="gaa-agents__info">Chave gerada · aguardando a primeira execução (agende de hora em hora)</span>
          : <span className="gaa-agents__info">
            <span>Última verificação {friendlyAgo(account.last_poll_at)}</span>
            {account.next_run_at ? <span className="gaa-agents__next">Próxima execução em <Countdown to={account.next_run_at} offset={actions.offset}/></span>
              : <span className="ga-strong">Sem execução recente: confira a programação no Google Ads</span>}
          </span>}
      <span className="gaa-agents__flags">
        {account.allow_writes === false && <span className="rs-badge is-warning">Escrita desligada</span>}
        {account.preview && <span className="rs-badge is-warning">Última execução em prévia</span>}
        {account.outdated && <span className="rs-badge is-error">Script desatualizado: gere de novo</span>}
        {account.has_key && <span className="rs-badge">Orçamento ±{account.limits.max_budget_change_pct}% · Lance ±{account.limits.max_cpc_change_pct}%</span>}
      </span>
    </li>;
  })}</ul>;
}

function ActionRow({item, actions}) {
  return <li className={`gaa-row is-${item.status}`}>
    <span className="gaa-row__main"><strong>{item.label}</strong>
      <small>{item.account_name} · {item.origin === 'undo' ? 'desfazer' : item.origin.startsWith('rule:') ? 'recomendação' : 'manual'} · aprovada {friendlyAgo(item.approved_at || item.created_at)}{item.attempts > 1 ? ` · ${item.attempts} entregas` : ''}</small></span>
    <ActionStatus action={item} actions={actions}/>
  </li>;
}

/** Mídia › Google Ads › Ações: the queue with its countdown, what each account's script did, and the history. */
export function ActionsView({actions}) {
  const {state} = actions;
  const [scope, setScope] = useState('all');
  if (state.error && !state.body) return <ErrorState message={state.error} onRetry={actions.reload}/>;
  if (state.loading && !state.body) return <LoadingState rows={6}/>;
  const body = state.body;
  if (!body.ready) return <EmptyState title="Ações ainda não habilitadas" description="Aplique a migração add_reports_google_ads_actions.sql para aprovar mudanças pelo Reports."/>;
  const open = body.actions.filter(item => OPEN.includes(item.status));
  const history = body.actions.filter(item => !OPEN.includes(item.status));
  const visible = scope === 'all' ? history : history.filter(item => scope === 'problems' ? ['failed', 'skipped', 'expired'].includes(item.status) : item.status === scope);
  const notifySupported = typeof Notification !== 'undefined';
  return <div className="rs-stack">
    <Section title="Script de Ações" description="O Google Ads só deixa scripts rodarem de hora em hora. Cada mudança aprovada aqui é aplicada na próxima execução do script de Ações da conta."
      action={notifySupported && <ReportsActionButton color={actions.notify ? 'secondary' : 'tertiary'} size="sm" onClick={actions.toggleNotify} iconLeading={Bell01}>{actions.notify ? 'Avisos do navegador ligados' : 'Avisar no navegador'}</ReportsActionButton>}>
      {body.accounts.length ? <Agents body={body} actions={actions}/> : <p className="rs-muted">Nenhuma conta Google Ads cadastrada.</p>}
    </Section>
    <Section title={`Na fila${open.length ? ` · ${open.length}` : ''}`} description="Aprovadas e esperando a próxima execução. Cancele enquanto estiverem agendadas.">
      {open.length ? <ul className="gaa-list">{open.map(item => <ActionRow key={item.id} item={item} actions={actions}/>)}</ul>
        : <p className="rs-muted gaa-empty"><Zap size={16} aria-hidden="true"/>Nada na fila. Aprove mudanças em Resumo e ações ou em Termos de pesquisa.</p>}
    </Section>
    <Section title="Histórico" description="O que o script fez em cada conta. Desfazer agenda a mudança oposta para a próxima execução."
      action={<div className="rs-segmented" role="group" aria-label="Filtrar histórico">
        {[['all', 'Todas'], ['applied', 'Aplicadas'], ['problems', 'Com problema'], ['cancelled', 'Canceladas']].map(([key, label]) =>
          <button type="button" key={key} aria-pressed={scope === key} onClick={() => setScope(key)}>{label}</button>)}
      </div>}>
      {visible.length ? <ul className="gaa-list">{visible.map(item => <ActionRow key={item.id} item={item} actions={actions}/>)}</ul>
        : <p className="rs-muted">Nada por aqui ainda.</p>}
    </Section>
  </div>;
}
