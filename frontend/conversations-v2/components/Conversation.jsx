import React, {useEffect, useRef, useState} from 'react';
import {Icon} from '../lib/icons';
import {Markdown} from './Markdown';
import {safeUrl} from '../lib/api';
import {ResponseBlocks} from './ResponseBlocks';

function Answer({message, onPrompt, onOpenArtifact, onOpenResource, onDecision}) {
  const response = message.response || {answer: message.content};
  const text = String(response.answer || '');
  const blocks = Array.isArray(response.blocks) ? response.blocks : [];
  const dense = text.length > 900 || text.split('\n').length > 12;
  if (message.kind === 'action') {
    return <div className="cv-max-w-[72ch]">
      <p className="cv-m-0 cv-text-[15px] cv-leading-7 cv-text-[#d9e7e4]">{message.action?.summary || 'Esta ação precisa da sua confirmação.'}</p>
      <div className="cv-mt-3 cv-flex cv-gap-2"><button type="button" onClick={() => onDecision(message, false)} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-3 cv-py-2 cv-text-xs">Cancelar</button><button type="button" onClick={() => onDecision(message, true)} className="cv-rounded-lg cv-border-0 cv-bg-teal cv-px-3 cv-py-2 cv-text-xs cv-font-semibold cv-text-[#04211e]">Confirmar</button></div>
    </div>;
  }
  return <div className="cv-message-enter cv-max-w-[72ch]">
    {dense ? <><p className="cv-m-0 cv-text-[15px] cv-leading-7 cv-text-[#d9e7e4]">{text.replace(/\[[^\]]+\]\([^)]+\)|[*_`#]/g, '').replace(/\s+/g, ' ').slice(0, 320).replace(/\s+\S*$/, '')}…</p><details className="cv-mt-3"><summary className="cv-cursor-pointer cv-text-xs cv-font-semibold cv-text-[#65d8cb]">Ver resposta completa</summary><div className="cv-prose cv-mt-3"><Markdown>{text}</Markdown></div></details></> : <div className="cv-prose"><Markdown>{text}</Markdown></div>}
    <ResponseBlocks blocks={blocks} onPrompt={onPrompt} onOpenResource={onOpenResource}/>
    {!!response.questions?.length && <div className="cv-mt-5 cv-border-l-2 cv-border-teal/50 cv-pl-4">{response.questions.map((question, index) => <div key={index} className="cv-my-2"><p className="cv-m-0 cv-text-sm cv-text-[#e4efed]">{question}</p><button type="button" onClick={() => onPrompt(`Sobre “${question}”: `)} className="cv-mt-2 cv-border-0 cv-bg-transparent cv-p-0 cv-text-xs cv-font-semibold cv-text-[#65d8cb]">Responder</button></div>)}</div>}
    {!!response.assumptions?.length && <details className="cv-mt-4 cv-text-xs cv-text-mist"><summary className="cv-cursor-pointer">{response.assumptions.length === 1 ? 'Premissa usada' : `${response.assumptions.length} premissas usadas`}</summary><ul>{response.assumptions.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
    {!!response.citations?.length && <div className="cv-mt-4 cv-flex cv-flex-wrap cv-gap-2">{response.citations.slice(0, 6).map((item, index) => { const href = safeUrl(item?.url); return href ? <a key={index} href={href} target="_blank" rel="noreferrer" className="cv-rounded-full cv-bg-white/[.06] cv-px-3 cv-py-1.5 cv-text-xs cv-text-[#b9cbc8] cv-no-underline hover:cv-text-white">{item.title || 'Fonte'}</a> : <span key={index} className="cv-rounded-full cv-bg-white/[.06] cv-px-3 cv-py-1.5 cv-text-xs cv-text-[#b9cbc8]">{item.title || 'Fonte'}</span>; })}</div>}
    {!blocks.length && !!response.actions?.length && <div className="cv-mt-4 cv-flex cv-flex-wrap cv-gap-2">{response.actions.slice(0, 2).map((item, index) => <button key={index} type="button" onClick={() => onPrompt(item.prompt || '')} className="cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-3 cv-py-2 cv-text-xs hover:cv-bg-white/[.05]">{item.label}</button>)}</div>}
    {message.artifact?.id && <button type="button" onClick={() => onOpenArtifact(message.artifact)} className="cv-mt-5 cv-flex cv-items-center cv-gap-2 cv-rounded-lg cv-border-0 cv-bg-teal/10 cv-px-3 cv-py-2 cv-text-xs cv-font-semibold cv-text-[#66dbce] hover:cv-bg-teal/15"><Icon name="file" size={15}/>Abrir {message.artifact.title || 'artefato'}</button>}
  </div>;
}

function SelectionTools({text, onPrompt, onClear}) {
  const quote = text.length > 420 ? `${text.slice(0, 420).replace(/\s+\S*$/, '')}…` : text;
  const ask = prompt => { onClear(); onPrompt(prompt, {type: 'selection', label: 'Trecho selecionado', text: quote}); };
  return <div className="cv-selection-tools cv-sticky cv-bottom-6 cv-z-10 cv-mx-auto cv-mb-5 cv-flex cv-w-fit cv-max-w-[calc(100%-32px)] cv-flex-wrap cv-items-center cv-justify-center cv-gap-1.5 cv-rounded-xl cv-border cv-border-teal/25 cv-bg-[#102326]/95 cv-p-1.5 cv-shadow-xl cv-backdrop-blur" role="toolbar" aria-label="Ações para o trecho selecionado">
    <span className="cv-px-2 cv-text-[10px] cv-text-[#8faaa5]">Trecho selecionado</span>
    <button type="button" onClick={() => ask('Explique este trecho de forma simples.')} className="cv-rounded-lg cv-border-0 cv-bg-transparent cv-px-2.5 cv-py-1.5 cv-text-[11px] cv-text-[#c3d6d2] hover:cv-bg-white/[.07] hover:cv-text-white">Perguntar</button>
    <button type="button" onClick={() => ask('Resuma este trecho em uma frase.')} className="cv-rounded-lg cv-border-0 cv-bg-transparent cv-px-2.5 cv-py-1.5 cv-text-[11px] cv-text-[#c3d6d2] hover:cv-bg-white/[.07] hover:cv-text-white">Resumir</button>
    <button type="button" onClick={() => ask('Adicione este trecho ao briefing do projeto como uma premissa.')} className="cv-rounded-lg cv-border-0 cv-bg-teal/15 cv-px-2.5 cv-py-1.5 cv-text-[11px] cv-font-semibold cv-text-teal hover:cv-bg-teal/25">Adicionar ao briefing</button>
    <button type="button" onClick={onClear} className="cv-grid cv-h-6 cv-w-6 cv-place-items-center cv-rounded-md cv-border-0 cv-bg-transparent cv-text-[#7e9994] hover:cv-bg-white/[.07] hover:cv-text-white" aria-label="Fechar ações do trecho">×</button>
  </div>;
}

function Thread({messages, onPrompt, onOpenArtifact, onOpenResource, onDecision, onOpenDiagnostics, running, runtime}) {
  const end = useRef(null);
  const thread = useRef(null);
  const [selection, setSelection] = useState('');
  useEffect(() => { end.current?.scrollIntoView({block: 'end'}); }, [messages]);
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
  if (!messages.length && !running) return <div className="cv-flex cv-min-h-full cv-items-center cv-justify-center cv-px-6 cv-py-16">
    <div className="cv-w-full cv-max-w-[700px] cv-text-center">
      <span className="cv-mx-auto cv-grid cv-h-10 cv-w-10 cv-place-items-center cv-rounded-xl cv-bg-teal/10 cv-text-lg cv-font-bold cv-text-teal">C</span>
      <h2 className="cv-mb-2 cv-mt-5 cv-text-2xl cv-font-semibold cv-tracking-[-.025em]">Em que vamos trabalhar?</h2>
      <p className="cv-mx-auto cv-mb-8 cv-max-w-[520px] cv-text-sm cv-leading-6 cv-text-mist">Converse, analise arquivos ou crie algo usando o contexto do projeto.</p>
      <div className="cv-flex cv-flex-wrap cv-justify-center cv-gap-2">{[
        ['Criar um briefing', 'Estruture um briefing para esta campanha e destaque somente o que ainda precisa ser decidido.'],
        ['Pesquisar no projeto', 'Pesquise nos documentos do projeto o que já definimos sobre orçamento e prazo.'],
        ['Comparar opções', 'Compare as opções disponíveis e recomende a melhor com uma justificativa curta.'],
      ].map(([label, prompt]) => <button key={label} type="button" onClick={() => onPrompt(prompt)} className="cv-rounded-full cv-border cv-border-white/10 cv-bg-white/[.025] cv-px-4 cv-py-2.5 cv-text-xs cv-text-[#bdcfcc] hover:cv-bg-white/[.06] hover:cv-text-white">{label}</button>)}</div>
    </div>
  </div>;
  return <div ref={thread} onMouseUp={captureSelection} className="cv-thread-content cv-mx-auto cv-w-full cv-max-w-[820px] cv-px-6 cv-pt-10 md:cv-px-10">
    {messages.map(message => message.role === 'user' ? <article key={message.id} className="cv-mb-10 cv-flex cv-justify-end"><div className="cv-max-w-[68ch] cv-rounded-2xl cv-rounded-br-md cv-bg-[#12322f] cv-px-4 cv-py-3 cv-text-[14px] cv-leading-6 cv-text-[#f0f8f6]"><p className="cv-m-0 cv-whitespace-pre-wrap">{message.content}</p>{!!message.files?.length && <small className="cv-mt-2 cv-block cv-text-[#8fc6bf]">{message.files.map(file => file.name || 'Arquivo').join(', ')}</small>}</div></article> : message.kind === 'worked' ? <button key={message.id} type="button" onClick={onOpenDiagnostics} className="cv-mb-4 cv-border-0 cv-bg-transparent cv-p-0 cv-text-xs cv-text-[#718b87] hover:cv-text-[#a9bfbb]">Trabalhou por {message.seconds} s ›</button> : <article key={message.id} data-cv-answer="true" className="cv-mb-10"><Answer message={message} onPrompt={onPrompt} onOpenArtifact={onOpenArtifact} onOpenResource={onOpenResource} onDecision={onDecision}/></article>)}
    {selection && <SelectionTools text={selection} onPrompt={onPrompt} onClear={clearSelection}/>}
    {running && <div className="cv-mb-10 cv-flex cv-items-center cv-gap-3 cv-text-xs cv-text-[#86a29e]" role="status"><span className="cv-flex cv-gap-1" aria-hidden="true"><i className="cv-h-1.5 cv-w-1.5 cv-animate-pulse cv-rounded-full cv-bg-teal"/><i className="cv-h-1.5 cv-w-1.5 cv-animate-pulse cv-rounded-full cv-bg-teal" style={{animationDelay: '160ms'}}/><i className="cv-h-1.5 cv-w-1.5 cv-animate-pulse cv-rounded-full cv-bg-teal" style={{animationDelay: '320ms'}}/></span>{runtime || 'Cadu está trabalhando'}</div>}
    <div ref={end}/>
  </div>;
}

function Composer({value, onChange, onSubmit, onAttach, attachments, onRemoveAttachment, running, onStop, contextLabel, composerContext, onClearContext}) {
  const textarea = useRef(null);
  useEffect(() => {
    if (!textarea.current) return;
    textarea.current.style.height = 'auto';
    textarea.current.style.height = `${Math.min(textarea.current.scrollHeight, 150)}px`;
    if (value && document.activeElement !== textarea.current) textarea.current.focus();
  }, [value]);
  return <div className="cv-composer-stage cv-pointer-events-none cv-absolute cv-inset-x-0 cv-bottom-0 cv-z-20 cv-px-4 md:cv-px-8">
    <form onSubmit={event => { event.preventDefault(); onSubmit(); }} className="cv-composer-shell cv-pointer-events-auto cv-mx-auto cv-w-full cv-max-w-[760px]">
      {!!composerContext && <div className="cv-flex cv-items-center cv-gap-2 cv-border-b cv-border-white/[.06] cv-px-3 cv-py-2"><span className="cv-min-w-0 cv-flex-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-[11px] cv-text-[#8fbab4]">↳ {composerContext.label}: “{composerContext.text}”</span><button type="button" onClick={onClearContext} className="cv-grid cv-h-5 cv-w-5 cv-place-items-center cv-rounded cv-border-0 cv-bg-transparent cv-text-[#78918d] hover:cv-bg-white/[.06] hover:cv-text-white" aria-label="Remover contexto">×</button></div>}
      {!!attachments.length && <div className="cv-flex cv-flex-wrap cv-gap-2 cv-px-2 cv-pb-2">{attachments.map((item, index) => <span key={`${item.name}-${index}`} className={`cv-attachment-chip cv-flex cv-items-center cv-gap-2 cv-rounded-lg cv-bg-white/[.06] cv-px-2 cv-py-1.5 cv-text-xs ${item.error ? 'cv-text-[#ff9ca1]' : 'cv-text-[#b9cbc8]'}`}>{item.previewUrl ? <img src={item.previewUrl} alt="" className="cv-attachment-thumb"/> : <Icon name="file" size={15}/>}<span className="cv-max-w-48 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap">{item.uploading ? 'Enviando · ' : ''}{item.name}</span><button type="button" disabled={item.uploading} onClick={() => onRemoveAttachment(index)} className="cv-border-0 cv-bg-transparent cv-p-0 cv-text-[#91aaa6]" aria-label={`Remover ${item.name}`}>×</button></span>)}</div>}
      <textarea ref={textarea} value={value} onChange={event => onChange(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} rows="1" maxLength="20000" placeholder="Pergunte ou peça uma alteração…" aria-label="Mensagem para o Cadu" className="cv-composer-input cv-block cv-max-h-[150px] cv-min-h-[48px] cv-w-full cv-resize-none cv-border-0 cv-bg-transparent cv-px-4 cv-py-3 cv-text-[15px] cv-leading-6 cv-text-white cv-outline-none placeholder:cv-text-[#6f8985]"/>
      <div className="cv-composer-actions cv-flex cv-items-center cv-justify-between">
        <div className="cv-flex cv-min-w-0 cv-items-center cv-gap-2"><button type="button" onClick={onAttach} className="cv-composer-add cv-grid cv-h-8 cv-w-8 cv-place-items-center cv-border-0 cv-bg-transparent cv-text-mist" aria-label="Adicionar arquivo" title="Adicionar arquivo"><Icon name="plus" size={17}/></button><span className="cv-context-label cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-[11px]">{contextLabel}</span></div>
        {running ? <button type="button" onClick={onStop} className="cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-xl cv-border-0 cv-bg-white/10" aria-label="Interromper geração"><span className="cv-h-2.5 cv-w-2.5 cv-rounded-sm cv-bg-[#d7e4e2]"/></button> : <button type="submit" disabled={!value.trim() || attachments.some(item => item.uploading)} className="cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-xl cv-border-0 cv-bg-teal cv-text-[#052522] disabled:cv-cursor-not-allowed disabled:cv-opacity-35" aria-label="Enviar mensagem"><Icon name="arrowUp" size={17}/></button>}
      </div>
    </form>
  </div>;
}

export function Conversation({title, context, projects, onProjectChange, contextLoading, runtime, diagnostics, messages, input, setInput, onSubmit, onAttach, attachments, onRemoveAttachment, running, onStop, onNew, onPrompt, onOpenArtifact, onOpenResource, onDecision, mobileMenu, artifactOpen, notice, onDismissNotice, composerContext, onClearContext}) {
  const details = useRef(null);
  const selected = projects.find(item => item.ref === context?.project_ref);
  return <section className="cv-relative cv-flex cv-min-w-0 cv-flex-1 cv-flex-col cv-bg-ink">
    <header className="cv-flex cv-h-[68px] cv-flex-none cv-items-center cv-gap-4 cv-border-b cv-border-white/[.07] cv-px-4 md:cv-px-6">
      <button type="button" onClick={mobileMenu} className="cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-mist md:cv-hidden" aria-label="Abrir navegação"><Icon name="menu"/></button>
      <h1 className={`cv-conversation-title cv-m-0 cv-min-w-0 cv-flex-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap ${artifactOpen ? 'cv-hidden 2xl:cv-block' : ''}`} title={title}>{title}</h1>
      <label className="cv-flex cv-items-center cv-gap-2"><span className="cv-hidden cv-text-[11px] cv-text-[#78908c] sm:cv-inline">Projeto</span><select value={context?.project_ref || ''} onChange={event => onProjectChange(event.target.value)} disabled={running || contextLoading} aria-busy={contextLoading} aria-label="Projeto usado nesta conversa" className="cv-h-9 cv-w-[180px] cv-rounded-lg cv-border-0 cv-bg-white/[.06] cv-px-3 cv-text-xs cv-text-[#d8e5e2] cv-outline-none disabled:cv-opacity-55 md:cv-w-[220px]"><option value="">{contextLoading && !projects.length ? 'Carregando projetos…' : 'Contexto pessoal'}</option>{projects.map(item => <option key={item.ref} value={item.ref}>{item.name}</option>)}</select></label>
      {runtime && <span className="cv-hidden cv-max-w-40 cv-items-center cv-gap-2 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-[11px] cv-text-[#85aaa5] lg:cv-flex"><i className={`cv-h-1.5 cv-w-1.5 cv-flex-none cv-rounded-full ${running ? 'cv-animate-pulse cv-bg-teal' : 'cv-bg-[#6f8884]'}`}/>{runtime}</span>}
      <details ref={details} className="cv-relative">
        <summary className="cv-grid cv-h-9 cv-w-9 cv-cursor-pointer cv-list-none cv-place-items-center cv-rounded-lg cv-text-mist hover:cv-bg-white/[.05]" aria-label="Detalhes da execução"><Icon name="pulse" size={17}/></summary>
        <div className="cv-absolute cv-right-0 cv-top-11 cv-z-50 cv-w-[320px] cv-rounded-xl cv-border cv-border-white/10 cv-bg-[#122124] cv-p-4 cv-shadow-2xl">
          <strong className="cv-block cv-text-sm">Detalhes da execução</strong><span className="cv-mt-1 cv-block cv-text-[11px] cv-text-[#79918d]">Eventos técnicos desta conversa</span>
          <div className="cv-scroll cv-mt-4 cv-max-h-72 cv-overflow-y-auto">{diagnostics.length ? diagnostics.map(item => <div key={item.id} className="cv-mb-3 cv-flex cv-gap-2"><i className={`cv-mt-1.5 cv-h-1.5 cv-w-1.5 cv-flex-none cv-rounded-full ${item.tone === 'error' ? 'cv-bg-[#ff7d83]' : 'cv-bg-teal'}`}/><div><b className="cv-block cv-text-xs cv-font-medium">{item.title}</b>{item.detail && <small className="cv-mt-0.5 cv-block cv-text-[10px] cv-text-[#79918d]">{item.detail}</small>}</div></div>) : <p className="cv-text-xs cv-text-[#79918d]">Nenhuma execução iniciada.</p>}</div>
        </div>
      </details>
      <button type="button" onClick={onNew} disabled={running} className="cv-grid cv-h-9 cv-w-9 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-mist hover:cv-bg-white/[.05] disabled:cv-cursor-not-allowed disabled:cv-opacity-30" aria-label={running ? 'Aguarde a resposta para iniciar outra conversa' : 'Nova conversa'}><Icon name="plus" size={18}/></button>
    </header>
    {notice && <div className="cv-absolute cv-right-5 cv-top-[78px] cv-z-30 cv-flex cv-w-[min(390px,calc(100%-40px))] cv-items-start cv-gap-3 cv-rounded-xl cv-border cv-border-[#ff7d83]/25 cv-bg-[#28191b]/95 cv-p-3 cv-shadow-2xl cv-backdrop-blur" role="alert"><span className="cv-mt-1 cv-h-2 cv-w-2 cv-flex-none cv-rounded-full cv-bg-[#ff7d83]"/><div className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-xs cv-font-semibold">{notice.title}</strong>{notice.detail && <span className="cv-mt-1 cv-block cv-text-[11px] cv-leading-5 cv-text-[#d8b5b7]">{notice.detail}</span>}</div><button type="button" onClick={onDismissNotice} className="cv-grid cv-h-6 cv-w-6 cv-place-items-center cv-rounded-md cv-border-0 cv-bg-transparent cv-text-[#c99b9e]" aria-label="Fechar aviso"><Icon name="close" size={14}/></button></div>}
    <div className="cv-thread-scroll cv-scroll cv-min-h-0 cv-flex-1 cv-overflow-y-auto"><Thread messages={messages} onPrompt={onPrompt} onOpenArtifact={onOpenArtifact} onOpenResource={onOpenResource} onDecision={onDecision} running={running} runtime={runtime} onOpenDiagnostics={() => { if (details.current) details.current.open = true; }}/></div>
    <Composer value={input} onChange={setInput} onSubmit={onSubmit} onAttach={onAttach} attachments={attachments} onRemoveAttachment={onRemoveAttachment} running={running} onStop={onStop} contextLabel={selected?.name || 'Contexto pessoal'} composerContext={composerContext} onClearContext={onClearContext}/>
    {artifactOpen && <span className="cv-sr-only">Artefato aberto ao lado da conversa</span>}
  </section>;
}
