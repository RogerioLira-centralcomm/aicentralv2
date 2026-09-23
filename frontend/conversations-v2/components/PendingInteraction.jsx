import React from 'react';
import {Icon} from '../lib/icons';
import {meaningfulResponseBlocks} from '../lib/responseModel.mjs';

export function pendingInteraction(messages, running) {
  if (running || !messages?.length) return null;
  const message = messages[messages.length - 1];
  if (message?.role !== 'assistant' || message.kind === 'failure') return null;
  if (message.kind === 'action') {
    const name = String(message.action?.name || '');
    const presentation = name === 'projects.create_link_reference'
      ? {eyebrow: 'Adicionar referência', approve: 'Adicionar ao projeto', progress: 'Adicionando…', detail: 'O link será salvo sem leitura ou indexação automática.'}
      : name === 'projects.create_note'
        ? {eyebrow: 'Salvar anotação', approve: 'Salvar no projeto', progress: 'Salvando…', detail: 'A anotação ficará disponível no contexto do projeto.'}
        : name === 'projects.reindex_source'
          ? {eyebrow: 'Atualizar fonte', approve: 'Reindexar fonte', progress: 'Reindexando…', detail: 'O conteúdo da fonte será processado novamente.'}
          : name === 'brands.start_audit'
            ? {eyebrow: 'Iniciar auditoria', approve: 'Iniciar auditoria', progress: 'Iniciando…', detail: 'A análise será executada com o contexto disponível da marca.'}
            : name.startsWith('brands.')
              ? {eyebrow: 'Atualizar marca', approve: 'Confirmar alteração', progress: 'Atualizando…', detail: 'A alteração será aplicada à marca selecionada.'}
              : {eyebrow: 'Confirmar ação', approve: 'Confirmar', progress: 'Executando…', detail: 'Nada será alterado até você escolher uma opção.'};
    return {
      kind: 'action', message, eyebrow: presentation.eyebrow,
      question: message.action?.summary || 'Deseja concluir esta ação?',
      detail: message.actionError || presentation.detail,
      error: Boolean(message.actionError), pending: Boolean(message.actionPending),
      options: [
        {id: 'approve', label: message.actionPending ? presentation.progress : presentation.approve, detail: 'Confirma e conclui esta ação.', approved: true, recommended: true},
        {id: 'decline', label: 'Agora não', detail: 'Mantém a conversa sem executar a ação.', approved: false},
      ],
    };
  }
  const response = message.response || {};
  const blocks = meaningfulResponseBlocks(response.blocks);
  const questionBlock = [...blocks].reverse().find(block => ['question', 'questions'].includes(block.type) && Array.isArray(block.items) && block.items.length);
  if (questionBlock) {
    const question = questionBlock.items.find(item => item?.question || item?.title)?.question || questionBlock.title || 'Responda à pergunta para continuar';
    return {kind: 'question', question};
  }
  const decision = [...blocks].reverse().find(block => block.type === 'decision' && Array.isArray(block.items) && block.items.length);
  const question = decision?.summary || decision?.title || '';
  const options = decision?.items?.map(item => ({
    id: item.id || item.title, label: item.title, detail: item.detail || '',
    prompt: item.prompt || `Continue usando a opção “${item.title}”.`, recommended: Boolean(item.recommended),
  })) || [];
  if (!question && !options.length) return null;
  const normalizedOptions = options.length ? options : [{id: 'write-answer', label: 'Responder', prompt: question, asContext: true, freeform: true}];
  return {question: question || 'Escolha como continuar', options: normalizedOptions.slice(0, 4)};
}

export function PendingInteraction({interaction, onPrompt, onDecision}) {
  if (!interaction || interaction.kind === 'question') return null;
  const freeform = interaction.kind !== 'action' && interaction.options.length === 1 && interaction.options[0].freeform;
  const choose = option => interaction.kind === 'action'
    ? onDecision(interaction.message, option.approved)
    : option.autoSubmit || !option.asContext ? onPrompt(option.prompt) : onPrompt('', {type: 'question', label: 'Respondendo', text: option.prompt});
  return <section className={`cv-pending-interaction ${interaction.kind === 'action' ? 'is-action' : ''}`} aria-label="Ação necessária">
    <div className="cv-pending-interaction__heading"><Icon name={interaction.kind === 'action' ? 'pulse' : 'alert'} size={16}/><span><small>{interaction.eyebrow || 'Para continuar'}</small><strong>{interaction.question}</strong>{interaction.detail && <i className={interaction.error ? 'is-error' : ''} role={interaction.error ? 'alert' : undefined}>{interaction.detail}</i>}</span>{freeform && <button type="button" className="cv-pending-interaction__respond" onClick={() => choose(interaction.options[0])}>Responder</button>}</div>
    {!freeform && !!interaction.options.length && <div className="cv-pending-interaction__options">{interaction.options.map(option => <button key={option.id} className={option.recommended ? 'is-recommended' : ''} type="button" disabled={interaction.pending} onClick={() => choose(option)}><span><b>{option.label}</b>{option.detail && <small>{option.detail}</small>}</span>{option.recommended && <em>Recomendada</em>}<Icon name="chevron" size={14}/></button>)}</div>}
  </section>;
}
