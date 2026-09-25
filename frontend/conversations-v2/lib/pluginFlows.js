// Product-facing flows. Mode IDs retain the existing command/runtime contracts.
export const PLUGIN_FLOWS = [
  {id: 'intelligence', name: 'Inteligência', icon: 'analysis',
    description: 'Pesquise mercado, concorrentes e sinais com fontes verificáveis.',
    modes: [['market-intelligence', 'Pesquisa'], ['market-radar', 'Radar'], ['insights', 'Insights'], ['campaign-search', 'Cases']]},
  {id: 'media-strategy', name: 'Estratégia de mídia', icon: 'table',
    description: 'Planeje públicos, canais, cenários e revise a coerência do plano.',
    modes: [['planner', 'Plano'], ['audience-map', 'Públicos'], ['investment-simulator', 'Cenários'], ['media-plan-audit', 'Auditoria']]},
  {id: 'creative-experience', name: 'Criação e experiência', icon: 'image',
    description: 'Desenvolva conceitos e textos e encontre melhorias na página.',
    modes: [['creative-concept', 'Conceito'], ['channel-copy', 'Copy'], ['page-review', 'Página'], ['studio', 'Studio']]},
  {id: 'performance', name: 'Performance', icon: 'analysis',
    description: 'Leia resultados reais e priorize mudanças na campanha.',
    modes: [['campaign-tracker', 'Campanha'], ['reports', 'Relatórios']]},
  {id: 'project-operations', name: 'Operações do projeto', icon: 'list',
    description: 'Recupere decisões, organize tarefas, reuniões e status.',
    modes: [['project-search', 'Buscar'], ['project-activities', 'Tarefas'], ['meeting-copilot', 'Reunião'], ['client-delivery', 'Status']]},
];

export function availableFlows(plugins) {
  const all = new Map((plugins || []).map(plugin => [plugin.id, plugin]));
  const entries = new Map((plugins || []).filter(plugin => plugin.selectable &&
    ['active', 'in_development'].includes(plugin.maturity)).map(plugin => [plugin.id, plugin]));
  return PLUGIN_FLOWS.map(flow => ({
    ...flow,
    availableModes: flow.modes.map(([id, label]) => ({id, label, plugin: entries.get(id)}))
      .filter(mode => mode.plugin),
    upcomingModes: flow.modes.filter(([id]) => all.has(id) && !entries.has(id))
      .map(([id, label]) => ({id, label})),
  })).filter(flow => flow.availableModes.length);
}
