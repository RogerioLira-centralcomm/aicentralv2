import React, {useState} from 'react';
import {Icon} from '../lib/icons';
import {safeUrl} from '../lib/api';
import {checklistPrompt} from '../lib/responseModel.mjs';

function BlockHeader({block}) {
  if (!block.title && !block.summary) return null;
  return <header className="cv-mb-3"><strong className="cv-block cv-text-sm cv-font-semibold cv-text-[#edf7f5]">{block.title}</strong>{block.summary && <p className="cv-mb-0 cv-mt-1 cv-text-xs cv-leading-5 cv-text-[#819b97]">{block.summary}</p>}</header>;
}

function DecisionBlock({block, onPrompt}) {
  const recommended = block.items.find(item => item.recommended);
  const [selected, setSelected] = useState(recommended?.id || '');
  const choice = block.items.find(item => item.id === selected);
  return <section className="cv-response-block cv-mt-5">
    <BlockHeader block={block}/>
    <div className="cv-grid cv-gap-1">{block.items.map(item => <button key={item.id} type="button" onClick={() => setSelected(item.id)} aria-pressed={selected === item.id} className={`cv-group cv-flex cv-w-full cv-items-start cv-gap-3 cv-rounded-xl cv-border-0 cv-px-3 cv-py-3 cv-text-left cv-transition-colors ${selected === item.id ? 'cv-bg-teal/10' : 'cv-bg-transparent hover:cv-bg-white/[.035]'}`}>
      <span className={`cv-mt-1 cv-grid cv-h-4 cv-w-4 cv-flex-none cv-place-items-center cv-rounded-full cv-border ${selected === item.id ? 'cv-border-teal cv-bg-teal' : 'cv-border-white/25'}`}>{selected === item.id && <i className="cv-h-1.5 cv-w-1.5 cv-rounded-full cv-bg-[#06211e]"/>}</span>
      <span className="cv-min-w-0 cv-flex-1"><strong className="cv-flex cv-items-center cv-gap-2 cv-text-sm cv-font-medium">{item.title}{item.recommended && <small className="cv-rounded-full cv-bg-teal/10 cv-px-2 cv-py-0.5 cv-text-[10px] cv-font-semibold cv-text-[#65d8cb]">Recomendada</small>}</strong>{item.detail && <small className="cv-mt-1 cv-block cv-text-xs cv-leading-5 cv-text-[#8ba39f]">{item.detail}</small>}</span>
    </button>)}</div>
    {choice && <button type="button" onClick={() => onPrompt(choice.prompt || `Use a opção “${choice.title}” e continue o trabalho.`)} className="cv-mt-3 cv-rounded-lg cv-border-0 cv-bg-teal cv-px-3.5 cv-py-2.5 cv-text-xs cv-font-semibold cv-text-[#052522]">Usar esta opção</button>}
  </section>;
}

