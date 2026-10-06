import React, {useCallback, useEffect, useRef, useState} from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {Illustration} from './Illustration.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';

export const QUADRANTS = {
  integrada: {label: 'Integrada', tone: 'brand', icon: 'branch', text: 'Iniciar a conversa no orgânico e amplificar com mídia.'},
  conteudo: {label: 'Conteúdo', tone: 'success', icon: 'compose', text: 'Excelente oportunidade para conteúdo.'},
  midia: {label: 'Mídia', tone: 'warning', icon: 'analysis', text: 'Existe audiência e contexto de mídia.'},
  ignorar: {label: 'Ignorar', tone: 'neutral', icon: 'close', text: 'Não merece investimento agora.'},
};
const VERDICTS = {confirmado: ['Confirmada', 'success'], parcial: ['Evidência parcial', 'warning'], contestado: ['Contestada', 'neutral'], nao_verificado: ['Não verificada', 'neutral']};
const STEP_STATUS = {pending: 'Aguardando', running: 'Em andamento', done: 'Concluída', failed: 'Falhou', skipped: 'Pulada'};
const tokens = value => Number(value || 0).toLocaleString('pt-BR');

/**
 * Ideias de busca: cada lente vira um pedido completo, já com a marca. É o
 * jeito mais rápido de o planejador pedir bem (tema + recorte), em vez de
 * digitar só o nome da marca.
 */
const IDEAS = [
  {id: 'datas', icon: 'calendar', label: 'Datas e sazonalidade', text: who => `datas comerciais, eventos e sazonalidade das próximas semanas que abrem espaço para ${who}`},
  {id: 'concorrentes', icon: 'users', label: 'Concorrentes', text: who => `lançamentos, campanhas e movimentos recentes dos concorrentes de ${who}`},
  {id: 'tendencias', icon: 'pulse', label: 'Tendências e buscas em alta', text: who => `assuntos e buscas em alta ligados ao setor de ${who}`},
  {id: 'regulacao', icon: 'check', label: 'Regulação e governo', text: who => `mudanças de regra, decisões de governo e reguladores que afetam ${who}`},
  {id: 'reputacao', icon: 'analysis', label: 'Reputação e imprensa', text: who => `o que a imprensa e o público estão falando sobre ${who}`},
  {id: 'praca', icon: 'search', label: 'Notícias da praça', text: who => `fatos locais recentes em [sua praça] que dão gancho para ${who}`},
];

