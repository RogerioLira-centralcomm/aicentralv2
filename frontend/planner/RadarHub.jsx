import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {Illustration} from './Illustration.jsx';
import {PlannerSelect} from './PlannerSelect.jsx';
import {radarChatUrl} from './RadarDetail.jsx';
import {upperFirst} from './api.js';
import {useConfirm} from './useConfirm.jsx';
import './radar-hub.css';

const TABS = [['radares', 'Meus radares'], ['pontuais', 'Solicitações pontuais'], ['pautas', 'Pautas salvas']];
const STATUS_FILTERS = [['todos', 'Todos'], ['ativo', 'Ativos'], ['pausado', 'Pausados'], ['concluido', 'Concluídos']];
const SORTS = [['recentes', 'Mais recentes'], ['novos', 'Mais novidades'], ['nome', 'Nome (A–Z)']];
const PHASE = {programado: ['Ativo', 'success'], em_execucao: ['Em execução', 'brand'], pausado: ['Pausado', 'neutral'], concluido: ['Concluído', 'brand'], falha: ['Atenção', 'warning']};
const plain = value => String(value || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const hueOf = text => [...String(text)].reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) % 360, 7);
const filterOf = phase => ({programado: 'ativo', em_execucao: 'ativo', pausado: 'pausado', concluido: 'concluido', falha: 'ativo'})[phase] || 'concluido';

/** "Hoje, 14:35" · "07 out, 09:12". */
export function stamp(value) {
  if (!value) return '—';
  const date = new Date(value);
  const time = date.toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit'});
  if (date.toDateString() === new Date().toDateString()) return `Hoje, ${time}`;
  return `${date.toLocaleDateString('pt-BR', {day: '2-digit', month: 'short'}).replace(/\./g, '')}, ${time}`;
}

/** Pautas de conteúdo salvas em todos os radares: prontas para o Cadu Chat produzir. */
function PautasList({boot, request, notify}) {
  const [items, setItems] = useState(null);
  useEffect(() => { request('/radar/pautas').then(result => setItems(result.pautas || [])).catch(error => { setItems([]); notify({tone: 'error', message: error.message}); }); }, [request, notify]);
  const remove = async item => {
    setItems(current => current.filter(entry => entry.id !== item.id));
    try { await request(`/radar/opportunities/${item.id}/pauta`, {method: 'PUT', body: JSON.stringify({saved: false})}); }
    catch (error) { setItems(current => [item, ...current]); notify({tone: 'error', message: error.message}); }
  };
  if (items === null) return <p className="planner-muted">Carregando…</p>;
  if (!items.length) return <p className="rv-none">Nenhuma pauta salva. Nas "Pautas de conteúdo" de um radar, use "Salvar pauta".</p>;
  return <div className="rp-list">{items.map(item => {
    const content = item.score_breakdown?.content || {};
    const chat = radarChatUrl(boot, item);
    return <article key={item.id} className="rp-card">
      <small>{item.focus || 'Radar'}</small>
      <h3>{item.title}</h3>
      {item.thesis && <p>{item.thesis}</p>}
      {(content.formats || []).length > 0 && <ul className="rd-tags">{content.formats.map(tag => <li key={tag}>{tag}</li>)}</ul>}
      <footer className="rd-actions">
        {chat && <CaduButton size="sm" href={chat}>Criar no Cadu Chat</CaduButton>}
        {item.run_id && <CaduButton size="sm" variant="secondary" href={`${boot.urls.radar}?run=${encodeURIComponent(item.run_id)}`}>Abrir o radar</CaduButton>}
        <CaduButton size="sm" variant="tertiary" onClick={() => remove(item)}>Remover</CaduButton>
      </footer>
    </article>;
  })}</div>;
}

/** Menu ⋯ de um radar: abrir, pausar/retomar e apagar (os dois últimos só para radares ativos). */
export function RadarMenu({radar, href, onAct, align = 'right'}) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const outside = event => { if (!root.current?.contains(event.target)) setOpen(false); };
    const escape = event => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, [open]);
  const watch = radar.kind === 'watch';
  const paused = radar.phase === 'pausado';
  const run = action => { setOpen(false); onAct(radar, action); };
  return <span className="rl-menu" ref={root}>
    <button type="button" className="rl-menu__button" aria-haspopup="menu" aria-expanded={open} aria-label={`Ações de ${radar.title}`} onClick={() => setOpen(value => !value)}><Icon name="more" size={16}/></button>
    {open && <div className={`rl-menu__list is-${align}`} role="menu">
      {href && <a role="menuitem" href={href}>Abrir radar</a>}
      {watch && <button type="button" role="menuitem" onClick={() => run(paused ? 'ativo' : 'pausado')}>{paused ? 'Retomar' : 'Pausar'}</button>}
      {watch && <button type="button" role="menuitem" className="is-danger" onClick={() => run('delete')}>Apagar radar</button>}
    </div>}
  </span>;
}