function ChecklistBlock({block, onPrompt}) {
  const [checked, setChecked] = useState(() => new Set());
  const toggle = id => setChecked(current => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const selected = block.items.filter(item => checked.has(item.id));
  return <section className="cv-response-block cv-mt-5">
    <BlockHeader block={block}/>
    <div>{block.items.map(item => { const chosen = checked.has(item.id); const done = item.state === 'done'; return <button key={item.id} type="button" aria-pressed={chosen} onClick={() => toggle(item.id)} className={`cv-flex cv-w-full cv-items-start cv-gap-3 cv-border-0 cv-border-b cv-border-white/[.06] cv-px-2 cv-py-3 cv-text-left last:cv-border-0 ${chosen ? 'cv-bg-white/[.045]' : 'cv-bg-transparent hover:cv-bg-white/[.025]'}`}>
      <span className={`cv-mt-0.5 cv-grid cv-h-5 cv-w-5 cv-flex-none cv-place-items-center cv-rounded-full cv-border ${done ? 'cv-border-teal/70 cv-bg-teal/15 cv-text-teal' : item.state === 'blocked' ? 'cv-border-[#ff7d83]/60 cv-text-[#ff9ca1]' : 'cv-border-white/20 cv-text-transparent'}`}>{done ? <Icon name="check" size={12}/> : item.state === 'blocked' ? '!' : '•'}</span>
      <span className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-sm cv-font-medium cv-text-[#e4efed]">{item.title}</strong>{item.detail && <small className="cv-mt-1 cv-block cv-text-xs cv-leading-5 cv-text-[#819b97]">{item.detail}</small>}</span>
      {chosen && <span className="cv-mt-1 cv-text-[10px] cv-font-semibold cv-text-teal">Selecionado</span>}
    </button>; })}</div>
    {!!selected.length && <button type="button" onClick={() => onPrompt(checklistPrompt(selected))} className="cv-mt-3 cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-3.5 cv-py-2.5 cv-text-xs cv-font-semibold hover:cv-bg-white/[.04]">Continuar com {selected.length === 1 ? 'este item' : `${selected.length} itens`}</button>}
  </section>;
}

function InsightsBlock({block, onPrompt}) {
  return <section className="cv-response-block cv-mt-5"><BlockHeader block={block}/><div className="cv-grid cv-gap-1">{block.items.map(item => <button key={item.id} type="button" onClick={() => onPrompt(item.prompt || `Aprofunde este ponto: ${item.title}.`)} className="cv-group cv-flex cv-w-full cv-items-start cv-gap-3 cv-rounded-lg cv-border-0 cv-bg-transparent cv-px-2 cv-py-2.5 cv-text-left hover:cv-bg-white/[.035]"><span className="cv-mt-2 cv-h-1.5 cv-w-1.5 cv-flex-none cv-rounded-full cv-bg-teal/70"/><span className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-sm cv-font-medium">{item.title}</strong>{item.detail && <small className="cv-mt-1 cv-block cv-text-xs cv-leading-5 cv-text-[#819b97]">{item.detail}</small>}</span><span className="cv-mt-1 cv-text-[10px] cv-font-semibold cv-text-[#66817d] group-hover:cv-text-teal">Aprofundar</span></button>)}</div></section>;
}

function MetricsBlock({block, onPrompt}) {
  return <section className="cv-response-block cv-mt-5 cv-border-y cv-border-white/[.07] cv-py-4"><BlockHeader block={block}/><div className="cv-grid cv-grid-cols-2 cv-gap-x-6 cv-gap-y-4 sm:cv-grid-cols-3">{block.items.map(item => { const body = <><strong className="cv-block cv-text-xl cv-font-semibold cv-tracking-[-.03em] cv-text-[#edf7f5]">{item.value || '—'}</strong><span className="cv-mt-1 cv-block cv-text-xs cv-text-[#819b97]">{item.title}</span>{item.detail && <small className="cv-mt-1 cv-block cv-text-[10px] cv-leading-4 cv-text-[#657f7b]">{item.detail}</small>}</>; return item.prompt ? <button key={item.id} type="button" onClick={() => onPrompt(item.prompt)} className="cv-border-0 cv-bg-transparent cv-p-0 cv-text-left">{body}<small className="cv-mt-2 cv-block cv-text-[10px] cv-font-semibold cv-text-teal">Analisar</small></button> : <div key={item.id}>{body}{safeUrl(item.url) && <a href={safeUrl(item.url)} target="_blank" rel="noreferrer" className="cv-mt-2 cv-block cv-text-[10px] cv-font-semibold cv-text-teal cv-no-underline">Ver fonte</a>}</div>; })}</div></section>;
}

function FilesBlock({block, onOpenResource}) {
  return <section className="cv-response-block cv-mt-5"><BlockHeader block={block}/><div className="cv-grid cv-gap-1">{block.items.map(item => <button key={item.id} type="button" onClick={() => onOpenResource?.(item)} className="cv-flex cv-w-full cv-items-center cv-gap-3 cv-rounded-xl cv-border-0 cv-bg-transparent cv-p-2 cv-text-left hover:cv-bg-white/[.035]"><span className="cv-grid cv-h-9 cv-w-9 cv-flex-none cv-place-items-center cv-rounded-lg cv-bg-white/[.05] cv-text-[#79b9b1]"><Icon name="file" size={16}/></span><span className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-sm cv-font-medium">{item.title}</strong><small className="cv-mt-0.5 cv-block cv-text-[11px] cv-text-[#78918d]">{item.kind || 'Arquivo'}{item.detail ? ` · ${item.detail}` : ''}</small></span><span className="cv-text-[10px] cv-font-semibold cv-text-teal">Abrir</span></button>)}</div></section>;
}

function StepsBlock({block, onPrompt}) {
  return <section className="cv-response-block cv-mt-5"><BlockHeader block={block}/><ol className="cv-m-0 cv-list-none cv-p-0">{block.items.map((item, index) => <li key={item.id} className="cv-relative cv-flex cv-gap-3 cv-pb-4 last:cv-pb-0">{index < block.items.length - 1 && <i className="cv-absolute cv-left-[7px] cv-top-5 cv-h-[calc(100%-16px)] cv-w-px cv-bg-white/10"/>}<span className={`cv-mt-1 cv-h-4 cv-w-4 cv-flex-none cv-rounded-full cv-border-2 ${item.state === 'done' ? 'cv-border-teal cv-bg-teal' : item.state === 'active' ? 'cv-animate-pulse cv-border-teal' : item.state === 'blocked' ? 'cv-border-[#ff7d83]' : 'cv-border-white/20'}`}/><span className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-sm cv-font-medium">{item.title}</strong>{item.detail && <small className="cv-mt-1 cv-block cv-text-xs cv-leading-5 cv-text-[#819b97]">{item.detail}</small>}{item.prompt && item.state !== 'done' && <button type="button" onClick={() => onPrompt(item.prompt)} className="cv-mt-2 cv-border-0 cv-bg-transparent cv-p-0 cv-text-[10px] cv-font-semibold cv-text-teal">Continuar esta etapa</button>}</span></li>)}</ol></section>;
}

export function ResponseBlocks({blocks, onPrompt, onOpenResource}) {
  return <>{(blocks || []).map((block, index) => {
    const key = `${block.type}-${index}`;
    if (block.type === 'decision') return <DecisionBlock key={key} block={block} onPrompt={onPrompt}/>;
    if (block.type === 'checklist') return <ChecklistBlock key={key} block={block} onPrompt={onPrompt}/>;
    if (block.type === 'insights') return <InsightsBlock key={key} block={block} onPrompt={onPrompt}/>;
    if (block.type === 'metrics') return <MetricsBlock key={key} block={block} onPrompt={onPrompt}/>;
    if (block.type === 'files') return <FilesBlock key={key} block={block} onOpenResource={onOpenResource}/>;
    if (block.type === 'steps') return <StepsBlock key={key} block={block} onPrompt={onPrompt}/>;
    return null;
  })}</>;
}
