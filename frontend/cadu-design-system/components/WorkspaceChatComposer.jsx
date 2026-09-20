import React, {useEffect, useRef} from 'react';
import {Icon} from './Icon';

const MODE_OPTIONS = [
  {id: 'fast', label: 'Rápido', detail: 'Resposta direta'},
  {id: 'analysis', label: 'Equilibrado', detail: 'Pensa com contexto e fontes'},
  {id: 'agentic', label: 'Profundo', detail: 'Planeja quando a tarefa pede'},
];

const CAPABILITIES = [
  {label: 'Pesquisar na internet', prompt: 'Pesquise na internet fontes atuais e relevantes para este trabalho, compare os achados e responda com links e implicações práticas.'},
  {label: 'Estruturar briefing', prompt: 'Estruture um briefing para este projeto e destaque somente o que ainda precisa ser decidido.'},
  {label: 'Planejar mídia', prompt: 'Crie um plano de mídia inicial para este projeto com hipóteses e decisões necessárias.'},
  {label: 'Analisar criativo', prompt: 'Analise este criativo considerando a marca, o público e o objetivo do projeto.'},
  {label: 'Resumir reunião', prompt: 'Transforme este conteúdo em um resumo de reunião: decisões, pendências, responsáveis e próximos passos.'},
  {label: 'Criar pauta', prompt: 'Crie uma pauta de reunião objetiva usando o contexto do projeto, com temas, resultado esperado e decisões a tomar.'},
];

const COMPOSER_MAX_HEIGHT = 260;

