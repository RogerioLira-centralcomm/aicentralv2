export function checklistPrompt(items) {
  const selected = Array.isArray(items) ? items : [];
  if (!selected.length) return '';
  if (selected.length === 1 && selected[0].prompt) return selected[0].prompt;
  return `Revise estes itens comigo: ${selected.map(item => item.title).join('; ')}.`;
}

const RESPONSE_KEYS = new Set(['answer', 'text', 'content', 'response', 'output']);

function decodePartialJsonString(value) {
  const escapes = {'"': '"', '\\': '\\', '/': '/', b: '\b', f: '\f', n: '\n', r: '\r', t: '\t'};
  let output = '';
  for (let index = 0; index < value.length; index += 1) {
    const character = value[index];
    if (character !== '\\') { output += character; continue; }
    if (index + 1 >= value.length) break;
    const escaped = value[index + 1];
    if (escaped === 'u') {
      const code = value.slice(index + 2, index + 6);
      if (!/^[0-9a-f]{4}$/i.test(code)) break;
      output += String.fromCharCode(Number.parseInt(code, 16));
      index += 5;
      continue;
    }
    output += escapes[escaped] ?? escaped;
    index += 1;
  }
  return output;
}

function partialStructuredText(value) {
  const raw = String(value || '');
  const matches = [...raw.matchAll(/\"(?:answer|content)\"\s*:\s*\"/gi)];
  if (!matches.length) return null;
  const start = matches[matches.length - 1].index + matches[matches.length - 1][0].length;
  let escaped = false;
  let end = raw.length;
  for (let index = start; index < raw.length; index += 1) {
    const character = raw[index];
    if (character === '"' && !escaped) { end = index; break; }
    escaped = character === '\\' && !escaped;
    if (character !== '\\') escaped = false;
  }
  return decodePartialJsonString(raw.slice(start, end));
}

function decodeStructuredValue(value, depth = 0) {
  if (depth > 4 || value == null) return value;
  if (typeof value === 'string') {
    const clean = value.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
    if (!(clean.startsWith('{') || clean.startsWith('[') || clean.startsWith('"{') || clean.startsWith('"['))) return value;
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
  if (typeof decoded !== 'string') return String(value || '');
  if (decoded !== value) return decoded;
  const partial = partialStructuredText(decoded);
  if (partial !== null) return partial;
  const clean = decoded.trimStart();
  if (/^(?:```(?:json)?\s*)?["']?\s*[\[{]/i.test(clean)) return '';
  return decoded;
}

export function reconcileCompletedResponse(streamingResponse, completedResponse, hasArtifact = false) {
  const completed = completedResponse && typeof completedResponse === 'object' ? completedResponse : {};
  const final = normalizeAnswerText(completed.answer || '');
  const streamed = normalizeAnswerText(streamingResponse?.answer || '');
  // The final event may carry only a short acknowledgement after a substantive
  // answer was already streamed. Keep that visible answer unless an artifact
  // is the authoritative completed delivery.
  return {...completed, answer: !hasArtifact && streamed.length > final.length ? streamed : final};
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
