import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Icon} from '../lib/icons';
import {csrf, request, safeUrl} from '../lib/api';
import {CaduDialog} from '../../cadu-design-system/components/CaduDialog';
import {normalizeArtifactContent} from '../lib/artifactContent.mjs';

const labels = {
  brief: 'Briefing', document: 'Documento', note: 'Nota', executive_summary: 'Resumo executivo',
  media_plan: 'Plano de mídia', scenario: 'Cenário', research: 'Pesquisa', project_map: 'Mapa do projeto',
  html: 'Página interativa', image: 'Imagem', spreadsheet: 'Planilha', report: 'Relatório',
  resource: 'Arquivo', brand_identity: 'Marca', project_profile: 'Projeto', meeting_summary: 'Resumo de reunião', meeting_agenda: 'Pauta',
  link_reader: 'Referência',
  library: 'Biblioteca',
};

function comparableLines(content) {
  const html = String(content?.html || '');
  if (html) return html.split(/<\/(?:p|li|h[1-6]|blockquote|div)>/i)
    .map(part => part.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  return Object.entries(content || {}).filter(([key]) => !['title', '_provenance'].includes(key))
    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`);
}

function versionChanges(before, after) {
  const oldLines = comparableLines(before), newLines = comparableLines(after);
  const oldSet = new Set(oldLines), newSet = new Set(newLines);
  return {removed: oldLines.filter(line => !newSet.has(line)).slice(0, 12), added: newLines.filter(line => !oldSet.has(line)).slice(0, 12)};
}

function LibraryArtifact({artifact, onOpenResource}) {
  const groups = Array.isArray(artifact.content?.groups) ? artifact.content.groups : [];
  const drag = (event, item) => {
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData('application/x-cadu-item', JSON.stringify({...item, type: 'resource', resourceRef: item.id}));
  };
  return <div className="cv-library-artifact">
    {groups.map(group => <section key={group.id} className={`cv-library-strip is-${group.id}`}>
      <header><h3>{group.title}</h3><span>{group.items.length}</span></header>
      <div className={group.layout === 'list' ? 'is-list' : 'is-carousel'}>
        {group.items.map(item => <button key={item.id || item.url} type="button" draggable onDragStart={event => drag(event, item)} onClick={() => onOpenResource?.(item)} title={item.title}>
          {item.preview ? <img src={safeUrl(item.preview)} alt="" loading="lazy"/> : <Icon name={item.kind === 'link' ? 'link' : 'file'} size={17}/>}<span>{item.title}</span>{item.detail && <small>{item.detail}</small>}
        </button>)}
      </div>
    </section>)}
    {!groups.some(group => group.items.length) && <p className="cv-library-empty">Os materiais do projeto aparecerão aqui.</p>}
  </div>;
}

function EditableTextarea({value, onChange, className = '', ...props}) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    ref.current.style.height = '0px';
    ref.current.style.height = `${Math.max(52, ref.current.scrollHeight)}px`;
  }, [value]);
  return <textarea ref={ref} className={className} value={value} onChange={event => onChange(event.target.value)} {...props}/>;
}

function htmlDocument(content, artifactTitle = '') {
  const css = String(content.css || '').replace(/<\/style/gi, '<\\/style');
  const javascript = String(content.js || '').replace(/<\/script/gi, '<\\/script');
  const origin = window.location.origin;
  const logo = safeUrl(content.logo_url);
  const color = value => /^#[0-9a-f]{3,8}$/i.test(String(value || '').trim()) ? String(value).trim() : '';
  const theme = [color(content.primary_color) && `--cadu-brand-primary:${color(content.primary_color)}`, color(content.secondary_color) && `--cadu-brand-secondary:${color(content.secondary_color)}`].filter(Boolean).join(';');
  const favicon = logo ? `<link rel="icon" href="${escapeHtml(logo)}">` : '';
  const artifactStylesheet = `${origin}/static/css/tailwind/artifact.css`;
  const body = String(content.html || '');
  const brandName = escapeHtml(content.title || artifactTitle || 'Cadu');
  const brandHeader = logo && !/<img\b/i.test(body) ? `<header data-cadu-brand-header class="mx-auto flex w-full max-w-6xl items-center gap-3 border-b border-slate-200 px-6 py-4" style="border-bottom-color:var(--cadu-brand-primary,#176b5e)"><img src="${escapeHtml(logo)}" alt="" class="h-8 w-auto object-contain"><span class="text-sm font-semibold text-slate-700">${brandName}</span></header>` : '';
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">${favicon}<link rel="stylesheet" href="${artifactStylesheet}"><meta http-equiv="Content-Security-Policy" content="sandbox allow-scripts; default-src 'none'; img-src https: data: blob: ${origin}; style-src 'self' 'unsafe-inline' ${origin}; font-src https: data: ${origin}; script-src 'unsafe-inline'; connect-src 'none'; media-src https: data: blob: ${origin}; form-action 'none'; base-uri 'none'"><style>:root{${theme}}html,body{margin:0;min-height:100%;background:#fff}${css}</style></head><body>${brandHeader}${body}<script>${javascript}<\/script></body></html>`;
}

function StructuredArtifact({artifact, onChange}) {
  const content = artifact.content || {};
  const updateField = (index, value) => onChange({...content, fields: (content.fields || []).map((field, fieldIndex) => fieldIndex === index ? {...field, value} : field)});
  return <article className="cv-artifact-editor cv-mx-auto cv-w-full cv-max-w-[780px] cv-p-6 md:cv-p-10">
    <EditableTextarea className="cv-artifact-summary" value={content.summary || ''} onChange={value => onChange({...content, summary: value})} placeholder="Resumo do trabalho" aria-label="Resumo da entrega"/>
    <div className="cv-mt-7 cv-grid cv-gap-1">{(content.fields || []).map((field, index) => <label key={`${field.key}-${index}`} className="cv-block cv-border-t cv-border-white/[.07] cv-py-5">
      <span className="cv-mb-2 cv-block cv-text-xs cv-font-semibold cv-text-[#78918d]">{field.key || `Seção ${index + 1}`}</span>
      <EditableTextarea value={field.value || ''} onChange={value => updateField(index, value)} aria-label={field.key || `Seção ${index + 1}`}/>
    </label>)}</div>
  </article>;
}

function BriefArtifact({artifact, editing, onChange}) {
  const content = useMemo(() => normalizeArtifactContent(artifact.content || {}, artifact.type), [artifact.content, artifact.type]);
  const fields = Array.isArray(content.fields) ? content.fields : [];
  const metadata = [
    ['Marca', content.brand || content.client || content.marca],
    ['Campanha', content.campaign || content.campaign_name || content.campaignName],
    ['Prazo', content.deadline || content.due_date || content.prazo],
    ['Investimento', content.budget || content.investment || content.verba],
    ['Status', content.status || content.readiness],
  ].filter(([, value]) => value && typeof value !== 'object');
  const images = Array.isArray(content.images) ? content.images : Array.isArray(content.assets) ? content.assets.filter(item => /image/i.test(item?.mime_type || item?.type || '')) : [];
  const updateField = (index, value) => onChange({...content, fields: fields.map((field, fieldIndex) => fieldIndex === index ? {...field, value} : field)});
  return <article className={`cv-brief-artifact${editing ? ' is-editing' : ''}`}>
    {(content.summary || metadata.length > 0) && <section className="cv-brief-artifact__overview">
      {content.summary && (editing
        ? <label className="cv-brief-artifact__summary"><span>Síntese</span><EditableTextarea value={content.summary} onChange={summary => onChange({...content, summary})} aria-label="Síntese do briefing"/></label>
        : <p className="cv-brief-artifact__summary-text">{content.summary}</p>)}
      {!!metadata.length && <dl>{metadata.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{String(value)}</dd></div>)}</dl>}
    </section>}
    <ArtifactImages images={images} label="Imagens do briefing"/>
    {!!fields.length ? <div className="cv-brief-artifact__grid">{fields.map((field, index) => <section key={`${field.key}-${index}`} className={`cv-brief-artifact__section${index === 0 ? ' is-primary' : ''}`}>
      <h3><span>{String(index + 1).padStart(2, '0')}</span>{field.key || `Seção ${index + 1}`}</h3>
      {editing ? <EditableTextarea value={field.value || ''} onChange={value => updateField(index, value)} aria-label={field.key || `Seção ${index + 1}`}/> : <BriefFieldValue value={field.value}/>}
    </section>)}</div> : <div className="cv-brief-artifact__empty">O briefing ainda não tem seções estruturadas.</div>}
  </article>;
}

function ArtifactImages({images, label = 'Imagens do material'}) {
  if (!images?.length) return null;
  return <section className="cv-brief-artifact__images" aria-label={label}>{images.map((image, index) => {
    const item = typeof image === 'string' ? {url:image} : image || {};
    const src = safeUrl(item.url || item.src || item.preview || item.path || imageSource({content:item}));
    return src ? <figure key={item.id || src}><img src={src} alt={item.alt || item.title || `Imagem de referência ${index + 1}`} loading="lazy"/>{(item.caption || item.title) && <figcaption>{item.caption || item.title}</figcaption>}</figure> : null;
  })}</section>;
}

const channelLogos = [
  [/instagram/i, 'creative-viewers/instagram.svg'], [/facebook|meta/i, 'creative-viewers/facebook.svg'],
  [/youtube/i, 'creative-viewers/youtube.svg'], [/linkedin/i, 'creative-viewers/linkedin.svg'],
  [/tiktok/i, 'canais/tiktok.png'], [/google|dv360|display & video/i, 'canais/google-dv360.svg'],
  [/spotify/i, 'canais/spotify.svg'], [/kwai/i, 'canais/kwai.svg'], [/globoplay/i, 'canais/globoplay.png'],
  [/prime video/i, 'canais/prime-video.svg'], [/waze/i, 'canais/waze.png'], [/whatsapp/i, 'canais/whatsapp.svg'],
  [/twitch/i, 'canais/twitch.svg'], [/uol/i, 'canais/uol.png'], [/eletrom[ií]dia/i, 'canais/eletromidia.svg'],
].map(([match, path]) => [match, `/static/images/${path}`]);

function ChannelMark({name}) {
  const logo = channelLogos.find(([match]) => match.test(String(name || '')))?.[1];
  return logo ? <img className="cv-content-artifact__channel-logo" src={logo} alt="" loading="lazy"/> : null;
}

