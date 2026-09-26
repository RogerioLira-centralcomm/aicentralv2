const ARCHIVED_STATES = new Set(['arquivado', 'archived', 'deletado', 'deleted']);

export function normalizedEntityKey(value) {
  return String(value || '')
    .replace(/^(?:studio|brand|ci|project):/i, '')
    .trim()
    .toLocaleLowerCase('pt-BR');
}

export function entityIdentity(item) {
  return String(item?.id || item?.ref || item?.projectRef || item?.project_ref || item?.brandRef || item?.brand_ref || '');
}

export function entityLabel(item, fallback = '') {
  return String(item?.name || item?.title || item?.projectName || item?.project_name || fallback).trim();
}

export function entityHref(item) {
  return item?.href || item?.url || '';
}

export function isArchivedEntity(item) {
  return ARCHIVED_STATES.has(String(item?.status || '').trim().toLocaleLowerCase('pt-BR'));
}

export function entityTimestamp(item) {
  return Date.parse(item?.updatedAt || item?.updated_at || item?.lastActivityAt || item?.last_activity_at || item?.createdAt || item?.created_at || '') || 0;
}

export function compareWorkspaceActivity(left, right) {
  return entityTimestamp(right) - entityTimestamp(left)
    || entityLabel(left).localeCompare(entityLabel(right), 'pt-BR', {sensitivity:'base'});
}

export function brandIdentityKeys(brand) {
  return new Set([brand?.id, brand?.ref, brand?.brandRef, brand?.brand_ref, brand?.name, brand?.title]
    .map(normalizedEntityKey).filter(Boolean));
}

export function projectBrandKeys(project) {
  const related = Array.isArray(project?.related_refs)
    ? project.related_refs
    : Array.isArray(project?.relatedRefs) ? project.relatedRefs : [];
  return [project?.brandId, project?.brand_id, project?.brandRef, project?.brand_ref, project?.brandName, project?.brand_name, ...related]
    .map(normalizedEntityKey).filter(Boolean);
}

export function groupWorkspaceProjects(brands = [], projects = []) {
  const activeProjects = projects.filter(item => !isArchivedEntity(item)).slice().sort(compareWorkspaceActivity);
  const candidates = brands.map(brand => {
    const keys = brandIdentityKeys(brand);
    return {...brand, projects:activeProjects.filter(project => projectBrandKeys(project).some(key => keys.has(key)))};
  });
  // Some legacy payloads expose one catalog record and one studio record for
  // the same brand. Merge equal labels only when both records actually point
  // to at least one common project; equal display names alone are not enough.
  const groups = [];
  candidates.forEach(candidate => {
    const candidateProjectIds = new Set(candidate.projects.map(entityIdentity).filter(Boolean));
    const existing = groups.find(group => normalizedEntityKey(entityLabel(group)) === normalizedEntityKey(entityLabel(candidate))
      && group.projects.some(project => candidateProjectIds.has(entityIdentity(project))));
    if (!existing) { groups.push(candidate); return; }
    const known = new Set(existing.projects.map(entityIdentity).filter(Boolean));
    existing.projects = [...existing.projects, ...candidate.projects.filter(project => !known.has(entityIdentity(project)))]
      .sort(compareWorkspaceActivity);
  });
  groups.sort((left, right) => entityTimestamp(right.projects[0]) - entityTimestamp(left.projects[0]) || compareWorkspaceActivity(left, right));
  const grouped = new Set(groups.flatMap(group => group.projects.map(entityIdentity)));
  return {groups, ungrouped:activeProjects.filter(project => !grouped.has(entityIdentity(project)))};
}

export function workspaceBrandByRef(groups = [], ref = '') {
  const key = normalizedEntityKey(ref);
  return key ? groups.find(brand => brandIdentityKeys(brand).has(key)) || null : null;
}

export function projectsForBrandSelection(groups = [], ungrouped = [], ref = '') {
  if (!ref) return ungrouped;
  return workspaceBrandByRef(groups, ref)?.projects || [];
}

export function nextBrandSelection(currentRef = '', clickedRef = '') {
  const nextRef = String(clickedRef || '');
  return nextRef && normalizedEntityKey(nextRef) === normalizedEntityKey(currentRef) ? '' : nextRef;
}
