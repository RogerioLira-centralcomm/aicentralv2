import React, {useMemo, useState} from 'react';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {SourceMedia} from './FlowMediaPanel.jsx';
import {flowBlockFor} from './flowBlockRegistry.js';
import {creativeFormatLabel, creativeStatusLabel, entryPageFor, mediaProgress, objectiveLabel, segmentKindLabel, utmLink} from './flowMedia.js';
import {sheetCell} from './flowProductionSheet.js';

const FILTERS = [['all', 'Todos'], ['pending', 'Pendentes'], ['ready', 'Prontos']];

function channelRows(config, host, flowName) {
  return (config.nodes || []).filter(node => node.type === 'source').map(node => {
    const block = flowBlockFor(node);
    const progress = mediaProgress(node);
    const entry = entryPageFor(config, node.id);
    const link = utmLink(node, {platform: block.source || node.source, host: host || entry?.host || '', entryPath: entry?.path, flowName});
    return {node, block, progress, link, ready: progress.missing.length === 0};
  });
}

const csv = rows => '﻿' + [['Canal', 'Público', 'Tipo de público', 'Objetivo', 'Link com UTM', 'Criativos', 'Criativos aprovados', 'Setup pendente', 'Situação'],
  ...rows.map(({node, block, progress, link, ready}) => [node.title || block.label, node.segment?.name || '', segmentKindLabel(node.segment?.kind), objectiveLabel(node.media?.objective),
    link.url || link.query, (node.media?.creatives || []).map(item => `${item.name} (${creativeFormatLabel(item.format)}, ${creativeStatusLabel(item.status)})`).join('\n'),
    `${progress.creatives.done}/${progress.creatives.total}`, (node.media?.setup || []).filter(item => !item.done).map(item => item.text).join('\n'), ready ? 'Pronto' : 'Pendente'])]
  .map(row => row.map(sheetCell).join(';')).join('\r\n');

/** Full-page review of every channel and audience: creatives, platform setup and tagged links, ready or pending. */
export function FlowReviewPage({config, host, flowName, readOnly, onChange, onSelectNode}) {
  const [filter, setFilter] = useState('all');
  const rows = useMemo(() => channelRows(config, host, flowName), [config, host, flowName]);
  const totals = rows.reduce((sum, {progress}) => ({creatives: {done: sum.creatives.done + progress.creatives.done, total: sum.creatives.total + progress.creatives.total},
    setup: {done: sum.setup.done + progress.setup.done, total: sum.setup.total + progress.setup.total}}), {creatives: {done: 0, total: 0}, setup: {done: 0, total: 0}});
  const ready = rows.filter(row => row.ready).length;
  const visible = rows.filter(row => filter === 'all' || (filter === 'ready' ? row.ready : !row.ready));
  const onMediaChange = (id, media) => onChange({...config, nodes: config.nodes.map(node => node.id === id ? {...node, media} : node)});
  const exportCsv = () => {
    const url = URL.createObjectURL(new Blob([csv(rows)], {type: 'text/csv;charset=utf-8'}));
    const link = Object.assign(document.createElement('a'), {href: url, download: 'revisao-canais.csv'});
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const percent = (done, total) => total ? Math.round(done / total * 100) : 0;
  return <section className="flow-review" aria-label="Revisão de criação e setup">
    <header className="flow-review__summary">
      {[['Canais e públicos prontos', ready, rows.length], ['Criativos aprovados', totals.creatives.done, totals.creatives.total], ['Itens de setup', totals.setup.done, totals.setup.total]].map(([label, done, total]) =>
        <div key={label} className="flow-review__stat"><span>{label}</span><strong>{done}<small>/{total}</small></strong>
          <div className="flow-review__bar" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent(done, total)}><span style={{width: `${percent(done, total)}%`}}/></div></div>)}
      <div className="flow-review__actions">
        <div className="rs-segmented rs-segmented--sm flow-review__filters" role="group" aria-label="Filtrar canais">{FILTERS.map(([id, label]) => <button key={id} type="button" aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}</div>
        <Button color="secondary" disabled={!rows.length} onClick={exportCsv}>Exportar CSV</Button>
      </div>
    </header>
    {visible.length ? <div className="flow-review__grid">{visible.map(({node, ready: isReady}) => <div key={node.id} className={`flow-review__card${isReady ? ' is-ready' : ''}`}>
      <span className="flow-review__flag">{isReady ? 'Pronto' : 'Pendente'}</span>
      <SourceMedia node={node} config={config} host={host} flowName={flowName} readOnly={readOnly} onMediaChange={onMediaChange} onSelect={onSelectNode}/>
    </div>)}</div> : <p className="flow-review__empty">{rows.length ? 'Nenhum canal neste filtro.' : 'Adicione origens de tráfego ao mapa para revisar criativos e setup por canal.'}</p>}
  </section>;
}
