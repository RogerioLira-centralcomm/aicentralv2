import React, {useMemo, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';
import {RunChain, tokens} from './RadarRun.jsx';
import './radar-detail.css';

const TABS = [['geral', 'Visão geral'], ['angulos', 'Ângulos estratégicos'], ['sinais', 'Sinais'], ['evidencias', 'Evidências'], ['aplicacoes', 'Aplicações'], ['metodologia', 'Metodologia']];
const TIER = {A: ['Fonte forte', 'success'], B: ['Fonte regional', 'brand'], C: ['Fonte a conferir', 'neutral']};
const STATUS = {done: ['Concluído', 'success'], running: ['Em andamento', 'brand'], failed: ['Falhou', 'neutral'], queued: ['Na fila', 'neutral'], cancelled: ['Cancelado', 'neutral']};
// Sem nota explicável ainda (Radar v2): os dois primeiros ângulos do ranking são os de maior oportunidade.
const HIGH_PRIORITY = 2;
const day = value => value ? new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'}).replace(/\./g, '') : '';
const verified = signal => ['ok', 'bloqueado'].includes(signal.verification?.url_status);
const count = (value, one, many) => `${value} ${value === 1 ? one : many}`;

function SourceLink({name, url, tier, date}) {
  const level = TIER[tier];
  return <a className="rd-source" href={url} target="_blank" rel="noreferrer noopener"><span>{name}</span>{date && <small>{day(date)}</small>}
    {level && <CaduBadge tone={level[1]}>{level[0]}</CaduBadge>}</a>;
}

function AngleCard({item, rank, onPlan, busy, compact = false}) {
  const detail = item.score_breakdown || {};
  const tags = [...(detail.formats || []), ...(detail.channels || [])];
  const high = rank < HIGH_PRIORITY;
  const inPlan = item.status === 'em_plano';
  return <article className="rd-angle">
    <div className="rd-angle__head">
      <span className={`rd-priority${high ? ' is-high' : ''}`}><Icon name="pulse" size={12}/>{high ? 'Alta oportunidade' : 'Média oportunidade'}</span>
      {detail.window && <small>Janela: {detail.window}</small>}
    </div>
    <h3>{item.title}</h3>
    <p>{item.thesis}</p>
    {!compact && detail.why_now && <p className="rd-angle__why"><b>Por que agora:</b> {detail.why_now}</p>}
    {tags.length > 0 && <ul className="rd-tags" aria-label="Formatos e canais">{tags.map(tag => <li key={tag}>{tag}</li>)}</ul>}
    {!compact && (detail.buzz || []).length > 0 && <div className="rd-angle__buzz"><small>Apoiado em</small>
      {detail.buzz.map(entry => <SourceLink key={entry.id} name={`${entry.assunto} · ${entry.veiculo || entry.domain}`} url={entry.url} tier={entry.tier} date={entry.data}/>)}</div>}
    <footer>
      <CaduButton size="sm" variant={high && !inPlan ? 'primary' : 'secondary'} loading={busy} disabled={inPlan} onClick={() => onPlan(item)}>
        {inPlan ? 'Já virou plano' : <><Icon name="plus" size={14}/>Criar planejamento</>}</CaduButton>
    </footer>
  </article>;
}

function Kpi({icon, value, label, hint}) {
  return <div className="rd-kpi"><span className="rd-kpi__icon" aria-hidden="true"><Icon name={icon} size={20}/></span>
    <div><strong>{value}</strong><span>{label}</span></div><p>{hint}</p></div>;
}

function Signals({signals, planOf, plansUrl, onSignalPlan, planning}) {
  return <ol className="rd-signals">{signals.map(item => {
    const plan = planOf[item.id];
    return <li key={item.id}>
      <strong>{item.headline}</strong>
      {item.description && <p>{item.description}</p>}
      <div className="rd-signals__foot">
        <SourceLink name={item.source || 'Fonte'} url={item.url} tier={item.verification?.tier} date={item.published_at}/>
        {plan ? <CaduButton size="sm" variant="secondary" href={`${plansUrl}/${encodeURIComponent(plan.id)}`}>Abrir plano</CaduButton>
          : <CaduButton size="sm" variant="secondary" loading={planning === item.id} onClick={() => onSignalPlan(item)}>Criar planejamento</CaduButton>}
      </div>
    </li>;
  })}</ol>;
}

/** Evidências: uma linha por veículo, com o nível dele na base curada e o que ele sustentou. */
function Evidence({signals}) {
  const rows = useMemo(() => {
    const byName = new Map();
    signals.forEach(item => {
      const key = item.source || 'Fonte';
      const row = byName.get(key) || {name: key, tier: item.verification?.tier, count: 0, ok: 0, latest: null, url: item.url};
      row.count += 1;
      row.ok += verified(item) ? 1 : 0;
      if (!row.latest || new Date(item.published_at) > new Date(row.latest)) { row.latest = item.published_at; row.url = item.url; }
      byName.set(key, row);
    });
    return [...byName.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'pt-BR'));
  }, [signals]);
  return <div className="rd-table" role="table" aria-label="Fontes consultadas">
    <div className="rd-table__head" role="row"><span>Fonte</span><span>Nível</span><span>Notícias</span><span>Link verificado</span><span>Mais recente</span></div>
    {rows.map(row => <a key={row.name} className="rd-table__row" role="row" href={row.url} target="_blank" rel="noreferrer noopener">
      <span><b>{row.name}</b></span>
      <span>{TIER[row.tier] ? <CaduBadge tone={TIER[row.tier][1]}>{TIER[row.tier][0]}</CaduBadge> : '—'}</span>
      <span>{row.count}</span><span>{row.ok} de {row.count}</span><span>{day(row.latest) || '—'}</span>
    </a>)}
  </div>;
}