function structuredHtmlContent(content, type) {
  const alreadyStructured = ['fields', 'tables', 'options', 'citations', 'rows', 'channels', 'allocations', 'highlights'].some(key => Array.isArray(content[key]) && content[key].length);
  if (alreadyStructured || !String(content.html || '').trim() || typeof DOMParser === 'undefined') return content;
  const doc = new DOMParser().parseFromString(String(content.html), 'text/html');
  const fields = [];
  const tables = [];
  const citations = Array.isArray(content.citations) ? [...content.citations] : [];
  const images = Array.isArray(content.images) ? [...content.images] : [];
  let summary = String(content.summary || '');
  let current = null;
  let sourceSection = false;
  const finishField = () => {
    if (current && current.value.trim()) fields.push({...current, value:current.value.trim()});
    current = null;
  };
  const appendField = value => {
    if (!value.trim()) return;
    if (!current) current = {key:'Conteúdo', value:''};
    current.value += `${current.value ? '\n' : ''}${value.trim()}`;
  };
  const sourceHeading = value => /fontes|refer[eê]ncias|sources|citations/i.test(value);
  for (const node of doc.body.querySelectorAll('h1,h2,h3,p,ul,ol,blockquote,table')) {
    if (/^H[1-3]$/.test(node.tagName)) {
      finishField();
      const heading = node.textContent.trim();
      sourceSection = sourceHeading(heading);
      if (!sourceSection && !(node.tagName === 'H1' && heading.toLocaleLowerCase('pt-BR') === String(content.title || '').toLocaleLowerCase('pt-BR'))) current = {key:heading || 'Seção', value:''};
      continue;
    }
    if (node.tagName === 'TABLE') {
      const rows = Array.from(node.querySelectorAll('tr'));
      const headerIndex = rows.findIndex(row => row.querySelector('th'));
      const headerRow = headerIndex >= 0 ? rows[headerIndex] : null;
      const columns = headerRow ? Array.from(headerRow.querySelectorAll('th,td')).map(cell => cell.textContent.trim()) : [];
      const bodyRows = rows.filter((_, index) => index !== headerIndex);
      const values = bodyRows.map(row => Array.from(row.querySelectorAll('th,td')).map(cell => cell.textContent.trim())).filter(row => row.length);
      if (values.length) tables.push({title:current?.key || '', columns, rows:values});
      continue;
    }
    if (sourceSection) {
      const candidates = node.matches('ul,ol') ? Array.from(node.querySelectorAll('li')) : [node];
      for (const candidate of candidates) {
        const anchor = candidate.querySelector('a[href]');
        const href = safeUrl(anchor?.getAttribute('href'));
        if (!anchor && !candidate.textContent.trim()) continue;
        citations.push({title:anchor?.textContent.trim() || candidate.textContent.trim(), url:href || '', excerpt:anchor ? candidate.textContent.replace(anchor.textContent, '').trim() : ''});
      }
      continue;
    }
    if (node.matches('ul,ol')) {
      const items = Array.from(node.querySelectorAll('li')).map(item => item.textContent.trim()).filter(Boolean);
      appendField(items.map(item => `- ${item}`).join('\n'));
    } else {
      const text = node.textContent.trim();
      if (!text) continue;
      if (!current && summary && node.tagName === 'P' && text === summary.trim()) continue;
      if (!current && !summary && node.tagName === 'P') summary = text;
      else appendField(text);
    }
  }
  finishField();
  if (!images.length) for (const image of doc.body.querySelectorAll('img[src]')) {
    const url = safeUrl(image.getAttribute('src'));
    if (url) images.push({url, alt:image.getAttribute('alt') || '', title:image.getAttribute('title') || ''});
  }
  return {...content, summary, fields, tables, citations, images};
}

function serializeStructuredHtml(content, type) {
  const sections = [];
  if (content.summary) sections.push(`<p>${escapeHtml(content.summary).replace(/\n/g, '<br/>')}</p>`);
  const images = Array.isArray(content.images) ? content.images : [];
  if (images.length) sections.push(images.map(image => {
    const item = typeof image === 'string' ? {url:image} : image || {};
    const url = safeUrl(item.url || item.src || item.preview);
    return url ? `<figure><img src="${escapeHtml(url)}" alt="${escapeHtml(item.alt || '')}">${item.caption || item.title ? `<figcaption>${escapeHtml(item.caption || item.title)}</figcaption>` : ''}</figure>` : '';
  }).join(''));
  const metrics = content.metrics || content.kpis;
  if (metrics && typeof metrics === 'object' && !Array.isArray(metrics)) {
    const entries = Object.entries(metrics).filter(([, value]) => value != null && typeof value !== 'object');
    if (entries.length) sections.push(`<table><thead><tr><th>Indicador</th><th>Valor</th></tr></thead><tbody>${entries.map(([key,value]) => `<tr><td>${escapeHtml(key.replaceAll('_',' '))}</td><td>${escapeHtml(value)}</td></tr>`).join('')}</tbody></table>`);
  }
  if (Array.isArray(content.highlights) && content.highlights.length) sections.push(`<h2>Destaques</h2><ul>${content.highlights.map(item => `<li>${escapeHtml(typeof item === 'string' ? item : item.text || item.title || item.value || '')}</li>`).join('')}</ul>`);
  (Array.isArray(content.tables) ? content.tables : []).forEach(table => {
    const rows = Array.isArray(table.rows) ? table.rows : [];
    if (!rows.length) return;
    if (table.title) sections.push(`<h2>${escapeHtml(table.title)}</h2>`);
    const columns = Array.isArray(table.columns) && table.columns.length ? table.columns : (Array.isArray(rows[0]) ? rows[0].map((_,index) => `Item ${index + 1}`) : Object.keys(rows[0] || {}));
    const cell = (row, column, index) => Array.isArray(row) ? row[index] : row?.[typeof column === 'string' ? column : column.key || column.name || column.label];
    sections.push(`<table><thead><tr>${columns.map(column => `<th>${escapeHtml(typeof column === 'string' ? column : column.label || column.name || column.key)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map((column,index) => `<td>${escapeHtml(cell(row,column,index) ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`);
  });
  (Array.isArray(content.options) ? content.options : []).forEach((option,index) => {
    const item = typeof option === 'string' ? {title:option} : option || {};
    sections.push(`<h2>${escapeHtml(item.title || `Cenário ${index + 1}`)}</h2>`);
    const body = item.summary || item.description || item.content;
    if (body) sections.push(`<p>${escapeHtml(body).replace(/\n/g, '<br/>')}</p>`);
    if (item.metrics && typeof item.metrics === 'object') sections.push(`<ul>${Object.entries(item.metrics).map(([key,value]) => `<li>${escapeHtml(key.replaceAll('_',' '))}: ${escapeHtml(value)}</li>`).join('')}</ul>`);
  });
  (Array.isArray(content.fields) ? content.fields : []).forEach(field => {
    if (field.key) sections.push(`<h2>${escapeHtml(field.key)}</h2>`);
    if (field.value) sections.push(`<p>${escapeHtml(field.value).replace(/\n/g, '<br/>')}</p>`);
  });
  (Array.isArray(content.citations) ? content.citations : []).forEach((citation,index) => {
    const item = typeof citation === 'string' ? {url:citation,title:citation} : citation || {};
    const url = safeUrl(item.url || item.href || item.link);
    sections.push(`<p>${url ? `<a href="${escapeHtml(url)}">${escapeHtml(item.title || item.source || url)}</a>` : escapeHtml(item.title || item.source || `Fonte ${index + 1}`)}${item.excerpt ? ` — ${escapeHtml(item.excerpt)}` : ''}</p>`);
  });
  const html = sections.join('\n');
  return html || `<p>${escapeHtml(type)}</p>`;
}

function ContentArtifact({artifact, editing, onChange}) {
  const normalizedContent = useMemo(() => normalizeArtifactContent(artifact.content || {}, artifact.type), [artifact.content, artifact.type]);
  const content = useMemo(() => structuredHtmlContent(normalizedContent, artifact.type), [normalizedContent, artifact.type]);
  const htmlBacked = useRef({key:'', value:false});
  const artifactKey = artifact.id || artifact.tabKey || `${artifact.type}:${artifact.title || ''}`;
  if (htmlBacked.current.key !== artifactKey) {
    htmlBacked.current = {key:artifactKey, value:Boolean(normalizedContent.html && !['fields','tables','options','citations','rows','channels','allocations','highlights'].some(key => Array.isArray(normalizedContent[key]) && normalizedContent[key].length))};
  }
  const emit = next => {
    if (!htmlBacked.current.value) return onChange(next);
    return onChange({...next, html:serializeStructuredHtml(next, artifact.type)});
  };
  const fields = Array.isArray(content.fields) ? content.fields : [];
  const images = Array.isArray(content.images) ? content.images : Array.isArray(content.assets) ? content.assets.filter(item => /image/i.test(item?.mime_type || item?.type || '')) : [];
  const updateField = (index, value) => emit({...content, fields: fields.map((field, fieldIndex) => fieldIndex === index ? {...field, value} : field)});
  const type = artifact.type;
  const metricEntries = Object.entries(content.metrics || content.kpis || {}).filter(([, value]) => value !== '' && value != null && typeof value !== 'object');
  const metricsKey = content.metrics ? 'metrics' : 'kpis';
  const tables = Array.isArray(content.tables) ? [...content.tables] : [];
  const mediaRows = content.channels || content.allocations || content.rows;
  if (type === 'media_plan' && !tables.length && Array.isArray(mediaRows) && mediaRows.length) {
    tables.push({title: 'Distribuição por canal', columns: content.columns, rows: mediaRows});
  }
  const scenarios = type === 'scenario' && Array.isArray(content.options) ? content.options : [];
  const citations = type === 'research' && Array.isArray(content.citations) ? content.citations : [];
  const highlights = type === 'executive_summary' && Array.isArray(content.highlights) ? content.highlights : [];
  const updateScenario = (index, patch) => emit({...content, options:scenarios.map((item, itemIndex) => itemIndex !== index ? item : typeof item === 'string' ? {...patch, title:patch.title ?? item} : {...item, ...patch})});
  const updateCitation = (index, patch) => emit({...content, citations:citations.map((item, itemIndex) => itemIndex !== index ? item : typeof item === 'string' ? {...patch, title:patch.title ?? item, url:item} : {...item, ...patch})});
  return <article className={`cv-content-artifact is-${type}`}>
    {(content.summary || editing && ['executive_summary', 'media_plan', 'scenario', 'research'].includes(type)) && (editing ? <EditableTextarea className="cv-content-artifact__summary-edit" aria-label="Síntese" placeholder="Síntese" value={content.summary || ''} onChange={value => emit({...content, summary:value})}/> : <p className="cv-content-artifact__summary">{content.summary}</p>)}
    <ArtifactImages images={images} label={type === 'media_plan' ? 'Imagens do plano de mídia' : 'Imagens do material'}/>
    {!!metricEntries.length && <dl className="cv-content-artifact__metrics">{metricEntries.map(([label, value]) => <div key={label}><dt>{label.replaceAll('_', ' ')}</dt><dd>{editing ? <input aria-label={label.replaceAll('_', ' ')} value={String(value)} onChange={event => emit({...content, [metricsKey]:{...content[metricsKey], [label]:event.target.value}})}/> : String(value)}</dd></div>)}</dl>}
    {(highlights.length > 0 || editing && type === 'executive_summary') && <section className="cv-content-artifact__highlights" aria-label="Destaques"><ul>{highlights.map((item, index) => <li key={item.id || index}>{editing ? <input aria-label={`Destaque ${index + 1}`} value={typeof item === 'string' ? item : item.text || item.title || item.value || ''} onChange={event => emit({...content, highlights:highlights.map((value, itemIndex) => itemIndex !== index ? value : typeof value === 'string' ? event.target.value : {...value, text:event.target.value})})}/> : typeof item === 'string' ? item : item.text || item.title || item.value}</li>)}</ul>{editing && <button type="button" onClick={() => emit({...content, highlights:[...highlights, '']})}>Adicionar destaque</button>}</section>}
    {tables.map((table, index) => <section className="cv-content-artifact__table" key={table.title || index}>{table.title && <h3>{table.title}</h3>}<ArtifactTable table={table} editing={editing} onChange={next => emit({...content, tables:tables.map((item, itemIndex) => itemIndex === index ? next : item)})}/></section>)}
    {(scenarios.length > 0 || editing && type === 'scenario') && <section className="cv-content-artifact__scenario-grid" aria-label="Cenários comparados">{scenarios.map((scenario, index) => <section key={scenario.id || scenario.title || index}>
      {editing ? <input aria-label={`Nome do cenário ${index + 1}`} value={typeof scenario === 'string' ? scenario : scenario.title || ''} onChange={event => updateScenario(index, {title:event.target.value})}/> : <h3>{typeof scenario === 'string' ? scenario : scenario.title || `Cenário ${index + 1}`}</h3>}
      {(editing || typeof scenario !== 'string' && (scenario.summary || scenario.description || scenario.content)) && (editing ? <EditableTextarea aria-label={`Descrição do cenário ${index + 1}`} value={typeof scenario === 'string' ? '' : scenario.summary || scenario.description || scenario.content || ''} onChange={value => updateScenario(index, {summary:value})}/> : <ContentFieldValue value={scenario.summary || scenario.description || scenario.content}/>)}
      {typeof scenario !== 'string' && scenario.metrics && <dl>{Object.entries(scenario.metrics).filter(([, value]) => value != null && typeof value !== 'object').map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{editing ? <input aria-label={`${scenario.title || `Cenário ${index + 1}`}: ${key.replaceAll('_', ' ')}`} value={String(value)} onChange={event => updateScenario(index, {metrics:{...scenario.metrics, [key]:event.target.value}})}/> : String(value)}</dd></div>)}</dl>}
    </section>)}{editing && <button type="button" onClick={() => emit({...content, options:[...scenarios, {title:'', summary:''}]})}>Adicionar cenário</button>}</section>}
    {!!fields.length && <div className="cv-content-artifact__sections">{fields.map((field, index) => <section className={`cv-content-artifact__section is-${type}`} key={`${field.key}-${index}`}>
      <h3>{field.key || `Seção ${index + 1}`}</h3>
      {editing ? <EditableTextarea value={field.value || ''} onChange={value => updateField(index, value)} aria-label={field.key || `Seção ${index + 1}`}/> : <><ChannelMark name={field.key}/><ContentFieldValue value={field.value}/></>}
    </section>)}</div>}
    {(citations.length > 0 || editing && type === 'research') && <section className="cv-content-artifact__citations"><h3>Fontes consultadas</h3><ol>{citations.map((citation, index) => {
      const item = typeof citation === 'string' ? {url:citation, title:citation} : citation || {};
      const href = safeUrl(item.url || item.href || item.link);
      const title = item.title || item.source || item.publisher || href || `Fonte ${index + 1}`;
      return <li key={item.id || href || `${title}-${index}`}>{editing ? <div className="cv-content-artifact__citation-edit"><input aria-label={`Título da fonte ${index + 1}`} value={item.title || item.source || ''} placeholder="Título da fonte" onChange={event => updateCitation(index, {title:event.target.value})}/><input aria-label={`URL da fonte ${index + 1}`} value={item.url || item.href || item.link || ''} placeholder="https://" onChange={event => updateCitation(index, {url:event.target.value})}/><textarea aria-label={`Trecho da fonte ${index + 1}`} value={item.excerpt || ''} placeholder="Trecho ou observação" onChange={event => updateCitation(index, {excerpt:event.target.value})}/></div> : <>{href ? <a href={href} target="_blank" rel="noreferrer">{title}</a> : <span>{title}</span>}{item.date && <time>{String(item.date)}</time>}{item.excerpt && <p>{item.excerpt}</p>}</>}</li>;
    })}</ol>{editing && <button type="button" className="cv-content-artifact__add-citation" onClick={() => emit({...content, citations:[...citations, {title:'', url:'', excerpt:''}]})}>Adicionar fonte</button>}</section>}
    {!fields.length && !tables.length && !scenarios.length && !citations.length && !highlights.length && !content.summary && !metricEntries.length && !(editing && ['executive_summary', 'scenario', 'research'].includes(type)) && <div className="cv-content-artifact__empty">Este material ainda não tem conteúdo.</div>}
  </article>;
}

function ContentFieldValue({value}) {
  if (Array.isArray(value)) {
    if (value.every(item => ['string', 'number'].includes(typeof item))) return value.length ? <ul>{value.map((item, index) => <li key={`${index}-${item}`}>{String(item)}</li>)}</ul> : <p className="cv-content-artifact__empty-value">A definir</p>;
    return <ArtifactTable table={{rows:value}}/>;
  }
  const text = String(value ?? '').trim();
  if (!text) return <p className="cv-content-artifact__empty-value">A definir</p>;
  const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  if (lines.length > 1 && lines.every(line => /^[-*•▪]\s+/.test(line))) return <ul>{lines.map((line,index) => <li key={`${index}-${line}`}>{line.replace(/^[-*•▪]\s+/, '')}</li>)}</ul>;
  return <p>{text}</p>;
}

function ArtifactTable({table, editing = false, onChange}) {
  const columns = Array.isArray(table?.columns) ? table.columns : [];
  const rows = Array.isArray(table?.rows) ? table.rows : [];
  if (!rows.length) return null;
  const inferredColumns = columns.length ? columns : Array.isArray(rows[0]) ? rows[0].map((_, index) => `Item ${index + 1}`) : Object.keys(rows[0] || {});
  return <div className="cv-content-artifact__table-scroll"><table><thead><tr>{inferredColumns.map((column, index) => <th key={`${column}-${index}`}>{typeof column === 'string' ? column : column.label || column.name}</th>)}</tr></thead><tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{inferredColumns.map((column, columnIndex) => {
    const key = typeof column === 'string' ? column : column.key || column.name || column.label;
    const value = Array.isArray(row) ? row[columnIndex] : row?.[key] ?? row?.[column.key];
    const channelCell = /channel|canal|plataforma/i.test(String(key));
    const update = nextValue => {
      const nextRows = rows.map((item, itemIndex) => itemIndex !== rowIndex ? item : Array.isArray(item)
        ? item.map((cell, cellIndex) => cellIndex === columnIndex ? nextValue : cell)
        : {...item, [key]:nextValue});
      onChange?.({...table, rows:nextRows});
    };
    return <td key={`${key}-${columnIndex}`}>{editing ? <input aria-label={`${typeof key === 'string' ? key : 'Campo'}, linha ${rowIndex + 1}`} value={value ?? ''} onChange={event => update(event.target.value)}/> : <span className={channelCell ? 'cv-content-artifact__channel-cell' : ''}>{channelCell && <ChannelMark name={value} />}{value == null || value === '' ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>}</td>;
  })}</tr>)}</tbody></table></div>;
}

