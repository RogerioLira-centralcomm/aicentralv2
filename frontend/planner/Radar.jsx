import React from 'react';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {PlannerPanel} from './PlannerUi.jsx';
import {newPlanUrl} from './api.js';

export const QUADRANTS = {
  integrada: {label: 'Integrada', tone: 'brand', icon: 'branch', text: 'Iniciar a conversa no orgânico e amplificar com mídia.'},
  conteudo: {label: 'Conteúdo', tone: 'success', icon: 'compose', text: 'Excelente oportunidade para conteúdo.'},
  midia: {label: 'Mídia', tone: 'warning', icon: 'analysis', text: 'Existe audiência e contexto de mídia.'},
  ignorar: {label: 'Ignorar', tone: 'neutral', icon: 'close', text: 'Não merece investimento agora.'},
};

const FLOW = ['Sinal', 'Oportunidade', 'Estratégia', 'Orgânico / Pago', 'Criativos', 'Plano de mídia', 'Resultado'];

/** Organic × paid decision matrix, the Radar's main reading. */
function Matrix({opportunities}) {
  const cell = key => opportunities.filter(item => item.quadrant === key);
  const box = key => {
    const meta = QUADRANTS[key];
    const items = cell(key);
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

function OpportunityRow({item, urls}) {
  const meta = QUADRANTS[item.quadrant] || QUADRANTS.ignorar;
  return <div className="planner-plan-row">
    <span className="planner-plan-row__icon" aria-hidden="true"><Icon name={meta.icon} size={18}/></span>
    <span className="planner-plan-row__copy"><strong>{item.title}</strong><small>{item.thesis}</small></span>
    <span className="planner-scores"><span><b>{item.editorial_score ?? '—'}</b><small>Editorial</small></span><span><b>{item.paid_score ?? '—'}</b><small>Pago</small></span></span>
    <CaduBadge tone={meta.tone}>{meta.label}</CaduBadge>
    <CaduButton size="sm" variant="secondary" href={newPlanUrl(urls) + `&opportunity=${encodeURIComponent(item.id)}`}>Criar plano</CaduButton>
  </div>;
}

export function RadarPage({boot}) {
  const opportunities = Array.isArray(boot.records) ? boot.records : [];
  const enabled = Boolean(boot.features?.radar);
  return <>
    <PlannerHeader title="Radar de Oportunidades" withContext
      description="Sinais de mercado que viram conteúdo, mídia ou os dois."
      meta={!enabled && <CaduBadge tone="brand">Em breve</CaduBadge>}
      actions={<CaduButton disabled={!enabled} title={enabled ? undefined : 'Disponível na próxima versão do Radar'}><Icon name="search" size={16}/>Buscar oportunidades</CaduButton>}/>
    {opportunities.length > 0 ? <>
      <Matrix opportunities={opportunities}/>
      <section className="planner-section"><header className="planner-section__header"><h2>Oportunidades</h2></header>
        <div className="planner-list">{opportunities.map(item => <OpportunityRow key={item.id} item={item} urls={boot.urls}/>)}</div>
      </section>
    </> : <div className="planner-radar-intro">
      <ol className="planner-flow" aria-label="Do sinal ao resultado">{FLOW.map(step => <li key={step}>{step}</li>)}</ol>
      <PlannerPanel title="Como o Radar vai funcionar" description="Cada sinal passa por três leituras independentes antes de virar oportunidade.">
        <ol className="planner-steps">
          <li><strong>Descobre</strong><small>Busca notícias, tendências e dados recentes ligados à marca e ao ICP.</small></li>
          <li><strong>Lê e estrutura</strong><small>Extrai as fontes encontradas em dados comparáveis.</small></li>
          <li><strong>Tenta provar que está errado</strong><small>Um verificador independente confere data, fonte primária e contexto.</small></li>
          <li><strong>Dá duas notas</strong><small>Editorial (vale um conteúdo?) e Paga (existe audiência comprável, em que praça?).</small></li>
        </ol>
      </PlannerPanel>
      <section className="planner-radar-decision" aria-labelledby="radar-decision">
        <h2 id="radar-decision">A decisão</h2>
        <p>O mesmo assunto pode virar conteúdo, mídia ou os dois.</p>
        <Matrix opportunities={[]}/>
      </section>
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
