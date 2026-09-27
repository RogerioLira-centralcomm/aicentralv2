// Keep a local presentation fallback for deployments where the capabilities
// endpoint predates the shared flow catalog.
export const PLUGIN_FLOWS = [
  {id:'intelligence', name:'Inteligência', icon:'analysis', description:'Pesquise mercado, concorrentes e sinais com fontes verificáveis.', steps:['Escolha Pesquisa, Radar, Insights ou Cases e defina o recorte.','Pesquisa e Radar consultam fontes externas; Insights usa contexto da marca; Cases busca referências no conteúdo do projeto.','Veja achados com fontes consultadas, contexto e limites da busca.'], modes:[['market-intelligence','Pesquisa'],['market-radar','Radar'],['insights','Insights'],['campaign-search','Cases']]},
  {id:'media-strategy', name:'Estratégia de mídia', icon:'table', description:'Planeje públicos, canais, cenários e revise a coerência do plano.', steps:['Escolha plano, públicos, cenários ou auditoria.','Plano estrutura a campanha; Públicos respeita os canais pedidos; Cenários simula; Auditoria revisa um plano existente.','Compare premissas e lacunas; a auditoria não altera o plano.'], modes:[['planner','Plano'],['audience-map','Públicos'],['investment-simulator','Cenários'],['media-plan-audit','Auditoria']]},
  {id:'creative-experience', name:'Criação e experiência', icon:'image', description:'Desenvolva conceitos e textos e encontre melhorias na página.', steps:['Escolha conceito, copy, revisão de página ou criação visual.','Conceito e Copy partem do briefing; Página requer URL ou conteúdo; Studio prepara o pedido visual no chat.','Revise a proposta no chat e peça material editável quando precisar.'], modes:[['creative-concept','Conceito'],['channel-copy','Copy'],['page-review','Página'],['studio','Studio']]},
  {id:'performance', name:'Performance', icon:'analysis', description:'Leia resultados reais e priorize mudanças na campanha.', steps:['Campanha analisa um relatório anexado; Relatórios consulta relatórios revisados do projeto.','O Cadu identifica métricas e períodos presentes e só compara dados compatíveis.','Veja achados e próximos passos ligados às fontes consultadas.'], modes:[['campaign-tracker','Campanha'],['reports','Relatórios']]},
  {id:'project-operations', name:'Operações do projeto', icon:'list', description:'Recupere decisões, organize tarefas, reuniões e status.', steps:['Escolha busca, tarefas, reunião ou status.','Busca recupera conteúdo do projeto; Tarefas lista atividades; Reunião usa notas ou prepara pauta; Status consulta tarefas e recursos.','Veja a origem e os responsáveis quando esses dados estiverem registrados.'], modes:[['project-search','Buscar'],['project-activities','Tarefas'],['meeting-copilot','Reunião'],['client-delivery','Status']]},
];

export function availableFlows(plugins, flowCatalog = []) {
  const catalog = Array.isArray(flowCatalog) && flowCatalog.length ? flowCatalog : PLUGIN_FLOWS.map(flow => ({
    ...flow,
    modes: flow.modes.map(([id, label]) => ({id, label})),
  }));
  const all = new Map((plugins || []).map(plugin => [plugin.id, plugin]));
  const entries = new Map((plugins || []).filter(plugin => plugin.selectable &&
    ['active', 'in_development'].includes(plugin.maturity)).map(plugin => [plugin.id, plugin]));
  return catalog.map(flow => ({
    ...flow,
    availableModes: (flow.modes || []).map(mode => ({...mode, plugin: entries.get(mode.id)}))
      .filter(mode => mode.plugin),
    upcomingModes: (flow.modes || []).filter(mode => !entries.has(mode.id)),
  })).filter(flow => flow.availableModes.length);
}

export function flowPluginIds(flowCatalog = []) {
  const catalog = Array.isArray(flowCatalog) && flowCatalog.length ? flowCatalog : PLUGIN_FLOWS.map(flow => ({
    modes: flow.modes.map(([id]) => ({id})),
  }));
  return new Set(catalog.flatMap(flow => (flow.modes || []).map(mode => mode.id)));
}
