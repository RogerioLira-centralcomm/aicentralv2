import React, {useCallback, useEffect, useRef, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {Illustration} from './Illustration.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';
import {RadarAnimation} from './RadarAnimation.jsx';
import {RADAR_DRAFT_KEY, RadarWizard} from './RadarWizard.jsx';

// Etapas mostradas na hora do clique; as de verdade (com tokens e detalhes) chegam do servidor logo depois.
const PENDING_STEPS = [
  ['buzz', 'Procurando o que está em alta', 'O Perplexity busca o que está gerando buzz agora sobre o conceito.'],
  ['check', 'Conferindo as fontes', 'Só entra o que tem data recente e link que abre.'],
  ['angles', 'Montando os ângulos', 'Ideias para a marca falar do conceito aproveitando o buzz.'],
  ['save', 'Organizando o resultado', 'O buzz e os ângulos ficam salvos para virar plano.'],
].map(([key, label, hint], index) => ({key, label, hint, status: index === 0 ? 'running' : 'pending', tokens: 0, detail: '', parallel: false}));
const STEP_STATUS = {pending: 'Aguardando', running: 'Em andamento', done: 'Concluída', failed: 'Falhou', skipped: 'Pulada'};
const tokens = value => Number(value || 0).toLocaleString('pt-BR');

function StepNode({step}) {
  return <li className={`radar-step is-${step.status}`}>
    <span className="radar-step__mark" aria-hidden="true">
      {step.status === 'done' ? <Icon name="check" size={12}/> : step.status === 'failed' ? <Icon name="close" size={12}/> : null}
    </span>
    <span className="radar-step__copy">
      <strong>{step.label}</strong>
      <small>{step.detail || step.hint}</small>
      {(step.preview || []).length > 0 && <span className="radar-step__preview">{step.preview.map(item => <i key={item.url || item.title}
        title={item.url || item.title}>{item.title}{item.score != null && <b>{item.score}</b>}</i>)}</span>}
    </span>
    <span className="radar-step__meta"><small className="sr-only">{STEP_STATUS[step.status]}</small>{step.tokens > 0 && <>{tokens(step.tokens)} tokens</>}</span>
  </li>;
}

/**
 * The run as a chain: two independent discovery flows side by side, then the
 * steps that depend on both. Each node shows what it found and what it cost.
 */
function RunChain({run}) {
  const steps = run.steps || [];
  const parallel = steps.filter(step => step.parallel);
  const serial = steps.filter(step => !step.parallel);
  const running = run.status === 'running';
  return <section className="radar-run" aria-labelledby="radar-run-title" aria-live="polite">
    <div className="radar-run__head">
      <RadarAnimation steps={steps} running={running}/>
      <div>
        <h2 id="radar-run-title">{running ? 'O Radar está procurando' : run.status === 'failed' ? 'A busca parou' : 'Busca concluída'}</h2>
        <p>{run.focus ? `Tema: ${run.focus}` : 'Tema a partir da marca e do projeto escolhidos.'}</p>
        <p className="radar-run__cost"><Icon name="analysis" size={14}/>
          <span><b>{tokens(run.tokens)}</b> tokens usados{run.estimated_tokens ? ` de até ${tokens(run.estimated_tokens)} reservados` : ''}.
            {running ? ' Você paga só o que for usado.' : ''}</span></p>
        {run.error && <p className="radar-run__error">{run.error}</p>}
      </div>
    </div>
    {/* Terminada a busca, o passo a passo recolhe: o que importa é o resultado. */}
    <details className="radar-chain-details" key={run.status} open={run.status !== 'done'}>
      <summary>Como a busca foi feita</summary>
      <ol className="radar-chain">
        {parallel.length > 0 && <li className="radar-chain__fork"><span className="radar-chain__label">Em paralelo</span><ol>{parallel.map(step => <StepNode key={step.key} step={step}/>)}</ol></li>}
        {serial.map(step => <StepNode key={step.key} step={step}/>)}
      </ol>
    </details>
  </section>;
}

const TIER = {A: ['Fonte forte', 'success'], B: ['Fonte regional', 'brand'], C: ['Fonte a conferir', 'neutral']};
const day = value => value ? new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'short', timeZone: 'UTC'}).replace('.', '') : '';

