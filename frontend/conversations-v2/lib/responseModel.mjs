export function checklistPrompt(items) {
  const selected = Array.isArray(items) ? items : [];
  if (!selected.length) return '';
  if (selected.length === 1 && selected[0].prompt) return selected[0].prompt;
  return `Revise estes itens comigo: ${selected.map(item => item.title).join('; ')}.`;
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
