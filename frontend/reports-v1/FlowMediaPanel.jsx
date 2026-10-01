import React, {useState} from 'react';
import {Announcement02} from '@untitledui/icons';
import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {flowBlockFor} from './flowBlockRegistry.js';
import {CREATIVE_FORMATS, CREATIVE_STATUSES, LIMITS, OBJECTIVES, entryPageFor, mediaProgress, segmentKindLabel, utmLink} from './flowMedia.js';

const newId = () => crypto.randomUUID().slice(0, 8);

function SourceMedia({node, config, host, flowName, readOnly, onMediaChange, onSelect}) {
  const [setupDraft, setSetupDraft] = useState('');
  const [copied, setCopied] = useState(false);
  const block = flowBlockFor(node);
  const media = node.media || {};
  const creatives = media.creatives || [];
  const setup = media.setup || [];
  const entry = entryPageFor(config, node.id);
  const link = utmLink(node, {platform: block.source || node.source, host, entryPath: entry?.path, flowName});
  const progress = mediaProgress(node);
  const update = patch => onMediaChange(node.id, {...media, ...patch});
  const setCreative = (id, patch) => update({creatives: creatives.map(item => item.id === id ? {...item, ...patch} : item)});
  const copy = async () => {try {await navigator.clipboard.writeText(link.url); setCopied(true); setTimeout(() => setCopied(false), 1500);} catch {setCopied(false);}};
  return <article className="flow-media-source" aria-label={`${node.title}${node.segment?.name ? ` · ${node.segment.name}` : ''}`}>
    <header>
      <button type="button" className="flow-media-source__title" onClick={() => onSelect(node.id)}><strong>{node.title}</strong>
        <small>{node.segment?.name ? `${node.segment.name}${node.segment.kind ? ` · ${segmentKindLabel(node.segment.kind)}` : ''}` : 'Sem público definido'}</small></button>
      <span className="flow-media-source__progress">{progress.creatives.done}/{progress.creatives.total} criativos · {progress.setup.done}/{progress.setup.total} setup</span>
    </header>
    <label>Objetivo<ReportsNativeSelect disabled={readOnly} value={media.objective || ''} onChange={event => update({objective: event.target.value || undefined})}>
      <option value="">Não definido</option>{OBJECTIVES.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</ReportsNativeSelect></label>
    <div className="flow-media-utm">
      <strong>Link com UTM</strong>
      {link.url ? <><code>{link.url}</code><Button color="secondary" onClick={copy}>{copied ? 'Copiado' : 'Copiar link'}</Button></>
        : <small>{host ? 'Defina o endereço da página de entrada desta origem para gerar o link.' : 'Conecte o site do fluxo para gerar o link.'} Parâmetros: <code>{link.query}</code></small>}
    </div>
    <section aria-label="Criativos"><h4>Criativos <small>{creatives.length}</small></h4>
      {creatives.map(item => <div key={item.id} className="flow-media-creative">
        <ReportsFieldInput aria-label="Nome do criativo" disabled={readOnly} maxLength="80" value={item.name} onChange={event => setCreative(item.id, {name: event.target.value})}/>
        <ReportsNativeSelect aria-label="Formato" disabled={readOnly} value={item.format} onChange={event => setCreative(item.id, {format: event.target.value})}>{CREATIVE_FORMATS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</ReportsNativeSelect>
        <ReportsNativeSelect aria-label="Situação" disabled={readOnly} value={item.status} onChange={event => setCreative(item.id, {status: event.target.value})}>{CREATIVE_STATUSES.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</ReportsNativeSelect>
        <ReportsFieldInput aria-label="Mensagem principal" disabled={readOnly} maxLength="500" placeholder="Mensagem principal" value={item.message || ''} onChange={event => setCreative(item.id, {message: event.target.value})}/>
        {!readOnly && <button type="button" className="flow-media-remove" aria-label={`Remover ${item.name}`} onClick={() => update({creatives: creatives.filter(entry => entry.id !== item.id)})}>×</button>}
      </div>)}
      {!readOnly && creatives.length < LIMITS.creatives && <Button color="tertiary" onClick={() => update({creatives: [...creatives, {id: newId(), name: `Criativo ${creatives.length + 1}`, format: CREATIVE_FORMATS[0][0], status: 'rascunho'}]})}>Adicionar criativo</Button>}
    </section>
    <section aria-label="Setup da plataforma"><h4>Setup da plataforma <small>{progress.setup.done}/{progress.setup.total}</small></h4>
      {setup.map(item => <label key={item.id} className="flow-media-check"><input type="checkbox" disabled={readOnly} checked={item.done} onChange={event => update({setup: setup.map(entry => entry.id === item.id ? {...entry, done: event.target.checked} : entry)})}/><span>{item.text}</span>
        {!readOnly && <button type="button" className="flow-media-remove" aria-label={`Remover ${item.text}`} onClick={event => {event.preventDefault(); update({setup: setup.filter(entry => entry.id !== item.id)});}}>×</button>}</label>)}
      {!readOnly && setup.length < LIMITS.setup && <form className="flow-media-add" onSubmit={event => {event.preventDefault(); const text = setupDraft.replace(/\s+/g, ' ').trim().slice(0, 200); if (!text) return; update({setup: [...setup, {id: newId(), text, done: false}]}); setSetupDraft('');}}>
        <ReportsFieldInput aria-label="Novo item de setup" placeholder="Novo item de setup" maxLength="200" value={setupDraft} onChange={event => setSetupDraft(event.target.value)}/><Button type="submit" color="secondary" disabled={!setupDraft.trim()}>Adicionar</Button></form>}
    </section>
  </article>;
}

/** Review of what each channel needs before going live: creatives and platform setup, per audience. */
export function FlowMediaPanel({config, host, flowName, readOnly, onChange, onSelectNode, onClose}) {
  const sources = (config.nodes || []).filter(node => node.type === 'source');
  const totals = sources.map(mediaProgress).reduce((sum, item) => ({
    creatives: {done: sum.creatives.done + item.creatives.done, total: sum.creatives.total + item.creatives.total},
    setup: {done: sum.setup.done + item.setup.done, total: sum.setup.total + item.setup.total}}),
  {creatives: {done: 0, total: 0}, setup: {done: 0, total: 0}});
  const onMediaChange = (id, media) => onChange({...config, nodes: config.nodes.map(node => node.id === id ? {...node, media} : node)});
  return <ReportsPanelShell className="flow-blueprint-panel flow-media-panel" icon={Announcement02} title="Criação e setup"
    description="O que cada canal e público precisa antes de ir ao ar: criativos aprovados e plataforma configurada." onClose={onClose}>
    <div className="flow-media-totals">
      <span><strong>{totals.creatives.done}/{totals.creatives.total}</strong> criativos aprovados</span>
      <span><strong>{totals.setup.done}/{totals.setup.total}</strong> itens de setup</span>
    </div>
    {sources.length ? sources.map(node => <SourceMedia key={node.id} node={node} config={config} host={host} flowName={flowName} readOnly={readOnly} onMediaChange={onMediaChange} onSelect={onSelectNode}/>)
      : <p>Adicione as origens de tráfego ao mapa para planejar criativos e setup.</p>}
  </ReportsPanelShell>;
}