export function RadarTile({title, size = 40}) {
  const hue = 130 + (hueOf(title) % 150);
  return <span className="rl-tile" aria-hidden="true" style={{width: size, height: size, background: `hsl(${hue} 60% 94%)`, color: `hsl(${hue} 55% 32%)`}}>{(title || '?').trim().charAt(0).toUpperCase()}</span>;
}

function Row({radar, names, href, onAct}) {
  const phase = PHASE[radar.phase] || PHASE.concluido;
  const theme = names[radar.brand_ref] || names[radar.project_ref] || '';
  const title = upperFirst(radar.title || 'Radar sem nome');
  const description = radar.focus && plain(radar.focus) !== plain(radar.title) ? upperFirst(radar.focus) : '';
  const fresh = radar.changes.signals;
  const [every, hours] = (radar.schedule?.label || 'Pontual').split(' · ');
  return <tr className="rl-row">
    <td><a className="rl-name" href={href}><RadarTile title={title}/><span><strong>{title}</strong>{description && <small>{description}</small>}</span></a></td>
    <td>{theme ? <span className="rl-theme">{theme}</span> : <span className="rl-dash">—</span>}</td>
    <td><span className="rl-two">{every}<small>{hours || ''}</small></span></td>
    <td>{stamp(radar.latest.created_at)}</td>
    <td><span className={`rl-results${fresh ? ' is-new' : ''}`}><i aria-hidden="true"/><span>{fresh} {fresh === 1 ? 'novo' : 'novos'}<small>{radar.latest.signals} no total</small></span></span></td>
    <td><CaduBadge tone={phase[1]}>{phase[0]}</CaduBadge></td>
    <td className="rl-end"><RadarMenu radar={radar} href={href} onAct={onAct}/></td>
  </tr>;
}

/**
 * Radar: a lista dos radares (recorrentes e buscas pontuais) em tabela. Cada linha abre o radar,
 * onde estão os resultados, os sinais e os ângulos. O assistente de criação fica em `?novo=1`.
 */
