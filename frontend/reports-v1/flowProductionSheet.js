import {flowBlockFor} from './flowBlockRegistry.js';
import {MEASURED_TYPES, NODE_STATUS_LABELS, hasRealPath, nodeStatus} from './flowLifecycle.js';
import {creativeFormatLabel, creativeStatusLabel, mediaProgress, objectiveLabel, segmentKindLabel} from './flowMedia.js';

// The production sheet is a view of the plan itself: what must be created, by whom and by when.
export const SHEET_SECTIONS = Object.freeze([
  ['page', 'Páginas a criar'],
  ['tracking', 'Eventos e conversões'],
  ['source', 'Origens e canais'],
  ['logic', 'Testes, esperas e CRM'],
  ['note', 'Checklists da mesa'],
]);
const SECTION_BY_TYPE = {page: 'page', form: 'page', error: 'page', event: 'tracking', conversion: 'tracking', whatsapp: 'tracking',
  source: 'source', condition: 'logic', delay: 'logic', segment: 'logic', webhook: 'logic', note: 'note'};

function missingFor(node) {
  if (node.type === 'note') return (node.checklist || []).filter(item => !item.done).map(item => item.text);
  if (node.type === 'source') return mediaProgress(node).missing;
  if (!MEASURED_TYPES.has(node.type)) return [];
  const spec = node.spec || {};
  const missing = [];
  if (!hasRealPath(node)) missing.push('Endereço final');
  if (node.type === 'event' && !node.event_name) missing.push('Nome do evento');
  if (['planned', 'in_production'].includes(nodeStatus(node))) {
    if (!spec.goal) missing.push('Objetivo');
    if (!spec.owner) missing.push('Responsável');
    if (!spec.due_date) missing.push('Prazo');
  }
  return missing;
}

/** Items grouped by section, with the share of measurable steps that are ready to go live. */
export function buildProductionSheet(config) {
  const items = (config.nodes || []).map(node => {
    const measured = MEASURED_TYPES.has(node.type);
    const status = measured ? nodeStatus(node) : null;
    const checklist = node.type === 'note' ? node.checklist || [] : [];
    const title = node.title || flowBlockFor(node).label;
    const kind = node.type === 'note' ? 'Nota' : flowBlockFor(node).label;
    return {
      id: node.id, section: SECTION_BY_TYPE[node.type] || 'logic', title,
      kind: kind === title ? '' : kind, measured, status,
      statusLabel: status ? NODE_STATUS_LABELS[status] : null, spec: node.spec || {}, path: hasRealPath(node) ? node.path : '',
      eventName: node.event_name || '', missing: missingFor(node),
      done: measured ? ['ready', 'live'].includes(status) && hasRealPath(node) : node.type === 'note' ? checklist.length > 0 && checklist.every(item => item.done)
        : node.type === 'source' ? mediaProgress(node).missing.length === 0 : true,
      checklist,
      segment: node.type === 'source' && node.segment ? [node.segment.name, segmentKindLabel(node.segment.kind)].filter(Boolean).join(' · ') : '',
      objective: node.type === 'source' ? objectiveLabel(node.media?.objective) : '',
      creatives: node.type === 'source' ? node.media?.creatives || [] : [],
      setup: node.type === 'source' ? node.media?.setup || [] : [],
    };
  });
  const tracked = items.filter(item => item.measured);
  const sections = SHEET_SECTIONS.map(([id, label]) => ({id, label, items: items.filter(item => item.section === id)}))
    .filter(section => section.items.length);
  return {sections, progress: {done: tracked.filter(item => item.done).length, total: tracked.length},
    openChecklist: items.filter(item => item.section === 'note').reduce((sum, item) => sum + item.missing.length, 0)};
}

const CSV_COLUMNS = [
  ['Seção', item => SHEET_SECTIONS.find(([id]) => id === item.section)?.[1]], ['Passo', item => item.title], ['Tipo', item => item.kind],
  ['Situação', item => item.statusLabel || ''], ['Responsável', item => item.spec.owner], ['Prazo', item => item.spec.due_date],
  ['Endereço sugerido', item => item.spec.suggested_path], ['Endereço final', item => item.path], ['Evento', item => item.eventName],
  ['Objetivo', item => item.spec.goal], ['Mensagem', item => item.spec.headline], ['Conteúdo', item => item.spec.content],
  ['Chamada para ação', item => item.spec.cta], ['Referências', item => item.spec.references], ['Observações', item => item.spec.notes],
  ['Público', item => item.segment], ['Objetivo da campanha', item => item.objective],
  ['Criativos', item => item.creatives.map(entry => `${entry.name} (${creativeFormatLabel(entry.format)}, ${creativeStatusLabel(entry.status)})`).join('\n')],
  ['Checklist', item => [...item.checklist, ...item.setup].map(entry => `${entry.done ? '[x]' : '[ ]'} ${entry.text}`).join('\n')],
  ['Pendências', item => item.missing.join('; ')],
];

