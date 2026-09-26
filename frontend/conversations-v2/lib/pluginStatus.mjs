export function routeSelectedStatus({plugin, targetArtifact} = {}) {
  if (targetArtifact?.title) return `Revisando ${targetArtifact.title}`;
  if (plugin?.name) return `Acionando ${plugin.name}`;
  return 'Preparando o contexto';
}

export function unavailableToolStatus(toolName = '') {
  const name = String(toolName || '');
  if (name.startsWith('web.')) return 'Pesquisa externa indisponível';
  if (name.startsWith('google.')) return 'Google Workspace indisponível';
  if (/^(workspace|projects|resources|artifacts)\./.test(name)) return 'Dados do projeto indisponíveis';
  if (name.startsWith('planner.')) return 'Dados de planejamento indisponíveis';
  if (name.startsWith('reports.') || name.startsWith('campaign.')) return 'Dados de desempenho indisponíveis';
  return 'Uma etapa do plugin está indisponível';
}
