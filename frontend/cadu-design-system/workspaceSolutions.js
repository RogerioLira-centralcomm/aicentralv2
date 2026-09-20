const workspaceSolutions = [
  ['workspace', 'Workspace', 'Projetos e contexto'],
  ['planner', 'Planner', 'Planos e cenários'],
  ['studio', 'Studio', 'Criação e análise'],
  ['connect', 'Reports', 'Relatórios e resultados'],
  ['skills', 'Skills', 'Recursos e automações'],
];

export function workspaceSolutionItems(bootstrap) {
  return workspaceSolutions.map(([id, name, description]) => ({
    id,
    name,
    description,
    href: bootstrap.urls?.solutions?.[id],
    icon: bootstrap.solutionIcons?.[id],
  }));
}
