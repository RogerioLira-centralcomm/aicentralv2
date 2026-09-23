export const PROJECT_RECENCY_KEY = 'cadu:workspace:project-recency:v1';
const PROJECT_RECENCY_LIMIT = 100;

const projectTimestamp = item => Date.parse(item?.lastUsedAt || item?.last_used_at || item?.updatedAt || item?.updated_at || item?.lastActivityAt || item?.last_activity_at || item?.createdAt || item?.created_at || '') || 0;
const projectAliases = item => [item?.ref, item?.projectRef, item?.project_ref, item?.id].map(value => String(value || '')).filter(Boolean);

const browserStorage = storage => {
  if (storage) return storage;
  try { return globalThis.localStorage; } catch (_) { return null; }
};

export function readProjectRecency(storage) {
  try {
    const value = JSON.parse(browserStorage(storage)?.getItem(PROJECT_RECENCY_KEY) || '{}');
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  } catch (_) {
    return {};
  }
}

export function markProjectUsed(projectRef, storage, now = Date.now()) {
  const ref = String(projectRef || '');
  const target = browserStorage(storage);
  if (!ref || !target) return;
  try {
    const recency = {...readProjectRecency(target), [ref]:now};
    const entries = Object.entries(recency).sort((left, right) => Number(right[1]) - Number(left[1])).slice(0, PROJECT_RECENCY_LIMIT);
    target.setItem(PROJECT_RECENCY_KEY, JSON.stringify(Object.fromEntries(entries)));
  } catch (_) {
    // Storage is optional; server dates remain a deterministic fallback.
  }
}

export function recentProjectOptions(items = [], value = '', limit = 10, recency = readProjectRecency()) {
  const usedAt = item => Math.max(...projectAliases(item).map(alias => Number(recency?.[alias]) || 0), 0);
  const ordered = [...items].sort((left, right) => usedAt(right) - usedAt(left) || projectTimestamp(right) - projectTimestamp(left));
  const selected = ordered.find(item => projectAliases(item).includes(String(value || '')));
  const recent = ordered.filter(item => item !== selected).slice(0, Math.max(0, limit - Number(Boolean(selected))));
  return selected ? [selected, ...recent] : recent.slice(0, limit);
}
