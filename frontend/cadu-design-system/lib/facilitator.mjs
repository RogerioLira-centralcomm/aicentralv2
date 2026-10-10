// Facilitador: sugestões de pedido na voz do usuário, filtradas pelo perfil de trabalho.
// Só prepara texto para o composer; nunca envia nada por conta própria.

export const FACILITATOR_PROFILES = [
  {id: 'planejamento', label: 'Planejamento'},
  {id: 'atendimento', label: 'Atendimento'},
  {id: 'midia', label: 'Operação de mídia'},
  {id: 'gestor', label: 'Gestor'},
  {id: 'diretor', label: 'Diretor'},
];

export const DEFAULT_FACILITATOR_PROFILE = 'planejamento';
export const MAX_FACILITATOR_SUGGESTIONS = 4;

const PROFILE_KEY = 'cadu.facilitator.profile';

// `text` recebe a referência ao projeto já com preposição (de/em/para), para não gerar "de este projeto". `needsProject` esconde a
// sugestão em conversas sem projeto, porque ela dependeria de dados que o Cadu não tem ali.
const RECIPES = [
  {id: 'briefing', icon: 'list', profiles: ['planejamento', 'atendimento'], needsProject: true,
    text: p => `Estruture um briefing ${p.para} e destaque somente o que ainda precisa ser decidido.`},
  {id: 'plano-midia', icon: 'table', profiles: ['planejamento', 'gestor'], needsProject: true,
    text: p => `Crie um plano de mídia inicial ${p.para} com hipóteses e decisões necessárias.`},
  {id: 'concorrentes', icon: 'analysis', profiles: ['planejamento', 'diretor'], needsProject: false,
    text: p => `Mapeie os principais concorrentes ${p.de} e compare posicionamento e diferenciais.`},
  {id: 'ilustracao', icon: 'image', profiles: ['planejamento', 'atendimento', 'midia'], needsProject: false,
    text: () => 'Crie uma ilustração para uma campanha. Pergunte o que faltar sobre marca, público e objetivo antes de gerar.'},
  {id: 'pauta', icon: 'calendar', profiles: ['atendimento', 'gestor'], needsProject: true,
    text: p => `Crie uma pauta de reunião objetiva ${p.para}, com temas, resultado esperado e decisões a tomar.`},
  {id: 'relatorio-cliente', icon: 'file', profiles: ['atendimento', 'midia'], needsProject: true,
    text: p => `Monte um relatório para o cliente com os principais resultados ${p.de} e os próximos passos.`},
  {id: 'resumo-reuniao', icon: 'file', profiles: ['atendimento', 'gestor'], needsProject: false,
    text: () => 'Transforme este conteúdo em um resumo de reunião: decisões, pendências, responsáveis e próximos passos.'},
  {id: 'diagnostico', icon: 'analysis', profiles: ['midia', 'diretor'], needsProject: true,
    text: p => `Analise o desempenho das campanhas ${p.de} e aponte as principais oportunidades de melhoria.`},
  {id: 'otimizacoes', icon: 'table', profiles: ['midia'], needsProject: true,
    text: p => `Sugira otimizações para a semana ${p.em}, priorizando o que mais impacta o resultado.`},
  {id: 'criativos', icon: 'image', profiles: ['midia'], needsProject: true,
    text: p => `Crie novos anúncios ${p.para}, com variações de mensagem para testar.`},
  {id: 'prazos', icon: 'history', profiles: ['gestor'], needsProject: true,
    text: p => `Liste as atividades ${p.de} agrupadas por prazo: vencidas, próximos 7 dias e sem prazo, com responsável.`},
  {id: 'resumo-executivo', icon: 'list', profiles: ['diretor', 'gestor'], needsProject: true,
    text: p => `Faça um resumo executivo ${p.de} em 5 tópicos: resultado, riscos, decisões pendentes e próximos passos.`},
  {id: 'apresentacao', icon: 'file', profiles: ['diretor', 'atendimento'], needsProject: true,
    text: p => `Transforme o que temos ${p.de} em uma apresentação executiva de 8 slides.`},
];

export function normalizeFacilitatorProfile(value) {
  return FACILITATOR_PROFILES.some(profile => profile.id === value) ? value : DEFAULT_FACILITATOR_PROFILE;
}

/** Sugestões do perfil, em ordem estável. Sem projeto, só as que não dependem dele. */
export function facilitatorSuggestions({profile, projectName = '', hasProject = false} = {}) {
  const id = normalizeFacilitatorProfile(profile);
  const name = String(projectName || '').trim();
  const project = name
    ? {de: `de ${name}`, em: `em ${name}`, para: `para ${name}`}
    : hasProject ? {de: 'deste projeto', em: 'neste projeto', para: 'para este projeto'}
      : {de: 'da marca', em: 'na marca', para: 'para a marca'};
  return RECIPES
    .filter(recipe => recipe.profiles.includes(id) && (hasProject || !recipe.needsProject))
    .slice(0, MAX_FACILITATOR_SUGGESTIONS)
    .map(recipe => ({id: recipe.id, icon: recipe.icon, text: recipe.text(project)}));
}

export function loadFacilitatorProfile(storage = globalThis.localStorage) {
  try { return normalizeFacilitatorProfile(storage?.getItem(PROFILE_KEY)); } catch (_) { return DEFAULT_FACILITATOR_PROFILE; }
}

export function saveFacilitatorProfile(profile, storage = globalThis.localStorage) {
  try { storage?.setItem(PROFILE_KEY, normalizeFacilitatorProfile(profile)); } catch (_) { /* preferência opcional */ }
}
