import React, {useState} from 'react';
import {Icon} from '../lib/icons';
import {safeUrl} from '../lib/api';
import {checklistPrompt} from '../lib/responseModel.mjs';

function BlockHeader({block}) {
  if (!block.title && !block.summary) return null;
  return <header className="cv-mb-3"><strong className="cv-block cv-text-sm cv-font-semibold cv-text-[#edf7f5]">{block.title}</strong>{block.summary && <p className="cv-mb-0 cv-mt-1 cv-text-xs cv-leading-5 cv-text-[#819b97]">{block.summary}</p>}</header>;
}

function SummaryBlock({block}) {
  return <section className="cv-response-summary cv-mt-5 cv-border-l-2 cv-border-teal/60 cv-pl-4">
    <span className="cv-block cv-text-[10px] cv-font-semibold cv-text-teal">Resumo</span>
    <p className="cv-m-0 cv-mt-1 cv-text-sm cv-leading-6 cv-text-[#d9e7e4]">{block.text || block.summary || block.title}</p>
  </section>;
}

function EntityBlock({block}) {
  const items = Array.isArray(block.items) ? block.items.slice(0, 4) : [];
  return <section className="cv-response-block cv-mt-5 cv-rounded-xl cv-border cv-border-teal/20 cv-bg-teal/[.06] cv-p-4">
    <div className="cv-flex cv-items-start cv-justify-between cv-gap-3"><div><span className="cv-block cv-text-[10px] cv-font-semibold cv-uppercase cv-tracking-[.08em] cv-text-teal">Contexto identificado</span><strong className="cv-mt-1 cv-block cv-text-base cv-font-semibold cv-text-[#edf7f5]">{block.title || 'Entidade'}</strong></div><span className="cv-rounded-full cv-bg-teal/10 cv-px-2 cv-py-1 cv-text-[10px] cv-text-[#8bd7cc]">{block.label || 'Referência'}</span></div>
    {block.summary && <p className="cv-mb-0 cv-mt-2 cv-text-xs cv-leading-5 cv-text-[#a9bfbb]">{block.summary}</p>}
    {!!items.length && <dl className="cv-mb-0 cv-mt-3 cv-grid cv-gap-2 sm:cv-grid-cols-2">{items.map((item, index) => <div key={item.id || index} className="cv-border-t cv-border-white/[.07] cv-pt-2"><dt className="cv-text-[10px] cv-font-semibold cv-text-[#78918d]">{item.title || item.label || 'Informação'}</dt><dd className="cv-mb-0 cv-mt-0.5 cv-text-xs cv-leading-5 cv-text-[#d9e7e4]">{item.value || item.detail || item.text || '—'}</dd></div>)}</dl>}
  </section>;
}

function ActivityBlock({block}) {
  const state = block.state || block.status || 'completed';
  const marker = state === 'running' || state === 'active' ? 'cv-animate-pulse cv-bg-teal' : state === 'error' || state === 'failed' ? 'cv-bg-[#ff7d83]' : 'cv-bg-[#6f8884]';
  return <div className="cv-mt-4 cv-flex cv-items-center cv-gap-2 cv-text-xs cv-text-[#819b97]" role="status">
    <i className={`cv-h-1.5 cv-w-1.5 cv-flex-none cv-rounded-full ${marker}`}/>
    <span>{block.label || block.title || block.text}</span>
    {block.detail && <span className="cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-[#627b77]">{block.detail}</span>}
  </div>;
}

