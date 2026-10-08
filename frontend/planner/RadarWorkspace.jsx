import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {PlannerSelect} from './PlannerSelect.jsx';
import {Applications, AngleGroups, Evidence, Signals, TIER, radarChatUrl, verified} from './RadarDetail.jsx';
import {RadarMenu, RadarTile, stamp} from './RadarHub.jsx';
import {RunChain} from './RadarRun.jsx';
import {upperFirst} from './api.js';
import {useConfirm} from './useConfirm.jsx';
import './radar-detail.css';
import './radar-hub.css';

const TABS = [['resultados', 'Resultados'], ['sinais', 'Sinais'], ['angulos', 'Ângulos'], ['config', 'Configurações']];
const PHASE = {programado: ['Ativo', 'success'], em_execucao: ['Em execução', 'brand'], pausado: ['Pausado', 'neutral'], concluido: ['Concluído', 'brand'], falha: ['Atenção', 'warning']};
const FREQUENCIES = [[1, 'Diário', 'Uma vez ao dia, às 08h'], [2, '2 vezes ao dia', 'Às 08h e às 17h'], [3, '3 vezes ao dia', 'Às 08h, 13h e 18h']];
const READ_FILTERS = [['todos', 'Todos'], ['novos', 'Novos'], ['lidos', 'Lidos']];
const long = value => new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'long', year: 'numeric'});
const short = value => new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'short'}).replace(/\./g, '');
const time = value => new Date(value).toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit'});
const count = (value, one, many) => `${value} ${value === 1 ? one : many}`;
const nextRun = value => value ? `${new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit'})}, ${time(value)}` : '';

/** O dia de um grupo: "Hoje • 08 de outubro de 2026". */
function dayLabel(key) {
  const date = new Date(`${key}T12:00:00`);
  const today = new Date();
  const yesterday = new Date(Date.now() - 86400000);
  const prefix = date.toDateString() === today.toDateString() ? 'Hoje • ' : date.toDateString() === yesterday.toDateString() ? 'Ontem • ' : '';
  return `${prefix}${long(date)}`;
}
const dayKey = value => { const date = new Date(value); return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; };

function Results({signals, angles, freshIds, plansUrl, onSignalPlan, planOf, planning}) {
  const [read, setRead] = useState('todos');
  const [order, setOrder] = useState('desc');
  const anglesOf = useMemo(() => {
    const map = new Map();
    angles.forEach(angle => (angle.signal_ids || []).forEach(id => map.set(id, (map.get(id) || 0) + 1)));
    return map;
  }, [angles]);
  const counts = {todos: signals.length, novos: signals.filter(item => freshIds.has(item.id)).length};
  counts.lidos = counts.todos - counts.novos;
  const groups = useMemo(() => {
    const list = signals.filter(item => read === 'todos' || (read === 'novos') === freshIds.has(item.id));
    const sorted = [...list].sort((a, b) => (new Date(a.published_at || 0) - new Date(b.published_at || 0)) * (order === 'asc' ? 1 : -1));
    const map = new Map();
    sorted.forEach(item => { const key = item.published_at ? dayKey(item.published_at) : 'sem-data'; map.set(key, [...(map.get(key) || []), item]); });
    return [...map];
  }, [signals, read, order, freshIds]);

  return <>
    <div className="rl-filters rw2-filters">
      <div className="rl-chips" role="group" aria-label="Leitura">
        {READ_FILTERS.map(([id, label]) => <button key={id} type="button" aria-pressed={read === id} className={read === id ? 'is-active' : ''} onClick={() => setRead(id)}>{label}<span>{counts[id]}</span></button>)}
      </div>
      <div className="rw2-order">
        <button type="button" className="rw2-flip" aria-label={order === 'desc' ? 'Mais recentes primeiro' : 'Mais antigos primeiro'} title={order === 'desc' ? 'Mais recentes primeiro' : 'Mais antigos primeiro'}
          onClick={() => setOrder(value => value === 'desc' ? 'asc' : 'desc')}><Icon name="list" size={16}/></button>
      </div>
    </div>
    {groups.length === 0 ? <p className="rd-empty">{signals.length ? 'Nada com esse filtro.' : 'Nenhum sinal passou na verificação desta busca.'}</p> : groups.map(([key, items]) => {
      const angleTotal = new Set(items.flatMap(item => angles.filter(angle => (angle.signal_ids || []).includes(item.id)).map(angle => angle.id))).size;
      return <section key={key} className="rw2-day">
        <h2><span>{key === 'sem-data' ? 'Sem data' : dayLabel(key)}</span><small>{count(items.length, 'sinal', 'sinais')}{angleTotal > 0 && ` • ${count(angleTotal, 'ângulo', 'ângulos')}`}</small></h2>
        <ul>{items.map(item => {
          const fresh = freshIds.has(item.id);
          const level = TIER[item.verification?.tier];
          const plan = planOf[item.id];
          return <li key={item.id}>
            <a className="rw2-item" href={item.url} target="_blank" rel="noreferrer noopener">
              <i className={`rw2-dot${fresh ? ' is-new' : ''}`} aria-label={fresh ? 'Novo' : 'Lido'}/>
              <span className="rw2-item__text"><strong>{item.headline}</strong>{item.description && <small>{item.description}</small>}
                <span className="rw2-tags"><em>{item.source || 'Fonte'}</em>{level && <em>{level[0]}</em>}{verified(item) && <em>Link verificado</em>}</span></span>
              <span className="rw2-item__meta"><b>{count(anglesOf.get(item.id) || 0, 'ângulo', 'ângulos')}</b>{item.published_at && <small>{stamp(item.published_at)}</small>}</span>
              <Icon name="external" size={16}/>
            </a>
            <span className="rw2-item__plan">{plan
              ? <CaduButton size="sm" variant="secondary" href={`${plansUrl}/${encodeURIComponent(plan.id)}`}>Abrir plano</CaduButton>
              : <CaduButton size="sm" variant="tertiary" loading={planning === item.id} onClick={() => onSignalPlan(item)}>Criar planejamento</CaduButton>}</span>
          </li>;
        })}</ul>
      </section>;
    })}
  </>;
}

