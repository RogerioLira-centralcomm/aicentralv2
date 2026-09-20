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
