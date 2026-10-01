import React, {useMemo, useState} from 'react';
import {ReportsActionButton} from './ReportsActionButton.jsx';
import {flowBlockRegistry} from './flowBlockRegistry.js';
import {flowSvg} from './flowExport.js';
import {FLOW_STRATEGIES, buildStrategyConfig, defaultStrategyChannels} from './flowStrategies.js';

const preview = strategy => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(flowSvg(buildStrategyConfig(strategy, strategy.channels.map(([kind]) => kind))))}`;

/** Ready-made plans to start from: the planner picks one, adjusts channels and edits everything after. */
export function FlowTemplateGallery({canCreate, onUse, teamTemplates = [], onUseTeam, onDeleteTeam}) {
  const [sector, setSector] = useState('');
  const sectors = useMemo(() => [...new Set(FLOW_STRATEGIES.map(item => item.sector))].sort((a, b) => a.localeCompare(b, 'pt-BR')), []);
  const previews = useMemo(() => Object.fromEntries(FLOW_STRATEGIES.map(item => [item.id, preview(item)])), []);
  const visible = FLOW_STRATEGIES.filter(item => !sector || item.sector === sector);
  const teamPreview = template => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(flowSvg(template.config))}`;
  return <section className="flow-template-gallery" aria-label="Modelos de fluxo">
    {teamTemplates.length > 0 && <section className="flow-template-gallery__team" aria-label="Modelos do time">
      <h2>Do time <small>{teamTemplates.length}</small></h2>
      <ul className="flow-template-gallery__grid">{teamTemplates.map(item => <li key={item.id}>
        <article className="flow-template-card is-team">
          <img src={teamPreview(item)} alt="" loading="lazy"/>
          <div className="flow-template-card__body">
            <small>{[item.sector, 'Modelo do time'].filter(Boolean).join(' · ')}</small>
            <h3>{item.name}</h3>
            {item.description && <p>{item.description}</p>}
            <span className="flow-template-card__meta">{(item.config.nodes || []).length} passos · salvo em {new Date(item.created_at).toLocaleDateString('pt-BR')}</span>
          </div>
          {canCreate && <div className="flow-template-card__actions"><ReportsActionButton color="secondary" onClick={() => onUseTeam(item)}>Usar modelo</ReportsActionButton>
            <ReportsActionButton color="tertiary" onClick={() => onDeleteTeam(item)}>Excluir</ReportsActionButton></div>}
        </article>
      </li>)}</ul>
      <h2>Modelos do Reports</h2>
    </section>}
    <div className="flow-template-gallery__filters" role="group" aria-label="Setor">
      <button type="button" aria-pressed={!sector} onClick={() => setSector('')}>Todos</button>
      {sectors.map(item => <button key={item} type="button" aria-pressed={sector === item} onClick={() => setSector(item)}>{item}</button>)}
    </div>
    <ul className="flow-template-gallery__grid">{visible.map(item => <li key={item.id}>
      <article className="flow-template-card">
        <img src={previews[item.id]} alt="" loading="lazy"/>
        <div className="flow-template-card__body">
          <small>{item.sector} · {item.objective}</small>
          <h3>{item.name}</h3>
          <p>{item.summary}</p>
          <ul className="flow-template-card__channels" aria-label="Canais sugeridos">{defaultStrategyChannels(item).map(kind => <li key={kind}>{flowBlockRegistry[kind]?.label || kind}</li>)}</ul>
          <span className="flow-template-card__meta">{item.steps.length} passos · previsão com taxas de referência · criativos e setup por canal</span>
        </div>
        {canCreate && <ReportsActionButton color="secondary" onClick={() => onUse(item)}>Usar modelo</ReportsActionButton>}
      </article>
    </li>)}</ul>
  </section>;
}