/** Aplicações: formatos e canais que os ângulos pedem, do mais repetido ao menos. */
function Applications({angles, catalogUrl}) {
  const groups = useMemo(() => {
    const build = key => {
      const map = new Map();
      angles.forEach(angle => ((angle.score_breakdown || {})[key] || []).forEach(name => {
        const entry = map.get(name) || {name, angles: []};
        entry.angles.push(angle.title);
        map.set(name, entry);
      }));
      return [...map.values()].sort((a, b) => b.angles.length - a.angles.length || a.name.localeCompare(b.name, 'pt-BR'));
    };
    return [['Canais sugeridos', build('channels'), catalogUrl.channels], ['Formatos sugeridos', build('formats'), catalogUrl.formats]];
  }, [angles, catalogUrl]);
  return <div className="rd-apps">{groups.map(([title, list, href]) => <section key={title}>
    <h3>{title}{href && <a href={href}>Abrir catálogo</a>}</h3>
    {list.length === 0 ? <p className="planner-muted">Os ângulos não sugeriram nada aqui.</p> : <ul>{list.map(entry => <li key={entry.name}>
      <b>{entry.name}</b><span>{count(entry.angles.length, 'ângulo', 'ângulos')}</span>
      <small>{entry.angles.join(' · ')}</small></li>)}</ul>}
  </section>)}</div>;
}

const PLAN_STATUS = {draft: 'Rascunho', ready: 'Pronto', archived: 'Arquivado'};

function Side({run, brand, signals, onTab, plansUrl}) {
  const related = run.related_plans || [];
  const rows = [['Marca', brand], ['Praça', run.params?.places || 'Brasil'], ['Janela', run.params?.recency_days ? `Últimos ${run.params.recency_days} dias` : ''],
    ['Rodada', run.trigger === 'agendado' ? 'Radar ativo' : 'Busca manual'], ['Feita em', day(run.created_at)],
    ['Tamanho da busca', `${tokens(run.tokens)} tokens`]].filter(([, value]) => value);
  return <aside className="rd-side">
    <section className="rd-card"><h2>Sobre este radar</h2>
      <dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section>
    <section className="rd-card"><h2>Planos relacionados<span>{related.length}</span></h2>
      {related.length === 0 ? <p className="rd-muted">Nenhum plano nasceu deste radar ainda. Use &quot;Criar planejamento&quot; em um ângulo ou em uma notícia.</p>
        : <ul className="rd-plans">{related.map(plan => <li key={plan.id}><a href={`${plansUrl}/${encodeURIComponent(plan.id)}`}>{plan.title}</a>
          {PLAN_STATUS[plan.status] && <small>{PLAN_STATUS[plan.status]}</small>}</li>)}</ul>}</section>
    <button type="button" className="rd-card rd-card--link" onClick={() => onTab('metodologia')}>
      <span><b>Como a busca foi feita</b><small>{count(signals.length, 'notícia lida e verificada', 'notícias lidas e verificadas')}, etapas e custo de cada uma.</small></span>
      <Icon name="chevron" size={16}/></button>
  </aside>;
}

