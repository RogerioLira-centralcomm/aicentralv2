import React from 'react';
import {Icon} from '../lib/icons';

const MODE_LABELS = {fast: 'Rápido', analysis: 'Equilibrado', agentic: 'Profundo'};

function entityName(items, ref) {
  if (!ref || !Array.isArray(items)) return '';
  const item = items.find(candidate => String(candidate?.ref || candidate?.projectRef || candidate?.brandRef || candidate?.id || candidate?.slug || '') === String(ref));
  return item?.name || item?.title || '';
}

export function ConversationSupport({context, projects, brands, messages, diagnostics, executionMode, running, runtime, automation, onPrompt}) {
  const lastUser = [...(messages || [])].reverse().find(message => message.role === 'user');
  const projectName = entityName(projects, context?.project_ref);
  const brandName = entityName(brands, context?.brand_ref);
  const contextLabel = projectName || brandName || (context?.project_ref ? 'Projeto selecionado' : context?.brand_ref ? 'Marca selecionada' : 'Conversa livre');
  const contextDetail = projectName ? 'Projeto ativo' : brandName ? 'Marca ativa' : 'Sem contexto obrigatório';
  const latestRequest = String(lastUser?.content || '').replace(/\s+/g, ' ').trim();
  const requestPreview = latestRequest.length > 180 ? `${latestRequest.slice(0, 180).replace(/\s+\S*$/, '')}…` : latestRequest;
  const state = running ? (runtime || 'Gerando resposta') : messages?.length ? 'Pronto para continuar' : 'Aguardando seu primeiro pedido';
  const suggestions = latestRequest ? [
    ['Aprofundar', 'Aprofunde a última resposta considerando o pedido atual.'],
    ['Virar decisão', 'Transforme a última resposta em uma decisão prática.'],
    ['Validar lacunas', 'O que ainda falta validar para responder bem ao pedido atual?'],
  ] : [
    ['Começar conversa', 'Ajude-me a organizar o que preciso fazer.'],
    ['Explorar contexto', 'O que é relevante no contexto selecionado?'],
  ];
  return <div className="cv-conversation-support">
    <div className="cv-conversation-support__intro">
      <div><strong>Apoio à conversa</strong><span>Contexto vivo para o próximo passo</span></div>
      <span className={`cv-conversation-support__status ${running ? 'is-running' : ''}`}><i/>{running ? 'Em andamento' : 'Pronto'}</span>
    </div>
    <div className="cv-conversation-support__meta">
      <div><span>Contexto</span><b>{contextLabel}</b><small>{contextDetail}</small></div>
      <div><span>Intensidade</span><b>{MODE_LABELS[executionMode] || 'Equilibrado'}</b><small>Controle no campo de mensagem</small></div>
      <div><span>Estado</span><b>{state}</b><small>{diagnostics?.length ? `${diagnostics.length} evento${diagnostics.length === 1 ? '' : 's'} registrado${diagnostics.length === 1 ? '' : 's'}` : 'Sem eventos técnicos'}</small></div>
    </div>
    {automation?.section === 'automation' && <div className="cv-conversation-support__automation"><span>Automação</span><b>{automation.automation_enabled ? 'Ativa' : 'Desligada'}</b>{automation.schedule_label && <small>{automation.schedule_label}</small>}</div>}
    {requestPreview && <div className="cv-conversation-support__request"><span>Último pedido</span><p>“{requestPreview}”</p></div>}
    <div className="cv-conversation-support__next"><span>Próximos movimentos</span>{suggestions.map(([label, prompt]) => <button key={label} type="button" onClick={() => onPrompt(prompt)}>{label}<Icon name="chevron" size={13}/></button>)}</div>
    {!!diagnostics?.length && <details className="cv-conversation-support__technical"><summary>Ver atividade técnica</summary><div>{diagnostics.slice(-6).map(item => <div key={item.id} className="cv-conversation-support__event"><i className={item.tone === 'error' ? 'is-error' : ''}/><span><b>{item.title}</b>{item.detail && <small>{item.detail}</small>}</span></div>)}</div></details>}
  </div>;
}