/** Uma fonte: veículo com link e o nível dela na base curada (só informação, nunca filtro). */
function SourceLink({name, url, tier, date}) {
  const level = TIER[tier];
  return <a className="radar-source" href={url} target="_blank" rel="noreferrer noopener">
    <span>{name}</span>{date && <small>{day(date)}</small>}{level && <CaduBadge tone={level[1]}>{level[0]}</CaduBadge>}</a>;
}

/** "O que está em buzz agora": os assuntos que sustentam os ângulos, com fonte e data. */
function BuzzList({signals}) {
  return <section className="radar-buzz" aria-labelledby="radar-buzz-title">
    <h2 id="radar-buzz-title">O que está em buzz agora<span>{signals.length}</span></h2>
    <ol>{signals.map(item => <li key={item.id}>
      <strong>{item.headline}</strong>
      {item.description && <p>{item.description}</p>}
      <SourceLink name={item.source || 'Fonte'} url={item.url} tier={item.verification?.tier} date={item.published_at}/>
    </li>)}</ol>
  </section>;
}

/** Um ângulo para a marca falar do conceito, com o buzz que o sustenta e um caminho direto para virar plano. */
function AngleCard({item, onPlan, busy, lead}) {
  const detail = item.score_breakdown || {};
  const tags = [...(detail.formats || []), ...(detail.channels || [])];
  return <article className="radar-opportunity">
    <header>{detail.window && <small>Janela: {detail.window}</small>}</header>
    <h3>{item.title}</h3>
    <p>{item.thesis}</p>
    {detail.why_now && <p className="radar-angle__why"><Icon name="pulse" size={14}/><span><b>Por que agora:</b> {detail.why_now}</span></p>}
    {tags.length > 0 && <ul className="radar-angle__tags" aria-label="Formatos e canais">{tags.map(tag => <li key={tag}>{tag}</li>)}</ul>}
    {(detail.buzz || []).length > 0 && <div className="radar-angle__buzz"><small>Apoiado em</small>
      {detail.buzz.map(entry => <SourceLink key={entry.id} name={`${entry.assunto} · ${entry.veiculo || entry.domain}`} url={entry.url} tier={entry.tier} date={entry.data}/>)}</div>}
    <footer>
      <CaduButton size="sm" variant={lead ? 'primary' : 'secondary'} loading={busy} disabled={item.status === 'em_plano'} onClick={() => onPlan(item)}>
        {item.status === 'em_plano' ? 'Já virou plano' : 'Criar planejamento'}</CaduButton>
    </footer>
  </article>;
}

