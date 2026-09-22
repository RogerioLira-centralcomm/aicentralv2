export function checklistPrompt(items) {
  const selected = Array.isArray(items) ? items : [];
  if (!selected.length) return '';
  if (selected.length === 1 && selected[0].prompt) return selected[0].prompt;
  return `Revise estes itens comigo: ${selected.map(item => item.title).join('; ')}.`;
}

const RESPONSE_KEYS = new Set(['answer', 'text', 'content', 'response', 'output']);

function decodeStructuredValue(value, depth = 0) {
  if (depth > 4 || value == null) return value;
  if (typeof value === 'string') {
    const clean = value.trim();
    if (!(clean.startsWith('{') || clean.startsWith('['))) return value;
    try { return decodeStructuredValue(JSON.parse(clean), depth + 1); } catch (_) { return value; }
  }
  if (Array.isArray(value)) return value;
  if (typeof value !== 'object') return value;
  for (const key of RESPONSE_KEYS) {
    if (Object.prototype.hasOwnProperty.call(value, key)) {
      const decoded = decodeStructuredValue(value[key], depth + 1);
      if (typeof decoded === 'string') return decoded;
      if (decoded && typeof decoded === 'object') return decodeStructuredValue(decoded, depth + 1);
    }
  }
  return value;
}

export function normalizeAnswerText(value) {
  const decoded = decodeStructuredValue(value);
  return typeof decoded === 'string' ? decoded : String(value || '');
}

export function meaningfulResponseBlocks(blocks) {
  return (Array.isArray(blocks) ? blocks : []).filter(block => {
    if (!block || typeof block !== 'object') return false;
    if (block.type === 'insights') return Array.isArray(block.items) && block.items.some(item => item?.title || item?.detail);
    if (block.type === 'question' || block.type === 'questions') return Array.isArray(block.items) && block.items.length > 0;
    return true;
  });
}

export function insertWorkedBeforeResult(items, turnId, worked) {
  const messages = Array.isArray(items) ? items : [];
  const index = messages.findIndex(item => item.turnId === turnId && item.role === 'assistant');
  if (index < 0) return [...messages, worked];
  return [...messages.slice(0, index), worked, ...messages.slice(index)];
}

export function isInternalWorkspaceUrl(value, origin = '') {
  try {
    const url = new URL(String(value || ''), origin || 'https://workspace.invalid');
    return url.origin === (origin || 'https://workspace.invalid') && url.pathname.startsWith('/workspace/');
  } catch (_) {
    return false;
  }
}