// Spreadsheet apps execute cells that start with these characters as formulas.
export const sheetCell = value => {
  let text = String(value ?? '');
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[";\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

export function productionSheetCsv(sheet) {
  const rows = sheet.sections.flatMap(section => section.items);
  return '﻿' + [CSV_COLUMNS.map(([label]) => label), ...rows.map(item => CSV_COLUMNS.map(([, read]) => read(item)))]
    .map(row => row.map(sheetCell).join(';')).join('\r\n');
}

const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[char]);

/** A standalone, script-free document to print or save as PDF from the browser. */
export function productionSheetHtml(sheet, {name = 'Fluxo', host = ''} = {}) {
  const field = (label, value) => value ? `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>` : '';
  const body = sheet.sections.map(section => `<h2>${escapeHtml(section.label)}</h2>${section.items.map(item => `<article><h3>${escapeHtml(item.title)}<small>${escapeHtml([item.kind, item.statusLabel].filter(Boolean).join(' · '))}</small></h3><dl>${
    field('Público', item.segment) + field('Objetivo da campanha', item.objective) +
    field('Responsável', item.spec.owner) + field('Prazo', item.spec.due_date) + field('Endereço sugerido', item.spec.suggested_path) + field('Endereço final', item.path)
    + field('Evento', item.eventName) + field('Objetivo', item.spec.goal) + field('Mensagem', item.spec.headline) + field('Conteúdo', item.spec.content)
    + field('Chamada para ação', item.spec.cta) + field('Referências', item.spec.references) + field('Observações', item.spec.notes)}</dl>${
    item.creatives.length ? `<p><strong>Criativos</strong></p><ul class="check">${item.creatives.map(entry => `<li>${escapeHtml(entry.name)} · ${escapeHtml(creativeFormatLabel(entry.format))} · ${escapeHtml(creativeStatusLabel(entry.status))}${entry.message ? ` — ${escapeHtml(entry.message)}` : ''}</li>`).join('')}</ul>` : ''}${
    [...item.checklist, ...item.setup].length ? `<ul class="check">${[...item.checklist, ...item.setup].map(entry => `<li>${entry.done ? '☑' : '☐'} ${escapeHtml(entry.text)}</li>`).join('')}</ul>` : ''}${
    item.missing.length && !['note', 'source'].includes(item.section) ? `<p class="missing">Falta: ${escapeHtml(item.missing.join(', '))}</p>` : ''}</article>`).join('')}`).join('');
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Folha de produção · ${escapeHtml(name)}</title><style>
body{margin:32px;color:#101828;font:13px/1.5 Inter,Arial,sans-serif}h1{margin:0;font-size:22px}header p{margin:4px 0 24px;color:#475467}
h2{margin:28px 0 8px;padding-bottom:6px;border-bottom:1px solid #eaecf0;font-size:15px}article{margin:0 0 14px;padding:12px 14px;border:1px solid #eaecf0;border-radius:10px;break-inside:avoid}
h3{display:flex;justify-content:space-between;gap:12px;margin:0 0 8px;font-size:14px}h3 small{color:#475467;font-weight:500}
dl{display:grid;grid-template-columns:150px 1fr;gap:4px 12px;margin:0}dt{color:#475467}dd{margin:0;white-space:pre-wrap}.check{margin:8px 0 0;padding:0;list-style:none}.missing{margin:8px 0 0;color:#b54708}
</style></head><body><header><h1>Folha de produção · ${escapeHtml(name)}</h1><p>${escapeHtml(host)}${host ? ' · ' : ''}${sheet.progress.done} de ${sheet.progress.total} passos prontos para medir · gerada em ${escapeHtml(new Date().toLocaleDateString('pt-BR'))}</p></header>${body}</body></html>`;
}
