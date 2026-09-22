import React, {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react';
import {Icon} from '../lib/icons';
import {Markdown} from './Markdown';
import {safeUrl} from '../lib/api';
import {ResponseBlocks} from './ResponseBlocks';
import {WorkspaceChatComposer} from '../../cadu-design-system/components/WorkspaceChatComposer';
import {WorkspacePromptSuggestions} from '../../cadu-design-system/components/WorkspacePromptSuggestions';
import {WorkspaceSourceList} from '../../cadu-design-system/components/WorkspaceSourceList';
import {WorkspaceTaskProgress} from '../../cadu-design-system/components/WorkspaceTaskProgress';
import {meaningfulResponseBlocks, normalizeAnswerText} from '../lib/responseModel.mjs';

function FailureCard({failure, prompt, onRevisitPrompt, creditsUrl}) {
  const needsCredits = failure?.kind === 'credits';
  const needsRefresh = failure?.kind === 'session';
  return <section className={`cv-chat-failure cv-chat-failure--${failure?.kind || 'generic'}`} role="alert">
    <div className="cv-chat-failure__marker" aria-hidden="true">{needsCredits ? '¢' : '!'}</div>
    <div className="cv-chat-failure__body">
      <span className="cv-chat-failure__eyebrow">{needsCredits ? 'Créditos da conta' : 'Conversa'}</span>
      <h2>{needsCredits ? 'Vamos liberar mais espaço para esse trabalho' : failure?.title || 'Não foi possível concluir esta solicitação'}</h2>
      <p>{needsCredits ? 'Seu saldo atual não é suficiente para concluir esta solicitação. Adicione créditos e tente novamente quando estiver pronto.' : failure?.detail}</p>
      {failure?.guidance && <small>{failure.guidance}</small>}
      <div className="cv-chat-failure__actions">
        {needsCredits && creditsUrl && <a href={creditsUrl}>Adicionar créditos</a>}
        {!needsCredits && (needsRefresh ? <button type="button" onClick={() => window.location.reload()}>Atualizar página</button> : null)}
      </div>
    </div>
  </section>;
}

const MODE_LABELS = {fast: 'Rápido', analysis: 'Equilibrado', agentic: 'Profundo'};

function entityName(items, ref) {
  if (!ref || !Array.isArray(items)) return '';
  const item = items.find(candidate => String(candidate?.ref || candidate?.projectRef || candidate?.brandRef || candidate?.id || candidate?.slug || '') === String(ref));
  return item?.name || item?.title || '';
}

function ConversationSupport({context, projects, brands, messages, diagnostics, executionMode, running, runtime, onPrompt}) {
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
      <div>
        <strong>Apoio à conversa</strong>
        <span>Contexto vivo para o próximo passo</span>
      </div>
      <span className={`cv-conversation-support__status ${running ? 'is-running' : ''}`}><i/>{running ? 'Em andamento' : 'Pronto'}</span>
    </div>
    <div className="cv-conversation-support__meta">
      <div><span>Contexto</span><b>{contextLabel}</b><small>{contextDetail}</small></div>
      <div><span>Intensidade</span><b>{MODE_LABELS[executionMode] || 'Equilibrado'}</b><small>Controle no campo de mensagem</small></div>
      <div><span>Estado</span><b>{state}</b><small>{diagnostics?.length ? `${diagnostics.length} evento${diagnostics.length === 1 ? '' : 's'} registrado${diagnostics.length === 1 ? '' : 's'}` : 'Sem eventos técnicos'}</small></div>
    </div>
    {requestPreview && <div className="cv-conversation-support__request"><span>Último pedido</span><p>“{requestPreview}”</p></div>}
    <div className="cv-conversation-support__next"><span>Próximos movimentos</span>{suggestions.map(([label, prompt]) => <button key={label} type="button" onClick={() => onPrompt(prompt)}>{label}<Icon name="chevron" size={13}/></button>)}</div>
    {!!diagnostics?.length && <details className="cv-conversation-support__technical"><summary>Ver atividade técnica</summary><div>{diagnostics.slice(-6).map(item => <div key={item.id} className="cv-conversation-support__event"><i className={item.tone === 'error' ? 'is-error' : ''}/><span><b>{item.title}</b>{item.detail && <small>{item.detail}</small>}</span></div>)}</div></details>}
  </div>;
}

function Answer({message, onPrompt, onOpenArtifact, onOpenResource, onDecision, onRevisitPrompt, creditsUrl}) {
  const response = message.response || {answer: message.content};
  const text = normalizeAnswerText(response.answer || '')
    .replace(/^\s*[^|\n]{1,240}\|\s*Confian(?:ça|ca)\s*:\s*\**\s*(?:baixa|m[eé]dia|alta|low|medium|high)\**[.,]?\s*/i, '')
    .replace(/^\s*S[ií]ntese:\s*contexto:\s*[^;]+;\s*decis(?:ão|ao):\s*[^;]+;\s*/i, '')
    .replace(/^\s*Projeto usado:\s*[^.]+\.\s*/i, '')
    .replace(/^\s*Decis(?:ão|ao) proposta:\s*/i, '')
    .replace(/\s+Confian(?:ça|ca):\s*[^.]+\.?/ig, '')
    .replace(/\s+Próxima ação:\s*[^.]+\.?/ig, '')
    .trim();
  const blocks = meaningfulResponseBlocks(response.blocks);
  const visibleQuestions = (Array.isArray(response.questions) ? response.questions : []).filter(question => {
    const normalized = String(question || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase('pt-BR');
    return normalized && !text.replace(/\s+/g, ' ').toLocaleLowerCase('pt-BR').includes(normalized);
  }).slice(0, 4);
  if (message.kind === 'failure') return <FailureCard failure={message.failure} prompt={message.prompt} onRevisitPrompt={onRevisitPrompt} creditsUrl={creditsUrl}/>;
  if (message.kind === 'action') {
    return <div className="cv-action-confirmation cv-max-w-[72ch]">
      <div className="cv-action-confirmation__heading"><Icon name="pulse" size={15}/><span>Confirme antes de continuar</span></div>
      <p>{message.action?.summary || 'Esta ação precisa da sua confirmação.'}</p>
      <small>O Cadu só executa esta etapa depois da sua confirmação.</small>
      <div className="cv-action-confirmation__actions"><button type="button" onClick={() => onDecision(message, false)}>Cancelar</button><button type="button" onClick={() => onDecision(message, true)}>Confirmar ação</button></div>
    </div>;
  }
  return <div className="cv-message-enter cv-assistant-answer cv-max-w-[72ch]">
    <div className="cv-prose"><Markdown>{text}</Markdown></div>
    {!!blocks.length && <ResponseBlocks blocks={blocks} onPrompt={onPrompt} onOpenResource={onOpenResource}/>}
    {!!visibleQuestions.length && <section className="cv-inline-questions cv-mt-6" aria-label="Perguntas para continuar">
      <span className="cv-inline-questions__label">Para continuar</span>
      {visibleQuestions.map((question, index) => <button key={index} type="button" onClick={() => onPrompt('', {type: 'question', label: 'Respondendo', text: question})} className="cv-inline-question"><span>{question}</span><small>Responder</small></button>)}
    </section>}
    {!!response.assumptions?.length && <details className="cv-mt-4 cv-text-xs cv-text-mist"><summary className="cv-cursor-pointer">{response.assumptions.length === 1 ? 'Premissa usada' : `${response.assumptions.length} premissas usadas`}</summary><ul>{response.assumptions.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
    {!!response.citations?.length && <WorkspaceSourceList items={response.citations.slice(0, 4).map(item => ({title: item.title || 'Fonte', href: safeUrl(item?.url)}))}/>}
    {!!response.actions?.length && <section className="cv-mt-5 cv-border-t cv-border-white/[.07] cv-pt-4"><span className="cv-mb-2 cv-block cv-text-[10px] cv-font-semibold cv-uppercase cv-tracking-[.08em] cv-text-[#78918d]">Próximas ações</span><div className="cv-flex cv-flex-wrap cv-gap-2">{response.actions.slice(0, 3).map((item, index) => <button key={index} type="button" onClick={() => onPrompt(item.prompt || '')} className={`${item.style === 'primary' ? 'cv-border-teal/30 cv-bg-teal/10 cv-text-teal' : 'cv-border-white/10 cv-bg-transparent cv-text-[#c7d8d4]'} cv-rounded-lg cv-border cv-px-3 cv-py-2 cv-text-xs hover:cv-bg-white/[.08]`}>{item.label}</button>)}</div></section>}
    {!message.streaming && text.length > 5000 && !message.artifact?.id && <div className="cv-long-answer-action"><span>Este conteúdo pode continuar em um documento editável.</span><button type="button" onClick={() => onPrompt('Transforme sua última resposta completa em um documento editável, preserve todos os detalhes e abra o artefato ao lado.')}>Abrir como documento</button></div>}
    {message.artifact?.id && <button type="button" onClick={() => onOpenArtifact(message.artifact)} className="cv-mt-5 cv-flex cv-items-center cv-gap-2 cv-rounded-lg cv-border-0 cv-bg-teal/10 cv-px-3 cv-py-2 cv-text-xs cv-font-semibold cv-text-[#66dbce] hover:cv-bg-teal/15"><Icon name="file" size={15}/>Abrir {message.artifact.title || 'artefato'}</button>}
  </div>;
}

function SelectionTools({text, onPrompt, onClear}) {
  const quote = text.length > 420 ? `${text.slice(0, 420).replace(/\s+\S*$/, '')}…` : text;
  const createText = () => {
    onClear();
    onPrompt('Crie um texto editável somente a partir do trecho selecionado e abra o resultado em um artefato de texto. Não inclua a conversa, a árvore de resposta, instruções técnicas ou conteúdo fora do trecho.', {
      type: 'selection', label: 'Trecho para criar texto', text: quote,
    });
  };
  return <div className="cv-selection-tools cv-sticky cv-bottom-6 cv-z-10 cv-mx-auto cv-mb-5 cv-flex cv-w-fit cv-max-w-[calc(100%-32px)] cv-flex-wrap cv-items-center cv-justify-center cv-gap-1.5 cv-rounded-xl cv-border cv-border-teal/25 cv-bg-[#102326]/95 cv-p-1.5 cv-shadow-xl cv-backdrop-blur" role="toolbar" aria-label="Ações para o trecho selecionado">
    <span className="cv-px-2 cv-text-[10px] cv-text-[#8faaa5]">Trecho selecionado</span>
    <button type="button" onClick={createText} className="cv-rounded-lg cv-border-0 cv-bg-teal/15 cv-px-2.5 cv-py-1.5 cv-text-[11px] cv-font-semibold cv-text-teal hover:cv-bg-teal/25">Criar texto no artefato</button>
    <button type="button" onClick={onClear} className="cv-grid cv-h-6 cv-w-6 cv-place-items-center cv-rounded-md cv-border-0 cv-bg-transparent cv-text-[#7e9994] hover:cv-bg-white/[.07] hover:cv-text-white" aria-label="Fechar ações do trecho">×</button>
  </div>;
}

function Thread({messages, onPrompt, onOpenArtifact, onOpenResource, onDecision, onRevisitPrompt, creditsUrl, onOpenDiagnostics, running, runtime, diagnostics, starterProject, starterBrand, starterHome}) {
  const thread = useRef(null);
  const [selection, setSelection] = useState('');
  const showActivity = running;
  const hasStreamingAnswer = messages.some(message => message.role === 'assistant' && message.streaming);
  const captureSelection = () => {
    window.requestAnimationFrame(() => {
      const current = window.getSelection();
      const text = String(current?.toString() || '').replace(/\s+/g, ' ').trim();
      const anchor = current?.anchorNode;
      if (!text || text.length < 3 || text.length > 1200 || !anchor || !thread.current?.contains(anchor)) return;
      const answer = anchor.parentElement?.closest('[data-cv-answer]');
      if (!answer) return;
      setSelection(text);
    });
  };
  const clearSelection = () => { setSelection(''); window.getSelection()?.removeAllRanges(); };
  if (!messages.length && !running) return <div className="cv-empty-state cv-flex cv-min-h-full cv-items-center cv-justify-center cv-px-6 cv-py-16">
    <div className="cv-w-full cv-max-w-[700px] cv-text-center">
      <h2 className="cv-mb-2 cv-mt-0 cv-text-2xl cv-font-semibold cv-tracking-[-.025em]">Em que vamos trabalhar?</h2>
      <p className="cv-mx-auto cv-mb-8 cv-max-w-[520px] cv-text-sm cv-leading-6 cv-text-mist">Converse, analise arquivos ou crie algo usando o contexto do projeto.</p>
      <WorkspacePromptSuggestions project={starterProject} brand={starterBrand} home={starterHome} onSelect={onPrompt} compact/>
    </div>
  </div>;
  return <div ref={thread} onMouseUp={captureSelection} className="cv-thread-content cv-mx-auto cv-w-full cv-max-w-[940px] cv-px-6 cv-pt-7 md:cv-px-10">
    {messages.map(message => message.role === 'user' ? <article key={message.id} className="cv-message cv-message--user cv-mb-7 cv-flex cv-flex-col cv-items-end"><span className="cv-message__label">Você</span><div className="cv-user-message cv-max-w-[68ch] cv-rounded-2xl cv-rounded-br-md cv-bg-[#12322f] cv-px-4 cv-py-3 cv-text-[14px] cv-leading-6 cv-text-[#f0f8f6]"><p className="cv-m-0 cv-whitespace-pre-wrap">{message.content}</p>{!!message.files?.length && <small className="cv-mt-2 cv-block cv-text-[#8fc6bf]">{message.files.map(file => file.name || 'Arquivo').join(', ')}</small>}</div></article> : message.kind === 'worked' ? null : <React.Fragment key={message.id}>{message.streaming && showActivity && <article className="cv-message cv-message--assistant cv-message--activity cv-mb-5"><span className="cv-message__label">Cadu</span><WorkspaceTaskProgress running={running} runtime={runtime} diagnostics={diagnostics}/></article>}<article data-cv-answer="true" className="cv-message cv-message--assistant cv-mb-7"><span className="cv-message__label">{message.streaming ? 'Resposta' : 'Cadu'}</span><Answer message={message} onPrompt={onPrompt} onOpenArtifact={onOpenArtifact} onOpenResource={onOpenResource} onDecision={onDecision} onRevisitPrompt={onRevisitPrompt} creditsUrl={creditsUrl}/></article></React.Fragment>)}
    {selection && <SelectionTools text={selection} onPrompt={onPrompt} onClear={clearSelection}/>}
    {showActivity && !hasStreamingAnswer && <article className="cv-message cv-message--assistant cv-message--activity cv-mb-7"><span className="cv-message__label">Cadu</span><WorkspaceTaskProgress running={running} runtime={runtime} diagnostics={diagnostics}/></article>}
  </div>;
}

export function Conversation({conversationId, title, context, projects, brands, starterProject, starterBrand, starterHome, contextLoading, runtime, diagnostics, messages, input, setInput, onSubmit, attachments, onRemoveAttachment, onAttachmentPurposeChange, attachmentDestination, onAttachmentDestinationChange, executionMode, onExecutionModeChange, running, onStop, onPrompt, onOpenArtifact, onOpenResource, onDecision, onRevisitPrompt, creditsUrl, onOpenHistory, historyOpen, artifactOpen, composerContext, onClearContext, onAttach, onContextDrop}) {
  const details = useRef(null);
  const historyTrigger = useRef(null);
  const wasHistoryOpen = useRef(historyOpen);
  const threadScroll = useRef(null);
  const stickToLatest = useRef(true);
  const previousConversation = useRef(conversationId);
  const scrollToLatest = useCallback(() => {
    const element = threadScroll.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, []);
  const trackScrollPosition = useCallback(event => {
    const element = event.currentTarget;
    stickToLatest.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
  }, []);
  const stopFollowingLatest = useCallback(() => { stickToLatest.current = false; }, []);
  const handleScrollIntent = useCallback(event => {
    if (event.deltaY < 0) stopFollowingLatest();
  }, [stopFollowingLatest]);
  const handleScrollKey = useCallback(event => {
    if (['ArrowUp', 'PageUp', 'Home'].includes(event.key)) stopFollowingLatest();
  }, [stopFollowingLatest]);
  const handleScrollPointer = useCallback(event => {
    const element = threadScroll.current;
    if (element && event.clientX >= element.getBoundingClientRect().right - 18) stopFollowingLatest();
  }, [stopFollowingLatest]);
  useLayoutEffect(() => {
    const changedConversation = previousConversation.current !== conversationId;
    previousConversation.current = conversationId;
    if (changedConversation) stickToLatest.current = true;
    if (!stickToLatest.current) return;
    scrollToLatest();
    const frame = window.requestAnimationFrame(scrollToLatest);
    return () => window.cancelAnimationFrame(frame);
  }, [conversationId, messages, artifactOpen, scrollToLatest]);
  useEffect(() => {
    const element = threadScroll.current;
    const content = element?.firstElementChild;
    if (!element || !content || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(() => { if (stickToLatest.current) scrollToLatest(); });
    observer.observe(content);
    return () => observer.disconnect();
  }, [conversationId, scrollToLatest]);
  useEffect(() => {
    if (wasHistoryOpen.current && !historyOpen) window.requestAnimationFrame(() => historyTrigger.current?.focus());
    wasHistoryOpen.current = historyOpen;
  }, [historyOpen]);
  return <section className={`cv-conversation-shell cv-relative cv-flex cv-min-w-0 cv-flex-1 cv-flex-col cv-bg-ink ${!messages.length && !running ? 'cv-conversation--empty' : ''}`}>
    <header className="cv-conversation-header cv-relative cv-z-50 cv-flex cv-h-[68px] cv-flex-none cv-items-center cv-gap-4 cv-px-4 md:cv-px-6">
      {!historyOpen && <button ref={historyTrigger} type="button" onClick={onOpenHistory} className="cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-mist hover:cv-bg-white/[.05]" aria-label="Abrir conversas recentes" aria-controls="cv-recent-sidebar" aria-expanded={historyOpen}><Icon name="menu"/></button>}
      <h1 className={`cv-conversation-title cv-m-0 cv-min-w-0 cv-flex-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap ${artifactOpen ? 'cv-hidden 2xl:cv-block' : ''}`} title={title}>{title}</h1>
      <span className="cv-ml-auto cv-flex cv-items-center cv-gap-2"><span className="cv-hidden cv-text-[11px] cv-text-[#78908c] sm:cv-inline">Contexto</span><span className="cv-chat-context-readonly" title="O contexto é identificado pela conversa ou por arrastar um projeto para o chat">{contextLoading ? 'Lendo…' : context?.project_ref || context?.brand_ref ? 'Contexto ativo' : 'Conversa livre'}</span></span>
      <details ref={details} className="cv-conversation-support-popover cv-relative">
        <summary className="cv-grid cv-h-9 cv-w-9 cv-cursor-pointer cv-list-none cv-place-items-center cv-rounded-lg cv-text-mist hover:cv-bg-white/[.05]" aria-label="Apoio à conversa" title="Apoio à conversa"><Icon name="pulse" size={17}/></summary>
        <div className="cv-conversation-support-popover__panel">
          <ConversationSupport context={context} projects={projects} brands={brands} messages={messages} diagnostics={diagnostics} executionMode={executionMode} running={running} runtime={runtime} onPrompt={onPrompt}/>
        </div>
      </details>
    </header>
    <div ref={threadScroll} onScroll={trackScrollPosition} onWheelCapture={handleScrollIntent} onTouchStart={stopFollowingLatest} onPointerDown={handleScrollPointer} onKeyDownCapture={handleScrollKey} tabIndex={0} className="cv-thread-scroll cv-scroll cv-min-h-0 cv-flex-1 cv-overflow-y-auto"><Thread messages={messages} onPrompt={onPrompt} onOpenArtifact={onOpenArtifact} onOpenResource={onOpenResource} onDecision={onDecision} onRevisitPrompt={onRevisitPrompt} creditsUrl={creditsUrl} running={running} runtime={runtime} diagnostics={diagnostics} starterProject={starterProject} starterBrand={starterBrand} starterHome={starterHome} onOpenDiagnostics={() => { if (details.current) details.current.open = true; }}/></div>
    <WorkspaceChatComposer value={input} onChange={setInput} onSubmit={onSubmit} attachments={attachments} onRemoveAttachment={onRemoveAttachment} onAttachmentPurposeChange={onAttachmentPurposeChange} attachmentDestination={attachmentDestination} onAttachmentDestinationChange={onAttachmentDestinationChange} hasProject={Boolean(context?.project_ref)} executionMode={executionMode} onExecutionModeChange={onExecutionModeChange} running={running} onStop={onStop} composerContext={composerContext} onClearContext={onClearContext} onAttach={onAttach} onContextDrop={onContextDrop}/>
    {artifactOpen && <span className="cv-sr-only">Artefato aberto ao lado da conversa</span>}
  </section>;
}
