const SOURCE_TYPES = new Set(['source', 'sources', 'source_group']);

export function consolidateSources(blocks, citations) {
  const content = Array.isArray(blocks) ? blocks : [];
  if (content.some(block => SOURCE_TYPES.has(block?.type))) return content;
  if (!Array.isArray(citations) || !citations.length) return content;
  return [...content, {type: 'sources', title: 'Fontes da resposta', items: citations}];
}

export function sourceDomain(value) {
  try {
    const url = new URL(String(value || ''));
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.hostname.replace(/^www\./, '') : '';
  } catch (_) { return ''; }
}

export function sourceSummary(items, limit = 3) {
  const all = Array.isArray(items) ? items : [];
  const domains = [...new Set(all.map(item => sourceDomain(item?.url)).filter(Boolean))];
  const visible = domains.slice(0, limit);
  return {
    count: all.length,
    domains,
    label: visible.join(', ') || 'Fontes da pesquisa',
    remaining: Math.max(0, domains.length - visible.length),
  };
}

export function sourceCollection(block, items) {
  const all = Array.isArray(items) ? items : [];
  return {
    id: `sources:${block?.id || all.map(item => item?.id || item?.url).filter(Boolean).join('|')}`,
    kind: 'source_collection',
    title: block?.title || 'Fontes da resposta',
    items: all,
  };
}
