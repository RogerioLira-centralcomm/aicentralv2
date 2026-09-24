import React, {useEffect, useReducer, useRef} from 'react';
import {Icon} from './Icon';
import {ProjectSelector} from './WorkspaceSelectors';
import {pluginPrompt} from '../../conversations-v2/lib/pluginPrompts';
import {composerReducer, composerState} from '../lib/composerState.mjs';
import {request} from '../../conversations-v2/lib/api';

const MODE_OPTIONS = [
  {id: 'fast', label: 'Rápido', detail: 'Resposta direta'},
  {id: 'analysis', label: 'Equilibrado', detail: 'Pensa com contexto e fontes'},
  {id: 'agentic', label: 'Profundo', detail: 'Planeja quando a tarefa pede'},
];

const CAPABILITIES = [
  {label: 'Estruturar briefing', detail: 'Organiza o contexto e aponta decisões', icon: 'list', prompt: 'Estruture um briefing para este projeto e destaque somente o que ainda precisa ser decidido.'},
  {label: 'Planejar mídia', detail: 'Cria um plano inicial com hipóteses', icon: 'table', prompt: 'Crie um plano de mídia inicial para este projeto com hipóteses e decisões necessárias.'},
  {label: 'Analisar criativo', detail: 'Avalia uma peça anexada ao pedido', icon: 'image', prompt: 'Analise este criativo considerando a marca, o público e o objetivo do projeto.'},
  {label: 'Resumir reunião', detail: 'Extrai decisões, responsáveis e próximos passos', icon: 'file', prompt: 'Transforme este conteúdo em um resumo de reunião: decisões, pendências, responsáveis e próximos passos.'},
  {label: 'Criar pauta', detail: 'Prepara temas e decisões para a reunião', icon: 'calendar', prompt: 'Crie uma pauta de reunião objetiva usando o contexto do projeto, com temas, resultado esperado e decisões a tomar.'},
  {label: 'Atividades por prazo', detail: 'Lista tarefas vencidas, próximas e sem prazo', icon: 'history', prompt: 'Liste as atividades e tarefas deste projeto agrupadas por prazo: vencidas, para hoje, próximos 7 dias, futuras, sem prazo e concluídas. Para cada item, informe título, estado, responsável e data de prazo. Use os dados atuais do projeto e indique claramente quando uma data ou responsável não estiver definido.'},
];

const PLUGIN_ICONS = {insights:'analysis', planner:'table', 'project-search':'search', 'project-activities':'list', 'campaign-search':'search', reports:'analysis', studio:'image', 'market-radar':'analysis', 'audience-map':'search', 'investment-simulator':'table', 'media-plan-audit':'list', 'campaign-tracker':'analysis', 'creative-concept':'image', 'channel-copy':'list', 'page-review':'browser', 'meeting-copilot':'calendar', 'client-delivery':'list'};

const COMPOSER_MAX_HEIGHT = 120;

const cleanVoiceText = value => String(value || '').replace(/\s+/g, ' ').replace(/\s+([,.;:!?])/g, '$1').trim();