/** Configurações: programação do radar ativo, de onde vieram os resultados e como a busca foi feita. */
function Settings({radar, run, request, notify, onChange, signals, angles, catalog}) {
  const watch = radar.kind === 'watch';
  const [busy, setBusy] = useState(false);
  const frequency = radar.schedule?.frequency;
  const save = async body => {
    setBusy(true);
    try { await request(`/radar/watches/${radar.id}`, {method: 'PATCH', body: JSON.stringify(body)}); await onChange(); notify({tone: 'success', message: 'Radar atualizado.'}); }
    catch (error) { notify({tone: 'error', message: error.message}); }
    finally { setBusy(false); }
  };
  const rows = [['Marca', run.names.brand], ['Praça', run.params?.places || 'Brasil'], ['Janela', run.params?.recency_days ? `Últimos ${run.params.recency_days} dias` : ''],
    ['Tema', run.focus]].filter(([, value]) => value);
  return <div className="rw2-settings">
    <section className="rd-card"><h2>Programação</h2>
      {watch ? <>
        <ul className="rw2-freq" role="radiogroup" aria-label="Frequência">{FREQUENCIES.map(([value, label, hint]) => <li key={value}>
          <button type="button" role="radio" aria-checked={frequency === value} disabled={busy} className={frequency === value ? 'is-active' : ''} onClick={() => frequency !== value && save({frequency: value})}>
            <b>{label}</b><small>{hint}</small></button></li>)}</ul>
        <CaduButton variant="secondary" loading={busy} onClick={() => save({status: radar.phase === 'pausado' ? 'ativo' : 'pausado'})}>{radar.phase === 'pausado' ? 'Retomar radar' : 'Pausar radar'}</CaduButton>
      </> : <p className="rd-muted">Esta é uma busca pontual: roda uma vez. Para acompanhar o tema todos os dias, crie um radar em &quot;Novo radar&quot; e ligue &quot;Me avise quando houver novidade&quot;.</p>}
    </section>
    <section className="rd-card"><h2>Sobre este radar</h2>
      <dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section>
    {signals.length > 0 && <section className="rd-card rw2-wide"><h2>Evidências</h2><Evidence signals={signals}/></section>}
    {angles.length > 0 && <section className="rd-card rw2-wide"><h2>Aplicações</h2><Applications angles={angles} catalogUrl={catalog}/></section>}
    <section className="rd-card rw2-wide"><h2>Como a busca foi feita</h2><RunChain run={run}/></section>
  </div>;
}