function SourcesBlock({block, onPrompt}) {
  const items = Array.isArray(block.items) ? block.items : block.resource ? [block.resource] : [];
  const [selected, setSelected] = useState([]);
  const [copied, setCopied] = useState(false);
  if (!items.length) return null;
  const visible = items.slice(0, 8);
  const selectedItems = visible.filter(item => selected.includes(item.id));
  const compiledText = JSON.stringify(selectedItems.map(item => ({
    source_id: item.id, title: item.title || 'Fonte', url: item.url || '',
    content: item.content || item.detail || '',
  }))).slice(0, 12000);
  const toggle = item => setSelected(current => current.includes(item.id) ? current.filter(id => id !== item.id) : [...current, item.id]);
  const compile = () => onPrompt?.('Compile os trechos selecionados em um texto limpo, indique o que é fato e o que é interpretação e me pergunte antes de adicionar ao projeto.', {type: 'web_sources', label: 'Fontes selecionadas', text: compiledText});
  const draft = () => onPrompt?.('Crie um rascunho editável a partir das fontes selecionadas. Organize um título e os parágrafos em texto fiel ao conteúdo, sem inventar informações.', {type: 'web_sources', label: 'Fontes para o rascunho', text: compiledText});
  const copy = async () => {
    try { await navigator.clipboard?.writeText(compiledText); setCopied(true); window.setTimeout(() => setCopied(false), 1600); } catch (_) {}
  };
  return <section className="cv-source-group cv-mt-5">
    <div className="cv-source-group__header">
      <div><strong>{block.title || 'Fontes consultadas'}</strong><span>{items.length} resultado{items.length === 1 ? '' : 's'} · selecione trechos para continuar</span></div>
      {selectedItems.length > 0 && <span className="cv-source-group__count">{selectedItems.length} selecionada{selectedItems.length === 1 ? '' : 's'}</span>}
    </div>
    <div className="cv-source-group__list">
      {visible.map((item, index) => {
        const href = safeUrl(item?.url);
        const active = selected.includes(item.id);
        let domain = '';
        try { domain = href ? new URL(href).hostname.replace(/^www\./, '') : ''; } catch (_) {}
        return <div key={item.id || index} className={`cv-source-result ${active ? 'is-selected' : ''}`}>
          <button type="button" className="cv-source-result__select" onClick={() => toggle(item)} aria-pressed={active}>
            <span className="cv-source-result__check" aria-hidden="true">{active ? '✓' : ''}</span>
            <span className="cv-source-result__select-label">{active ? 'Selecionada' : 'Selecionar'}</span>
          </button>
          <details className="cv-source-card">
            <summary>
              <span className="cv-source-result__favicon">{item.favicon ? <img src={safeUrl(item.favicon)} alt="" loading="lazy"/> : <span>{(domain || 'F').slice(0, 1).toUpperCase()}</span>}</span>
              <span className="cv-source-result__copy"><b>{item.title || item.name || item.label || 'Fonte'}</b><small>{domain || item.kind || 'Fonte externa'}</small></span>
              <span className="cv-source-card__chevron" aria-hidden="true">⌄</span>
            </summary>
            <div className="cv-source-card__body">
              <p>{item.detail || 'Conteúdo selecionado para responder ao pedido atual.'}</p>
              {item.published_at && <small className="cv-source-card__date">Atualizado em {item.published_at}</small>}
              <footer className="cv-source-card__footer">
                <span>{active ? 'Incluída na seleção' : 'Fonte pública'}</span>
                {href && <a href={href} target="_blank" rel="noreferrer" className="cv-source-result__open" aria-label={`Abrir ${item.title || 'fonte'}`} title="Abrir fonte">Abrir fonte <Icon name="external" size={12}/></a>}
              </footer>
            </div>
          </details>
        </div>;
      })}
    </div>
    {selectedItems.length > 0 && <div className="cv-source-group__actions"><button type="button" onClick={draft} className="is-primary">Criar rascunho</button><button type="button" onClick={compile}>Compilar no chat</button><button type="button" onClick={copy}>{copied ? 'Copiado' : 'Copiar texto'}</button></div>}
  </section>;
}

function NoteBlock({block, tone = 'neutral'}) {
  const colors = tone === 'warning' ? 'cv-border-[#ff7d83]/35 cv-text-[#e8c4c6]' : 'cv-border-white/[.08] cv-text-[#a9bfbb]';
  return <aside className={`cv-mt-5 cv-border-l-2 cv-pl-3 cv-text-xs cv-leading-5 ${colors}`}>
    <strong className="cv-block cv-font-semibold">{block.title || (tone === 'warning' ? 'Atenção' : 'Premissa')}</strong>
    <span className="cv-mt-0.5 cv-block">{block.text || block.detail || block.summary}</span>
  </aside>;
}