function pastedUrl(value) {
  const match = String(value || '').match(/https?:\/\/[^\s<>\]\["']+|(?<!@)\b(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:\/[^\s<>\]\["']*)?/i);
  return match ? match[0].replace(/[.,;:)]$/, '') : '';
}

export function WorkspaceChatComposer({
  value = '', onChange, onSubmit, attachments = [], onRemoveAttachment, onAttachmentPurposeChange,
  attachmentDestination = 'conversation', onAttachmentDestinationChange, hasProject = false,
  executionMode = 'analysis', onExecutionModeChange, running = false, onStop,
  composerContext, onClearContext, onContextDrop, onAttach, embedded = false, homeMode = false,
}) {
  const textarea = useRef(null);
  const capabilityMenu = useRef(null);
  const intensityMenu = useRef(null);
  const fileInput = useRef(null);
  const recognitionRef = useRef(null);
  const voiceBaseRef = useRef('');
  const voiceNoticeTimer = useRef(null);
  const [contextActive, setContextActive] = React.useState(false);
  const [voiceState, setVoiceState] = React.useState('idle');
  const [voiceNotice, setVoiceNotice] = React.useState('');
  const currentMode = MODE_OPTIONS.find(option => option.id === executionMode) || MODE_OPTIONS[1];
  const selectCapability = capability => {
    onChange?.(capability.prompt);
    capabilityMenu.current?.removeAttribute('open');
    textarea.current?.focus();
  };
  const chooseFiles = () => fileInput.current?.click();
  const toggleVoice = () => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setVoiceState('unsupported');
      setVoiceNotice('Ditado por voz não está disponível neste navegador.');
      window.clearTimeout(voiceNoticeTimer.current);
      voiceNoticeTimer.current = window.setTimeout(() => setVoiceNotice(''), 4200);
      return;
    }
    if (voiceState === 'listening') {
      recognitionRef.current?.stop();
      return;
    }
    const recognition = new Recognition();
    voiceBaseRef.current = value.trim();
    recognition.lang = 'pt-BR';
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onstart = () => setVoiceState('listening');
    recognition.onresult = event => {
      const transcript = Array.from(event.results).map(result => result[0]?.transcript || '').join(' ').trim();
      onChange?.([voiceBaseRef.current, transcript].filter(Boolean).join(voiceBaseRef.current ? ' ' : ''));
    };
    recognition.onerror = event => {
      setVoiceState('error');
      setVoiceNotice(event?.error === 'not-allowed' ? 'Permita o microfone para usar o ditado.' : 'Não foi possível iniciar o ditado.');
      window.clearTimeout(voiceNoticeTimer.current);
      voiceNoticeTimer.current = window.setTimeout(() => setVoiceNotice(''), 4200);
    };
    recognition.onend = () => { recognitionRef.current = null; setVoiceState('idle'); };
    recognitionRef.current = recognition;
    try { recognition.start(); } catch (_) {
      setVoiceState('error');
      setVoiceNotice('Não foi possível iniciar o ditado.');
      window.clearTimeout(voiceNoticeTimer.current);
      voiceNoticeTimer.current = window.setTimeout(() => setVoiceNotice(''), 4200);
    }
  };
  useEffect(() => () => { recognitionRef.current?.stop(); window.clearTimeout(voiceNoticeTimer.current); }, []);
  useEffect(() => {
    if (!textarea.current) return;
    textarea.current.style.height = 'auto';
    textarea.current.style.height = `${Math.min(textarea.current.scrollHeight, COMPOSER_MAX_HEIGHT)}px`;
  }, [value]);
  const detectedUrl = pastedUrl(value);
  const saveLink = () => {
    if (!detectedUrl || !hasProject) return;
    onChange?.(`Adicione este link ao projeto: ${detectedUrl}`);
    textarea.current?.focus();
  };
  const stageClass = embedded ? 'cadu-ds-home-chat-stage' : 'cv-composer-stage cv-flex-none cv-px-4 md:cv-px-8';
  const shellClass = homeMode ? 'cv-composer-shell cadu-ds-home-chat-shell' : 'cv-composer-shell';
  const handleDrop = event => {
    event.preventDefault();
    setContextActive(false);
    const files = Array.from(event.dataTransfer?.files || []);
    // The composer is itself a valid drop target. Do not try to parse a file
    // as a workspace-context payload: that used to make drops over the input
    // look accepted while silently discarding the attachment.
    if (files.length) {
      onAttach?.(files);
      return;
    }
    const raw = event.dataTransfer?.getData('application/x-cadu-item') || event.dataTransfer?.getData('application/json') || event.dataTransfer?.getData('text/plain');
    if (!raw) return;
    try { onContextDrop?.(JSON.parse(raw)); } catch (_) { /* Ignore non-context drops. */ }
  };
  return <div className={`${stageClass}${contextActive ? ' is-context-drop' : ''}`} onDragEnter={event => { event.preventDefault(); setContextActive(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { if (event.currentTarget === event.target) setContextActive(false); }} onDrop={handleDrop}>
    <form onSubmit={event => { event.preventDefault(); onSubmit?.(); }} className={`${shellClass} cv-pointer-events-auto cv-mx-auto cv-w-full ${embedded ? '' : 'cv-max-w-[760px]'}`}>
      {!!composerContext && <div className="cv-flex cv-items-center cv-gap-2 cv-px-3 cv-py-2"><span className="cv-min-w-0 cv-flex-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-[11px] cv-text-[#8fbab4]">↳ {composerContext.label}: “{composerContext.text}”</span><button type="button" onClick={onClearContext} className="cv-grid cv-h-5 cv-w-5 cv-place-items-center cv-rounded cv-border-0 cv-bg-transparent cv-text-[#78918d] hover:cv-bg-white/[.06] hover:cv-text-white" aria-label="Remover contexto">×</button></div>}
      {!!attachments.length && <div className="cv-flex cv-flex-wrap cv-gap-2 cv-px-3 cv-pt-3 cv-pb-2">{attachments.map((item, index) => { const suggested = item.intake?.purpose === 'knowledge_source' ? 'knowledge' : item.intake?.purpose === 'project_attachment' ? 'attachment' : ''; const label = suggested === 'knowledge' ? 'Fonte sugerida' : suggested === 'attachment' ? 'Anexo sugerido' : item.intake?.state === 'pending' ? 'Classificando…' : ''; return <span key={item.localId || `${item.name}-${index}`} className={`cv-attachment-chip ${item.previewUrl ? 'is-image' : 'is-file'} ${item.error ? 'has-error' : ''}`} aria-label={item.name}>{item.previewUrl ? <img src={item.previewUrl} alt="" className="cv-attachment-thumb"/> : <Icon name="file" size={19}/>}<button type="button" disabled={item.uploading} onClick={() => onRemoveAttachment?.(index)} className="cv-attachment-remove" aria-label={`Remover ${item.name}`}>×</button>{label && <button type="button" disabled={!suggested || !hasProject || item.uploading} onClick={() => suggested && onAttachmentPurposeChange?.(index, suggested)} className={`cv-attachment-intake ${item.destination === suggested ? 'is-applied' : ''}`}>{item.destination === suggested ? '✓' : label}</button>}</span>; })}</div>}
      <textarea ref={textarea} value={value} onChange={event => onChange?.(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} rows="1" maxLength="20000" placeholder="Pergunte ou peça uma alteração…" aria-label="Mensagem para o Cadu" className="cv-composer-input cv-block cv-min-h-[48px] cv-w-full cv-resize-none cv-border-0 cv-bg-transparent cv-px-4 cv-py-3 cv-text-[15px] cv-leading-6 cv-text-white cv-outline-none placeholder:cv-text-[#6f8985]"/>
      {!!detectedUrl && <div className="cv-link-intake cv-flex cv-items-center cv-justify-between cv-gap-3 cv-px-4 cv-pb-1"><span>{hasProject ? 'Link detectado. Salve como referência antes de extrair conteúdo.' : 'Link detectado. Selecione um projeto para salvá-lo como referência.'}</span>{hasProject && <button type="button" onClick={saveLink}>Preparar referência</button>}</div>}
      <div className="cv-composer-actions cv-flex cv-items-center cv-justify-between">
        <div className="cv-flex cv-min-w-0 cv-items-center cv-gap-2">
          <details ref={capabilityMenu} className="cv-composer-capabilities">
            <summary className="cv-composer-add cv-grid cv-h-8 cv-w-8 cv-cursor-pointer cv-list-none cv-place-items-center cv-rounded-full cv-border-0 cv-bg-transparent cv-text-mist" aria-label="Mais recursos" title="Mais recursos"><Icon name="plus" size={17}/></summary>
            <div className="cv-capability-menu" role="menu" aria-label="Escolher modo e recursos">
              <div className="cv-capability-heading">Recursos</div>
              {onAttach && <button type="button" role="menuitem" onClick={() => { chooseFiles(); capabilityMenu.current?.removeAttribute('open'); }}><span><b>Anexar arquivo</b><small>Imagem, PDF, texto ou Office</small></span><Icon name="file" size={14}/></button>}
              {CAPABILITIES.map(capability => <button key={capability.label} type="button" role="menuitem" onClick={() => selectCapability(capability)}><span><b>{capability.label}</b></span><Icon name="arrowUp" size={14}/></button>)}
              <div className="cv-capability-heading cv-capability-heading--resources">Destino dos anexos</div>{[['conversation', 'Usar só nesta conversa'], ['knowledge', 'Adicionar como fonte do projeto'], ['attachment', 'Anexar ao projeto sem indexar']].map(([id, label]) => <button key={id} type="button" role="menuitemradio" aria-checked={attachmentDestination === id} disabled={id !== 'conversation' && !hasProject} className={attachmentDestination === id ? 'is-active' : ''} onClick={() => onAttachmentDestinationChange?.(id)}><span><b>{label}</b>{id !== 'conversation' && !hasProject && <small>Selecione um projeto primeiro</small>}</span>{attachmentDestination === id && <Icon name="check" size={15}/>}</button>)}
              <p>Skills e integrações disponíveis para esta conta aparecerão aqui.</p>
            </div>
          </details>
          {onAttach && <><input ref={fileInput} type="file" multiple accept="image/*,.pdf,.txt,.csv,.md,.json,.docx,.xlsx,.pptx" className="cv-sr-only" onChange={event => { onAttach(Array.from(event.target.files || [])); event.target.value = ''; }} /><button type="button" className="cv-composer-add cv-grid cv-h-8 cv-w-8 cv-place-items-center cv-rounded-full cv-border-0 cv-bg-transparent cv-text-mist" onClick={chooseFiles} aria-label="Anexar arquivo" title="Anexar arquivo"><Icon name="file" size={16}/></button></>}
        </div>
        <div className="cv-composer-submit-group cv-flex cv-items-center cv-gap-1.5">
          <details ref={intensityMenu} className="cv-composer-intensity">
            <summary className="cv-composer-intensity__trigger" aria-label={`Intensidade do agente: ${currentMode.label}`} title={`Intensidade: ${currentMode.label}`}><Icon name="pulse" size={14}/><span>{currentMode.label}</span><Icon name="chevron" size={13}/></summary>
            <div className="cv-composer-intensity__menu" role="menu" aria-label="Intensidade do agente">
              <div className="cv-capability-heading">Intensidade do agente</div>
              {MODE_OPTIONS.map(option => <button key={option.id} type="button" role="menuitemradio" aria-checked={executionMode === option.id} className={executionMode === option.id ? 'is-active' : ''} onClick={() => { onExecutionModeChange?.(option.id); intensityMenu.current?.removeAttribute('open'); }}><span><b>{option.label}</b><small>{option.detail}</small></span>{executionMode === option.id && <Icon name="check" size={15}/>}</button>)}
            </div>
          </details>
          <button type="button" onClick={toggleVoice} className={`cv-composer-audio cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-xl cv-border-0 cv-bg-transparent cv-text-mist ${voiceState === 'listening' ? 'is-listening' : ''} ${voiceState === 'unsupported' ? 'is-unavailable' : ''}`} aria-label={voiceState === 'listening' ? 'Parar ditado por voz' : 'Ditado por voz'} title={voiceState === 'listening' ? 'Parar ditado por voz' : 'Ditado por voz'}><Icon name="audio" size={17}/></button>
          {running ? <button type="button" onClick={onStop} className="cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-xl cv-border-0 cv-bg-white/10" aria-label="Interromper geração"><span className="cv-h-2.5 cv-w-2.5 cv-rounded-sm cv-bg-[#d7e4e2]"/></button> : <button type="submit" disabled={!value.trim() || attachments.some(item => item.uploading)} className="cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-xl cv-border-0 cv-bg-teal cv-text-[#052522] disabled:cv-cursor-not-allowed disabled:cv-opacity-35" aria-label="Enviar mensagem"><Icon name="arrowUp" size={17}/></button>}
        </div>
        {voiceNotice && <span className="cv-composer-audio-status" role="status">{voiceNotice}</span>}
      </div>
    </form>
  </div>;
}
