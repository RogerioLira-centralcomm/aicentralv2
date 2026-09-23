import React, {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react';
import {Icon} from '../lib/icons';
import {Markdown} from './Markdown';
import {safeUrl} from '../lib/api';
import {ResponseBlocks} from './ResponseBlocks';
import {WorkspaceChatComposer} from '../../cadu-design-system/components/WorkspaceChatComposer';
import {ExecutionQueue} from './ExecutionQueue';
import {WorkspaceSourceList} from '../../cadu-design-system/components/WorkspaceSourceList';
import {WorkspaceTaskProgress} from '../../cadu-design-system/components/WorkspaceTaskProgress';
import {meaningfulResponseBlocks, normalizeAnswerText} from '../lib/responseModel.mjs';
import {formatResponseParagraphs} from '../lib/responsePresentation.mjs';
import {ConversationSupport} from './ConversationSupport';
import {PendingInteraction, pendingInteraction} from './PendingInteraction';
import {conversationContextLabel, conversationDisplayTitle} from '../lib/conversationPresentation.mjs';

async function copyText(text) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  const field = document.createElement('textarea');
  field.value = text;
  field.setAttribute('readonly', '');
  field.style.position = 'fixed';
  field.style.opacity = '0';
  document.body.appendChild(field);
  field.select();
  const copied = document.execCommand('copy');
  field.remove();
  if (!copied) throw new Error('copy_failed');
}

function FailureCard({failure, prompt, onRevisitPrompt, creditsUrl}) {
  const needsCredits = failure?.kind === 'credits';
  const needsRefresh = failure?.kind === 'session';
  return <section className={`cv-chat-failure cv-chat-failure--${failure?.kind || 'generic'}`} role="alert">
    <div className="cv-chat-failure__marker" aria-hidden="true">{needsCredits ? '¢' : '!'}</div>
    <div className="cv-chat-failure__body">
      <span className="cv-chat-failure__eyebrow">{needsCredits ? 'Créditos da conta' : 'Conversa'}</span>
      <h2>{failure?.title || 'Não foi possível concluir esta solicitação'}</h2>
      <p>{failure?.detail}</p>
      {failure?.guidance && <small>{failure.guidance}</small>}
      <div className="cv-chat-failure__actions">
        {needsCredits && <a href={creditsUrl || 'https://workspace.centralcomm.media/creditos'}>Adicionar créditos no Workspace</a>}
        {!needsCredits && (needsRefresh ? <button type="button" onClick={() => window.location.reload()}>Atualizar página</button> : null)}
      </div>
    </div>
  </section>;
}