export function RadarPage({boot, request, notify, context}) {
  const enabled = Boolean(boot.features?.radar);
  const runId = new URLSearchParams(window.location.search).get('run');
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(Boolean(runId));
  const [starting, setStarting] = useState(false);
  const [pending, setPending] = useState({focus: ''});
  const [planning, setPlanning] = useState('');
  const poll = useRef(null);

  const load = useCallback(async id => {
    const data = await request(`/radar/runs/${id}`);
    setRun(data.run || null);
    return data.run;
  }, [request]);

  useEffect(() => {
    if (!enabled || !runId) return;
    load(runId).catch(() => notify({tone: 'error', message: 'Não encontramos esta busca.'})).finally(() => setLoading(false));
  }, [enabled, runId, load, notify]);

  useEffect(() => {
    window.clearTimeout(poll.current);
    if (run?.status === 'running') poll.current = window.setTimeout(() => load(run.id).catch(() => {}), 2000);
    return () => window.clearTimeout(poll.current);
  }, [run, load]);

  // O botão Voltar do navegador sai de ?run= e volta para o wizard.
  useEffect(() => {
    const back = () => { if (!new URLSearchParams(window.location.search).get('run')) setRun(null); };
    window.addEventListener('popstate', back);
    return () => window.removeEventListener('popstate', back);
  }, []);

  const start = async fields => {
    setPending({focus: fields.focus});
    setStarting(true);
    try {
      const {watch, ...body} = fields;
      // `repeat` só entra no e-mail "o que será feito"; o radar ativo em si é criado logo abaixo.
      const data = await request('/radar/runs', {method: 'POST', body: JSON.stringify({...body, repeat: watch?.frequency || null})});
      let watchError = '';
      if (watch) {
        // O radar ativo é um extra: se falhar, a busca já começou e o aviso diz o que faltou.
        try { await request('/radar/watches', {method: 'POST', body: JSON.stringify({...body, frequency: watch.frequency})}); }
        catch (error) { watchError = error.message; }
      }
      try { window.sessionStorage.removeItem(RADAR_DRAFT_KEY); } catch { /* the draft is only a convenience */ }
      window.history.pushState({}, '', `${boot.urls.radar}?run=${encodeURIComponent(data.run.id)}`);
      setRun(data.run);
      if (watchError) notify({tone: 'error', message: `A busca começou, mas o radar ativo não foi criado: ${watchError}`});
      else if (watch) notify({tone: 'success', message: 'Radar ativo criado. Ele aparece em Meus radares.'});
    } catch (error) {
      notify({tone: 'error', message: error.message});
    } finally {
      setStarting(false);
    }
  };
  const createPlan = async item => {
    setPlanning(item.id);
    try {
      const data = await request(`/radar/opportunities/${item.id}/plan`, {method: 'POST', body: JSON.stringify({})});
      window.location.assign(`${boot.urls.plans}/${encodeURIComponent(data.plan.id)}`);
    } catch (error) {
      notify({tone: 'error', message: error.message});
      setPlanning('');
    }
  };

  if (!enabled) {
    return <PlannerHeader title="Radar" description="O que está em buzz agora e os ângulos para falar de um conceito."
      meta={<CaduBadge tone="brand">Em breve</CaduBadge>}/>;
  }
  if (!runId && !run) {
    // Ao clicar em buscar a animação entra na hora, sem esperar a resposta; se falhar, o wizard volta com o rascunho.
    return <>
      <div hidden={starting}><RadarWizard boot={boot} request={request} busy={starting} onSubmit={start} context={context}/></div>
      {starting && <>
        <PlannerHeader title="Radar" description="O que está em buzz agora e os ângulos para falar de um conceito."/>
        <RunChain run={{status: 'running', focus: pending.focus, tokens: 0, steps: PENDING_STEPS}}/>
      </>}
    </>;
  }
  if (loading && !run) return <PlannerHeader title="Radar" description="Carregando a busca…"/>;

  const running = run?.status === 'running';
  const angles = run?.opportunities || [];
  const signals = run?.signals || [];
  return <>
    <PlannerHeader title="Radar" crumbs={[['Meus radares', boot.urls.radars]]}
      description="O que está em buzz agora e os ângulos para falar de um conceito."
      actions={<><CaduButton variant="secondary" href={boot.urls.radars}>Meus radares</CaduButton>
        <CaduButton href={boot.urls.radar} onClick={() => { try { window.sessionStorage.removeItem(RADAR_DRAFT_KEY); } catch { /* ignore */ } }}><Icon name="plus" size={16}/>Novo radar</CaduButton></>}/>
    {run && <RunChain run={run}/>}
    {angles.length > 0 && <section className="radar-results" aria-labelledby="radar-results-title">
      <h2 id="radar-results-title">Ângulos para falar do conceito<span>{angles.length}</span></h2>
      <div className="radar-results__grid">{angles.map((item, index) => <AngleCard key={item.id} item={item} lead={index === 0}
        busy={planning === item.id} onPlan={createPlan}/>)}</div>
    </section>}
    {signals.length > 0 && <BuzzList signals={signals}/>}
    {run?.status === 'done' && !angles.length && <div className="radar-empty-result">
      <Illustration slot="radar-empty"/>
      <div><strong>Nada em buzz com fonte recente e link que abre.</strong>
        <p className="planner-muted">Tente um conceito mais conhecido, uma janela maior (30 ou 60 dias) ou parta de uma das ideias do assistente.</p></div>
    </div>}
    {!running && run?.status === 'failed' && <p className="planner-muted">Você pode começar uma nova busca em &quot;Novo radar&quot;.</p>}
  </>;
}

/** Compact Radar block for the Planner home. */
export function RadarTeaser({boot}) {
  return <a className="planner-radar-teaser" href={boot.urls.radar}>
    <span className="planner-discover__icon" aria-hidden="true"><Icon name="pulse" size={18}/></span>
    <strong>Radar</strong>
    {boot.features?.radar ? <Icon name="chevron" size={16}/> : <CaduBadge tone="brand">Em breve</CaduBadge>}
    <small>O que está em buzz agora e os ângulos para falar de um conceito. Cada ângulo abre um planejamento.</small>
  </a>;
}