/** Detalhe de um radar: números, ângulos, sinais, evidências, aplicações e metodologia, com os dados da busca ao lado. */
export function RadarDetail({boot, run, names, onPlan, onSignalPlan, planning}) {
  const [tab, setTab] = useState('geral');
  const status = STATUS[run.status] || STATUS.done;
  const angles = run.opportunities || [];
  const signals = run.signals || [];
  const brand = names[run.brand_ref] || names[run.project_ref] || '';
  const title = run.focus || brand || 'Radar';
  const finished = run.status === 'done';
  const sources = new Set(signals.filter(verified).map(item => item.source)).size;
  const urls = {channels: boot.urls.channels, formats: boot.urls.formats};
  const planOf = useMemo(() => Object.fromEntries((run.related_plans || []).filter(plan => plan.signal_id).map(plan => [plan.signal_id, plan])), [run.related_plans]);
  const tabCount = {angulos: angles.length, sinais: signals.length, evidencias: sources};
  const description = [brand, run.params?.places, run.params?.recency_days && `últimos ${run.params.recency_days} dias`, day(run.created_at)].filter(Boolean).join(' · ');

  return <>
    <PlannerHeader title={title} crumbs={[['Radar', boot.urls.radar]]} description={description} meta={<CaduBadge tone={status[1]}>{status[0]}</CaduBadge>}
      actions={<CaduButton href={`${boot.urls.radar}?novo=1`}><Icon name="plus" size={16}/>Novo radar</CaduButton>}/>
    {!finished && <RunChain run={run}/>}
    {finished && <div className="rd">
      <div className="rd-main">
        <div className="rd-tabs" role="tablist" aria-label="Seções do radar">
          {TABS.map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? 'is-active' : ''} onClick={() => setTab(id)}>
            {label}{tabCount[id] != null && <span>{tabCount[id]}</span>}</button>)}
        </div>
        {tab === 'geral' && <>
          <div className="rd-kpis">
            <Kpi icon="pulse" value={signals.length} label={signals.length === 1 ? 'Sinal identificado' : 'Sinais identificados'} hint="Notícias recentes sobre o tema, com data e link que abre."/>
            <Kpi icon="check" value={sources} label={sources === 1 ? 'Fonte verificada' : 'Fontes verificadas'} hint="Veículos cujo link foi aberto e conferido."/>
            <Kpi icon="analysis" value={angles.length} label={angles.length === 1 ? 'Ângulo estratégico' : 'Ângulos estratégicos'} hint="Oportunidades para a marca falar do tema."/>
            <Kpi icon="plus" value={angles.filter(angle => angle.status === 'em_plano').length} label="Ângulos em plano" hint="Ângulos que já viraram planejamento."/>
          </div>
          {angles.length === 0 ? <p className="rd-empty">Nada em buzz com fonte recente e link que abre. Tente um tema mais conhecido ou uma janela maior.</p>
            : <section aria-labelledby="rd-top"><h2 id="rd-top" className="rd-h2">Ângulos estratégicos<button type="button" onClick={() => setTab('angulos')}>Ver todos</button></h2>
              <div className="rd-grid">{angles.slice(0, 4).map((item, index) => <AngleCard key={item.id} item={item} rank={index} compact busy={planning === item.id} onPlan={onPlan}/>)}</div></section>}
          {run.time_saved?.label && <p className="rd-saved"><Icon name="pulse" size={14}/>Tempo poupado: ~{run.time_saved.label}</p>}
        </>}
        {tab === 'angulos' && <div className="rd-grid">{angles.map((item, index) => <AngleCard key={item.id} item={item} rank={index} busy={planning === item.id} onPlan={onPlan}/>)}</div>}
        {tab === 'sinais' && (signals.length ? <Signals signals={signals} planOf={planOf} plansUrl={boot.urls.plans} onSignalPlan={onSignalPlan} planning={planning}/> : <p className="rd-empty">Nenhum sinal passou na verificação.</p>)}
        {tab === 'evidencias' && (signals.length ? <Evidence signals={signals}/> : <p className="rd-empty">Sem fontes para mostrar.</p>)}
        {tab === 'aplicacoes' && <Applications angles={angles} catalogUrl={urls}/>}
        {tab === 'metodologia' && <RunChain run={run}/>}
      </div>
      <Side run={run} brand={brand} signals={signals} onTab={setTab} plansUrl={boot.urls.plans}/>
    </div>}
  </>;
}