/** Ajuda curta para pedir bem; aberta até a primeira busca. */
function RadarTips({open}) {
  return <details className="radar-tips" open={open}>
    <summary>Como pedir uma boa busca</summary>
    <ul>
      <li><strong>Tema + recorte.</strong> "Black Friday de eletrodomésticos em BH" rende mais que "Black Friday".</li>
      <li><strong>Escolha a marca no topo.</strong> O Radar usa o perfil dela: público, concorrentes e posicionamento.</li>
      <li><strong>Diga a praça</strong> quando a campanha for regional. Assim a busca procura fatos daquele lugar.</li>
      <li><strong>Uma pergunta por busca.</strong> Temas misturados viram oportunidades genéricas.</li>
      <li><strong>Janela:</strong> o Radar olha os últimos 30 a 60 dias, e um segundo modelo confere data, fonte e contexto de cada oportunidade.</li>
    </ul>
  </details>;
}

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
  const places = (item.geo_scores || []).slice(0, 3);
  return <article className="radar-opportunity">
    <header>
      <CaduBadge tone={meta.tone}>{meta.label}</CaduBadge><CaduBadge tone={verdict[1]}>{verdict[0]}</CaduBadge>
      {breakdown.window && <small>Janela: {breakdown.window}</small>}
    </header>
    <h3>{item.title}</h3>
    <p>{item.thesis}</p>
    <dl className="radar-opportunity__scores">
      <div><dt>Editorial</dt><dd>{item.editorial_score ?? '—'}</dd>{breakdown.why?.editorial && <small>{breakdown.why.editorial}</small>}</div>
      <div><dt>Pago</dt><dd>{item.paid_score ?? '—'}</dd>{breakdown.why?.paid && <small>{breakdown.why.paid}</small>}</div>
      {places.length > 0 && <div><dt>Praças</dt><dd className="radar-opportunity__places">{places.map(place => <span key={place.place}>{place.place}<b>{place.score}</b></span>)}</dd></div>}
    </dl>
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
  const [focus, setFocus] = useState('');
  const [estimate, setEstimate] = useState(null);
  const [run, setRun] = useState(null);
  const [starting, setStarting] = useState(false);
  const [planning, setPlanning] = useState('');
  const poll = useRef(null);
  const brand = boot.contextBar?.brands?.find(item => item.ref === context?.brand_ref);
  const project = boot.contextBar?.projects?.find(item => item.ref === context?.project_ref);

  const load = useCallback(async id => {
    const data = await request(id ? `/radar/runs/${id}` : '/radar/runs/latest');
    setRun(data.run || null);
    return data.run;
  }, [request]);

  useEffect(() => {
    if (!enabled) return;
    load().catch(() => {});
    request('/radar/estimate').then(setEstimate).catch(() => {});
  }, [enabled, load, request]);

  useEffect(() => {
    window.clearTimeout(poll.current);
    if (run?.status === 'running') poll.current = window.setTimeout(() => load(run.id).catch(() => {}), 2000);
    return () => window.clearTimeout(poll.current);
  }, [run, load]);

  const start = async event => {
    event.preventDefault();
    setStarting(true);
    try {
      const data = await request('/radar/runs', {method: 'POST', body: JSON.stringify({
        focus, brand_ref: context?.brand_ref || null, project_ref: context?.project_ref || null})});
      setRun(data.run);
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

  const running = run?.status === 'running';
  const opportunities = run?.opportunities || [];
  return <>
    <PlannerHeader title="Radar de Oportunidades" withContext description="Sinais de mercado que viram conteúdo, mídia ou os dois."
      meta={!enabled && <CaduBadge tone="brand">Em breve</CaduBadge>}/>

    <form className="radar-compose" onSubmit={start}>
      {!run && <Illustration slot="radar-empty"/>}
      <div className="radar-compose__body">
        <label htmlFor="radar-focus">O que o Radar deve procurar?</label>
        <div className="radar-compose__row">
          <CaduInput id="radar-focus" value={focus} maxLength={240} disabled={!enabled || running}
            placeholder="Ex.: volta às aulas e crédito estudantil no Sudeste" onChange={event => setFocus(event.target.value)}/>
          <CaduButton type="submit" loading={starting} disabled={!enabled || running || (focus.trim().length < 3 && !brand && !project)}>
            <Icon name="search" size={16}/>Buscar oportunidades</CaduButton>
        </div>
        <div className="radar-ideas" role="group" aria-label="Ideias de busca">
          {IDEAS.map(idea => <button key={idea.id} type="button" disabled={!enabled || running}
            onClick={() => setFocus(idea.text(brand?.name || project?.name || 'a marca'))}>
            <Icon name={idea.icon} size={14}/>{idea.label}</button>)}
        </div>
        {!brand && !project && enabled && <p className="radar-compose__hint">Escolha uma marca ou um projeto no topo: as ideias e a busca passam a usar o perfil dela.</p>}
        <p className="radar-compose__meta">
          {(brand || project) && <span>Contexto: {[brand?.name, project?.name].filter(Boolean).join(' · ')}</span>}
          {enabled ? <span>Cada busca reserva até {estimate ? tokens(estimate.estimated_tokens) : '…'} tokens dos seus créditos; você paga só o que usar.</span>
            : <span>O Radar será liberado para a sua conta em breve.</span>}
        </p>
      </div>
    </form>

    <RadarTips open={!run}/>

    {run ? <RunChain run={run}/> : <ol className="radar-how" aria-label="Como o Radar trabalha">
      <li><strong>Descobre e busca, em paralelo</strong><small>Perplexity e Firecrawl procuram sinais recentes por caminhos independentes.</small></li>
      <li><strong>Lê as fontes</strong><small>Só páginas lidas viram evidência.</small></li>
      <li><strong>Dá notas</strong><small>Editorial (vale conteúdo?), Paga (há audiência comprável?) e por praça.</small></li>
      <li><strong>Tenta provar que está errado</strong><small>Um segundo modelo confere data, fonte primária e contexto.</small></li>
    </ol>}

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
        <p className="planner-muted">Tente recortar mais: acrescente a praça, o período ou comece por uma das ideias de busca acima.</p></div>
    </div>}
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
