export const workspaceSolutions = [
  ['workspace', 'Workspace', 'Projetos e contexto'],
  ['planner', 'Planner', 'Planos e cenários'],
  ['studio', 'Studio', 'Criação e análise'],
  ['connect', 'Reports', 'Relatórios e resultados'],
  ['skills', 'Skills', 'Recursos e automações'],
];

export const workspaceMobileDestinations = [
  ['home', 'Início', 'home'],
  ['conversations', 'Chat', 'compose'],
  ['projects', 'Projetos', 'folder'],
  ['brands', 'Marcas', 'brand'],
  ['docs', 'Arquivos', 'file'],
];

export function workspaceChatHref(urls = {}, {history = false} = {}) {
  const href = urls.conversations || urls.newConversation || '';
  if (!href || !history) return href;
  return `${href}${href.includes('?') ? '&' : '?'}history=1`;
}

export function workspaceMobileDestinationItems(urls = {}) {
  return workspaceMobileDestinations
    .map(([id, name, icon]) => ({id, name, icon, href: id === 'conversations' ? workspaceChatHref(urls) : urls[id]}))
    .filter(item => item.href);
}

export function workspaceMobileSolutionItems(urls = {}) {
  return workspaceSolutions
    .filter(([id]) => !['workspace', 'studio'].includes(id) && urls.solutions?.[id])
    .map(([id, name, description]) => ({id, name, description, href: urls.solutions[id]}));
}

export function workspaceSolutionItems(bootstrap) {
  return workspaceSolutions.map(([id, name, description]) => ({
    id,
    name,
    description,
    href: bootstrap.urls?.solutions?.[id],
    icon: bootstrap.solutionIcons?.[id],
  }));
}
