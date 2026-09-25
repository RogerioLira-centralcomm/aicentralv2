const prompts = {
  'market-intelligence': '/market-intelligence quick Faça um scan do mercado relacionado ao contexto selecionado. Diferencie fatos, interpretações e hipóteses e cite as fontes.',
  insights: 'Pesquise insights atuais de marketing e mídia para o mercado da marca deste projeto.',
  planner: 'Estruture um plano de mídia para a campanha deste projeto.',
  'project-search': 'Busque no projeto as informações relevantes para minha próxima pergunta.',
  'project-activities': 'Consulte as atividades deste projeto e sugira os próximos passos.',
  'campaign-search': 'Busque campanhas e cases relacionados à marca deste projeto.',
  reports: 'Analise os relatórios revisados deste projeto e destaque decisões práticas.',
  studio: 'Ajude a criar uma imagem para a campanha deste projeto.',
  'market-radar': '/market-radar Pesquise movimentos recentes do mercado e dos concorrentes da marca deste projeto.',
  'audience-map': '/audience-map Mapeie segmentos de público e canais para a marca deste projeto.',
  'investment-simulator': '/investment-simulator Proponha cenários de verba para este projeto; use percentuais se não houver valor definido.',
  'media-plan-audit': '/media-plan-audit Revise o plano de mídia deste projeto e priorize os ajustes.',
  'campaign-tracker': '/campaign-tracker Analise o relatório que anexei, extraia os resultados e indique os próximos passos prioritários.',
  'creative-concept': '/creative-concept Proponha um conceito criativo para a marca deste projeto.',
  'channel-copy': '/channel-copy Escreva variações de texto para os canais desta campanha.',
  'page-review': '/page-review Revise a página que vou indicar e priorize melhorias.',
  'meeting-copilot': '/meeting-copilot Prepare uma pauta objetiva para a próxima reunião deste projeto.',
  'client-delivery': '/client-delivery Organize o status e os próximos passos deste projeto para o cliente.',
};

export function pluginPrompt(plugin) {
  return prompts[plugin?.id] || '';
}