function pastedUrl(value) {
  const match = String(value || '').match(/https?:\/\/[^\s<>\]\["']+|(?<!@)\b(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:\/[^\s<>\]\["']*)?/i);
  return match ? match[0].replace(/[.,;:)]$/, '') : '';
}

function linkProfile(value) {
  const raw = String(value || '').trim();
  try {
    const url = new URL(raw.startsWith('http') ? raw : `https://${raw}`);
    const host = url.hostname.replace(/^www\./, '').toLowerCase();
    const path = url.pathname;
    const driveId = path.match(/\/(?:folders|file\/d|document\/d|spreadsheets\/d|presentation\/d)\/([^/]+)/i)?.[1] || '';
    const extension = path.match(/\.([a-z0-9]{2,8})$/i)?.[1]?.toLowerCase() || '';
    if (host === 'drive.google.com') {
      const isFolder = /\/drive\/folders\//i.test(path);
      return {provider: 'Google Drive', type: isFolder ? 'Pasta' : 'Arquivo ou atalho', name: isFolder ? 'Pasta do Google Drive' : 'Arquivo do Google Drive', id: driveId || url.searchParams.get('id') || '', icon: isFolder ? '▰' : '□', sharePrompt: `Verifique se esta referência está aberta para compartilhamento e diga o que é possível acessar: ${url.href}`};
    }
    if (host === 'docs.google.com') {
      const kind = /\/spreadsheets\//i.test(path) ? 'Planilha' : /\/presentation\//i.test(path) ? 'Apresentação' : 'Documento';
      return {provider: 'Google Workspace', type: kind, name: `${kind} Google`, id: driveId, icon: kind === 'Planilha' ? '▤' : kind === 'Apresentação' ? '▥' : '▱', sharePrompt: `Verifique se este ${kind.toLowerCase()} está aberto para compartilhamento e informe se o conteúdo pode ser lido: ${url.href}`};
    }
    if (host === 'meet.google.com') return {provider: 'Google Meet', type: 'Reunião', name: 'Reunião Google Meet', id: '', icon: '◉', sharePrompt: `Verifique se esta reunião do Google Meet pode ser acessada por pessoas com o link: ${url.href}`};
    if (host === 'calendar.google.com') return {provider: 'Google Calendar', type: 'Evento', name: 'Evento Google Calendar', id: '', icon: '▣', sharePrompt: `Verifique se este evento do Google Calendar está disponível para compartilhamento: ${url.href}`};
    return {provider: host, type: extension ? `Arquivo .${extension}` : 'Site público', name: host, id: '', icon: extension ? '□' : '↗', sharePrompt: ''};
  } catch (_) {
    return {provider: 'Link', type: 'Referência', name: 'Link externo', id: '', icon: '↗', sharePrompt: ''};
  }
}

export function WorkspaceChatComposer({
  value = '', onChange, onSubmit, attachments = [], onRemoveAttachment, hasProject = false,
  executionMode = 'analysis', onExecutionModeChange, running = false, onStop,
  composerContext, onClearContext, onContextDrop, onOpenLink, onAttach, allowQueue = false, queuedCount = 0, embedded = false, homeMode = false,
  projects = [], projectRef = '', onProjectChange, showProjectSelector = true,
  layout = 'desktop', disabled = false, onStateChange, audioTranscriptionEndpoint = '', csrfToken = '',
}) {
  const textarea = useRef(null);
  const capabilityMenu = useRef(null);
  const pluginMenu = useRef(null);
  const slashQuery = String(value).match(/^\/([^\s]*)$/)?.[1] ?? null;
  const [pluginCatalog, setPluginCatalog] = React.useState([]);
  const [pluginsLoading, setPluginsLoading] = React.useState(false);
  const [pluginsError, setPluginsError] = React.useState('');
  const fileInput = useRef(null);
  const imageInput = useRef(null);
  const intensityMenu = useRef(null);
  const recognitionRef = useRef(null);
  const recorderRef = useRef(null);
  const voiceStreamRef = useRef(null);
  const voiceChunksRef = useRef([]);
  const voiceBaseRef = useRef('');
  const voiceTextRef = useRef('');
  const voiceAutoSubmitRef = useRef(false);
  const voiceLimitTimer = useRef(null);
  const latestValueRef = useRef(value);
  const voiceNoticeTimer = useRef(null);
  const [contextActive, setContextActive] = React.useState(false);
  const [voiceState, setVoiceState] = React.useState('idle');
  const [voiceNotice, setVoiceNotice] = React.useState('');
  const [machine, dispatchComposer] = useReducer(composerReducer, {value, running, disabled}, composerState);
  const focused = useRef(false);
  const currentMode = MODE_OPTIONS.find(option => option.id === executionMode) || MODE_OPTIONS[1];
  const availableCapabilities = hasProject ? CAPABILITIES : CAPABILITIES.filter(item => !['Estruturar briefing', 'Planejar mídia', 'Criar pauta', 'Atividades por prazo'].includes(item.label));
  const selectCapability = capability => {
    onChange?.(capability.prompt);
    capabilityMenu.current?.removeAttribute('open');
    textarea.current?.focus();
  };
  useEffect(() => {
    if (slashQuery === null || pluginCatalog.length) return;
    let current = true;
    setPluginsLoading(true);
    request('/workspace/api/v2/capabilities')
      .then(data => { if (current) setPluginCatalog(Array.isArray(data.plugins) ? data.plugins : []); })
      .catch(error => { if (current) setPluginsError(error.message || 'Não foi possível carregar os plugins.'); })
      .finally(() => { if (current) setPluginsLoading(false); });
    return () => { current = false; };
  }, [slashQuery, pluginCatalog.length]);
  const slashPlugins = pluginCatalog.filter(plugin => plugin.selectable && ['active', 'in_development'].includes(plugin.maturity)
    && `${plugin.id} ${plugin.name} ${plugin.description}`.toLocaleLowerCase('pt-BR').includes(String(slashQuery || '').toLocaleLowerCase('pt-BR')));
  const choosePlugin = plugin => {
    const prompt = pluginPrompt(plugin);
    if (!prompt) return;
    onChange?.(prompt);
    pluginMenu.current?.removeAttribute('open');
    textarea.current?.focus();
  };
  const pickFiles = inputRef => {
    capabilityMenu.current?.removeAttribute('open');
    inputRef.current?.click();
  };
  const acceptFiles = event => {
    const files = Array.from(event.target.files || []);
    if (files.length) onAttach?.(files);
    event.target.value = '';
  };
  useEffect(() => { latestValueRef.current = value; }, [value]);
  const combineVoiceText = transcript => [voiceBaseRef.current, String(transcript || '').trim()].filter(Boolean).join(voiceBaseRef.current ? ' ' : '');
  const releaseVoiceStream = () => {
    window.clearTimeout(voiceLimitTimer.current); voiceLimitTimer.current = null;
    voiceStreamRef.current?.getTracks?.().forEach(track => track.stop());
    voiceStreamRef.current = null;
  };
  const transcribeRecording = async blob => {
    if (!audioTranscriptionEndpoint || !blob?.size) return voiceTextRef.current;
    const body = new FormData();
    const extension = blob.type.includes('ogg') ? 'ogg' : blob.type.includes('mp4') ? 'm4a' : 'webm';
    body.append('audio', blob, `mensagem.${extension}`);
    const response = await fetch(audioTranscriptionEndpoint, {method:'POST', credentials:'same-origin', headers:{'X-CSRF-Token':csrfToken, 'X-Idempotency-Key':crypto.randomUUID()}, body});
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.transcript?.text) throw new Error(data.error || 'Não foi possível transcrever o áudio.');
    return data.transcript.text;
  };
  const finishVoice = autoSubmit => {
    voiceAutoSubmitRef.current = voiceAutoSubmitRef.current || Boolean(autoSubmit);
    setVoiceNotice('');
    recognitionRef.current?.stop();
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
    else if (autoSubmit && voiceState !== 'transcribing' && voiceTextRef.current) onSubmit?.(combineVoiceText(voiceTextRef.current));
  };
  const toggleVoice = async () => {
    if (voiceState === 'recording' || voiceState === 'transcribing') {
      finishVoice(false);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder || !audioTranscriptionEndpoint) {
      setVoiceState('unsupported');
      setVoiceNotice('A gravação de voz não está disponível neste navegador.');
      window.clearTimeout(voiceNoticeTimer.current);
      voiceNoticeTimer.current = window.setTimeout(() => setVoiceNotice(''), 4200);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true, noiseSuppression:true, channelCount:1}});
      const preferred = ['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(type => MediaRecorder.isTypeSupported?.(type));
      const recorder = new MediaRecorder(stream, preferred ? {mimeType:preferred} : undefined);
      voiceStreamRef.current = stream; recorderRef.current = recorder; voiceChunksRef.current = [];
      voiceBaseRef.current = latestValueRef.current.trim(); voiceTextRef.current = ''; voiceAutoSubmitRef.current = false;
      recorder.ondataavailable = event => { if (event.data?.size) voiceChunksRef.current.push(event.data); };
      recorder.onerror = () => { recognitionRef.current?.stop(); recorderRef.current = null; voiceChunksRef.current = []; releaseVoiceStream(); setVoiceState('error'); setVoiceNotice('Não foi possível gravar o áudio.'); };
      recorder.onstop = async () => {
        const blob = new Blob(voiceChunksRef.current, {type:recorder.mimeType || 'audio/webm'});
        releaseVoiceStream(); recorderRef.current = null; setVoiceState('transcribing'); setVoiceNotice('');
        try {
          const transcript = await transcribeRecording(blob);
          const finalValue = combineVoiceText(transcript || voiceTextRef.current);
          onChange?.(finalValue); latestValueRef.current = finalValue;
          setVoiceState('idle'); setVoiceNotice('');
          if (voiceAutoSubmitRef.current && finalValue.trim()) await onSubmit?.(finalValue);
          else window.requestAnimationFrame(() => textarea.current?.focus());
        } catch (error) {
          const fallback = combineVoiceText(cleanVoiceText(voiceTextRef.current));
          if (fallback.trim()) { onChange?.(fallback); setVoiceNotice(''); if (voiceAutoSubmitRef.current) await onSubmit?.(fallback); }
          else { setVoiceNotice(error.message); window.clearTimeout(voiceNoticeTimer.current); voiceNoticeTimer.current = window.setTimeout(() => setVoiceNotice(''), 4200); }
          setVoiceState('idle');
        }
      };
      window.clearTimeout(voiceNoticeTimer.current);
      recorder.start(250); setVoiceState('recording'); setVoiceNotice('');
      voiceLimitTimer.current = window.setTimeout(() => finishVoice(false), 295000);
    } catch (error) {
      setVoiceState('error');
      setVoiceNotice(error?.name === 'NotAllowedError' ? 'Permita o microfone para usar a voz.' : 'Não foi possível iniciar a gravação.');
      window.clearTimeout(voiceNoticeTimer.current);
      voiceNoticeTimer.current = window.setTimeout(() => setVoiceNotice(''), 4200);
      return;
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) return;
    const recognition = new Recognition();
    recognition.lang = 'pt-BR';
    recognition.interimResults = true;
    recognition.continuous = true;
    recognition.onresult = event => {
      const transcript = Array.from(event.results).map(result => result[0]?.transcript || '').join(' ').trim();
      voiceTextRef.current = transcript;
      const next = combineVoiceText(transcript); latestValueRef.current = next; onChange?.(next);
    };
    recognition.onerror = () => { recognitionRef.current = null; };
    recognition.onend = () => { recognitionRef.current = null; };
    recognitionRef.current = recognition;
    try { recognition.start(); } catch (_) { recognitionRef.current = null; }
  };
  useEffect(() => () => { recognitionRef.current?.stop(); if (recorderRef.current?.state === 'recording') { recorderRef.current.onstop = null; recorderRef.current.stop(); } releaseVoiceStream(); window.clearTimeout(voiceNoticeTimer.current); }, []);
  useEffect(() => {
    if (!textarea.current) return;
    textarea.current.style.height = 'auto';
    const viewportHeight = window.visualViewport?.height || window.innerHeight;
    const height = Math.min(textarea.current.scrollHeight, COMPOSER_MAX_HEIGHT, viewportHeight * .35);
    textarea.current.style.height = `${height}px`;
    textarea.current.style.overflowY = textarea.current.scrollHeight > height ? 'auto' : 'hidden';
  }, [value]);
  useEffect(() => {
    if (disabled) dispatchComposer({type: 'disable'});
    else if (running) dispatchComposer({type: 'stream'});
    else if (['streaming', 'submitting', 'disabled'].includes(machine.status)) dispatchComposer({type: 'complete', focused: focused.current});
  }, [disabled, running, machine.status]);
  useEffect(() => { onStateChange?.(machine.status); }, [machine.status, onStateChange]);
  useEffect(() => {
    if (composerContext?.type !== 'question') return;
    window.requestAnimationFrame(() => textarea.current?.focus());
  }, [composerContext]);
  const detectedUrl = pastedUrl(value);
  const detectedProfile = detectedUrl ? linkProfile(detectedUrl) : null;
  const saveLink = () => {
    if (!detectedUrl || !hasProject) return;
    const command = `Adicione este link ao projeto: ${detectedUrl}`;
    onChange?.(command);
    onSubmit?.(command, {skipAttachments: true});
  };
  const stageClass = embedded ? 'cadu-ds-home-chat-stage' : 'cv-composer-stage cv-flex-none cv-px-4 md:cv-px-8';
  const shellClass = homeMode ? 'cv-composer-shell cadu-ds-home-chat-shell' : 'cv-composer-shell';
  const handleDrop = event => {
    event.preventDefault();
    event.stopPropagation();
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
  const submitComposer = async event => {
    event.preventDefault();
    if (disabled) return;
    if (voiceState === 'recording' || voiceState === 'transcribing') { finishVoice(true); return; }
    dispatchComposer({type: 'submit'});
    capabilityMenu.current?.removeAttribute('open');
    intensityMenu.current?.removeAttribute('open');
    const compact = layout === 'phone' || layout === 'tablet';
    if (compact) {
      focused.current = false;
      textarea.current?.blur();
    }
    try {
      await onSubmit?.();
      if (!compact && !running) window.requestAnimationFrame(() => textarea.current?.focus());
    } catch (error) {
      dispatchComposer({type: 'error', error: error?.message});
    }
  };
  return <div className={`${stageClass}${contextActive ? ' is-context-drop' : ''}`} data-composer-state={machine.status} onDragEnter={event => { event.preventDefault(); setContextActive(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { if (event.currentTarget === event.target) setContextActive(false); }} onDrop={handleDrop}>
    <form onSubmit={submitComposer} className={`${shellClass} cv-pointer-events-auto cv-mx-auto cv-w-full ${embedded ? '' : 'cv-max-w-[760px]'}`}>
      {!!composerContext && <div className="cv-flex cv-items-center cv-gap-2 cv-px-3 cv-py-2"><span className="cv-min-w-0 cv-flex-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-[11px] cv-text-[#8fbab4]">↳ {composerContext.label}: “{composerContext.text}”</span><button type="button" onClick={onClearContext} className="cv-grid cv-h-5 cv-w-5 cv-place-items-center cv-rounded cv-border-0 cv-bg-transparent cv-text-[#78918d] hover:cv-bg-white/[.06] hover:cv-text-white" aria-label="Remover contexto">×</button></div>}
      {!!attachments.length && <div className="cv-attachment-list">{attachments.map((item, index) => { const state = item.error ? 'Não foi possível anexar' : item.uploading ? 'Enviando' : 'Pronto para enviar'; return <span key={item.localId || `${item.name}-${index}`} className={`cv-attachment-chip ${item.previewUrl ? 'is-image' : 'is-file'} ${item.error ? 'has-error' : ''}`} aria-label={`${item.name}. ${state}.`} title={item.name}><span className="cv-attachment-preview">{item.previewUrl ? <img src={item.previewUrl} alt="" className="cv-attachment-thumb"/> : <Icon name="file" size={19}/>}</span><button type="button" disabled={item.uploading} onClick={() => onRemoveAttachment?.(index)} className="cv-attachment-remove" aria-label={`Remover ${item.name}`}>×</button></span>; })}</div>}
      <textarea ref={textarea} value={value} disabled={disabled} onFocus={() => { focused.current = true; dispatchComposer({type: 'focus', hasValue: Boolean(value.trim())}); }} onBlur={() => { focused.current = false; dispatchComposer({type: 'blur'}); }} onChange={event => { onChange?.(event.target.value); dispatchComposer({type: 'change', hasValue: Boolean(event.target.value.trim()), focused: focused.current}); }} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { if (slashQuery !== null && slashPlugins.length) { event.preventDefault(); choosePlugin(slashPlugins[0]); return; } event.preventDefault(); event.currentTarget.form?.requestSubmit(); } if (event.key === 'Escape' && slashQuery !== null) onChange?.(''); }} rows="1" maxLength="20000" enterKeyHint="send" autoComplete="off" autoCorrect="on" autoCapitalize="sentences" spellCheck placeholder={composerContext?.type === 'question' ? 'Digite sua resposta…' : 'Pergunte ao Cadu…'} aria-label={composerContext?.type === 'question' ? `Resposta para: ${composerContext.text}` : 'Mensagem para o Cadu'} className="cv-composer-input cv-block cv-min-h-[48px] cv-w-full cv-resize-none cv-border-0 cv-bg-transparent cv-px-4 cv-py-3 cv-text-[15px] cv-leading-6 cv-text-white cv-outline-none placeholder:cv-text-[#6f8985]"/>
      {slashQuery !== null && <div className="cv-plugin-slash" role="listbox" aria-label="Plugins disponíveis">
        <div className="cv-plugin-slash__header"><b>Plugins</b><span>Digite para filtrar · Enter escolhe o primeiro</span></div>
        {pluginsLoading ? <p>Carregando plugins…</p> : pluginsError ? <p role="alert">{pluginsError}</p> : slashPlugins.length ? slashPlugins.map(plugin => <button key={plugin.id} type="button" role="option" aria-selected="false" onMouseDown={event => event.preventDefault()} onClick={() => choosePlugin(plugin)}>
          <span className="cv-plugin-slash__icon"><Icon name={PLUGIN_ICONS[plugin.id] || 'brand'} size={16}/></span>
          <span className="cv-plugin-slash__copy"><b>{plugin.name}</b><small>{plugin.description}</small></span>
          <span className="cv-plugin-slash__status">{plugin.maturity === 'active' ? 'Disponível' : 'Em integração'}</span>
        </button>) : <p>Nenhum plugin encontrado.</p>}
        <div className="cv-plugin-slash__hint">Escolher prepara o pedido; revise e envie na conversa.</div>
      </div>}
      {!!detectedUrl && detectedProfile && <div className="cv-link-intake cv-px-4 cv-pb-2" role="status" aria-live="polite">
        <div className="cv-link-intake__card">
          <span className="cv-link-intake__icon" aria-hidden="true">{detectedProfile.icon}</span>
          <div className="cv-link-intake__meta"><strong>{detectedProfile.name}</strong><small>{detectedProfile.provider}</small></div>
          <div className="cv-link-intake__actions">
            {onOpenLink
              ? <button type="button" onClick={() => onOpenLink({url: detectedUrl, title: detectedProfile.name, kind: detectedProfile.type, provider: detectedProfile.provider, access_type: 'reference'})}>Ver</button>
              : <a href={detectedUrl} target="_blank" rel="noreferrer">Abrir</a>}
            {hasProject && <button type="button" onClick={saveLink}>Salvar</button>}
          </div>
        </div>
      </div>}
      <div className="cv-composer-actions cv-flex cv-items-center cv-justify-between">
        <div className="cv-flex cv-min-w-0 cv-items-center cv-gap-2">
          <details ref={capabilityMenu} className="cv-composer-capabilities">
            <summary className={`cv-composer-add ${homeMode ? 'is-labeled' : ''} cv-cursor-pointer cv-list-none cv-rounded-full cv-border-0 cv-bg-transparent cv-text-mist`} aria-label="Mais recursos" title="Mais recursos"><Icon name="plus" size={17}/>{homeMode && <span>Recursos</span>}</summary>
            <div className="cv-capability-menu" role="menu" aria-label="Escolher modo e recursos">
              <input ref={fileInput} type="file" multiple tabIndex="-1" aria-hidden="true" onChange={acceptFiles} style={{display: 'none'}}/>
              <input ref={imageInput} type="file" multiple accept="image/*" tabIndex="-1" aria-hidden="true" onChange={acceptFiles} style={{display: 'none'}}/>
              <div className="cv-composer-mobile-actions">
                <div className="cv-capability-heading">Adicionar</div>
                <button type="button" role="menuitem" onClick={() => pickFiles(fileInput)}><span><b>Arquivo</b><small>PDF, documento ou qualquer arquivo</small></span><Icon name="file" size={15}/></button>
                <button type="button" role="menuitem" onClick={() => pickFiles(imageInput)}><span><b>Imagem</b><small>Adicionar uma imagem ao pedido</small></span><Icon name="image" size={15}/></button>
                <button type="button" role="menuitem" onClick={() => onContextDrop?.({type: 'project', projectRef: projects[0]?.ref || projects[0]?.projectRef || projects[0]?.id})} disabled={!projects.length}><span><b>Projeto</b><small>{projects.length ? `Usar ${projects[0]?.name || 'um projeto'} como contexto` : 'Nenhum projeto disponível'}</small></span><Icon name="folder" size={15}/></button>
                {['Drive', 'Documento', 'Planilha', 'Apresentação', 'Automação', 'Ferramenta'].map(label => <button key={label} type="button" role="menuitem" disabled><span><b>{label}</b><small>Disponível após conectar este recurso</small></span><span className="cv-composer-coming-soon">Em breve</span></button>)}
              </div>
              <div className="cv-composer-mobile-modes">
                <div className="cv-capability-heading">Modo</div>
                {MODE_OPTIONS.map(option => <button key={option.id} type="button" role="menuitemradio" aria-checked={executionMode === option.id} className={executionMode === option.id ? 'is-active' : ''} onClick={() => { onExecutionModeChange?.(option.id); capabilityMenu.current?.removeAttribute('open'); }}><span><b>{option.label}</b><small>{option.detail}</small></span>{executionMode === option.id && <Icon name="check" size={15}/>}</button>)}
              </div>
              <div className="cv-capability-heading">Começar com um recurso</div>
              <p className="cv-capability-intro">Escolha uma ação para preparar o pedido. Você pode editar o texto antes de enviar.</p>
              {availableCapabilities.map(capability => <button key={capability.label} type="button" role="menuitem" className="cv-capability-action" onClick={() => selectCapability(capability)}><Icon name={capability.icon} size={16}/><span><b>{capability.label}</b><small>{capability.detail}</small></span><span className="cv-capability-action__result">Preencher</span></button>)}
            </div>
          </details>
        </div>
        <div className="cv-composer-submit-group cv-flex cv-items-center cv-gap-1.5">
          {homeMode && showProjectSelector && <ProjectSelector
            label="Contexto da conversa"
            emptyLabel="Sessão rápida"
            items={projects}
            value={projectRef}
            onChange={onProjectChange}
          />}
          <details ref={intensityMenu} className="cv-composer-intensity">
            <summary className="cv-composer-intensity__trigger" aria-label={`Intensidade do agente: ${currentMode.label}`} title={`Intensidade: ${currentMode.label}`}><Icon name="pulse" size={14}/><span>{currentMode.label}</span><Icon name="chevron" size={13}/></summary>
            <div className="cv-composer-intensity__menu" role="menu" aria-label="Intensidade do agente">
              <div className="cv-capability-heading">Intensidade do agente</div>
              {MODE_OPTIONS.map(option => <button key={option.id} type="button" role="menuitemradio" aria-checked={executionMode === option.id} className={executionMode === option.id ? 'is-active' : ''} onClick={() => { onExecutionModeChange?.(option.id); intensityMenu.current?.removeAttribute('open'); }}><span><b>{option.label}</b><small>{option.detail}</small></span>{executionMode === option.id && <Icon name="check" size={15}/>}</button>)}
            </div>
          </details>
          <button type="button" onClick={toggleVoice} disabled={voiceState === 'transcribing'} className={`cv-composer-audio cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-xl cv-border-0 cv-bg-transparent cv-text-mist ${voiceState === 'recording' ? 'is-listening' : ''} ${voiceState === 'transcribing' ? 'is-transcribing' : ''} ${['unsupported', 'error'].includes(voiceState) ? 'is-unavailable' : ''}`} aria-label={voiceState === 'recording' ? 'Concluir gravação' : voiceState === 'transcribing' ? 'Transcrevendo áudio' : 'Gravar mensagem de voz'} title={voiceState === 'recording' ? 'Concluir gravação' : voiceState === 'transcribing' ? 'Transcrevendo' : 'Gravar mensagem de voz'} aria-busy={voiceState === 'transcribing'}>{voiceState === 'recording' ? <span className="cv-composer-audio__pause" aria-hidden="true"/> : voiceState === 'transcribing' ? <span className="cv-composer-audio__loading" aria-hidden="true"/> : <Icon name="audio" size={17}/>}</button>
          {running && allowQueue && <button type="submit" disabled={!value.trim() || queuedCount >= 5} className="cv-composer-queue cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-xl cv-border-0 cv-bg-transparent cv-text-mist disabled:cv-opacity-35" aria-label="Adicionar pedido à fila" title="Adicionar à fila"><Icon name="plus" size={16}/></button>}
          <span className="cv-composer-action-slot">
            {running ? <button type="button" onClick={onStop} className="cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-xl cv-border-0 cv-bg-white/10" aria-label="Interromper geração"><span className="cv-h-2.5 cv-w-2.5 cv-rounded-sm cv-bg-[#d7e4e2]"/></button>
              : <button type="submit" disabled={disabled || (!value.trim() && !attachments.length && voiceState !== 'recording' && voiceState !== 'transcribing') || attachments.some(item => item.uploading)} className="cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-xl cv-border-0 cv-bg-teal cv-text-[#052522] disabled:cv-cursor-not-allowed disabled:cv-opacity-35" aria-label="Enviar mensagem" title="Enviar mensagem"><Icon name="arrowUp" size={17}/></button>}
          </span>
        </div>
        {voiceNotice && <span className="cv-composer-audio-status" role="status">{voiceNotice}</span>}
      </div>
    </form>
  </div>;
}
