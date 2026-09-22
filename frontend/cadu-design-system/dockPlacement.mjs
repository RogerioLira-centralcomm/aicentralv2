export function insertionIndexFromCenters(centers, pointerY) {
  const index = centers.findIndex(center => pointerY < center);
  return index < 0 ? centers.length : index;
}

export function reorderAtInsertion(items, sourceIdentity, insertionIndex, identityOf) {
  const from = items.findIndex(item => identityOf(item) === sourceIdentity);
  if (from < 0) return items;
  const next = [...items];
  const [moved] = next.splice(from, 1);
  const to = Math.max(0, Math.min(next.length, insertionIndex - (from < insertionIndex ? 1 : 0)));
  next.splice(to, 0, moved);
  return next;
}

export function completeDockOrder(visibleIds, allIds) {
  const ordered = [...new Set(visibleIds.filter(Boolean))];
  for (const id of allIds) if (id && !ordered.includes(id)) ordered.push(id);
  return ordered;
}
