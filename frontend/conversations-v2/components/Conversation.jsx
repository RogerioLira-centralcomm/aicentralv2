import React, {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react';
import {Icon} from '../lib/icons';
import {Markdown} from './Markdown';
import {safeUrl} from '../lib/api';
import {ResponseBlocks} from './ResponseBlocks';
import {WorkspaceChatComposer} from '../../cadu-design-system/components/WorkspaceChatComposer';
import {ExecutionQueue} from './ExecutionQueue';
import {WorkspaceTaskProgress} from '../../cadu-design-system/components/WorkspaceTaskProgress';
import {meaningfulResponseBlocks, normalizeAnswerText} from '../lib/responseModel.mjs';
import {formatResponseParagraphs} from '../lib/responsePresentation.mjs';
import {consolidateSources} from '../lib/sourceModel.mjs';
import {ConversationSupport} from './ConversationSupport';
import {PendingInteraction, pendingInteraction} from './PendingInteraction';
import {conversationDisplayTitle} from '../lib/conversationPresentation.mjs';
import {ChatContextSelector} from '../../cadu-design-system/components/WorkspaceSelectors';

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

function userLinkPresentation(value, metadata = {}) {
  try {
    const parsed = new URL(value);
    const host = parsed.hostname.replace(/^www\./, '').toLowerCase();
    const previews = [metadata?.link_previews, metadata?.links, metadata?.urls].flat().filter(Boolean);
    const preview = previews.find(item => typeof item === 'object' && String(item.url || item.href || '').replace(/\/$/, '') === value.replace(/\/$/, '')) || {};
    let title = String(preview.title || preview.name || '').trim();
    if (!title && host === 'docs.google.com') {
      title = parsed.pathname.startsWith('/spreadsheets/') ? 'Planilha Google'
        : parsed.pathname.startsWith('/presentation/') ? 'Apresentação Google'
          : parsed.pathname.startsWith('/forms/') ? 'Formulário Google'
            : 'Documento Google';
    }
    if (!title && host === 'drive.google.com') title = 'Arquivo Google Drive';
    if (!title && host.endsWith('figma.com')) title = 'Arquivo do Figma';
    if (!title && (host.endsWith('notion.so') || host.endsWith('notion.site'))) title = 'Página do Notion';
    if (!title && host.endsWith('trello.com')) title = 'Quadro do Trello';
    if (!title) title = host;
    return {title, domain: host, favicon: safeUrl(preview.favicon || preview.icon || `${parsed.origin}/favicon.ico`)};
  } catch { return {title: 'Abrir link', domain: '', favicon: ''}; }
}

function UserLink({value, metadata}) {
  const [faviconFailed, setFaviconFailed] = useState(false);
  const link = userLinkPresentation(value, metadata);
  return <a className="cv-user-message__link" href={safeUrl(value)} target="_blank" rel="noreferrer" aria-label={`Abrir ${link.title}`}>
    <span className="cv-user-message__link-icon">{link.favicon && !faviconFailed ? <img src={link.favicon} alt="" loading="lazy" onError={() => setFaviconFailed(true)}/> : <Icon name="link" size={13}/>}</span>
    <span className="cv-user-message__link-copy"><b>{link.title}</b>{link.domain && link.domain !== link.title && <small>{link.domain}</small>}</span>
  </a>;
}

function UserMessageContent({content, metadata}) {
  const parts = String(content || '').split(/(https:\/\/[^\s<]+)/gi);
  return <p className="cv-m-0 cv-whitespace-pre-wrap">{parts.map((part, index) => {
    if (!/^https:\/\//i.test(part)) return <React.Fragment key={index}>{part}</React.Fragment>;
    const clean = part.replace(/[),.;!?]+$/, '');
    const suffix = part.slice(clean.length);
    return <React.Fragment key={index}><UserLink value={clean} metadata={metadata}/>{suffix}</React.Fragment>;
  })}</p>;
}

function CopyMessageButton({text, state, onCopy}) {
  return <button type="button" className={`cv-message-copy${state === 'copied' ? ' is-confirmed' : ''}`} onClick={() => onCopy(text)} aria-label={state === 'copied' ? 'Mensagem copiada' : 'Copiar mensagem'} title={state === 'copied' ? 'Copiado' : 'Copiar mensagem'}><Icon name={state === 'copied' ? 'check' : 'copy'} size={14}/><span className="cv-sr-only" aria-live="polite">{state === 'copied' ? 'Copiado' : state === 'failed' ? 'Não foi possível copiar' : 'Copiar mensagem'}</span></button>;
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

function Answer({message, onPrompt, onOpenArtifact, onOpenResource, onRevisitPrompt, creditsUrl, interactive}) {
  const copyTimer = useRef(null);
  const [messageCopyState, setMessageCopyState] = useState('idle');
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
  const legacyQuestions = (Array.isArray(response.questions) ? response.questions : []).filter(Boolean).map((question, index) => ({
    id: `legacy-question-${index + 1}`, question: String(question), required: true, allow_custom: true,
  }));
  const contentBlocks = blocks.filter(block => block.type !== 'decision');
  if (legacyQuestions.length && !contentBlocks.some(block => ['question', 'questions'].includes(block.type))) {
    contentBlocks.push({type: 'questions', items: legacyQuestions});
  }
  const presentedBlocks = consolidateSources(contentBlocks, response.citations);
  useEffect(() => () => window.clearTimeout(copyTimer.current), []);
  const copyAnswer = async value => {
    try {
      await copyText(value);
      setMessageCopyState('copied');
      window.clearTimeout(copyTimer.current);
      copyTimer.current = window.setTimeout(() => setMessageCopyState('idle'), 1800);
    } catch {
      setMessageCopyState('failed');
    }
  };
  if (message.kind === 'failure') return <FailureCard failure={message.failure} prompt={message.prompt} onRevisitPrompt={onRevisitPrompt} creditsUrl={creditsUrl}/>;
  if (message.kind === 'action') return null;
  return <div className="cv-message-enter cv-assistant-answer cv-max-w-[72ch]">
    <div className="cv-prose"><Markdown onOpenResource={onOpenResource}>{presentedText}</Markdown></div>
    {!!presentedBlocks.length && <ResponseBlocks blocks={presentedBlocks} onPrompt={onPrompt} onOpenResource={onOpenResource} interactive={interactive}/>}
    {!!response.actions?.length && <section className="cv-mt-5 cv-border-t cv-border-white/[.07] cv-pt-4"><span className="cv-mb-2 cv-block cv-text-[10px] cv-font-semibold cv-uppercase cv-tracking-[.08em] cv-text-[#78918d]">Próximas ações</span><div className="cv-flex cv-flex-wrap cv-gap-2">{response.actions.slice(0, 3).map((item, index) => <button key={index} type="button" onClick={() => onPrompt(item.prompt || '')} className={`${item.style === 'primary' ? 'cv-border-teal/30 cv-bg-teal/10 cv-text-teal' : 'cv-border-white/10 cv-bg-transparent cv-text-[#c7d8d4]'} cv-rounded-lg cv-border cv-px-3 cv-py-2 cv-text-xs hover:cv-bg-white/[.08]`}>{item.label}</button>)}</div></section>}
    {!message.streaming && text && <CopyMessageButton text={text} state={messageCopyState} onCopy={copyAnswer}/>}
    {message.artifact?.id && <button type="button" onClick={() => onOpenArtifact(message.artifact)} className="cv-artifact-result">
      <span className="cv-artifact-result__icon"><Icon name="file" size={17}/></span>
      <span className="cv-artifact-result__copy"><b>{message.artifact.title || 'Documento editável'}</b><small>{message.artifact.project_ref ? 'Salvo no projeto' : 'Rascunho da conversa'}{message.artifact.current_version ? ` · versão ${message.artifact.current_version}` : ''}</small></span>
      <span className="cv-artifact-result__action">Abrir material <Icon name="chevron" size={14}/></span>
    </button>}
  </div>;
}

function Thread({messages, interaction, onPrompt, onOpenArtifact, onOpenResource, onDecision, onRevisitPrompt, creditsUrl, onOpenDiagnostics, running, runtime, diagnostics, starterProject, starterBrand, starterHome}) {
  const thread = useRef(null);
  const [copiedMessageId, setCopiedMessageId] = useState(null);
  const copyMessage = async (id, text) => {
    try {
      await copyText(text);
      setCopiedMessageId(id);
      window.setTimeout(() => setCopiedMessageId(current => current === id ? null : current), 1800);
    } catch { setCopiedMessageId(null); }
  };
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
    {messages.map(message => message.role === 'user' ? <article key={message.id} className="cv-message cv-message--user cv-mb-7 cv-flex cv-flex-col cv-items-end"><span className="cv-message__label">Você</span><div className="cv-message-copy-wrap"><div className="cv-user-message cv-max-w-[68ch] cv-rounded-2xl cv-rounded-br-md cv-bg-[#12322f] cv-px-4 cv-py-3 cv-text-[14px] cv-leading-6 cv-text-[#f0f8f6]"><UserMessageContent content={message.content} metadata={message.metadata}/>{!!message.files?.length && <small className="cv-mt-2 cv-block cv-text-[#8fc6bf]">{message.files.map(file => file.name || 'Arquivo').join(', ')}</small>}</div><CopyMessageButton text={String(message.content || '')} state={copiedMessageId === message.id ? 'copied' : 'idle'} onCopy={text => copyMessage(message.id, text)}/></div></article> : ['worked', 'action'].includes(message.kind) ? null : <React.Fragment key={message.id}>{message.streaming && showActivity && !String(message.response?.answer || message.content || '').trim() && <article className="cv-message cv-message--assistant cv-message--activity cv-mb-5"><WorkspaceTaskProgress running={running} runtime={runtime} diagnostics={diagnostics}/></article>}<article data-cv-answer="true" className="cv-message cv-message--assistant cv-mb-7"><Answer message={message} interactive={!running && messages[messages.length - 1] === message} onPrompt={onPrompt} onOpenArtifact={onOpenArtifact} onOpenResource={onOpenResource} onRevisitPrompt={onRevisitPrompt} creditsUrl={creditsUrl}/></article></React.Fragment>)}
    {showActivity && !hasStreamingAnswer && <article className="cv-message cv-message--assistant cv-message--activity cv-mb-7"><WorkspaceTaskProgress running={running} runtime={runtime} diagnostics={diagnostics}/></article>}
    <PendingInteraction interaction={interaction} onPrompt={onPrompt} onDecision={onDecision}/>
  </div>;
}

export function Conversation({inactive, layout, viewport, shellV2 = true, conversationId, title, context, projects, brands, starterProject, starterBrand, starterHome, contextLoading, runtime, diagnostics, messages, input, setInput, onSubmit, attachments, onRemoveAttachment, onAttachmentPurposeChange, attachmentDestination, onAttachmentDestinationChange, executionMode, onExecutionModeChange, running, onStop, onPrompt, onOpenArtifact, onOpenResource, onDecision, onRevisitPrompt, creditsUrl, onOpenHistory, historyOpen, artifactOpen, composerContext, onClearContext, onAttach, onContextDrop, onProjectChange, queuedTurns, onUpdateQueuedTurn, onRemoveQueuedTurn, onMoveQueuedTurn, onOpenLibrary, automation, audioTranscriptionEndpoint, csrfToken}) {
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
      {messages.length ? <h1 className={`cv-conversation-title cv-m-0 cv-min-w-0 cv-flex-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap ${artifactOpen ? 'cv-hidden 2xl:cv-block' : ''}`} title={displayTitle}>{displayTitle}</h1> : <span className="cv-flex-1"/>}
      {interaction && <span className="cv-conversation-needs-action" title={interaction.kind === 'question' ? 'Esta conversa aguarda sua resposta' : 'Esta conversa aguarda sua decisão'} aria-label={interaction.kind === 'question' ? 'Aguardando sua resposta' : 'Ação necessária'}><Icon name="alert" size={17}/></span>}
      <span className="cv-conversation-context"><span className="cv-hidden cv-text-[11px] cv-text-[#78908c] sm:cv-inline">Contexto</span><ChatContextSelector context={context} projects={projects} brands={brands} onProjectChange={onProjectChange} disabled={running} loading={contextLoading} projectsOnly/></span>
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
    <WorkspaceChatComposer value={input} onChange={setInput} onSubmit={onSubmit} attachments={attachments} onRemoveAttachment={onRemoveAttachment} onAttachmentPurposeChange={onAttachmentPurposeChange} attachmentDestination={attachmentDestination} onAttachmentDestinationChange={onAttachmentDestinationChange} hasProject={Boolean(context?.project_ref)} executionMode={executionMode} onExecutionModeChange={onExecutionModeChange} running={running} onStop={onStop} allowQueue queuedCount={queuedTurns?.length || 0} composerContext={composerContext} onClearContext={onClearContext} onAttach={onAttach} onContextDrop={onContextDrop} onOpenLink={onOpenResource} layout={shellV2 ? layout : 'desktop'} disabled={contextLoading} onStateChange={setComposerStatus} audioTranscriptionEndpoint={audioTranscriptionEndpoint} csrfToken={csrfToken}/>
    {artifactOpen && <span className="cv-sr-only">Entrega aberta ao lado da conversa</span>}
  </section>;
}