function BriefFieldValue({value}) {
  const raw = String(value || '').trim();
  if (!raw) return <p className="cv-brief-artifact__missing">A definir</p>;
  const items = raw.split(/\n|\s*[•▪]\s*|\s*;\s*/).map(item => item.replace(/^[-*]\s*/, '').trim()).filter(Boolean);
  if (items.length > 1) return <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>;
  return <p>{raw}</p>;
}

const meetingSectionAliases = {
  participantes: ['participantes', 'presentes', 'pessoas'],
  contexto: ['contexto', 'objetivo', 'assunto'],
  decisoes: ['decisões', 'decisoes', 'decisões tomadas'],
  encaminhamentos: ['encaminhamentos', 'próximos passos', 'proximos passos', 'ações', 'acoes'],
  pendencias: ['pendências', 'pendencias', 'pontos em aberto'],
};

function meetingFieldKind(key = '') {
  const normalized = String(key).trim().toLocaleLowerCase('pt-BR');
  return Object.entries(meetingSectionAliases).find(([, aliases]) => aliases.includes(normalized))?.[0] || 'other';
}

function meetingMetadataEntries(content = {}) {
  const displayDate = value => {
    const raw = String(value || '').trim();
    const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return raw;
    return new Intl.DateTimeFormat('pt-BR', {dateStyle: 'medium'}).format(new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  };
  const people = content.participants || content.attendees || content.shared_with || content.collaborators || content.people;
  const peopleText = Array.isArray(people)
    ? people.map(person => typeof person === 'string' ? person : person?.name || person?.display_name || person?.email).filter(Boolean).join(', ')
    : String(people || '').trim();
  return [
    {label: 'Data', value: displayDate(content.date || content.meeting_date || content.scheduled_at), icon: 'calendar'},
    {label: 'Prazo', value: displayDate(content.deadline || content.due_date || content.prazo), icon: 'clock'},
    {label: 'Pessoas', value: peopleText, icon: 'users'},
  ].filter(item => item.value);
}

function MeetingSummaryArtifact({artifact, editing, onChange}) {
  const content = useMemo(() => normalizeArtifactContent(artifact.content || {}, artifact.type), [artifact.content, artifact.type]);
  const fields = Array.isArray(content.fields) ? content.fields : [];
  const metadata = meetingMetadataEntries(content);
  const updateSummary = summary => onChange({...content, summary});
  const updateField = (index, value) => onChange({...content, fields: fields.map((field, fieldIndex) => fieldIndex === index ? {...field, value} : field)});
  return <article className={`cv-meeting-summary is-${artifact.type} cv-mx-auto cv-w-full cv-max-w-[820px]`}>
    <header className="cv-meeting-summary__intro">
      <span><Icon name="calendar" size={15}/>{artifact.type === 'meeting_agenda' ? 'Pauta da reunião' : 'Registro da reunião'}</span>
      {editing ? <EditableTextarea value={content.summary || ''} onChange={updateSummary} placeholder="Escreva uma síntese objetiva da reunião." aria-label={artifact.type === 'meeting_agenda' ? 'Objetivo da reunião' : 'Síntese da reunião'}/> : <h1>{content.summary || artifact.title}</h1>}
    </header>
    {!!metadata.length && <dl className="cv-meeting-summary__metadata" aria-label="Data, prazo e pessoas da reunião">{metadata.map(item => <div key={item.label}><dt><Icon name={item.icon} size={15}/>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>}
    <div className="cv-meeting-summary__sections">
      {fields.map((field, index) => {
        const kind = meetingFieldKind(field.key);
        return <section key={`${field.key}-${index}`} className={`cv-meeting-summary__section is-${kind}`}>
          <h3>{field.key || `Seção ${index + 1}`}</h3>
          {editing ? <EditableTextarea value={field.value || ''} onChange={value => updateField(index, value)} placeholder="Adicione as informações confirmadas." aria-label={field.key || `Seção ${index + 1}`}/> : <ContentFieldValue value={field.value}/>}
        </section>;
      })}
      {!fields.length && <p className="cv-meeting-summary__empty">O resumo ainda não possui decisões, responsáveis ou próximos passos registrados.</p>}
    </div>
  </article>;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
}

function providerEnvelopeText(value) {
  let current = value;
  let insideEnvelope = false;
  for (let depth = 0; depth < 8; depth += 1) {
    if (typeof current === 'string') {
      const clean = current.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
      try {
        const decoded = JSON.parse(clean);
        if (decoded !== current) {
          if (decoded && typeof decoded === 'object') insideEnvelope = true;
          current = decoded;
          continue;
        }
      } catch (_) { return insideEnvelope ? current : null; }
    }
    if (!current || typeof current !== 'object') return null;
    const patch = current.artifact_patch && typeof current.artifact_patch === 'object' ? current.artifact_patch : {};
    const candidates = [
      current.text?.content, current.answer, current.content,
      current.output, current.structured_output, current.data,
      patch.html, patch.summary,
    ];
    const next = candidates.find(candidate => typeof candidate === 'string' || (candidate && typeof candidate === 'object'));
    if (next == null) return null;
    current = next;
  }
  return null;
}

function documentHtml(content) {
  if (content.html) {
    const raw = typeof content.html === 'string' ? content.html : JSON.stringify(content.html);
    const clean = raw.trim();
    const visible = providerEnvelopeText(clean)
      || providerEnvelopeText(new DOMParser().parseFromString(raw, 'text/html').body.textContent?.trim() || '');
    if (visible) {
      const repaired = normalizeArtifactContent(visible, 'document');
      if (repaired.html) return repaired.html;
    }
    if (clean.startsWith('{') || clean.startsWith('"{')) {
      try {
        let decoded = JSON.parse(clean);
        if (typeof decoded === 'string') decoded = JSON.parse(decoded);
        const visible = decoded?.text?.content || decoded?.answer;
        if (typeof visible === 'string' && visible.trim()) {
          return visible.trim().split(/\n\s*\n/).map(part => `<p>${escapeHtml(part).replace(/\n/g, '<br/>')}</p>`).join('');
        }
        return '<p><br/></p>';
      } catch (_) {
        // An incomplete protocol envelope must not become editable content.
        if (/^\s*["']?\s*\{\s*"(?:text|ui|answer|artifact_patch)"/i.test(clean)) return '<p><br/></p>';
      }
    }
    return raw;
  }
  const sections = [];
  if (content.summary) sections.push(`<p>${escapeHtml(content.summary)}</p>`);
  (content.fields || []).forEach(field => {
    if (field?.key) sections.push(`<h2>${escapeHtml(field.key)}</h2>`);
    if (field?.value) sections.push(`<p>${escapeHtml(field.value).replace(/\n/g, '<br/>')}</p>`);
  });
  return sections.join('') || '<p><br/></p>';
}

function downloadTextArtifact(artifact, format) {
  const html = artifact.type === 'html' ? htmlDocument(artifact.content || {}, artifact.title) : documentHtml(artifact.content || {});
  const plain = new DOMParser().parseFromString(html, 'text/html').body.textContent?.trim() || '';
  const title = String(artifact.title || 'documento').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9_-]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase() || 'documento';
  const markdown = artifact.type === 'html' ? `# ${artifact.title || 'Documento'}\n\n${plain}` : `# ${artifact.title || 'Documento'}\n\n${plain}`;
  const data = format === 'html' ? html : format === 'md' ? markdown : plain;
  const blob = new Blob([data], {type: format === 'html' ? 'text/html;charset=utf-8' : 'text/plain;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = `${title}.${format}`; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function cleanDocumentHtml(html) {
  const doc = new DOMParser().parseFromString(String(html || ''), 'text/html');
  const allowed = new Set(['P', 'BR', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'STRONG', 'B', 'EM', 'I', 'U', 'S', 'BLOCKQUOTE', 'UL', 'OL', 'LI', 'A', 'IMG', 'TABLE', 'THEAD', 'TBODY', 'TFOOT', 'TR', 'TH', 'TD', 'DIV', 'SPAN', 'PRE', 'CODE', 'HR', 'SUP', 'SUB']);
  const discard = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'FORM', 'META', 'LINK', 'SVG', 'MATH', 'TEMPLATE', 'INPUT', 'BUTTON', 'TEXTAREA', 'SELECT', 'VIDEO', 'AUDIO']);
  const visit = node => {
    for (const child of Array.from(node.children)) {
      if (discard.has(child.tagName)) { child.remove(); continue; }
      visit(child);
      if (!allowed.has(child.tagName)) { child.replaceWith(...Array.from(child.childNodes)); continue; }
      for (const attribute of Array.from(child.attributes)) child.removeAttribute(attribute.name);
    }
  };
  // Keep only document formatting and safe links/images, never executable markup.
  const links = Array.from(doc.body.querySelectorAll('a')).map(node => [node, node.getAttribute('href')]);
  const images = Array.from(doc.body.querySelectorAll('img')).map(node => [node, node.getAttribute('src'), node.getAttribute('alt')]);
  visit(doc.body);
  for (const [node, raw] of links) {
    if (!node.isConnected) continue;
    const url = safeUrl(raw);
    if (url) { node.setAttribute('href', url); node.setAttribute('rel', 'noopener noreferrer'); node.setAttribute('target', '_blank'); }
  }
  for (const [node, raw, alt] of images) {
    if (!node.isConnected) continue;
    const imageData = /^data:image\/(?:png|jpeg|webp|gif);base64,[a-z0-9+/=]+$/i.test(raw || '');
    const url = imageData ? raw : safeUrl(raw);
    if (url) node.setAttribute('src', url);
    if (alt) node.setAttribute('alt', alt);
  }
  return doc.body.innerHTML;
}

function RichDocumentArtifact({artifact, onChange, editing = false}) {
  const content = useMemo(() => normalizeArtifactContent(artifact.content || {}, artifact.type), [artifact.content, artifact.type]);
  const canvas = useRef(null);
  const urlInput = useRef(null);
  const [urlRequest, setUrlRequest] = useState(null);
  const html = useMemo(() => cleanDocumentHtml(documentHtml(content)), [content]);
  const reading = useMemo(() => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const sections = Array.from(doc.body.querySelectorAll('h1,h2,h3')).map((node, index) => {
      const id = `cadu-section-${index}`;
      node.id = id;
      return {id, title: node.textContent?.trim() || `Seção ${index + 1}`, level: node.tagName};
    });
    return {html: doc.body.innerHTML, sections};
  }, [html]);
  useEffect(() => {
    if (!canvas.current || canvas.current.innerHTML === html) return;
    if (document.activeElement !== canvas.current) canvas.current.innerHTML = html;
  }, [artifact.id, html]);
  const emit = () => onChange({...content, html: cleanDocumentHtml(canvas.current?.innerHTML || '')});
  const command = (name, value = null) => {
    canvas.current?.focus();
    document.execCommand(name, false, value);
    emit();
  };
  const applyUrl = event => {
    event.preventDefault();
    const url = safeUrl(new FormData(event.currentTarget).get('url'));
    if (!url) return;
    command(urlRequest === 'image' ? 'insertImage' : 'createLink', url);
    setUrlRequest(null);
  };
  const pasteIntoDocument = event => {
    const image = Array.from(event.clipboardData?.items || []).find(item => item.type.startsWith('image/'));
    if (!image) {
      const pastedHtml = event.clipboardData?.getData('text/html');
      if (pastedHtml) {
        event.preventDefault();
        command('insertHTML', cleanDocumentHtml(pastedHtml));
      }
      return;
    }
    const file = image.getAsFile();
    if (!file) return;
    event.preventDefault();
    const reader = new FileReader();
    reader.onload = () => command('insertImage', String(reader.result || ''));
    reader.readAsDataURL(file);
  };
  const addTable = () => {
    command('insertHTML', '<table><thead><tr><th>Item</th><th>Valor</th><th>Observação</th></tr></thead><tbody><tr><td>Exemplo</td><td>—</td><td>Edite este campo</td></tr><tr><td>Outro item</td><td>—</td><td>Edite este campo</td></tr></tbody></table><p><br></p>');
  };
  if (!editing) return <div className={`cv-artifact-reading is-${artifact.type || 'document'}`}>
    {reading.sections.length > 1 && <nav className="cv-artifact-reading__toc" aria-label="Seções do documento"><strong>Neste material</strong>{reading.sections.map(section => <a key={section.id} className={section.level === 'H3' ? 'is-nested' : ''} href={`#${section.id}`}>{section.title}</a>)}</nav>}
    <article className="cv-rich-document cv-rich-document--reading cv-mx-auto cv-w-full cv-max-w-[860px] cv-px-6 cv-py-5 md:cv-px-8 md:cv-py-6"><div className="cv-rich-document__canvas" dangerouslySetInnerHTML={{__html: reading.html}}/></article>
  </div>;
  return <article className={`cv-rich-document is-${artifact.type || 'document'} cv-mx-auto cv-w-full cv-max-w-[860px] cv-px-6 cv-py-5 md:cv-px-8 md:cv-py-6`}>
    <div className="cv-rich-document__toolbar" role="toolbar" aria-label="Formatação do documento" onMouseDown={event => event.preventDefault()}>
      <button type="button" onClick={() => command('undo')} aria-label="Desfazer última edição" title="Desfazer"><Icon name="undo" size={16}/></button>
      <button type="button" onClick={() => command('redo')} aria-label="Refazer edição" title="Refazer"><Icon name="redo" size={16}/></button>
      <button type="button" onClick={() => command('bold')} aria-label="Negrito"><b>B</b></button>
      <button type="button" onClick={() => command('italic')} aria-label="Itálico"><i>I</i></button>
      <button type="button" onClick={() => command('formatBlock', 'h2')} aria-label="Título de seção">H2</button>
      <button type="button" onClick={() => command('formatBlock', 'blockquote')} aria-label="Citação" title="Citação"><Icon name="quote" size={16}/></button>
      <button type="button" onClick={() => command('insertUnorderedList')} aria-label="Lista" title="Lista"><Icon name="list" size={16}/></button>
      <button type="button" onClick={() => setUrlRequest('link')} aria-label="Adicionar link" title="Adicionar link"><Icon name="link" size={16}/></button>
      <button type="button" onClick={addTable} aria-label="Inserir tabela" title="Inserir tabela"><Icon name="table" size={16}/></button>
      <button type="button" onClick={() => setUrlRequest('image')} aria-label="Adicionar imagem" title="Adicionar imagem"><Icon name="image" size={16}/></button>
    </div>
    <div ref={canvas} className="cv-rich-document__canvas" contentEditable suppressContentEditableWarning onInput={emit} onBlur={emit} onPaste={pasteIntoDocument} dangerouslySetInnerHTML={{__html: html}} role="textbox" aria-label="Texto do documento"/>
    <p className="cv-rich-document__hint">Cole textos, links e imagens diretamente · salvamento automático</p>
    {urlRequest && <CaduDialog label={urlRequest === 'image' ? 'Adicionar imagem' : 'Adicionar link'} initialFocusRef={urlInput} onClose={() => setUrlRequest(null)} className="cv-dialog cv-artifact-url-dialog">
      <form onSubmit={applyUrl}>
        <header><div><h2>{urlRequest === 'image' ? 'Adicionar imagem' : 'Adicionar link'}</h2><p>Cole um endereço HTTPS válido.</p></div><button type="button" onClick={() => setUrlRequest(null)} aria-label="Fechar"><Icon name="close" size={18}/></button></header>
        <label>Endereço<input ref={urlInput} name="url" type="url" inputMode="url" required pattern="https://.*" placeholder="https://" autoComplete="url"/></label>
        <footer><button type="button" onClick={() => setUrlRequest(null)}>Cancelar</button><button type="submit" className="is-primary">Adicionar</button></footer>
      </form>
    </CaduDialog>}
  </article>;
}

function HtmlArtifact({artifact}) {
  const content = artifact.content || {};
  if (!String(content.html || '').trim()) {
    const malformed = /^\s*(?:```(?:json)?\s*)?\{\s*"(?:text|ui|answer|artifact_patch)"/i.test(String(content.summary || ''));
    return <div className="cv-artifact-loading is-failed" role="alert"><strong>{malformed ? 'A geração retornou um formato inválido' : 'Esta página não possui conteúdo'}</strong><span>{malformed ? 'O sistema preservou a versão para diagnóstico, mas ela não pode ser renderizada. Peça ao Cadu para regenerar o HTML completo.' : 'O HTML desta versão não foi gerado. Peça ao Cadu para criar novamente o dashboard.'}</span></div>;
  }
  return <iframe title={artifact.title || 'Página interativa'} sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={htmlDocument(content, artifact.title)} className="cv-h-full cv-w-full cv-border-0 cv-bg-white"/>;
}

function imageSource(artifact) {
  const content = artifact?.content || {};
  return safeUrl(content.url || content.image_url || content.src);
}

function imageFileName(artifact) {
  const content = artifact?.content || {};
  const explicit = content.filename || content.file_name || artifact?.filename;
  if (explicit) return String(explicit);
  const title = String(artifact?.title || content.title || '').trim();
  if (title && !/^ativo da marca$/i.test(title)) return title;
  const src = imageSource(artifact);
  if (src) {
    try {
      const pathname = new URL(src, window.location.origin).pathname;
      const candidate = decodeURIComponent(pathname.split('/').filter(Boolean).pop() || '');
      if (candidate) return candidate;
    } catch (_) { /* A URL já foi validada por safeUrl. */ }
  }
  return 'imagem.png';
}

function imageStudioLink(artifact, studioEditorUrl, projectRef, mode = 'select', prompt = '') {
  const content = artifact.content || {};
  const src = imageSource(artifact);
  if (!src || !studioEditorUrl) return '';
  const url = new URL(studioEditorUrl, window.location.origin);
  url.searchParams.set('source_url', src);
  url.searchParams.set('source_title', imageFileName(artifact) || content.alt || 'Imagem de referência');
  url.searchParams.set('editor_mode', mode);
  if (prompt) url.searchParams.set('instruction', prompt);
  const projectId = String(projectRef || '').replace(/^ci:/, '');
  if (projectId) url.searchParams.set('project_id', projectId);
  return url.href;
}

function ImageArtifact({artifact}) {
  const content = artifact.content || {};
  const src = imageSource(artifact);
  const [imageMetadata, setImageMetadata] = useState(null);
  useEffect(() => {
    const knownBytes = Number(content.file_size || content.size || artifact.file_size || artifact.size || 0);
    setImageMetadata(current => ({
      width: Number(content.width || artifact.width || current?.width || 0),
      height: Number(content.height || artifact.height || current?.height || 0),
      bytes: knownBytes || current?.bytes || 0,
      mime: content.mime_type || content.content_type || artifact.mime_type || current?.mime || '',
    }));
    if (!src || knownBytes) return undefined;
    const controller = new AbortController();
    fetch(src, {method: 'HEAD', credentials: 'same-origin', signal: controller.signal}).then(response => {
      if (!response.ok) return;
      setImageMetadata(current => ({...(current || {}), bytes: Number(response.headers.get('content-length') || 0), mime: response.headers.get('content-type') || ''}));
    }).catch(() => {});
    return () => controller.abort();
  }, [artifact.file_size, artifact.height, artifact.size, artifact.width, content.content_type, content.file_size, content.height, content.mime_type, content.size, content.width, src]);
  const reportMetadata = event => setImageMetadata(current => ({
    ...(current || {}),
    width: event.currentTarget.naturalWidth,
    height: event.currentTarget.naturalHeight,
    bytes: Number(content.file_size || content.size || artifact.file_size || artifact.size || current?.bytes || 0),
    mime: content.mime_type || content.content_type || artifact.mime_type || current?.mime || '',
  }));
  return <div className="cv-image-artifact">
    {src ? <figure><img src={src} alt={content.alt || imageFileName(artifact)} onLoad={reportMetadata}/><figcaption className="cv-image-metadata" aria-label="Informações da imagem"><span>{imageMetadata?.width && imageMetadata?.height ? `${imageMetadata.width} × ${imageMetadata.height} px` : 'Imagem'}</span><span>{imageMetadata?.width && imageMetadata?.height ? `${((imageMetadata.width * imageMetadata.height) / 1000000).toLocaleString('pt-BR', {maximumFractionDigits: 1})} MP` : ''}</span><span>{formatFileSize(imageMetadata?.bytes)}</span></figcaption></figure> : <p>A imagem ainda não está disponível.</p>}
  </div>;
}

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (!value) return 'Não informado';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toLocaleString('pt-BR', {maximumFractionDigits: 1})} MB`;
}

function compactArtifactTitle(artifact) {
  return artifact?.type === 'image' ? imageFileName(artifact) : String(artifact?.title || 'Entrega').trim();
}

function artifactTabIcon(artifact) {
  const content = artifact?.content || {};
  const haystack = `${artifact?.title || ''} ${content.provider || ''} ${content.url || content.editor_url || ''}`.toLowerCase();
  if (haystack.includes('drive.google.com') || haystack.includes('google drive')) return 'drive';
  if (artifact?.type === 'image') return 'image';
  if (artifact?.type === 'html') return 'browser';
  if (artifact?.type === 'spreadsheet') return 'table';
  if (artifact?.type === 'link_reader' || /^https?:/i.test(content.url || '')) return 'link';
  if (artifact?.type === 'project_map' || artifact?.type === 'library' || artifact?.type === 'project_profile') return 'folder';
  if (artifact?.type === 'brand_identity') return 'brand';
  if (artifact?.type === 'meeting_summary' || artifact?.type === 'meeting_agenda') return 'calendar';
  return 'file';
}

function artifactBrowserUrl(artifact, publishedUrl = '') {
  const content = artifact?.content || {};
  return safeUrl(
    publishedUrl
    || artifact?.published_url
    || artifact?.public_url
    || content.published_url
    || content.public_url
    || content.editor_url
    || content.download_url
    || content.url
    || content.image_url
    || content.src,
  );
}

function ResourceArtifact({artifact}) {
  const content = artifact.content || {};
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { setCreating(false); setCreated(null); setError(''); }, [artifact.title, content.editable_copy_url]);
  const editor = safeUrl(created?.editor_url || content.editor_url || content.url);
  const download = safeUrl(content.download_url);
  const editableCopy = safeUrl(content.editable_copy_url);
  const project = safeUrl(content.project_href);
  const createCopy = async () => {
    if (!editableCopy || creating) return;
    setCreating(true); setError('');
    try {
      const data = await request(editableCopy, {method: 'POST', headers: {'X-CSRF-Token': csrf()}});
      setCreated(data.document || null);
    } catch (reason) { setError(reason.message); }
    finally { setCreating(false); }
  };
  return <article className="cv-link-reader cv-mx-auto cv-flex cv-h-full cv-w-full cv-max-w-[720px] cv-flex-col cv-justify-center cv-p-8 md:cv-p-12">
    <span className="cv-grid cv-h-11 cv-w-11 cv-place-items-center cv-rounded-xl cv-bg-teal/10 cv-text-teal"><Icon name="file" size={20}/></span>
    <h3 className="cv-mb-0 cv-mt-5 cv-text-xl cv-font-semibold cv-tracking-[-.02em]">{artifact.title}</h3>
    <p className="cv-mb-0 cv-mt-2 cv-text-sm cv-leading-6 cv-text-[#819b97]">{content.detail || `${content.kind || 'Arquivo'} conectado a esta conversa.`}</p>
    <div className="cv-mt-6 cv-flex cv-flex-wrap cv-gap-2">
      {editor && <a href={editor} target="_blank" rel="noreferrer" className="cv-rounded-lg cv-bg-teal cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#052522] cv-no-underline">{created ? 'Abrir documento editável' : 'Abrir arquivo'}</a>}
      {!created && editableCopy && <button type="button" onClick={createCopy} disabled={creating} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold disabled:cv-opacity-50">{creating ? 'Preparando…' : 'Criar versão editável'}</button>}
      {download && download !== editor && <a href={download} className="cv-rounded-lg cv-border cv-border-white/10 cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#c4d5d2] cv-no-underline">Baixar</a>}
      {!editor && !editableCopy && !download && project && <a href={project} className="cv-rounded-lg cv-bg-teal cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#052522] cv-no-underline">{content.project_link_label || 'Ver no projeto'}</a>}
    </div>
    {created && <p className="cv-mb-0 cv-mt-4 cv-text-xs cv-text-teal" role="status">Versão editável criada no Workspace.</p>}
    {error && <p className="cv-mb-0 cv-mt-4 cv-text-xs cv-leading-5 cv-text-[#ff9ca1]" role="alert">{error}</p>}
    {!editor && !editableCopy && !download && <p className="cv-mb-0 cv-mt-5 cv-text-xs cv-text-[#819b97]">Este arquivo está disponível apenas como referência nesta conversa.</p>}
  </article>;
}

function LinkReaderArtifact({artifact, onRequestSummary, onSaveReference, onRequestMeetingPlan}) {
  const content = artifact.content || {};
  const url = safeUrl(content.url);
  let domain = '';
  try { domain = url ? new URL(url).hostname.replace(/^www\./, '') : ''; } catch (_) {}
  const isGoogle = /(^|\.)google\.com$|googleusercontent\.com$/i.test(domain);
  const isMeeting = /meet\.google\.com|calendar\.google\.com/i.test(domain) || /meet|calendar|reuni[aã]o/i.test(String(content.kind || content.provider || ''));
  const access = content.access_mode || (isGoogle ? 'referência Google' : 'link público');
  const isPublic = content.access_type === 'public' || /p[uú]blico/i.test(String(content.kind || content.access_mode || '')) || (!isGoogle && Boolean(url));
  let embedded = isPublic ? url : '';
  if (/youtu\.be|youtube\.com/i.test(domain)) {
    try {
      const parsed = new URL(url);
      const videoId = domain === 'youtu.be' ? parsed.pathname.slice(1) : parsed.searchParams.get('v');
      if (videoId) embedded = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}`;
    } catch (_) {}
  }
  if (/docs\.google\.com/i.test(domain)) {
    embedded = url.replace(/\/(edit|view)(?:\?.*)?$/i, '/preview');
  }
  if (/drive\.google\.com/i.test(domain)) {
    const file = url.match(/\/file\/d\/([^/]+)/i);
    const folder = url.match(/\/(?:drive\/)?folders\/([^/?]+)/i);
    if (file) embedded = `https://drive.google.com/file/d/${encodeURIComponent(file[1])}/preview`;
    else if (folder) embedded = `https://drive.google.com/embeddedfolderview?id=${encodeURIComponent(folder[1])}#list`;
  }
  if (embedded) return <article className="cv-link-embed cv-flex cv-h-full cv-min-h-0 cv-w-full cv-flex-col">
    <header className="cv-link-embed__bar">
      <span><Icon name="external" size={15}/><b>{artifact.title || domain}</b><small>{domain}</small></span>
      <div>{!isGoogle && !isMeeting && <button type="button" onClick={() => onRequestSummary?.(url)}>Resumir</button>}<button type="button" onClick={() => onSaveReference?.(url)}>Salvar referência</button><a href={url} target="_blank" rel="noreferrer">Abrir fora</a></div>
    </header>
    <iframe title={artifact.title || domain || 'Link público'} src={embedded} sandbox="allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox" referrerPolicy="strict-origin-when-cross-origin" className="cv-link-embed__frame"/>
    <footer>Se o site bloquear a visualização incorporada, use “Abrir fora”.</footer>
  </article>;
  return <article className="cv-mx-auto cv-flex cv-h-full cv-w-full cv-max-w-[720px] cv-flex-col cv-justify-center cv-p-8 md:cv-p-12">
    <span className="cv-grid cv-h-11 cv-w-11 cv-place-items-center cv-rounded-xl cv-bg-teal/10 cv-text-teal"><Icon name="external" size={20}/></span>
    <span className="cv-mt-5 cv-text-xs cv-font-semibold cv-text-[#78cfc3]">{access}</span>
    <h3 className="cv-mb-0 cv-mt-2 cv-text-xl cv-font-semibold cv-tracking-[-.02em]">{artifact.title || 'Link externo'}</h3>
    <p className="cv-mb-0 cv-mt-2 cv-text-sm cv-leading-6 cv-text-[#819b97]">{domain || 'Endereço externo'}{content.detail ? ` · ${content.detail}` : ''}</p>
    {content.thumbnail && <img src={safeUrl(content.thumbnail)} alt="" className="cv-mt-6 cv-max-h-52 cv-w-full cv-rounded-xl cv-object-cover"/>}
    {isMeeting && <section className="cv-meeting-note cv-mt-6"><strong className="cv-block cv-text-sm">Reunião no projeto</strong><p className="cv-mb-0 cv-mt-1 cv-text-xs cv-leading-5 cv-text-[#99b4af]">Organize pauta, decisões e próximos passos. A participação automática em chamadas não é iniciada por este fluxo.</p></section>}
    <div className="cv-mt-6 cv-grid cv-gap-2">
      {url && <a href={url} target="_blank" rel="noreferrer" className="cv-rounded-lg cv-bg-teal cv-px-4 cv-py-2.5 cv-text-center cv-text-xs cv-font-semibold cv-text-[#052522] cv-no-underline">Abrir endereço original</a>}
      {url && <button type="button" onClick={() => onSaveReference?.(url)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold">Salvar como referência</button>}
      {isMeeting && url && <button type="button" onClick={() => onRequestMeetingPlan?.(url)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold">Preparar reunião</button>}
      {!isGoogle && !isMeeting && url && <button type="button" onClick={() => onRequestSummary?.(url)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold">Abrir e resumir</button>}
    </div>
    <p className="cv-mb-0 cv-mt-4 cv-text-xs cv-leading-5 cv-text-[#71908b]">{isGoogle ? 'Você pode guardar o link mesmo sem integração. Para conteúdo privado, o Google poderá solicitar acesso.' : 'O conteúdo só será extraído depois de escolher “Abrir e resumir”.'}</p>
  </article>;
}

function tokenValue(value) {
  if (typeof value === 'string') return {value, label: value};
  if (!value || typeof value !== 'object') return null;
  const token = value.hex || value.value || value.color || value.family || value.name;
  if (!token) return null;
  return {value: String(token), label: value.role || value.usage || value.name || String(token)};
}

function BrandIdentityArtifact({artifact}) {
  const content = artifact.content || {};
  const logo = safeUrl(content.logo_url);
  const details = (content.details || []).filter(detail => detail?.value && !/^Ainda não definido\.?$/i.test(String(detail.value).trim()));
  const colors = (content.colors || []).map(tokenValue).filter(Boolean);
  const fonts = (content.fonts || []).map(tokenValue).filter(Boolean);
  const hasIdentitySignals = Boolean(logo || content.colors?.length);
  const auditLabel = content.audit_status ? 'Refazer auditoria da marca' : 'Reavaliar auditoria da marca';
  return <article className="cv-brand-identity cv-mx-auto cv-w-full cv-max-w-[720px] cv-p-8 md:cv-p-12">
    <div className="cv-brand-identity__actions"><span>Ações da marca</span><div>{content.website_url && <a href={safeUrl(content.website_url)} target="_blank" rel="noreferrer">Site</a>}{content.audit_url && <a href={safeUrl(content.audit_url)}>{auditLabel}</a>}</div></div>
    <header className="cv-brand-identity__header cv-flex cv-items-center cv-gap-4"><span className="cv-grid cv-h-16 cv-w-16 cv-place-items-center cv-overflow-hidden cv-rounded-2xl cv-bg-white cv-p-1">{logo ? <img src={logo} alt="" className="cv-h-full cv-w-full cv-object-contain"/> : <b className="cv-text-xl cv-text-[#174c45]">{String(content.name || 'M').slice(0, 1)}</b>}</span><div><p className="cv-m-0 cv-text-xs cv-font-medium cv-text-[#8fbab4]">Marca ativa no chat</p><h3 className="cv-m-0 cv-mt-1 cv-text-xl cv-font-semibold">{content.name || artifact.title}</h3>{content.website_url && <a href={safeUrl(content.website_url)} target="_blank" rel="noreferrer" className="cv-brand-identity__website">{content.website_url}</a>}</div></header>
    <p className="cv-mb-0 cv-mt-7 cv-text-sm cv-leading-6 cv-text-[#d2e1de]">{content.summary}</p>
    <div className="cv-brand-identity__stats cv-mt-7" aria-label="Resumo da identidade">
      <div><b>{content.projects?.length || 0}</b><span>projetos vinculados</span></div>
      <div><b>{content.asset_count || 0}</b><span>ativos aprovados</span></div>
      <div><b>{content.colors?.length || 0}</b><span>cores registradas</span></div>
    </div>
    {!!colors.length && <section className="cv-mt-8"><h4 className="cv-m-0 cv-text-xs cv-font-semibold cv-text-[#8da6a1]">Cores</h4><div className="cv-mt-3 cv-flex cv-flex-wrap cv-gap-2">{colors.map((color, index) => <span key={`${color.value}-${index}`} className="cv-flex cv-items-center cv-gap-2 cv-rounded-lg cv-bg-white/[.05] cv-p-2 cv-text-[11px] cv-text-[#bbceca]" title={color.label}><i className="cv-h-5 cv-w-5 cv-rounded-md cv-border cv-border-white/15" style={{background: color.value}}/>{color.value}</span>)}</div></section>}
    {!!fonts.length && <section className="cv-mt-7"><h4 className="cv-m-0 cv-text-xs cv-font-semibold cv-text-[#9ab3ae]">Tipografia</h4><div className="cv-mt-3 cv-flex cv-flex-wrap cv-gap-2">{fonts.map((font, index) => <span key={`${font.value}-${index}`} className="cv-rounded-lg cv-bg-white/[.06] cv-px-3 cv-py-2 cv-text-xs cv-text-[#dbe8e5]"><b>{font.value}</b>{font.label !== font.value && <small className="cv-ml-2 cv-text-[#91aaa5]">{font.label}</small>}</span>)}</div></section>}
    {!hasIdentitySignals && <section className="cv-mt-8 cv-rounded-2xl cv-border cv-border-[#2c5552] cv-bg-[#102325] cv-p-5"><p className="cv-m-0 cv-text-xs cv-font-semibold cv-uppercase cv-tracking-[.08em] cv-text-[#79cfc3]">Identidade incompleta</p><h4 className="cv-mb-0 cv-mt-2 cv-text-base cv-font-semibold cv-text-[#e1efec]">Ainda faltam referências para orientar a marca</h4><p className="cv-mb-0 cv-mt-2 cv-text-sm cv-leading-6 cv-text-[#a9c0bc]">Não há logo, cores ou diretrizes suficientes neste momento. Refaça a auditoria para atualizar a identidade antes de usar este contexto em uma conversa.</p>{content.audit_url && <a href={content.audit_url} className="cv-mt-4 cv-inline-flex cv-items-center cv-rounded-xl cv-bg-teal cv-px-4 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#052522] cv-no-underline hover:cv-bg-[#72e0d2]">{auditLabel}</a>}</section>}
    {!!details.length && <dl className="cv-brand-identity__details cv-mt-8 cv-grid cv-gap-4">{details.map(detail => <div key={detail.label} className="cv-border-t cv-border-white/[.08] cv-pt-4"><dt className="cv-text-[11px] cv-font-semibold cv-text-[#8fbab4]">{detail.label}</dt><dd className="cv-m-0 cv-mt-1 cv-text-sm cv-leading-6 cv-text-[#dce9e6]">{detail.value}</dd></div>)}</dl>}
    {!!content.projects?.length && <section className="cv-brand-identity__projects cv-mt-8"><h4>Projetos que herdam este contexto</h4><div>{content.projects.map(project => <span key={project.ref}>{project.name}</span>)}</div></section>}
  </article>;
}

function ProjectProfileArtifact({artifact}) {
  const content = artifact.content || {};
  const missing = [
    !content.description && 'Adicionar uma descrição curta do propósito e do resultado esperado.',
    !content.instructions && 'Registrar orientações, limites e critérios para o trabalho.',
    !content.brands?.length && 'Vincular uma marca quando decisões precisarem herdar sua identidade.',
  ].filter(Boolean);
  const visibility = {private: 'Privado', team: 'Equipe', restricted: 'Acesso definido'}[content.visibility] || content.visibility || 'Privado';
  const date = value => value ? new Intl.DateTimeFormat('pt-BR', {dateStyle: 'medium'}).format(new Date(value)) : '';
  return <article className="cv-project-profile cv-mx-auto cv-w-full cv-max-w-[760px] cv-p-8 md:cv-p-12">
    <header className="cv-project-profile__header"><span style={{background: content.color || '#176b5e'}}><Icon name="folder" size={20}/></span><div><p>Projeto ativo no chat</p><h3>{content.name || artifact.title}</h3><small>{content.status === 'ativo' ? 'Em andamento' : content.status} · {visibility}</small></div></header>
    <p className="cv-project-profile__description">{content.description || 'Este projeto ainda não tem uma descrição. Defina em poucas linhas o que será realizado, para quem e qual resultado deve orientar as decisões.'}</p>
    <section className="cv-project-profile__stats" aria-label="Metadados do projeto"><div><b>{content.file_count || 0}</b><span>arquivos</span></div><div><b>{content.conversation_count || 0}</b><span>conversas</span></div><div><b>{content.brands?.length || 0}</b><span>marcas vinculadas</span></div></section>
    {content.instructions && <section className="cv-project-profile__section"><h4>Como trabalhar neste projeto</h4><p>{content.instructions}</p></section>}
    {!!content.brands?.length && <section className="cv-project-profile__section"><h4>Contexto de marca</h4><div className="cv-project-profile__brands">{content.brands.map(brand => <span key={brand.ref}>{brand.name}</span>)}</div></section>}
    {!!missing.length && <section className="cv-project-profile__next"><h4>Para deixar o contexto mais útil</h4>{missing.map(item => <p key={item}>{item}</p>)}</section>}
    <div className="cv-project-profile__meta">{date(content.created_at) && <span>Criado em {date(content.created_at)}</span>}{date(content.updated_at) && <span>Atualizado em {date(content.updated_at)}</span>}</div>
  </article>;
}

function ProjectMap({artifact, editing, onChange}) {
  const content = artifact.content || {};
  const [zoom, setZoom] = useState(Number(content.layout?.zoom || 1));
  useEffect(() => { setZoom(Number(content.layout?.zoom || 1)); }, [artifact.id, content.layout?.zoom]);
  const groups = content.groups || [];
  const resources = content.resources || [];
  const move = (resourceId, groupId) => onChange({
    ...content,
    resources: resources.map(item => item.id === resourceId ? {...item, group_id: groupId} : item),
    groups: groups.map(group => ({...group, resource_ids: [...(group.resource_ids || []).filter(id => id !== resourceId), ...(group.id === groupId ? [resourceId] : [])]})),
  });
  const height = Math.max(680, ...groups.map(group => Number(group.y || 0) + Number(group.height || 160) + 60));
  return <div className="cv-relative cv-h-full cv-overflow-hidden">
    <div className="cv-scroll cv-h-full cv-overflow-auto cv-bg-[radial-gradient(circle_at_1px_1px,rgba(148,184,179,.12)_1px,transparent_0)] cv-bg-[length:22px_22px] cv-p-6">
      <div className="cv-map-scene" style={{height, transform: `scale(${zoom})`}}>{groups.map(group => <section key={group.id} className="cv-map-group" style={{left: group.x || 48, top: group.y || 48, width: group.width || 310, minHeight: group.height || 150}}>
        <header className="cv-flex cv-items-center cv-justify-between cv-border-b cv-border-white/[.07] cv-px-4 cv-py-3"><strong className="cv-text-xs cv-font-semibold">{group.title}</strong><span className="cv-text-[10px] cv-text-[#76908c]">{resources.filter(item => item.group_id === group.id).length}</span></header>
        <div className="cv-grid cv-gap-1 cv-p-2">{resources.filter(item => item.group_id === group.id).map(resource => <details key={resource.id} className="cv-rounded-xl cv-bg-white/[.035] cv-p-3">
          <summary className="cv-cursor-pointer cv-list-none"><span className="cv-block cv-text-[10px] cv-uppercase cv-tracking-wider cv-text-[#71928d]">{resource.type || 'Arquivo'}</span><strong className="cv-mt-1 cv-block cv-text-xs cv-font-medium">{resource.title}</strong></summary>
          <div className="cv-mt-3 cv-border-t cv-border-white/[.07] cv-pt-3">
            {editing ? <label className="cv-block cv-text-[10px] cv-text-[#78918d]">Mover para<select value={resource.group_id} onChange={event => move(resource.id, event.target.value)} className="cv-mt-1 cv-block cv-h-8 cv-w-full cv-rounded-lg cv-border-0 cv-bg-[#1c3033] cv-px-2 cv-text-[11px]">{groups.map(option => <option key={option.id} value={option.id}>{option.title}</option>)}</select></label> : <p className="cv-m-0 cv-text-[10px] cv-text-[#78918d]">Em {groups.find(item => item.id === resource.group_id)?.title || 'sem grupo'}</p>}
            <div className="cv-mt-3 cv-flex cv-gap-2">{safeUrl(resource.editor_url) && <a href={safeUrl(resource.editor_url)} target="_blank" rel="noreferrer" className="cv-flex cv-items-center cv-gap-1 cv-text-[11px] cv-text-[#65d8cb] cv-no-underline"><Icon name="external" size={13}/>Editar</a>}{safeUrl(resource.download_url) && <a href={safeUrl(resource.download_url)} className="cv-flex cv-items-center cv-gap-1 cv-text-[11px] cv-text-[#a6bbb7] cv-no-underline"><Icon name="download" size={13}/>Baixar</a>}</div>
          </div>
        </details>)}</div>
      </section>)}</div>
    </div>
    <div className="cv-absolute cv-bottom-4 cv-right-4 cv-flex cv-items-center cv-gap-1 cv-rounded-xl cv-border cv-border-white/10 cv-bg-[#132326]/90 cv-p-1 cv-backdrop-blur"><button type="button" onClick={() => setZoom(value => Math.max(.62, value - .1))} className="cv-h-8 cv-w-8 cv-rounded-lg cv-border-0 cv-bg-transparent">−</button><button type="button" onClick={() => setZoom(1)} className="cv-h-8 cv-min-w-12 cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-[10px]">{Math.round(zoom * 100)}%</button><button type="button" onClick={() => setZoom(value => Math.min(1.35, value + .1))} className="cv-h-8 cv-w-8 cv-rounded-lg cv-border-0 cv-bg-transparent">+</button></div>
  </div>;
}

export function ArtifactPane({artifact, mobile = false, tabs = [], activeTabKey = '', onSelectTab, onCloseTab, onCloseOtherTabs, onCloseAllTabs, dirty, saving, publishing, publishedUrl, side = 'right', onSideChange, onChange, onTitleChange, projectRef, projects = [], studioEditorUrl, onSaveToProject, onAttachToProject, onMoveToProject, onPublish, onCopyPublishedUrl, onUnpublish, onClose, onSave, onLoadVersions, versions = [], onRestoreVersion, onRequestSummary, onSaveReference, onRequestMeetingPlan, onOrganizeImage, onOpenResource}) {
  const dialog = useRef(null);
  const closeTimer = useRef(null);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [comparison, setComparison] = useState(null);
  const [comparingVersion, setComparingVersion] = useState(null);
  const [closing, setClosing] = useState(false);
  const [lightTheme, setLightTheme] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [organizingImage, setOrganizingImage] = useState(false);
  const [tabMenu, setTabMenu] = useState(null);
  const [editingDocument, setEditingDocument] = useState(false);
  const [sourceFormat, setSourceFormat] = useState('md');
  const type = artifact?.type || 'document';
  const indexable = artifact?.capabilities?.indexable ?? !['html', 'project_map', 'link_reader'].includes(type);
  const textArtifact = type === 'document' || type === 'brief' || type === 'note' || type === 'executive_summary' || type === 'media_plan' || type === 'scenario' || type === 'research' || type === 'meeting_summary' || type === 'meeting_agenda';
  const hasEditMode = textArtifact || type === 'project_map';
  useEffect(() => {
    const match = document.cookie.match(/(?:^|; )cadu-artifact-theme=([^;]+)/);
    setLightTheme(match?.[1] === 'light');
  }, []);
  const toggleTheme = () => {
    const next = !lightTheme;
    setLightTheme(next);
    document.cookie = `cadu-artifact-theme=${next ? 'light' : 'dark'}; Max-Age=31536000; Path=/; SameSite=Lax`;
  };
  const contentView = useMemo(() => {
    if (!artifact) return null;
    if (artifact.pending) return <div className="cv-artifact-loading" role="status" aria-live="polite"><i/><strong>Preparando a entrega</strong><span>O conteúdo aparecerá aqui quando estiver pronto.</span></div>;
    if (artifact.failed) return <div className="cv-artifact-loading is-failed" role="status"><strong>A entrega não foi concluída</strong><span>{artifact.error}</span></div>;
    if (type === 'html') return <HtmlArtifact artifact={artifact}/>;
    if (type === 'project_map') return <ProjectMap artifact={artifact} editing={editingDocument} onChange={onChange}/>;
    if (type === 'meeting_summary' || type === 'meeting_agenda') return <MeetingSummaryArtifact artifact={artifact} editing={editingDocument} onChange={onChange}/>;
    if (type === 'image') return <ImageArtifact key={`${artifact.tabKey || artifact.id || artifact.title}:${imageSource(artifact)}`} artifact={artifact}/>;
    if (type === 'resource') return <ResourceArtifact artifact={artifact}/>;
    if (type === 'link_reader') return <LinkReaderArtifact artifact={artifact} onRequestSummary={onRequestSummary} onSaveReference={onSaveReference} onRequestMeetingPlan={onRequestMeetingPlan}/>;
    if (type === 'brand_identity') return <BrandIdentityArtifact artifact={artifact}/>;
    if (type === 'project_profile') return <ProjectProfileArtifact artifact={artifact}/>;
    if (type === 'library') return <LibraryArtifact artifact={artifact} onOpenResource={onOpenResource}/>;
    if (type === 'brief') return <BriefArtifact artifact={artifact} editing={editingDocument} onChange={onChange}/>;
    if (['executive_summary', 'media_plan', 'scenario', 'research'].includes(type)) {
      const structured = normalizeArtifactContent(artifact.content || {}, type);
      if (Array.isArray(structured.fields) || Array.isArray(structured.tables) || Array.isArray(structured.rows) || Array.isArray(structured.channels) || Array.isArray(structured.allocations) || Array.isArray(structured.options) || Array.isArray(structured.citations) || Array.isArray(structured.highlights) || structured.metrics || structured.kpis || typeof structured.html === 'string' && structured.html.trim()) return <ContentArtifact artifact={{...artifact, content:structured}} editing={editingDocument} onChange={onChange}/>;
    }
    return textArtifact
      ? <RichDocumentArtifact artifact={artifact} onChange={onChange} editing={editingDocument}/>
      : <StructuredArtifact artifact={artifact} onChange={onChange}/>;
  }, [artifact, type, textArtifact, editingDocument, onChange, onRequestSummary, onSaveReference, onRequestMeetingPlan, onOpenResource]);
  useEffect(() => {
    setClosing(false);
    setEditingTitle(false);
    setEditingDocument(false);
    let preferred = 'md';
    try {
      preferred = window.sessionStorage.getItem('cadu:next-file-format') || 'md';
      if (artifact?.id) window.sessionStorage.removeItem('cadu:next-file-format');
    } catch (_) { /* Storage may be unavailable. */ }
    setSourceFormat(artifact?.type === 'html' ? 'html' : preferred === 'txt' ? 'txt' : 'md');
    setTitleDraft(type === 'image' ? imageFileName(artifact) : (artifact?.title || artifact?.content?.title || 'Trabalho em andamento'));
    setOrganizingImage(false);
    setTabMenu(null);
    setComparison(null);
    setComparingVersion(null);
    setLoadingVersions(false);
    if (dialog.current?.open) dialog.current.close();
    return () => window.clearTimeout(closeTimer.current);
  }, [artifact?.id, artifact?.tabKey]);
  useEffect(() => {
    if (!tabMenu) return undefined;
    const closeMenu = event => {
      if (event.type === 'keydown' && event.key !== 'Escape') return;
      setTabMenu(null);
    };
    window.addEventListener('pointerdown', closeMenu);
    window.addEventListener('keydown', closeMenu);
    return () => {
      window.removeEventListener('pointerdown', closeMenu);
      window.removeEventListener('keydown', closeMenu);
    };
  }, [tabMenu]);
  const displayTitle = type === 'image' ? imageFileName(artifact) : (artifact.title || artifact.content?.title || 'Trabalho em andamento');
  const publicLink = type === 'html' && artifact.id && artifact.status === 'published'
    ? publishedUrl || `${window.location.origin}/public/cadu/artifacts/${encodeURIComponent(artifact.id)}` : '';
  const commitTitle = () => {
    const next = titleDraft.trim();
    if (next && next !== displayTitle) onTitleChange?.(next);
    setEditingTitle(false);
  };
  const src = type === 'image' ? imageSource(artifact) : '';
  const imageEditUrl = type === 'image' ? imageStudioLink(artifact, studioEditorUrl, projectRef) : '';
  const organizeImage = async () => {
    if (organizingImage || !onOrganizeImage) return;
    setOrganizingImage(true);
    try { await onOrganizeImage(artifact); }
    finally { setOrganizingImage(false); }
  };
  const requestClose = () => {
    setClosing(true);
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(onClose, 180);
  };
  const openVersions = async () => {
    setLoadingVersions(true);
    setComparison(null);
    dialog.current?.showModal();
    await onLoadVersions();
    setLoadingVersions(false);
  };
  const compareVersion = async version => {
    setComparingVersion(version);
    try {
      const data = await request(`/workspace/api/v2/artifacts/${encodeURIComponent(artifact.id)}/versions/${version}`);
      setComparison({version, ...versionChanges(data.version?.content, artifact.content)});
    } catch (error) { setComparison({version, error: error.message || 'Não foi possível comparar as versões.'}); }
    finally { setComparingVersion(null); }
  };
  if (!artifact) return null;
  return <aside data-artifact-type={type} className={`cv-artifact-panel cv-artifact-overlay cv-artifact-panel--${side} cv-relative cv-flex cv-h-full cv-flex-none cv-flex-col cv-border-l cv-border-white/[.08] cv-bg-panel ${lightTheme && textArtifact ? 'is-light' : ''} ${closing ? 'cv-is-closing' : ''}`} aria-label={labels[type] || 'Entrega'}>
    {tabs.length > 0 && <nav className="cv-artifact-tabs" aria-label="Entregas abertas">{tabs.map(item => {
      const key = String(item.tabKey || item.id || '');
      const itemTitle = item.type === 'image' ? imageFileName(item) : (item.title || 'Entrega');
      return <div key={key} className={key === activeTabKey ? 'is-active' : ''} onContextMenu={event => { event.preventDefault(); setTabMenu({item, key, x: Math.min(event.clientX, window.innerWidth - 218), y: Math.min(event.clientY, window.innerHeight - 190)}); }}><button type="button" onClick={() => onSelectTab?.(item)} title={itemTitle} aria-label={`Abrir ${itemTitle}`}><span className="cv-artifact-tab__icon">{item.pending ? <i/> : <Icon name={artifactTabIcon(item)} size={13}/>}</span><span className="cv-artifact-tab__title">{compactArtifactTitle(item)}</span></button><button type="button" onClick={() => onCloseTab?.(key)} aria-label={`Fechar ${itemTitle}`} title={`Fechar ${itemTitle}`}><Icon name="close" size={13}/></button></div>;
    })}</nav>}
    {tabMenu && <div className="cv-artifact-tab-menu" style={{left: tabMenu.x, top: tabMenu.y}} role="menu" onPointerDown={event => event.stopPropagation()}>
      <button type="button" role="menuitem" onClick={() => { onCloseTab?.(tabMenu.key); setTabMenu(null); }}>Fechar aba</button>
      <button type="button" role="menuitem" disabled={tabs.length < 2} onClick={() => { onCloseOtherTabs?.(tabMenu.key); setTabMenu(null); }}>Fechar outras abas</button>
      <button type="button" role="menuitem" onClick={() => { onCloseAllTabs?.(); setTabMenu(null); }}>Fechar todas</button>
      {artifactBrowserUrl(tabMenu.item, tabMenu.key === activeTabKey ? publishedUrl : '') && <a role="menuitem" href={artifactBrowserUrl(tabMenu.item, tabMenu.key === activeTabKey ? publishedUrl : '')} target="_blank" rel="noreferrer"><Icon name="external" size={13}/>Abrir no navegador</a>}
      {tabMenu.item.type === 'html' && tabMenu.item.status !== 'published' && tabMenu.key === activeTabKey && <button type="button" role="menuitem" disabled={publishing || saving} onClick={() => { onPublish?.(); setTabMenu(null); }}><Icon name="external" size={13}/>Publicar</button>}
    </div>}
    <header className={`cv-artifact-header cv-flex cv-h-[52px] cv-flex-none cv-items-center cv-gap-2 cv-border-b cv-border-white/[.07] cv-px-4${type === 'brief' ? ' is-brief' : ''}`}>
      <div className="cv-min-w-0 cv-flex-1">{type !== 'image' && <span className="cv-flex cv-items-center cv-gap-2 cv-text-[11px] cv-font-medium cv-text-[#759a95]">{labels[type] || 'Entrega'}{dirty && <i className="cv-h-1.5 cv-w-1.5 cv-rounded-full cv-bg-[#e3a45f]" title="Alterações não salvas"/>}</span>}{type === 'image' || textArtifact ? editingTitle ? <input autoFocus className="cv-artifact-title-input" value={titleDraft} onChange={event => setTitleDraft(event.target.value)} onBlur={commitTitle} onKeyDown={event => { if (event.key === 'Enter') commitTitle(); if (event.key === 'Escape') setEditingTitle(false); }} aria-label={type === 'image' ? 'Nome do arquivo' : 'Título do documento'}/> : <button type="button" className="cv-artifact-title-button" onClick={() => { setTitleDraft(displayTitle); setEditingTitle(true); }} title="Clique para editar o título">{displayTitle}{dirty && <i className="cv-artifact-title-dirty" title="Alterações não salvas"/>}</button> : <h2 className="cv-m-0 cv-mt-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-[15px] cv-font-semibold">{displayTitle}</h2>}</div>
      {type === 'html' && artifact.id && <button type="button" onClick={publicLink ? onCopyPublishedUrl : onPublish} disabled={publishing || saving} className="cv-artifact-publish" aria-label={publishing ? 'Publicando' : saving ? 'Salvando' : publicLink ? 'Copiar link publicado' : 'Publicar página'} title={publishing ? 'Publicando…' : saving ? 'Salvando…' : publicLink ? 'Copiar link' : 'Publicar'}><Icon name={publicLink ? 'link' : 'external'} size={15}/><span>{publishing ? 'Publicando…' : saving ? 'Salvando…' : publicLink ? 'Link' : 'Publicar'}</span></button>}
      {hasEditMode && !artifact.pending && !artifact.failed && <button type="button" className="cv-artifact-edit-mode" onClick={() => setEditingDocument(value => !value)} aria-label={editingDocument ? 'Visualizar material' : type === 'brief' ? 'Editar briefing' : type === 'meeting_agenda' ? 'Editar pauta' : type === 'meeting_summary' ? 'Editar registro' : type === 'project_map' ? 'Editar mapa' : 'Editar documento'} title={editingDocument ? 'Visualizar' : 'Editar'}><Icon name={editingDocument ? 'file' : 'compose'} size={15}/><span>{editingDocument ? 'Visualizar' : 'Editar'}</span></button>}
      {artifact.id && type !== 'image' && <div className="cv-brief-header-save" title={saving ? 'Salvando no projeto' : dirty ? 'Alterações pendentes' : artifact.project_ref ? 'Salvo no projeto' : 'Rascunho salvo automaticamente'}><i className={saving || dirty ? 'is-pending' : ''}/><span>{saving ? 'Salvando' : dirty ? 'Pendente' : artifact.project_ref ? 'No projeto' : 'Salvo'}</span></div>}
      {projectRef && type !== 'link_reader' && indexable && <label className="cv-brief-header-format"><span>Fonte</span><select aria-label="Formato da fonte" value={sourceFormat} disabled={saving} onChange={event => setSourceFormat(event.target.value)}><option value={type === 'html' ? 'html' : 'md'}>{type === 'html' ? '.html' : '.md'}</option>{type !== 'html' && <option value="txt">.txt</option>}</select></label>}
      {projectRef && type !== 'link_reader' && indexable && <button type="button" onClick={() => onSaveToProject(sourceFormat)} disabled={saving} className="cv-brief-header-index">{saving ? 'Indexando…' : artifact.status === 'active' && artifact.project_ref ? 'Atualizar índice' : 'Indexar'}</button>}
      {projectRef && type !== 'link_reader' && !indexable && !artifact.project_ref && <button type="button" onClick={onAttachToProject} disabled={saving} className="cv-brief-header-index">Salvar no projeto</button>}
      {dirty && <button type="button" onClick={onSave} disabled={saving} className="cv-brief-header-save-now" title="Salvar alterações">Salvar</button>}
      {!artifact.pending && !artifact.failed && <details className="cv-artifact-more">
        <summary aria-label="Mais ações da entrega" title="Mais ações"><Icon name="more" size={18}/><span className="cv-sr-only">Mais ações</span></summary>
        <div>
          {type === 'image' && imageEditUrl && <a href={imageEditUrl} target="_blank" rel="noreferrer" className="is-primary"><Icon name="compose" size={14}/>Editar no Studio</a>}
          {type === 'image' && src && <button type="button" disabled={organizingImage} onClick={organizeImage}><Icon name="brand" size={14}/>{organizingImage ? 'Analisando imagem…' : 'Analisar e organizar arquivo'}</button>}
          {type === 'image' && imageEditUrl && <a href={imageStudioLink(artifact, studioEditorUrl, projectRef, 'mask', 'Altere somente a região que eu marcar, preservando todo o restante da imagem.')} target="_blank" rel="noreferrer"><Icon name="compose" size={14}/>Marcar uma área</a>}
          {type === 'image' && imageEditUrl && <a href={imageStudioLink(artifact, studioEditorUrl, projectRef, 'crop', 'Recorte e reenquadre a imagem mantendo o elemento principal em destaque.')} target="_blank" rel="noreferrer"><Icon name="image" size={14}/>Recortar e reenquadrar</a>}
          {type === 'image' && imageEditUrl && <a href={imageStudioLink(artifact, studioEditorUrl, projectRef, 'select', 'Remova o fundo desta imagem e preserve as bordas do elemento principal com acabamento limpo.')} target="_blank" rel="noreferrer"><Icon name="image" size={14}/>Remover fundo</a>}
          {type === 'image' && imageEditUrl && <a href={imageStudioLink(artifact, studioEditorUrl, projectRef, 'format', 'Adapte esta imagem para um novo formato sem perder o conteúdo principal.')} target="_blank" rel="noreferrer"><Icon name="file" size={14}/>Alterar formato</a>}
          {type === 'image' && imageEditUrl && <a href={imageStudioLink(artifact, studioEditorUrl, projectRef, 'select', 'Otimize esta imagem para uso digital, reduzindo o peso sem perda visual perceptível.')} target="_blank" rel="noreferrer"><Icon name="check" size={14}/>Otimizar para web</a>}
          {type === 'image' && src && <a href={src} target="_blank" rel="noreferrer"><Icon name="external" size={14}/>Abrir original</a>}
          {type === 'image' && src && <a href={src} download><Icon name="download" size={14}/>Baixar arquivo</a>}
          {textArtifact && <button type="button" onClick={toggleTheme}><Icon name={lightTheme ? 'moon' : 'sun'} size={14}/>{lightTheme ? 'Usar tema escuro' : 'Usar tema claro'}</button>}
          {(textArtifact || type === 'html') && artifact.id && <div role="group" aria-label="Baixar arquivo"><button type="button" onClick={() => downloadTextArtifact(artifact, 'md')}><Icon name="download" size={14}/>Baixar .md</button><button type="button" onClick={() => downloadTextArtifact(artifact, 'txt')}><Icon name="download" size={14}/>Baixar .txt</button><button type="button" onClick={() => downloadTextArtifact(artifact, 'html')}><Icon name="download" size={14}/>Baixar .html</button></div>}
          {artifact.id && onMoveToProject && <label className="cv-artifact-project-picker">Mover material<select value={artifact.project_ref || ''} disabled={saving} onChange={event => onMoveToProject(event.target.value)}><option value="">Espaço pessoal</option>{projects.map(item => { const ref = item.projectRef || item.ref || item.id; return <option key={ref} value={ref}>{item.name || item.title || ref}</option>; })}</select></label>}
          {publicLink && <button type="button" onClick={onUnpublish} disabled={publishing || saving}><Icon name="close" size={14}/>Despublicar</button>}
          <button type="button" onClick={() => onSideChange?.(side === 'right' ? 'left' : 'right')}><Icon name="browser" size={14}/>{side === 'right' ? 'Mover para a esquerda' : 'Mover para a direita'}</button>
          {artifact.id && <button type="button" onClick={openVersions}><Icon name="history" size={14}/>Ver versões <small>v{artifact.current_version || 1}</small></button>}
        </div>
      </details>}
      <button type="button" onClick={requestClose} className={`cv-artifact-return cv-grid cv-h-8 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-mist hover:cv-bg-white/[.05] ${mobile ? 'is-mobile' : 'cv-w-8'}`} aria-label={mobile ? 'Voltar à conversa' : 'Fechar entrega'}><Icon name={mobile ? 'chevron' : 'close'} size={17}/>{mobile && <span>Conversa</span>}</button>
    </header>
    {artifact.current_version > 1 && artifact.change_summary && !artifact.pending && <div className="cv-flex cv-items-center cv-gap-3 cv-border-b cv-border-white/[.07] cv-bg-[#173a35] cv-px-4 cv-py-2 cv-text-xs" role="status"><strong className="cv-whitespace-nowrap cv-text-[#9ee1cd]">Versão {artifact.current_version}</strong><span className="cv-min-w-0 cv-flex-1 cv-truncate cv-text-[#d4e8e0]" title={artifact.change_summary}>{artifact.change_summary.replace(/^Cadu:\s*/, '')}</span></div>}
    <div className="cv-scroll cv-min-h-0 cv-flex-1 cv-overflow-auto">{contentView}</div>
    <dialog ref={dialog} className="cv-dialog cv-w-[min(540px,calc(100vw-32px))] cv-p-0">
      <section><header className="cv-flex cv-items-center cv-justify-between cv-border-b cv-border-white/10 cv-p-5"><div><h2 className="cv-m-0 cv-text-base">Versões</h2><p className="cv-mb-0 cv-mt-1 cv-text-xs cv-text-mist">Restaure uma revisão anterior.</p></div><button type="button" onClick={() => dialog.current?.close()} className="cv-grid cv-h-8 cv-w-8 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent"><Icon name="close" size={16}/></button></header>
        <div className="cv-scroll cv-max-h-[55vh] cv-overflow-y-auto cv-p-3">{loadingVersions ? <p className="cv-p-3 cv-text-sm cv-text-mist">Carregando…</p> : versions.length ? versions.map(item => <article key={item.version} className="cv-flex cv-items-center cv-gap-4 cv-rounded-xl cv-p-3 hover:cv-bg-white/[.04]"><div className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-sm">Versão {item.version}</strong><small className="cv-mt-1 cv-block cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-xs cv-text-mist">{item.change_summary || 'Revisão da entrega'}</small></div><button type="button" disabled={Number(item.version) === Number(artifact.current_version) || comparingVersion !== null} onClick={() => compareVersion(item.version)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-3 cv-py-2 cv-text-xs disabled:cv-opacity-35">{comparingVersion === item.version ? 'Comparando…' : 'Comparar'}</button><button type="button" disabled={Number(item.version) === Number(artifact.current_version)} onClick={async () => { await onRestoreVersion(item.version); dialog.current?.close(); }} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-3 cv-py-2 cv-text-xs disabled:cv-opacity-35">{Number(item.version) === Number(artifact.current_version) ? 'Atual' : 'Restaurar'}</button></article>) : <p className="cv-p-3 cv-text-sm cv-text-mist">Nenhuma versão disponível.</p>}{comparison && <section className="cv-m-3 cv-rounded-xl cv-border cv-border-white/10 cv-p-4" aria-live="polite"><h3 className="cv-m-0 cv-text-sm">Versão {comparison.version} → atual</h3>{comparison.error ? <p className="cv-text-xs cv-text-mist">{comparison.error}</p> : <div className="cv-mt-3 cv-grid cv-gap-4 md:cv-grid-cols-2"><div><strong className="cv-text-xs cv-text-[#e8b4a9]">Trechos removidos ou substituídos</strong>{comparison.removed.length ? comparison.removed.map((line, index) => <p key={index} className="cv-mb-0 cv-mt-2 cv-text-xs cv-text-mist">{line}</p>) : <p className="cv-text-xs cv-text-mist">Nenhum trecho textual removido.</p>}</div><div><strong className="cv-text-xs cv-text-[#9ee1cd]">Trechos adicionados ou revisados</strong>{comparison.added.length ? comparison.added.map((line, index) => <p key={index} className="cv-mb-0 cv-mt-2 cv-text-xs cv-text-mist">{line}</p>) : <p className="cv-text-xs cv-text-mist">Nenhum trecho textual adicionado.</p>}</div></div>}</section>}</div>
      </section>
    </dialog>
  </aside>;
}