function QuestionsBlock({block, onPrompt}) {
  const items = Array.isArray(block.items) ? block.items : [];
  return <section className="cv-mt-5">
    <span className="cv-block cv-text-[10px] cv-font-semibold cv-text-[#819b97]">{block.title || 'Próximas decisões'}</span>
    <div className="cv-mt-1 cv-grid cv-gap-0.5">{items.slice(0, 4).map((item, index) => {
      const label = typeof item === 'string' ? item : item.title || item.label || item.question;
      const prompt = typeof item === 'string' ? item : item.prompt || label;
      return <button key={item.id || index} type="button" onClick={() => onPrompt(prompt)} className="cv-flex cv-items-start cv-gap-2 cv-border-0 cv-bg-transparent cv-px-0 cv-py-1.5 cv-text-left cv-text-sm cv-text-[#c0d1ce] hover:cv-text-white"><span className="cv-text-teal">→</span><span>{label}</span></button>;
    })}</div>
  </section>;
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

function ImagesBlock({block}) {
  return <section className="cv-response-block cv-mt-5"><BlockHeader block={block}/><div className="cv-grid cv-grid-cols-1 cv-gap-3 sm:cv-grid-cols-2 lg:cv-grid-cols-3">{(block.items || []).map(item => { const image = safeUrl(item.url); const source = safeUrl(item.source_url); return image ? <figure key={item.id} className="cv-m-0 cv-overflow-hidden cv-rounded-xl cv-border cv-border-white/[.08] cv-bg-white/[.03]"><img src={image} alt={item.title || 'Imagem relacionada'} loading="lazy" className="cv-aspect-[4/3] cv-w-full cv-object-cover"/><figcaption className="cv-p-2"><strong className="cv-block cv-truncate cv-text-xs">{item.title}</strong>{source && <a href={source} target="_blank" rel="noreferrer" className="cv-mt-1 cv-block cv-text-[10px] cv-text-teal">Ver fonte</a>}</figcaption></figure> : null; })}</div></section>;
}

function StepsBlock({block, onPrompt}) {
  return <section className="cv-response-block cv-mt-5"><BlockHeader block={block}/><ol className="cv-m-0 cv-list-none cv-p-0">{block.items.map((item, index) => <li key={item.id} className="cv-relative cv-flex cv-gap-3 cv-pb-4 last:cv-pb-0">{index < block.items.length - 1 && <i className="cv-absolute cv-left-[7px] cv-top-5 cv-h-[calc(100%-16px)] cv-w-px cv-bg-white/10"/>}<span className={`cv-mt-1 cv-h-4 cv-w-4 cv-flex-none cv-rounded-full cv-border-2 ${item.state === 'done' ? 'cv-border-teal cv-bg-teal' : item.state === 'active' ? 'cv-animate-pulse cv-border-teal' : item.state === 'blocked' ? 'cv-border-[#ff7d83]' : 'cv-border-white/20'}`}/><span className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-sm cv-font-medium">{item.title}</strong>{item.detail && <small className="cv-mt-1 cv-block cv-text-xs cv-leading-5 cv-text-[#819b97]">{item.detail}</small>}{item.prompt && item.state !== 'done' && <button type="button" onClick={() => onPrompt(item.prompt)} className="cv-mt-2 cv-border-0 cv-bg-transparent cv-p-0 cv-text-[10px] cv-font-semibold cv-text-teal">Continuar esta etapa</button>}</span></li>)}</ol></section>;
}

export function ResponseBlocks({blocks, onPrompt, onOpenResource}) {
  return <>{(blocks || []).map((block, index) => {
    const key = `${block.type}-${index}`;
    if (block.type === 'summary') return <SummaryBlock key={key} block={block}/>;
    if (block.type === 'entity') return <EntityBlock key={key} block={block}/>;
    if (block.type === 'activity' || block.type === 'progress') return <ActivityBlock key={key} block={block}/>;
    if (block.type === 'source' || block.type === 'sources' || block.type === 'source_group') return <SourcesBlock key={key} block={block} onPrompt={onPrompt}/>;
    if (block.type === 'assumption') return <NoteBlock key={key} block={block}/>;
    if (block.type === 'warning' || block.type === 'error') return <NoteBlock key={key} block={block} tone="warning"/>;
    if (block.type === 'question' || block.type === 'questions') return <QuestionsBlock key={key} block={block} onPrompt={onPrompt}/>;
    if (block.type === 'decision') return <DecisionBlock key={key} block={block} onPrompt={onPrompt}/>;
    if (block.type === 'checklist') return <ChecklistBlock key={key} block={block} onPrompt={onPrompt}/>;
    if (block.type === 'insights') return <InsightsBlock key={key} block={block} onPrompt={onPrompt}/>;
    if (block.type === 'metrics') return <MetricsBlock key={key} block={block} onPrompt={onPrompt}/>;
    if (block.type === 'files') return <FilesBlock key={key} block={block} onOpenResource={onOpenResource}/>;
    if (block.type === 'images') return <ImagesBlock key={key} block={block}/>;
    if (block.type === 'steps') return <StepsBlock key={key} block={block} onPrompt={onPrompt}/>;
    return null;
  })}</>;
}
