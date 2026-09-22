export const MAX_QUEUED_TURNS = 5;

export function queueKey(conversationId) {
  return `cadu:conversation-queue:${conversationId || 'pending'}`;
}

export function readQueue(conversationId, storage = globalThis.localStorage) {
  try {
    const value = JSON.parse(storage.getItem(queueKey(conversationId)) || '[]');
    return Array.isArray(value) ? value.filter(item => item?.id && item?.prompt).slice(0, MAX_QUEUED_TURNS) : [];
  } catch (_) {
    return [];
  }
}

export function writeQueue(conversationId, items, storage = globalThis.localStorage) {
  try {
    const key = queueKey(conversationId);
    if (items.length) storage.setItem(key, JSON.stringify(items.slice(0, MAX_QUEUED_TURNS)));
    else storage.removeItem(key);
  } catch (_) { /* Storage can be unavailable in private browsing. */ }
}

export function enqueue(items, item) {
  if (items.length >= MAX_QUEUED_TURNS) return items;
  return [...items, item];
}

export function updateQueued(items, id, prompt) {
  const clean = String(prompt || '').trim();
  return clean ? items.map(item => item.id === id ? {...item, prompt: clean, updatedAt: Date.now()} : item) : items;
}

export function moveQueued(items, id, direction) {
  const index = items.findIndex(item => item.id === id);
  const target = index + direction;
  if (index < 0 || target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}
