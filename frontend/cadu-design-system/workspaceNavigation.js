export function openProjectChat(chatUrl, item) {
  const projectRef = item?.projectRef || item?.id;
  if (!chatUrl || !projectRef) return;

  const target = new URL(chatUrl, window.location.origin);
  target.searchParams.set('project_ref', projectRef);
  // A dock shortcut is a context switch: bring the chat history into view so
  // the person can resume work instead of landing on the project detail page.
  target.searchParams.set('history', '1');
  window.location.assign(target.pathname + target.search);
}

export function openWorkspaceDetail(item) {
  if (item?.href) window.location.assign(item.href);
}

export function openWorkspaceResourceConversation(chatUrl, item) {
  if (!chatUrl || !item) return;
  const target = new URL(chatUrl, window.location.origin);
  const projectRef = item.projectRef || item.project_ref;
  const resourceRef = item.resourceRef || item.resource_ref || String(item.id || '').replace(/^resource:/, '');
  if (projectRef) target.searchParams.set('project_ref', projectRef);
  if (resourceRef) target.searchParams.set('resource_ref', resourceRef);
  target.searchParams.set('prompt', `Abra “${item.title || item.name || 'este recurso'}” como artefato para eu continuar trabalhando nele.`);
  target.searchParams.set('mode', 'analysis');
  target.searchParams.set('auto_send', '1');
  window.location.assign(target.pathname + target.search);
}

export function openConversationDockDetail(item) {
  if (!item) return;
  if (item.href) {
    window.location.assign(item.href);
    return;
  }
  const kind = String(item.kind || item.type || '').toLowerCase();
  const resourceKinds = new Set(['resource', 'file', 'image', 'artifact', 'video', 'media_plan', 'report', 'analysis', 'link']);
  let target;
  if (kind === 'brand') {
    target = `/workspace/brands/${encodeURIComponent(String(item.brandRef || item.id || '').replace(/^studio:/, ''))}`;
  } else if (resourceKinds.has(kind) || item.resourceRef) {
    const projectId = String(item.projectRef || '').replace(/^ci:/, '');
    const resourceId = String(item.resourceRef || item.id || '').replace(/^resource:/, '');
    target = projectId
      ? `/workspace/projects/${encodeURIComponent(projectId)}?resource=${encodeURIComponent(resourceId)}`
      : '/workspace/projects';
  } else {
    target = `/workspace/projects/${encodeURIComponent(String(item.projectRef || item.id || '').replace(/^ci:/, ''))}`;
  }
  window.location.assign(target);
}