/** Radar aberto: cabeçalho, quatro abas e a última execução sempre à vista. */
export function RadarWorkspace({boot, radarId, names, request, notify, onPlan, onSignalPlan, planning}) {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState('resultados');
  const [pautas, setPautas] = useState({});
  const [confirm, confirmDialog] = useConfirm();

  const load = useCallback(async () => { const result = await request(`/radar/radars/${encodeURIComponent(radarId)}`); setData(result); return result; }, [request, radarId]);
  useEffect(() => {
    load().then(() => request(`/radar/radars/${encodeURIComponent(radarId)}/seen`, {method: 'POST', body: '{}'}).catch(() => {}))
      .catch(error => { notify({tone: 'error', message: error.message}); setData(false); });
  }, [load, request, radarId, notify]);
  useEffect(() => {
    if (!data || !['running', 'queued'].includes(data.run?.status)) return undefined;
    const timer = window.setTimeout(() => load().catch(() => {}), 2500);
    return () => window.clearTimeout(timer);
  }, [data, load]);

  const back = <a className="rw2-back" href={boot.urls.radar}><Icon name="chevron" size={16}/>Voltar para radares</a>;
  if (data === null) return <div className="rw2">{back}<p className="planner-muted">Carregando…</p></div>;
  if (data === false) return <div className="rw2">{back}<p className="rd-empty">Não encontramos este radar.</p></div>;

  const {radar, run, changed} = data;
  const signals = run?.signals || [];
  const angles = run?.opportunities || [];
  const brand = names[radar.brand_ref] || names[radar.project_ref] || '';
  const title = upperFirst(radar.title || run?.focus || 'Radar');
  const phase = PHASE[radar.phase] || PHASE.concluido;
  const freshIds = new Set(changed?.signals || []);
  const freshAngles = new Set(changed?.angles || []);
  const finished = run?.status === 'done';
  const typed = angles.filter(item => item.score_breakdown?.type);
  const planOf = Object.fromEntries((run?.related_plans || []).filter(plan => plan.signal_id).map(plan => [plan.signal_id, plan]));
  const description = radar.focus && radar.focus !== radar.title ? upperFirst(radar.focus) : [brand, run?.params?.places].filter(Boolean).join(' · ');
  const catalog = {channels: boot.urls.channels, formats: boot.urls.formats};
  const tabCount = {sinais: signals.length, angulos: angles.length};

  const act = async (item, action) => {
    try {
      if (action === 'delete') {
        if (!await confirm({title: `Apagar o radar "${item.title}"?`, description: 'As consultas já feitas continuam no histórico.', confirmLabel: 'Apagar radar', tone: 'danger'})) return;
        await request(`/radar/watches/${item.id}`, {method: 'DELETE'});
        window.location.assign(boot.urls.radar);
        return;
      }
      await request(`/radar/watches/${item.id}`, {method: 'PATCH', body: JSON.stringify({status: action})});
      await load();
    } catch (error) { notify({tone: 'error', message: error.message}); }
  };
  const onPauta = async (item, saved) => {
    setPautas(current => ({...current, [item.id]: saved ? 'salva' : 'nova'}));
    try {
      const result = await request(`/radar/opportunities/${item.id}/pauta`, {method: 'PUT', body: JSON.stringify({saved})});
      setPautas(current => ({...current, [item.id]: result.status}));
    } catch (error) { setPautas(current => ({...current, [item.id]: item.status})); notify({tone: 'error', message: error.message}); }
  };
  const groupProps = {changedAngles: freshAngles, planning, onPlan, pautas, onPauta, request, notify, plansUrl: boot.urls.plans,
    chatHref: item => radarChatUrl(boot, {...item, project_ref: run.project_ref, brand_ref: run.brand_ref})};
  const schedule = radar.schedule;
  const status = [radar.phase === 'pausado' ? 'Pausado' : null, schedule?.label, radar.phase === 'programado' && schedule?.next_run_at ? `Próxima execução em ${nextRun(schedule.next_run_at)}` : null].filter(Boolean);

  return <div className="rw2">
    {confirmDialog}
    {back}
    <header className="rw2-head">
      <RadarTile title={title} size={64}/>
      <div className="rw2-head__text">
        <h1>{title}</h1>
        {description && <p>{description}</p>}
        <div className="rw2-head__status"><CaduBadge tone={phase[1]}>{phase[0]}</CaduBadge>{status.map(item => <span key={item}>{item}</span>)}
          {run && <span>Última execução {stamp(run.created_at)}</span>}</div>
      </div>
      <div className="rw2-head__actions">
        <RadarMenu radar={radar} onAct={act}/>
        <CaduButton variant="secondary" onClick={() => setTab('config')}>Editar radar</CaduButton>
      </div>
    </header>
    <div className="rl-tabs" role="tablist" aria-label="Seções do radar">
      {TABS.map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? 'is-active' : ''} onClick={() => setTab(id)}>
        {label}{tabCount[id] != null && <span>{tabCount[id]}</span>}</button>)}
    </div>

    {tab === 'config' ? <Settings radar={radar} run={{...run, names: {brand}}} request={request} notify={notify} onChange={load} signals={signals} angles={angles} catalog={catalog}/>
      : !finished ? (run ? <RunChain run={run}/> : <p className="rd-empty">Este radar ainda não rodou.</p>)
      : tab === 'resultados' ? <Results signals={signals} angles={angles} freshIds={freshIds} plansUrl={boot.urls.plans} onSignalPlan={onSignalPlan} planOf={planOf} planning={planning}/>
      : tab === 'sinais' ? (signals.length ? <Signals signals={signals} planOf={planOf} plansUrl={boot.urls.plans} onSignalPlan={onSignalPlan} planning={planning}/> : <p className="rd-empty">Nenhum sinal passou na verificação.</p>)
      : angles.length ? <AngleGroups angles={typed} full {...groupProps}
        legacy={angles.some(item => !item.score_breakdown?.type) && <div className="rd-grid">{angles.filter(item => !item.score_breakdown?.type).map(item => <article key={item.id} className="rd-angle"><h3>{item.title}</h3><p>{item.thesis}</p></article>)}</div>}/>
        : <p className="rd-empty">Nada em buzz com fonte recente e link que abre. Tente um tema mais conhecido ou uma janela maior.</p>}
  </div>;
}