function Answer({message, onPrompt, onOpenArtifact, onOpenResource, onRevisitPrompt, creditsUrl}) {
  const [copyState, setCopyState] = useState('idle');
  const copyTimer = useRef(null);
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
  const presentedText = formatResponseParagraphs(text);
  const contentBlocks = blocks.filter(block => !['question', 'questions', 'decision'].includes(block.type));
  const canCreateDocument = !message.artifact?.id && text.length > 500 && (
    text.length > 1800 || response.citations?.length || contentBlocks.some(block =>
      ['sources', 'source_group', 'images', 'insights', 'checklist', 'steps', 'metrics'].includes(block.type)
    )
  );
  useEffect(() => () => window.clearTimeout(copyTimer.current), []);
  const copyAnswer = async () => {
    try {
      await copyText(text);
      setCopyState('copied');
      window.clearTimeout(copyTimer.current);
      copyTimer.current = window.setTimeout(() => setCopyState('idle'), 1800);
    } catch {
      setCopyState('failed');
    }
  };
  if (message.kind === 'failure') return <FailureCard failure={message.failure} prompt={message.prompt} onRevisitPrompt={onRevisitPrompt} creditsUrl={creditsUrl}/>;
  if (message.kind === 'action') return null;
  return <div className="cv-message-enter cv-assistant-answer cv-max-w-[72ch]">
    <div className="cv-prose"><Markdown onOpenResource={onOpenResource}>{presentedText}</Markdown></div>
    {!!contentBlocks.length && <ResponseBlocks blocks={contentBlocks} onPrompt={onPrompt} onOpenResource={onOpenResource}/>}
    {!!response.assumptions?.length && <details className="cv-mt-4 cv-text-xs cv-text-mist"><summary className="cv-cursor-pointer">{response.assumptions.length === 1 ? 'Premissa usada' : `${response.assumptions.length} premissas usadas`}</summary><ul>{response.assumptions.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
    {!!response.citations?.length && <WorkspaceSourceList items={response.citations.slice(0, 4).map(item => ({title: item.title || 'Fonte', href: safeUrl(item?.url)}))}/>}
    {!!response.actions?.length && <section className="cv-mt-5 cv-border-t cv-border-white/[.07] cv-pt-4"><span className="cv-mb-2 cv-block cv-text-[10px] cv-font-semibold cv-uppercase cv-tracking-[.08em] cv-text-[#78918d]">Próximas ações</span><div className="cv-flex cv-flex-wrap cv-gap-2">{response.actions.slice(0, 3).map((item, index) => <button key={index} type="button" onClick={() => onPrompt(item.prompt || '')} className={`${item.style === 'primary' ? 'cv-border-teal/30 cv-bg-teal/10 cv-text-teal' : 'cv-border-white/10 cv-bg-transparent cv-text-[#c7d8d4]'} cv-rounded-lg cv-border cv-px-3 cv-py-2 cv-text-xs hover:cv-bg-white/[.08]`}>{item.label}</button>)}</div></section>}
    {!message.streaming && text && <div className="cv-answer-tools" aria-label="Ações da resposta">
      <button type="button" onClick={copyAnswer} className={copyState === 'copied' ? 'is-confirmed' : ''} aria-label="Copiar resposta" title="Copiar resposta"><Icon name={copyState === 'copied' ? 'check' : 'copy'} size={14}/><span aria-live="polite">{copyState === 'copied' ? 'Copiado' : copyState === 'failed' ? 'Não foi possível copiar' : 'Copiar'}</span></button>
      {canCreateDocument && <button type="button" onClick={() => onPrompt('Crie um documento editável com esta resposta. Preserve integralmente fatos, números, fontes, ressalvas e conclusões; use um título específico e subtítulos semânticos. Abra o documento ao lado para revisão e ofereça salvá-lo no projeto ativo.', {type:'assistant_response', label:'Resposta completa para o documento', text})}><Icon name="file" size={14}/><span>Criar documento</span></button>}
    </div>}
    {message.artifact?.id && <button type="button" onClick={() => onOpenArtifact(message.artifact)} className="cv-artifact-result">
      <span className="cv-artifact-result__icon"><Icon name="file" size={17}/></span>
      <span className="cv-artifact-result__copy"><b>{message.artifact.title || 'Documento editável'}</b><small>{message.artifact.project_ref ? 'Salvo no projeto' : 'Rascunho da conversa'}{message.artifact.current_version ? ` · versão ${message.artifact.current_version}` : ''}</small></span>
      <span className="cv-artifact-result__action">Abrir e editar <Icon name="chevron" size={14}/></span>
    </button>}
  </div>;
}

function Thread({messages, interaction, onPrompt, onOpenArtifact, onOpenResource, onDecision, onRevisitPrompt, creditsUrl, onOpenDiagnostics, running, runtime, diagnostics, starterProject, starterBrand, starterHome}) {
  const thread = useRef(null);
  const showActivity = running;
  const hasStreamingAnswer = messages.some(message => message.role === 'assistant' && message.streaming);
  const captureSelection = () => {
    window.requestAnimationFrame(() => {
      const current = window.getSelection();
      const text = String(current?.toString() || '').replace(/\s+/g, ' ').trim();
      const anchor = current?.anchorNode;
      const focus = current?.focusNode;
      if (!text || text.length < 3 || text.length > 1200 || !anchor || !focus || !thread.current?.contains(anchor)) return;
      const prose = anchor.parentElement?.closest('.cv-prose');
      if (!prose || focus.parentElement?.closest('.cv-prose') !== prose) return;
      const quote = text.length > 700 ? `${text.slice(0, 700).replace(/\s+\S*$/, '')}…` : text;
      onPrompt('', {type: 'selection', label: 'Trecho selecionado', text: quote});
    });
  };
  if (!messages.length && !running) return <div className="cv-empty-state cv-flex cv-min-h-full cv-items-center cv-justify-center cv-px-6 cv-py-16">
    <div className="cv-w-full cv-max-w-[700px] cv-text-center">
      <h2 className="cv-mb-2 cv-mt-0 cv-text-2xl cv-font-semibold cv-tracking-[-.025em]">Em que vamos trabalhar?</h2>
      <p className="cv-mx-auto cv-mb-0 cv-max-w-[520px] cv-text-sm cv-leading-6 cv-text-mist">Converse, analise arquivos ou crie algo usando o contexto do projeto.</p>
    </div>
  </div>;
  return <div ref={thread} onMouseUp={captureSelection} className="cv-thread-content cv-mx-auto cv-w-full cv-max-w-[940px] cv-px-6 cv-pt-7 md:cv-px-10">
    {messages.map(message => message.role === 'user' ? <article key={message.id} className="cv-message cv-message--user cv-mb-7 cv-flex cv-flex-col cv-items-end"><span className="cv-message__label">Você</span><div className="cv-user-message cv-max-w-[68ch] cv-rounded-2xl cv-rounded-br-md cv-bg-[#12322f] cv-px-4 cv-py-3 cv-text-[14px] cv-leading-6 cv-text-[#f0f8f6]"><p className="cv-m-0 cv-whitespace-pre-wrap">{message.content}</p>{!!message.files?.length && <small className="cv-mt-2 cv-block cv-text-[#8fc6bf]">{message.files.map(file => file.name || 'Arquivo').join(', ')}</small>}</div></article> : ['worked', 'action'].includes(message.kind) ? null : <React.Fragment key={message.id}>{message.streaming && showActivity && <article className="cv-message cv-message--assistant cv-message--activity cv-mb-5"><WorkspaceTaskProgress running={running} runtime={runtime} diagnostics={diagnostics}/></article>}<article data-cv-answer="true" className="cv-message cv-message--assistant cv-mb-7"><Answer message={message} onPrompt={onPrompt} onOpenArtifact={onOpenArtifact} onOpenResource={onOpenResource} onRevisitPrompt={onRevisitPrompt} creditsUrl={creditsUrl}/></article></React.Fragment>)}
    {showActivity && !hasStreamingAnswer && <article className="cv-message cv-message--assistant cv-message--activity cv-mb-7"><WorkspaceTaskProgress running={running} runtime={runtime} diagnostics={diagnostics}/></article>}
    <PendingInteraction interaction={interaction} onPrompt={onPrompt} onDecision={onDecision}/>
  </div>;
}

export function Conversation({inactive, layout, viewport, shellV2 = true, conversationId, title, context, projects, brands, starterProject, starterBrand, starterHome, contextLoading, runtime, diagnostics, messages, input, setInput, onSubmit, attachments, onRemoveAttachment, onAttachmentPurposeChange, attachmentDestination, onAttachmentDestinationChange, executionMode, onExecutionModeChange, running, onStop, onPrompt, onOpenArtifact, onOpenResource, onDecision, onRevisitPrompt, creditsUrl, onOpenHistory, historyOpen, artifactOpen, composerContext, onClearContext, onAttach, onContextDrop, queuedTurns, onUpdateQueuedTurn, onRemoveQueuedTurn, onMoveQueuedTurn, onOpenLibrary, automation}) {
  const details = useRef(null);
  const historyTrigger = useRef(null);
  const wasHistoryOpen = useRef(historyOpen);
  const threadScroll = useRef(null);
  const stickToLatest = useRef(true);
  const [hasUnreadBelow, setHasUnreadBelow] = useState(false);
  const [composerStatus, setComposerStatus] = useState('idle');
  const [scrollMode, setScrollMode] = useState('following');
  const previousConversation = useRef(conversationId);
  const interaction = pendingInteraction(messages, running);
  const displayTitle = conversationDisplayTitle(title);
  const activeContext = conversationContextLabel(context, projects, brands);
  const scrollToLatest = useCallback(() => {
    const element = threadScroll.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, []);
  const trackScrollPosition = useCallback(event => {
    const element = event.currentTarget;
    stickToLatest.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
    setScrollMode(stickToLatest.current ? 'following' : 'reading');
    if (stickToLatest.current) setHasUnreadBelow(false);
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
    if (!stickToLatest.current) {
      setHasUnreadBelow(true);
      return;
    }
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
  return <section inert={inactive ? '' : undefined} aria-hidden={inactive ? 'true' : undefined} className={`cv-conversation-shell cv-relative cv-flex cv-min-w-0 cv-flex-1 cv-flex-col cv-bg-ink ${!messages.length && !running ? 'cv-conversation--empty' : ''}`}>
    <header className="cv-conversation-header cv-relative cv-z-50 cv-flex cv-h-[68px] cv-flex-none cv-items-center cv-gap-4 cv-px-4 md:cv-px-6">
      {!historyOpen && <button ref={historyTrigger} type="button" onClick={onOpenHistory} className="cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-mist hover:cv-bg-white/[.05]" aria-label="Abrir conversas recentes" aria-controls="cv-recent-sidebar" aria-expanded={historyOpen}><Icon name="menu"/></button>}
      <h1 className={`cv-conversation-title cv-m-0 cv-min-w-0 cv-flex-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap ${artifactOpen ? 'cv-hidden 2xl:cv-block' : ''}`} title={displayTitle}>{displayTitle}</h1>
      {interaction && <span className="cv-conversation-needs-action" title="Esta conversa aguarda sua decisão" aria-label="Ação necessária"><Icon name="alert" size={17}/></span>}
      <span className="cv-conversation-context"><span className="cv-hidden cv-text-[11px] cv-text-[#78908c] sm:cv-inline">Contexto</span><span className="cv-chat-context-readonly" title="O contexto é identificado pela conversa ou por arrastar um projeto para o chat">{!contextLoading && <Icon name={activeContext.kind === 'project' ? 'folder' : activeContext.kind === 'brand' ? 'brand' : 'compose'} size={13}/>}<span>{contextLoading ? 'Lendo…' : activeContext.label}</span></span></span>
      <button type="button" onClick={onOpenLibrary} className="cv-conversation-library-link" title="Abrir biblioteca do contexto"><Icon name="file" size={14}/><span>Biblioteca</span></button>
      <details ref={details} className="cv-conversation-support-popover cv-relative">
        <summary className={`cv-conversation-runtime ${running ? 'is-running' : ''} ${automation?.automation_enabled ? 'is-automation' : ''}`} aria-label={running ? runtime || 'Atividade em execução' : automation?.automation_enabled ? 'Automação ativa' : 'Saúde e atividade'} title={running ? runtime || 'Atividade em execução' : automation?.automation_enabled ? automation.schedule_label || 'Automação ativa' : 'Saúde e atividade'}><Icon name="pulse" size={17}/>{running ? <span>{runtime || 'Executando'}</span> : automation?.automation_enabled && <span>{automation.schedule_label || 'Automação ativa'}</span>}</summary>
        <div className="cv-conversation-support-popover__panel">
          <ConversationSupport context={context} projects={projects} brands={brands} messages={messages} diagnostics={diagnostics} executionMode={executionMode} running={running} runtime={runtime} automation={automation} onPrompt={onPrompt} technicalState={{layout, keyboardOpen: viewport?.keyboardOpen, visualWidth: viewport?.visualWidth, visualHeight: viewport?.visualHeight, orientation: viewport?.orientation, composerStatus, scrollMode}}/>
        </div>
      </details>
    </header>
    <div ref={threadScroll} onScroll={trackScrollPosition} onWheelCapture={handleScrollIntent} onTouchStart={stopFollowingLatest} onPointerDown={handleScrollPointer} onKeyDownCapture={handleScrollKey} tabIndex={0} className="cv-thread-scroll cv-scroll cv-min-h-0 cv-flex-1 cv-overflow-y-auto"><Thread messages={messages} interaction={interaction} onPrompt={onPrompt} onOpenArtifact={onOpenArtifact} onOpenResource={onOpenResource} onDecision={onDecision} onRevisitPrompt={onRevisitPrompt} creditsUrl={creditsUrl} running={running} runtime={runtime} diagnostics={diagnostics} starterProject={starterProject} starterBrand={starterBrand} starterHome={starterHome} onOpenDiagnostics={() => { if (details.current) details.current.open = true; }}/></div>
    {hasUnreadBelow && <button type="button" className="cv-scroll-latest" onClick={() => {
      stickToLatest.current = true;
      setHasUnreadBelow(false);
      scrollToLatest();
    }}><Icon name="chevron" size={14}/>Novas atualizações</button>}
    <ExecutionQueue items={queuedTurns} onUpdate={onUpdateQueuedTurn} onRemove={onRemoveQueuedTurn} onMove={onMoveQueuedTurn}/>
    <WorkspaceChatComposer value={input} onChange={setInput} onSubmit={onSubmit} attachments={attachments} onRemoveAttachment={onRemoveAttachment} onAttachmentPurposeChange={onAttachmentPurposeChange} attachmentDestination={attachmentDestination} onAttachmentDestinationChange={onAttachmentDestinationChange} hasProject={Boolean(context?.project_ref)} executionMode={executionMode} onExecutionModeChange={onExecutionModeChange} running={running} onStop={onStop} allowQueue queuedCount={queuedTurns?.length || 0} composerContext={composerContext} onClearContext={onClearContext} onAttach={onAttach} onContextDrop={onContextDrop} layout={shellV2 ? layout : 'desktop'} disabled={contextLoading} onStateChange={setComposerStatus}/>
    {artifactOpen && <span className="cv-sr-only">Artefato aberto ao lado da conversa</span>}
  </section>;
}
