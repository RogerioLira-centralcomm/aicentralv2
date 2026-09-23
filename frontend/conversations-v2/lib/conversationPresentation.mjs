const URL_PATTERN = /https?:\/\/[^\s]+/gi;

function compact(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function sentenceLabel(value) {
  const clean = compact(value).replace(/^[\s:;,.\-–—]+|[\s:;,.\-–—]+$/g, '');
  if (!clean) return '';
  return clean.charAt(0).toLocaleUpperCase('pt-BR') + clean.slice(1);
}

export function conversationDisplayTitle(value, fallback = 'Conversa') {
  const raw = String(value || '').trim();
  if (!raw) return fallback;
  const urls = raw.match(URL_PATTERN) || [];
  const intent = sentenceLabel(raw.replace(URL_PATTERN, ' '));
  if (intent) return intent.length > 64 ? `${intent.slice(0, 61).replace(/\s+\S*$/, '')}…` : intent;
  if (urls.length) {
    try {
      const host = new URL(urls[0]).hostname.replace(/^www\./, '');
      if (host === 'docs.google.com') return 'Documento compartilhado';
      if (host === 'drive.google.com') return 'Arquivo compartilhado';
    } catch (_) { /* Fall back to a safe human label. */ }
    return 'Link compartilhado';
  }
  const title = sentenceLabel(raw);
  return title.length > 64 ? `${title.slice(0, 61).replace(/\s+\S*$/, '')}…` : title;
}

function entityMatches(item, value, kind) {
  const aliases = kind === 'project'
    ? [item?.ref, item?.projectRef, item?.project_ref, item?.id, item?.id && `ci:${item.id}`]
    : [item?.ref, item?.brandRef, item?.brand_ref, item?.id, item?.id && `studio:${item.id}`];
  return aliases.some(alias => String(alias || '') === String(value || ''));
}

export function conversationContextLabel(context = {}, projects = [], brands = []) {
  if (context.project_ref) {
    const project = projects.find(item => entityMatches(item, context.project_ref, 'project'));
    return {kind: 'project', label: project?.name || project?.title || 'Projeto ativo'};
  }
  if (context.brand_ref) {
    const brand = brands.find(item => entityMatches(item, context.brand_ref, 'brand'));
    return {kind: 'brand', label: brand?.name || brand?.title || 'Marca ativa'};
  }
  return {kind: 'free', label: 'Conversa livre'};
}
