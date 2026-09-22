import React, {useMemo} from 'react';
import {Icon} from './Icon';

const PERSONAL_SUGGESTIONS = [
  {label: 'Organizar minhas prioridades', prompt: 'Organize minhas prioridades de hoje e proponha uma sequência prática para começar.'},
  {label: 'Retomar uma pendência', prompt: 'Revise minhas conversas recentes e destaque a pendência mais importante para eu retomar agora.'},
  {label: 'Analisar um arquivo', prompt: 'Ajude a analisar um arquivo recente e transforme os principais achados em próximos passos.'},
  {label: 'Começar um briefing', prompt: 'Estruture um briefing inicial e faça apenas as perguntas necessárias para avançar.'},
];

function suggestionsFor({project, brand, home = {}}) {
  const configured = Array.isArray(home.conversationSuggestions) ? home.conversationSuggestions : [];
  if (configured.length) return configured.slice(0, 3).map(item => ({label: item.label || item.title, prompt: item.prompt || item.label || item.title}));
  if (project) {
    const name = project.name || project.title || 'este projeto';
    const hasSources = Number(project.sources || project.fontes_prontas || 0) > 0;
    return [
      {label: 'Ler o contexto do projeto', prompt: `Faça uma leitura do contexto de ${name} e destaque o que está claro e o que falta decidir.`},
      {label: hasSources ? 'Pesquisar nas fontes' : 'Adicionar as primeiras fontes', prompt: hasSources ? `Pesquise nas fontes de ${name} e traga os pontos mais relevantes para o próximo passo.` : `Sugira as fontes e referências que devemos adicionar a ${name} para começar bem.`},
      {label: 'Mapear próximos passos', prompt: `Mapeie os próximos passos de ${name}, separando decisões, tarefas e riscos.`},
      {label: 'Criar um briefing', prompt: `Monte um briefing objetivo para ${name} com base no contexto disponível e indique as lacunas.`},
    ];
  }
  if (brand) {
    const name = brand.name || brand.title || 'esta marca';
    return [
      {label: `Entender ${name}`, prompt: `Resuma a identidade e as oportunidades de trabalho de ${name}.`},
      {label: 'Criar uma direção', prompt: `Crie uma direção criativa para trabalhar ${name} sem perder sua identidade.`},
      {label: 'Planejar uma campanha', prompt: `Monte um plano inicial de campanha para ${name} e destaque as decisões necessárias.`},
      {label: 'Encontrar referências', prompt: `Sugira referências e caminhos visuais coerentes com ${name}.`},
    ];
  }
  return PERSONAL_SUGGESTIONS;
}

export function buildWorkspaceSuggestions(options = {}) {
  return suggestionsFor(options).filter(item => item.label && item.prompt).slice(0, 3);
}

export function WorkspacePromptSuggestions({project, brand, home, onSelect, compact = false, surface = 'chat'}) {
  const suggestions = useMemo(() => buildWorkspaceSuggestions({project, brand, home}), [brand, home, project]);
  return <section className={`cadu-ds-prompt-suggestions is-${surface} ${compact ? 'is-compact' : ''}`} aria-label={project ? `Sugestões para ${project.name || 'o projeto'}` : 'Sugestões para começar'}>
    <span className="cadu-ds-prompt-suggestions__label">{project ? `Para ${project.name || 'este projeto'}` : brand ? `Para ${brand.name || 'esta marca'}` : surface === 'workspace-home' ? 'Ou escolha um ponto de partida' : 'Comece por aqui'}</span>
    <div>{suggestions.map(item => <button key={item.label} type="button" onClick={() => onSelect?.(item.prompt)}><span>{item.label}{surface === 'workspace-home' && <small>Preparar no chat</small>}</span><Icon name="chevron" size={16}/></button>)}</div>
  </section>;
}
