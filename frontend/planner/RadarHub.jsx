import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {Illustration} from './Illustration.jsx';
import {RadarListPage} from './RadarList.jsx';
import './radar-hub.css';

const TABS = [['radares', 'Meus radares'], ['alta', 'Em alta'], ['recentes', 'Recentes'], ['salvos', 'Salvos']];
const PERIODS = [[7, 'Últimos 7 dias'], [30, 'Últimos 30 dias'], [90, 'Últimos 90 dias']];
const TIER = {A: 'Fonte forte', B: 'Fonte regional', C: 'Fonte a conferir'};
const SOURCES_SHOWN = 5;
const day = value => value ? new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'}).replace(/\./g, '') : '';
const sinceDays = value => value ? (Date.now() - new Date(value).getTime()) / 86400000 : Infinity;
const plain = value => String(value || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const hueOf = text => [...String(text)].reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) % 360, 7);

/** O feed não traz imagem da matéria: a capa é a inicial da fonte sobre um degradê estável por fonte. */
function Cover({item}) {
  const hue = 130 + (hueOf(item.source) % 70);
  return <div className="rh-cover" aria-hidden="true" style={{background: `linear-gradient(135deg, hsl(${hue} 45% 14%), hsl(${hue + 20} 55% 30%))`}}>
    <span>{(item.source || '?').trim().charAt(0).toUpperCase()}</span><small>{item.theme_label}</small>
  </div>;
}

function Tag({tone = 'plain', children}) { return <span className={`rh-tag rh-tag--${tone}`}>{children}</span>; }

