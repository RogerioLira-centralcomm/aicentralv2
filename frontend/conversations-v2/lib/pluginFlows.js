// Product-facing flows. Mode IDs retain the existing command/runtime contracts.
export const PLUGIN_FLOWS = [
  {id: 'intelligence', name: 'Inteligência', icon: 'analysis',
    description: 'Pesquise mercado, concorrentes e sinais com fontes verificáveis.',
    steps: ['Escolha o modo e defina tema, marca e período.', 'Pesquisa e Radar buscam fontes externas; Insights e Cases seguem seus recortes próprios.', 'Veja achados com fontes recuperadas, contexto e limites da busca.'],
    modes: [['market-intelligence', 'Pesquisa'], ['market-radar', 'Radar'], ['insights', 'Insights'], ['campaign-search', 'Cases']]},
  {id: 'media-strategy', name: 'Estratégia de mídia', icon: 'table',
    description: 'Planeje públicos, canais, cenários e revise a coerência do plano.',
    steps: ['Escolha plano, públicos, cenários ou auditoria.', 'Plano estrutura a campanha; Públicos respeita os canais pedidos; Cenários simula; Auditoria revisa um plano existente.', 'Compare premissas e lacunas; a auditoria não altera o plano.'],
    modes: [['planner', 'Plano'], ['audience-map', 'Públicos'], ['investment-simulator', 'Cenários'], ['media-plan-audit', 'Auditoria']]},
  {id: 'creative-experience', name: 'Criação e experiência', icon: 'image',
    description: 'Desenvolva conceitos e textos e encontre melhorias na página.',
    steps: ['Escolha conceito, copy, revisão de página ou criação visual.', 'Conceito e Copy usam o briefing; Página precisa de uma URL; Studio abre a criação visual.', 'Revise a proposta no chat e peça material editável quando precisar.'],
    modes: [['creative-concept', 'Conceito'], ['channel-copy', 'Copy'], ['page-review', 'Página'], ['studio', 'Studio']]},
  {id: 'performance', name: 'Performance', icon: 'analysis',
    description: 'Leia resultados reais e priorize mudanças na campanha.',
    steps: ['Campanha analisa um relatório anexado; Relatórios consulta relatórios revisados do projeto.', 'O Cadu identifica métricas e períodos presentes e só compara dados compatíveis.', 'Veja achados e próximos passos ligados às fontes consultadas.'],
    modes: [['campaign-tracker', 'Campanha'], ['reports', 'Relatórios']]},
  {id: 'project-operations', name: 'Operações do projeto', icon: 'list',
    description: 'Recupere decisões, organize tarefas, reuniões e status.',
    steps: ['Escolha busca, tarefas, reunião ou status.', 'Busca e Tarefas consultam registros do projeto; Reunião usa notas disponíveis ou prepara uma pauta.', 'Status organiza tarefas e recursos; responsáveis aparecem quando constam nas fontes.'],
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
