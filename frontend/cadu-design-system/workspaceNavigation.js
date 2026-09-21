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

export function openConversationDockDetail(item) {
  if (!item) return;
  if (item.href) {
    window.location.assign(item.href);
    return;
  }
  const target = item.kind === 'brand'
    ? `/workspace/brands/${encodeURIComponent(String(item.id || '').replace(/^studio:/, ''))}`
    : `/workspace/projects/${encodeURIComponent(String(item.projectRef || item.id || '').replace(/^ci:/, ''))}`;
  window.location.assign(target);
}
