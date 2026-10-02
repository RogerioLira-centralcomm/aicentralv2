import React, {useMemo, useState} from 'react';
import {ArrowUpRight, Minus, Plus, ZoomIn} from '@untitledui/icons';
import {CaduModal} from '../cadu-design-system/components/CaduModal.jsx';
import {ReportsActionButton} from './ReportsActionButton.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {flowBlockRegistry} from './flowBlockRegistry.js';
import {flowSvg} from './flowExport.js';
import {FLOW_STRATEGIES, FUNNEL_STAGES, buildStrategyConfig, defaultStrategyChannels, strategyResult} from './flowStrategies.js';
import './flow-templates.css';

const svgUrl = config => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(flowSvg(config))}`;
const funnelLabel = id => FUNNEL_STAGES.find(item => item.id === id)?.label || '';
const channelLabel = kind => flowBlockRegistry[kind]?.label || kind;
const ZOOMS = [100, 150, 200, 300];

/** Normalises a built-in strategy and a team template to what the cards and the detail dialog show. */
function describeStrategy(strategy) {
  return {
    key: strategy.id, kind: 'strategy', source: strategy, title: strategy.name, funnel: strategy.funnel, sector: strategy.sector,
    summary: strategy.summary, objective: strategy.objective, result: strategyResult(strategy),
    steps: strategy.steps.map(step => ({title: step.title, goal: step.spec?.goal || ''})),
    channels: defaultStrategyChannels(strategy).map(channelLabel),
  };
}

function describeTeam(template) {
  const nodes = (template.config?.nodes || []).filter(node => node.type !== 'source');
  return {
    key: `team:${template.id}`, kind: 'team', source: template, title: template.name, sector: template.sector,
    summary: template.description || 'Modelo salvo pelo time a partir de um plano.', result: nodes.at(-1)?.title || '',
    steps: nodes.map(node => ({title: node.title || node.kind, goal: node.spec?.goal || ''})),
    channels: (template.config?.nodes || []).filter(node => node.type === 'source').map(node => node.title),
    savedAt: template.created_at,
  };
}

function ModelDetail({item, preview, canCreate, onUse, onClose}) {
  const [zoom, setZoom] = useState(100);
  const step = direction => setZoom(current => ZOOMS[Math.min(ZOOMS.length - 1, Math.max(0, ZOOMS.indexOf(current) + direction))]);
  return <CaduModal className="ftg-modal" label={`Modelo ${item.title}`} closeOnBackdrop onClose={onClose}>
    <div className="ftg-detail">
      <header>
        <div>
          <div className="ftg-tags">{item.funnel && <span className={`ftg-pill is-${item.funnel}`}>{funnelLabel(item.funnel)}</span>}{item.sector && <span className="ftg-pill">{item.sector}</span>}{item.kind === 'team' && <span className="ftg-pill is-team">Do time</span>}</div>
          <h2>{item.title}</h2>
          <p>{item.summary}</p>
        </div>
        <ReportsActionButton color="tertiary" size="sm" className="ftg-close" onClick={onClose} aria-label="Fechar">×</ReportsActionButton>
      </header>
      <div className="ftg-detail__body">
        <section className="ftg-stage" aria-label="Diagrama do modelo">
          <div className="ftg-stage__tools" role="group" aria-label="Zoom">
            <ReportsActionButton color="secondary" size="sm" onClick={() => step(-1)} disabled={zoom === ZOOMS[0]} aria-label="Reduzir"><Minus size={16}/></ReportsActionButton>
            <span>{zoom}%</span>
            <ReportsActionButton color="secondary" size="sm" onClick={() => step(1)} disabled={zoom === ZOOMS.at(-1)} aria-label="Ampliar"><Plus size={16}/></ReportsActionButton>
          </div>
          <div className="ftg-stage__canvas"><img src={preview} alt={`Diagrama do modelo ${item.title}`} style={{width: `${zoom}%`}}/></div>
        </section>
        <aside className="ftg-side">
          <section><h3>Resultado medido</h3><p>{item.result || 'Definido pelo plano.'}</p></section>
          <section><h3>Passos do plano <small>{item.steps.length}</small></h3>
            <ol>{item.steps.map((entry, index) => <li key={`${entry.title}:${index}`}><strong>{entry.title}</strong>{entry.goal && <small>{entry.goal}</small>}</li>)}</ol></section>
          {item.channels.length > 0 && <section><h3>Canais sugeridos</h3><ul className="ftg-channels">{item.channels.map(name => <li key={name}>{name}</li>)}</ul><small>Você escolhe os canais ao criar o plano. Tudo pode ser editado depois.</small></section>}
        </aside>
      </div>
      <footer>
        <ReportsActionButton color="secondary" onClick={onClose}>Fechar</ReportsActionButton>
        {canCreate && <ReportsActionButton color="primary" onClick={() => onUse(item)}>Usar este modelo</ReportsActionButton>}
      </footer>
    </div>
  </CaduModal>;
}

function ModelCard({item, preview, canCreate, onOpen, onUse, onDelete}) {
  return <article className={`ftg-card${item.kind === 'team' ? ' is-team' : ''}`}>
    <button type="button" className="ftg-card__preview" onClick={() => onOpen(item)} aria-label={`Abrir o modelo ${item.title}`}>
      <img src={preview} alt="" loading="lazy"/><span><ZoomIn size={16} aria-hidden="true"/>Ver em detalhe</span>
    </button>
    <div className="ftg-card__body">
      <div className="ftg-tags">{item.funnel && <span className={`ftg-pill is-${item.funnel}`}>{funnelLabel(item.funnel)}</span>}{item.kind === 'team' && <span className="ftg-pill is-team">Do time</span>}{item.sector && <span className="ftg-pill">{item.sector}</span>}</div>
      <h3>{item.title}</h3>
      <p>{item.summary}</p>
      <dl><div><dt>Resultado</dt><dd>{item.result || '—'}</dd></div><div><dt>Passos</dt><dd>{item.steps.length}</dd></div></dl>
    </div>
    <footer>
      <ReportsActionButton color="secondary" iconTrailing={ArrowUpRight} onClick={() => onOpen(item)}>Abrir</ReportsActionButton>
      {canCreate && <ReportsActionButton color="primary" onClick={() => onUse(item)}>Usar modelo</ReportsActionButton>}
      {canCreate && item.kind === 'team' && <ReportsActionButton color="tertiary" onClick={() => onDelete(item)}>Excluir</ReportsActionButton>}
    </footer>
  </article>;
}

/** Ready-made plans: browse by funnel stage, open one to read it in full, then start from it. */
export function FlowTemplateGallery({canCreate, onUse, teamTemplates = [], onUseTeam, onDeleteTeam}) {
  const [funnel, setFunnel] = useState('');
  const [sector, setSector] = useState('');
  const [opened, setOpened] = useState(null);
  const strategies = useMemo(() => FLOW_STRATEGIES.map(describeStrategy), []);
  const team = useMemo(() => teamTemplates.map(describeTeam), [teamTemplates]);
  const previews = useMemo(() => ({
    ...Object.fromEntries(FLOW_STRATEGIES.map(item => [item.id, svgUrl(buildStrategyConfig(item, defaultStrategyChannels(item)))])),
    ...Object.fromEntries(teamTemplates.map(item => [`team:${item.id}`, svgUrl(item.config)])),
  }), [teamTemplates]);
  const sectors = useMemo(() => [...new Set(strategies.map(item => item.sector))].sort((a, b) => a.localeCompare(b, 'pt-BR')), [strategies]);
  const visible = strategies.filter(item => (!funnel || item.funnel === funnel) && (!sector || item.sector === sector));
  const count = id => strategies.filter(item => !id || item.funnel === id).length;
  const use = item => {setOpened(null); if (item.kind === 'team') onUseTeam(item.source); else onUse(item.source);};
  const remove = item => onDeleteTeam(item.source);
  return <section className="ftg" aria-label="Modelos de fluxo">
    {team.length > 0 && <section aria-label="Modelos do time"><h2>Do time <small>{team.length}</small></h2>
      <div className="ftg-grid">{team.map(item => <ModelCard key={item.key} item={item} preview={previews[item.key]} canCreate={canCreate} onOpen={setOpened} onUse={use} onDelete={remove}/>)}</div></section>}
    <section aria-label="Modelos do Reports">
      <div className="ftg-toolbar">
        <div className="rs-segmented ftg-segmented" role="group" aria-label="Etapa do funil">
          <button type="button" aria-pressed={!funnel} onClick={() => setFunnel('')}>Todos <small>{count('')}</small></button>
          {FUNNEL_STAGES.map(stage => <button key={stage.id} type="button" aria-pressed={funnel === stage.id} onClick={() => setFunnel(stage.id)} title={stage.hint}>{stage.label} <small>{count(stage.id)}</small></button>)}
        </div>
        <ReportsNativeSelect aria-label="Setor" value={sector} onChange={event => setSector(event.target.value)}><option value="">Todos os setores</option>{sectors.map(item => <option key={item} value={item}>{item}</option>)}</ReportsNativeSelect>
      </div>
      {funnel && <p className="ftg-hint">{FUNNEL_STAGES.find(stage => stage.id === funnel)?.hint}</p>}
      <div className="ftg-grid">{visible.map(item => <ModelCard key={item.key} item={item} preview={previews[item.key]} canCreate={canCreate} onOpen={setOpened} onUse={use}/>)}</div>
      {!visible.length && <p className="ftg-hint">Nenhum modelo para este filtro.</p>}
    </section>
    {opened && <ModelDetail item={opened} preview={previews[opened.key]} canCreate={canCreate} onUse={use} onClose={() => setOpened(null)}/>}
  </section>;
}