function NewsCard({item, onSave, onPlan, planning}) {
  const lead = item.angles.find(angle => angle.status !== 'em_plano') || null;
  return <article className="rh-card">
    <Cover item={item}/>
    <div className="rh-card__body">
      <div className="rh-card__tags">
        <Tag>{item.theme_label}</Tag>
        {item.tier && <Tag tone={item.tier === 'A' ? 'good' : 'plain'}>{TIER[item.tier]}</Tag>}
        {item.angle_count > 0 && <Tag tone="brand"><Icon name="pulse" size={12}/>{item.angle_count === 1 ? 'Oportunidade' : `${item.angle_count} oportunidades`}</Tag>}
      </div>
      <h3><a href={item.url} target="_blank" rel="noreferrer noopener">{item.title}</a></h3>
      {item.summary && <p>{item.summary}</p>}
      {item.radar && <small className="rh-card__radar">Radar: {item.radar}</small>}
      <footer>
        <span className="rh-card__source"><i aria-hidden="true">{(item.source || '?').trim().charAt(0)}</i>{item.source}<small>· {day(item.published_at || item.detected_at)}</small></span>
        <span className="rh-card__actions">
          {lead && <CaduButton size="sm" variant="secondary" loading={planning === lead.id} onClick={() => onPlan(lead)}>Criar planejamento</CaduButton>}
          <button type="button" className={`rh-icon${item.saved ? ' is-on' : ''}`} aria-pressed={item.saved} aria-label={item.saved ? 'Remover dos salvos' : 'Salvar'} title={item.saved ? 'Remover dos salvos' : 'Salvar'} onClick={() => onSave(item)}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill={item.saved ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"><path d="M6 3h12v18l-6-4-6 4z"/></svg>
          </button>
          <a className="rh-icon" href={item.url} target="_blank" rel="noreferrer noopener" aria-label="Abrir a fonte" title="Abrir a fonte"><Icon name="external" size={16}/></a>
        </span>
      </footer>
    </div>
  </article>;
}

/**
 * Resultados dos radares: o que as buscas acharam, com tema, fonte e os ângulos que cada notícia sustenta.
 * O assistente de busca ("Novo radar") fica em `?novo=1`; aqui só se lê, filtra, salva e vira plano.
 */
export function RadarHub({boot, request, notify}) {
  const newUrl = `${boot.urls.radar}?novo=1`;
  const [tab, setTab] = useState('radares');
  const [data, setData] = useState(null);
  const [theme, setTheme] = useState('todos');
  const [period, setPeriod] = useState(30);
  const [query, setQuery] = useState('');
  const [sources, setSources] = useState([]);
  const [allSources, setAllSources] = useState(false);
  const [planning, setPlanning] = useState('');

  useEffect(() => {
    request('/radar/feed?days=90').then(setData).catch(error => { setData({items: [], themes: []}); notify({tone: 'error', message: error.message}); });
  }, [request, notify]);

  const inPeriod = useMemo(() => (data?.items || []).filter(item => sinceDays(item.published_at || item.detected_at) <= period), [data, period]);
  const searched = useMemo(() => {
    const needle = plain(query.trim());
    return needle ? inPeriod.filter(item => plain(`${item.title} ${item.summary} ${item.source} ${item.radar}`).includes(needle)) : inPeriod;
  }, [inPeriod, query]);
  const themes = useMemo(() => {
    const counts = {};
    searched.forEach(item => { counts[item.theme] = (counts[item.theme] || 0) + 1; });
    return (data?.themes || []).filter(entry => counts[entry.id]).map(entry => ({...entry, count: counts[entry.id]}));
  }, [data, searched]);
  const sourceList = useMemo(() => {
    const counts = new Map();
    searched.filter(item => theme === 'todos' || item.theme === theme).forEach(item => counts.set(item.source, (counts.get(item.source) || 0) + 1));
    return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'pt-BR'));
  }, [searched, theme]);
  const visible = useMemo(() => {
    let list = searched.filter(item => (theme === 'todos' || item.theme === theme) && (!sources.length || sources.includes(item.source)));
    if (tab === 'salvos') list = list.filter(item => item.saved);
    return [...list].sort(tab === 'alta'
      ? (a, b) => b.score - a.score
      : (a, b) => new Date(b.published_at || b.detected_at) - new Date(a.published_at || a.detected_at));
  }, [searched, theme, sources, tab]);
  const total = searched.filter(item => theme === 'todos' || item.theme === theme).length;

  const toggleSource = name => setSources(current => current.includes(name) ? current.filter(entry => entry !== name) : [...current, name]);
  const save = useCallback(async item => {
    const next = !item.saved;
    const mark = value => setData(current => ({...current, items: current.items.map(entry => entry.id === item.id ? {...entry, saved: value} : entry)}));
    mark(next);
    try { await request(`/radar/signals/${item.id}/saved`, {method: 'PUT', body: JSON.stringify({saved: next})}); }
    catch (error) { mark(!next); notify({tone: 'error', message: error.message}); }
  }, [request, notify]);
  const plan = useCallback(async angle => {
    setPlanning(angle.id);
    try {
      const created = await request(`/radar/opportunities/${angle.id}/plan`, {method: 'POST', body: JSON.stringify({})});
      window.location.assign(`${boot.urls.plans}/${encodeURIComponent(created.plan.id)}`);
    } catch (error) { notify({tone: 'error', message: error.message}); setPlanning(''); }
  }, [request, notify, boot.urls.plans]);

  const highlights = useMemo(() => [...(data?.items || [])].sort((a, b) => b.score - a.score).slice(0, 4), [data]);
  const loading = data === null;
  const shownSources = allSources ? sourceList : sourceList.slice(0, SOURCES_SHOWN);
  const savedCount = (data?.items || []).filter(item => item.saved).length;

  return <div className="rh">
    <section className="rh-hero">
      <div className="rh-hero__copy">
        <small>Seus radares</small>
        <h1>Radar</h1>
        <p>Tendências, insights e oportunidades para transformar ideias em planos de mídia.</p>
      </div>
