import React, {useCallback, useEffect, useRef, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {Illustration} from './Illustration.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';
import {RADAR_DRAFT_KEY, RadarWizard} from './RadarWizard.jsx';

export const QUADRANTS = {
  integrada: {label: 'Integrada', tone: 'brand', icon: 'branch', text: 'Iniciar a conversa no orgânico e amplificar com mídia.'},
  conteudo: {label: 'Conteúdo', tone: 'success', icon: 'compose', text: 'Excelente oportunidade para conteúdo.'},
  midia: {label: 'Mídia', tone: 'warning', icon: 'analysis', text: 'Existe audiência e contexto de mídia.'},
  ignorar: {label: 'Ignorar', tone: 'neutral', icon: 'close', text: 'Não merece investimento agora.'},
};
const VERDICTS = {confirmado: ['Confirmada', 'success'], parcial: ['Evidência parcial', 'warning'], contestado: ['Contestada', 'neutral'], nao_verificado: ['Não verificada', 'neutral']};
export const CONFIDENCE = {alta: ['Confiança alta', 'success'], media: ['Confiança média', 'warning'], baixa: ['Confiança baixa', 'neutral']};
const STEP_STATUS = {pending: 'Aguardando', running: 'Em andamento', done: 'Concluída', failed: 'Falhou', skipped: 'Pulada'};
const tokens = value => Number(value || 0).toLocaleString('pt-BR');

/** Organic × paid decision matrix, the Radar's main reading. */
function Matrix({opportunities}) {
  const box = key => {
    const meta = QUADRANTS[key];
    const items = opportunities.filter(item => item.quadrant === key);
    return <div className={`planner-matrix__cell is-${key}`}>
      <span className="planner-matrix__title"><Icon name={meta.icon} size={14}/>{meta.label}<b>{items.length}</b></span>
      <small>{meta.text}</small>
      {items.slice(0, 3).map(item => <span key={item.id} className="planner-matrix__item">{item.title}<em>{item.editorial_score}/{item.paid_score}</em></span>)}
    </div>;
  };
  return <div className="planner-matrix" role="group" aria-label="Matriz orgânico por pago">
    <span className="planner-matrix__axis is-y">Orgânico</span>
    <span className="planner-matrix__axis is-x">Oportunidade paga</span>
    {box('conteudo')}{box('integrada')}{box('ignorar')}{box('midia')}
  </div>;
}

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
      <Illustration slot="radar-scan" busy={running}/>
      <div>
        <h2 id="radar-run-title">{running ? 'O Radar está procurando' : run.status === 'failed' ? 'A busca parou' : 'Busca concluída'}</h2>
        <p>{run.focus ? `Tema: ${run.focus}` : 'Tema a partir da marca e do projeto escolhidos.'}</p>
        <p className="radar-run__cost"><Icon name="analysis" size={14}/>
          <span><b>{tokens(run.tokens)}</b> tokens usados{run.estimated_tokens ? ` de até ${tokens(run.estimated_tokens)} reservados` : ''}.
            {running ? ' Você paga só o que for usado.' : ''}</span></p>
        {run.error && <p className="radar-run__error">{run.error}</p>}
      </div>
    </div>
    <ol className="radar-chain">
      <li className="radar-chain__fork"><span className="radar-chain__label">Em paralelo</span><ol>{parallel.map(step => <StepNode key={step.key} step={step}/>)}</ol></li>
      {serial.map(step => <StepNode key={step.key} step={step}/>)}
    </ol>
  </section>;
}