export function RadarHub({boot, request, notify}) {
  const newUrl = `${boot.urls.radar}?novo=1`;
  const [tab, setTab] = useState('radares');
  const [radars, setRadars] = useState(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('todos');
  const [sort, setSort] = useState('recentes');
  const [busy, setBusy] = useState(false);
  const [confirm, confirmDialog] = useConfirm();
  const names = useMemo(() => Object.fromEntries([...(boot.contextBar?.brands || []), ...(boot.contextBar?.projects || [])].map(entry => [entry.ref, entry.name])), [boot.contextBar]);

  const load = useCallback(() => request('/radar/radars').then(result => setRadars(result.radars || [])), [request]);
  useEffect(() => { load().catch(error => { setRadars([]); notify({tone: 'error', message: error.message}); }); }, [load, notify]);
  // Uma busca em andamento atualiza sozinha.
  useEffect(() => {
    if (!(radars || []).some(item => item.phase === 'em_execucao')) return undefined;
    const timer = window.setTimeout(() => load().catch(() => {}), 4000);
    return () => window.clearTimeout(timer);
  }, [radars, load]);

  const act = async (radar, action) => {
    setBusy(true);
    try {
      if (action === 'delete') {
        if (!await confirm({title: `Apagar o radar "${radar.title}"?`, description: 'As consultas já feitas continuam no histórico.', confirmLabel: 'Apagar radar', tone: 'danger'})) return;
        await request(`/radar/watches/${radar.id}`, {method: 'DELETE'});
      } else {
        await request(`/radar/watches/${radar.id}`, {method: 'PATCH', body: JSON.stringify({status: action})});
      }
      await load();
    } catch (error) {
      notify({tone: 'error', message: error.message});
    } finally {
      setBusy(false);
    }
  };

  const ofKind = useMemo(() => (radars || []).filter(item => item.kind === (tab === 'pontuais' ? 'single' : 'watch')), [radars, tab]);
  const counts = useMemo(() => {
    const result = {todos: ofKind.length, ativo: 0, pausado: 0, concluido: 0};
    ofKind.forEach(item => { result[filterOf(item.phase)] += 1; });
    return result;
  }, [ofKind]);
  const visible = useMemo(() => {
    const needle = plain(query.trim());
    const list = ofKind.filter(item => (status === 'todos' || filterOf(item.phase) === status)
      && (!needle || plain(`${item.title} ${item.focus} ${names[item.brand_ref] || ''} ${names[item.project_ref] || ''}`).includes(needle)));
    const order = {
      recentes: (a, b) => new Date(b.activity_at) - new Date(a.activity_at),
      novos: (a, b) => b.changes.signals - a.changes.signals || new Date(b.activity_at) - new Date(a.activity_at),
      nome: (a, b) => a.title.localeCompare(b.title, 'pt-BR'),
    }[sort];
    return [...list].sort(order);
  }, [ofKind, status, query, sort, names]);
  const counted = kind => (radars || []).filter(item => item.kind === kind).length;
  const tabCount = {radares: counted('watch'), pontuais: counted('single')};
  const enabled = Boolean(boot.features?.radar);
  const loading = radars === null;

  return <div className="rl">
    {confirmDialog}
    <header className="rl-head">
      <div><h1>Radar</h1><p>Monitore o mercado, concorrentes e tendências para melhores decisões.</p></div>
      {enabled ? <CaduButton href={newUrl}><Icon name="plus" size={16}/>Novo radar</CaduButton> : <CaduBadge tone="brand">Em breve</CaduBadge>}
    </header>
    <div className="rl-tabs" role="tablist" aria-label="Visões do Radar">
      {TABS.map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? 'is-active' : ''} onClick={() => { setTab(id); setStatus('todos'); }}>
        {label}{tabCount[id] != null && <span>{tabCount[id]}</span>}</button>)}
    </div>

    {tab === 'pautas' ? <PautasList boot={boot} request={request} notify={notify}/> : <>
      <label className="rl-search"><Icon name="search" size={16}/>
        <input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar radares por nome, tema, marca ou palavra-chave…" aria-label="Buscar radares"/></label>
      <div className="rl-filters">
        <div className="rl-chips" role="group" aria-label="Status">
          {STATUS_FILTERS.map(([id, label]) => <button key={id} type="button" aria-pressed={status === id} className={status === id ? 'is-active' : ''} onClick={() => setStatus(id)}>
            {label}<span>{counts[id]}</span></button>)}
        </div>
        <div className="rl-sort"><PlannerSelect ariaLabel="Ordenar" value={sort} onChange={setSort} options={SORTS.map(([value, label]) => ({value, label}))}/></div>
      </div>

      {loading ? <p className="planner-muted">Carregando…</p> : visible.length === 0 ? <div className={ofKind.length ? 'radar-empty-result' : 'rh-empty'}>
        {ofKind.length ? <Illustration slot="radar-empty"/> : (tab === 'radares' && <img src="/static/images/planner/radar-empty-v1.webp" alt="" loading="lazy"/>)}
        <div><strong>{ofKind.length ? 'Nenhum radar com esses filtros.' : tab === 'pontuais' ? 'Nenhuma solicitação pontual ainda.' : 'Você ainda não tem radares.'}</strong>
          <p className="planner-muted">{ofKind.length ? 'Mude a busca ou o status.' : tab === 'pontuais' ? 'As buscas avulsas que você fizer aparecem aqui.' : 'Monte uma busca em "Novo radar" e ligue "Me avise quando houver novidade" para ela se repetir sozinha.'}</p>
          {enabled && !ofKind.length && <CaduButton size="sm" href={newUrl}>Criar {tab === 'pontuais' ? 'uma busca' : 'o primeiro radar'}</CaduButton>}</div>
      </div> : <div className="rl-table" aria-busy={busy}>
        <table>
          <thead><tr><th scope="col">Radar</th><th scope="col">Tema</th><th scope="col">Frequência</th><th scope="col">Última execução</th><th scope="col">Resultados</th><th scope="col">Status</th><th scope="col"><span className="rl-sr">Ações</span></th></tr></thead>
          <tbody>{visible.map(radar => <Row key={radar.id} radar={radar} names={names} onAct={act} href={`${boot.urls.radar}?radar=${encodeURIComponent(radar.id)}`}/>)}</tbody>
        </table>
      </div>}
    </>}
  </div>;
}