</section>

    <section className="rh-sheet">
      <div className="rh-toolbar">
        <div className="rh-tabs" role="tablist" aria-label="Resultados do Radar">
          {TABS.map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? 'is-active' : ''} onClick={() => setTab(id)}>
            {label}{id === 'salvos' && savedCount > 0 && <span>{savedCount}</span>}</button>)}
        </div>
        {tab !== 'radares' && <>
          <label className="rh-search"><Icon name="search" size={16}/><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar insights, temas ou fontes…" aria-label="Buscar nos resultados"/></label>
          <label className="rh-select"><select value={theme} onChange={event => setTheme(event.target.value)} aria-label="Tema">
            <option value="todos">Todos os temas</option>{themes.map(entry => <option key={entry.id} value={entry.id}>{entry.label}</option>)}</select></label>
          <label className="rh-select"><select value={period} onChange={event => setPeriod(Number(event.target.value))} aria-label="Período">
            {PERIODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </>}
        {tab === 'radares' && <span className="rh-toolbar__spacer"/>}
        {boot.features?.radar && <CaduButton href={newUrl}><Icon name="plus" size={16}/>Novo radar</CaduButton>}
      </div>

      {tab === 'radares' ? <div className="rh-embedded">
          <RadarListPage boot={boot} request={request} notify={notify} embedded/>
          {highlights.length > 0 && <section className="rh-highlights" aria-labelledby="rh-highlights-title">
            <h2 id="rh-highlights-title">Em alta nos seus radares<button type="button" onClick={() => setTab('alta')}>Ver tudo</button></h2>
            <div className="rh-grid">{highlights.map(item => <NewsCard key={item.id} item={item} onSave={save} onPlan={plan} planning={planning}/>)}</div>
          </section>}
        </div>
        : <div className="rh-layout">
          <aside className="rh-side" aria-label="Filtros">
            <h2>Temas</h2>
            <ul>
              <li><button type="button" className={theme === 'todos' ? 'is-active' : ''} onClick={() => setTheme('todos')}><span>Todos os temas</span><b>{searched.length}</b></button></li>
              {themes.map(entry => <li key={entry.id}><button type="button" className={theme === entry.id ? 'is-active' : ''} onClick={() => setTheme(entry.id)}><span>{entry.label}</span><b>{entry.count}</b></button></li>)}
            </ul>
            {sourceList.length > 0 && <>
              <h2>Fontes</h2>
              <ul>
                <li><label className="rh-check"><input type="checkbox" checked={!sources.length} onChange={() => setSources([])}/><span>Todas as fontes</span><b>{total}</b></label></li>
                {shownSources.map(([name, count]) => <li key={name}><label className="rh-check"><input type="checkbox" checked={sources.includes(name)} onChange={() => toggleSource(name)}/><span>{name}</span><b>{count}</b></label></li>)}
              </ul>
              {sourceList.length > SOURCES_SHOWN && <button type="button" className="rh-more" onClick={() => setAllSources(value => !value)}>{allSources ? 'Ver menos' : 'Ver mais'}</button>}
            </>}
          </aside>
          <div className="rh-main">
            {loading ? <p className="planner-muted">Carregando…</p> : visible.length === 0 ? <div className="radar-empty-result">
              <Illustration slot="radar-empty"/>
              <div><strong>{tab === 'salvos' ? 'Nada salvo ainda.' : (data.items || []).length ? 'Nada com esses filtros.' : 'Seus radares ainda não trouxeram resultados.'}</strong>
                <p className="planner-muted">{tab === 'salvos' ? 'Use o marcador de um card para guardar o que vale revisitar.' : (data.items || []).length ? 'Mude o tema, a fonte ou o período.' : 'Monte um radar com um tema ou uma marca. Cada busca traz notícias com data recente e link que abre, e os ângulos para virar plano.'}</p>
                {boot.features?.radar && !(data.items || []).length && <CaduButton size="sm" href={newUrl}>Criar o primeiro radar</CaduButton>}
                {!boot.features?.radar && <CaduBadge tone="brand">Em breve</CaduBadge>}</div>
            </div> : <div className="rh-grid">{visible.map(item => <NewsCard key={item.id} item={item} onSave={save} onPlan={plan} planning={planning}/>)}</div>}
          </div>
        </div>}
    </section>
  </div>;
}