function OpportunityCard({item, onPlan, busy, lead}) {
  const meta = QUADRANTS[item.quadrant] || QUADRANTS.ignorar;
  const breakdown = item.score_breakdown || {};
  const verdict = VERDICTS[breakdown.verification?.verdict] || VERDICTS.nao_verificado;
  const confidence = CONFIDENCE[breakdown.verification?.confidence];
  const places = (item.geo_scores || []).slice(0, 3);
  const sources = (breakdown.sources || []).filter(source => source.url).slice(0, 3);
  return <article className="radar-opportunity">
    <header>
      <CaduBadge tone={meta.tone}>{meta.label}</CaduBadge><CaduBadge tone={verdict[1]}>{verdict[0]}</CaduBadge>
      {confidence && <CaduBadge tone={confidence[1]}>{confidence[0]}</CaduBadge>}
      {breakdown.window && <small>Janela: {breakdown.window}</small>}
    </header>
    <h3>{item.title}</h3>
    <p>{item.thesis}</p>
    <dl className="radar-opportunity__scores">
      <div><dt>Editorial</dt><dd>{item.editorial_score ?? '—'}</dd>{breakdown.why?.editorial && <small>{breakdown.why.editorial}</small>}</div>
      <div><dt>Pago</dt><dd>{item.paid_score ?? '—'}</dd>{breakdown.why?.paid && <small>{breakdown.why.paid}</small>}</div>
      {places.length > 0 && <div><dt>Praças</dt><dd className="radar-opportunity__places">{places.map(place => <span key={place.place}>{place.place}<b>{place.score}</b></span>)}</dd></div>}
    </dl>
    {sources.length > 0 && <ul className="radar-opportunity__sources" aria-label="Fontes">
      {sources.map(source => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer noopener">{source.domain || source.source}</a>
        {source.tier && <small title={`Nível de confiança da fonte: ${source.tier}`}>{source.tier}</small>}
        {source.url_status === 'quebrado' && <small className="is-broken">link não abre</small>}</li>)}
    </ul>}
    {breakdown.verification?.notes && <p className="radar-opportunity__check"><Icon name="search" size={14}/>{breakdown.verification.notes}</p>}
    <footer>
      {(breakdown.channels || []).length > 0 && <span className="planner-muted">Canais: {breakdown.channels.join(', ')}</span>}
      {/* One primary action on the page: the strongest opportunity. Ignored ones stay quiet. */}
      <CaduButton size="sm" variant={item.quadrant === 'ignorar' ? 'tertiary' : lead ? 'primary' : 'secondary'}
        loading={busy} disabled={item.status === 'em_plano'} onClick={() => onPlan(item)}>
        {item.status === 'em_plano' ? 'Já virou plano' : item.quadrant === 'ignorar' ? 'Planejar mesmo assim' : 'Criar planejamento'}</CaduButton>
    </footer>
  </article>;
}

export function RadarPage({boot, request, notify, context}) {
  const enabled = Boolean(boot.features?.radar);
  const runId = new URLSearchParams(window.location.search).get('run');
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(Boolean(runId));
  const [starting, setStarting] = useState(false);
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

  const start = async fields => {
    setStarting(true);
    try {
      const {watch, ...body} = fields;
      const data = await request('/radar/runs', {method: 'POST', body: JSON.stringify(body)});
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
    return <PlannerHeader title="Radar de Oportunidades" description="Sinais de mercado que viram conteúdo, mídia ou os dois."
      meta={<CaduBadge tone="brand">Em breve</CaduBadge>}/>;
  }
  if (!runId && !run) return <RadarWizard boot={boot} request={request} busy={starting} onSubmit={start} context={context}/>;
  if (loading && !run) return <PlannerHeader title="Radar de Oportunidades" description="Carregando a busca…"/>;

  const running = run?.status === 'running';
  const opportunities = run?.opportunities || [];
  return <>
    <PlannerHeader title="Radar de Oportunidades" crumbs={[['Meus radares', boot.urls.radars]]}
      description="Sinais de mercado que viram conteúdo, mídia ou os dois."
      actions={<><CaduButton variant="secondary" href={boot.urls.radars}>Meus radares</CaduButton>
        <CaduButton href={boot.urls.radar} onClick={() => { try { window.sessionStorage.removeItem(RADAR_DRAFT_KEY); } catch { /* ignore */ } }}><Icon name="plus" size={16}/>Novo radar</CaduButton></>}/>
    {run && <RunChain run={run}/>}
    {opportunities.length > 0 && <>
      <Matrix opportunities={opportunities}/>
      <section className="radar-results" aria-labelledby="radar-results-title">
        <h2 id="radar-results-title">Oportunidades<span>{opportunities.length}</span></h2>
        <div className="radar-results__grid">{opportunities.map((item, index) => <OpportunityCard key={item.id} item={item} lead={index === 0 && item.quadrant !== 'ignorar'}
          busy={planning === item.id} onPlan={createPlan}/>)}</div>
      </section>
    </>}
    {run?.status === 'done' && !opportunities.length && <div className="radar-empty-result">
      <Illustration slot="radar-empty"/>
      <div><strong>Nenhuma oportunidade forte desta vez.</strong>
        <p className="planner-muted">Tente recortar mais: acrescente a praça, a janela ou parta de uma das ideias de busca do assistente.</p></div>
    </div>}
    {!running && run?.status === 'failed' && <p className="planner-muted">Você pode começar uma nova busca em &quot;Novo radar&quot;.</p>}
  </>;
}

/** Compact Radar block for the Planner home. */
export function RadarTeaser({boot}) {
  return <a className="planner-radar-teaser" href={boot.urls.radar}>
    <span className="planner-discover__icon" aria-hidden="true"><Icon name="pulse" size={18}/></span>
    <strong>Radar de Oportunidades</strong>
    {boot.features?.radar ? <Icon name="chevron" size={16}/> : <CaduBadge tone="brand">Em breve</CaduBadge>}
    <small>Sinais de mercado viram oportunidades de conteúdo, mídia ou as duas. Cada oportunidade abre um planejamento.</small>
  </a>;
}
