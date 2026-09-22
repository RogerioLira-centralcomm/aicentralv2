import React, {useState} from 'react';
import {Icon} from '../lib/icons';
import {safeUrl} from '../lib/api';
import {checklistPrompt} from '../lib/responseModel.mjs';

function BlockHeader({block}) {
  if (!block.title && !block.summary) return null;
  return <header className="cv-mb-3"><strong className="cv-block cv-text-sm cv-font-semibold cv-text-[#edf7f5]">{block.title}</strong>{block.summary && <p className="cv-mb-0 cv-mt-1 cv-text-xs cv-leading-5 cv-text-[#819b97]">{block.summary}</p>}</header>;
}

const MAX_VISIBLE_ITEMS = 4;

function BoundedItems({items, children, label = 'itens'}) {
  const [expanded, setExpanded] = useState(false);
  const all = Array.isArray(items) ? items : [];
  const visible = expanded ? all : all.slice(0, MAX_VISIBLE_ITEMS);
  const remaining = all.length - visible.length;
  return <>
    {children(visible)}
    {all.length > MAX_VISIBLE_ITEMS && <button type="button" onClick={() => setExpanded(value => !value)} className="cv-mt-2 cv-border-0 cv-bg-transparent cv-p-0 cv-text-xs cv-font-semibold cv-text-[#65d8cb] hover:cv-text-white" aria-expanded={expanded}>
      {expanded ? 'Mostrar menos' : `Ver mais ${remaining} ${remaining === 1 ? label.slice(0, -1) : label}`}
    </button>}
  </>;
}

function SummaryBlock({block}) {
  return <section className="cv-response-summary cv-mt-5">
    <span className="cv-block cv-text-[10px] cv-font-semibold cv-text-teal">Resumo</span>
    <p className="cv-m-0 cv-mt-1 cv-text-sm cv-leading-6 cv-text-[#d9e7e4]">{block.text || block.summary || block.title}</p>
  </section>;
}

function EntityBlock({block}) {
  const items = Array.isArray(block.items) ? block.items : [];
  return <section className="cv-response-block cv-mt-5 cv-rounded-xl cv-border cv-border-teal/20 cv-bg-teal/[.06] cv-p-4">
    <div className="cv-flex cv-items-start cv-justify-between cv-gap-3"><div><span className="cv-block cv-text-[10px] cv-font-semibold cv-uppercase cv-tracking-[.08em] cv-text-teal">Contexto identificado</span><strong className="cv-mt-1 cv-block cv-text-base cv-font-semibold cv-text-[#edf7f5]">{block.title || 'Entidade'}</strong></div><span className="cv-rounded-full cv-bg-teal/10 cv-px-2 cv-py-1 cv-text-[10px] cv-text-[#8bd7cc]">{block.label || 'Referência'}</span></div>
    {block.summary && <p className="cv-mb-0 cv-mt-2 cv-text-xs cv-leading-5 cv-text-[#a9bfbb]">{block.summary}</p>}
    {!!items.length && <div className="cv-mt-3 cv-grid cv-gap-2 sm:cv-grid-cols-2"><BoundedItems items={items}>{visible => visible.map((item, index) => <div key={item.id || index} className="cv-border-t cv-border-white/[.07] cv-pt-2"><strong className="cv-block cv-text-[10px] cv-font-semibold cv-text-[#78918d]">{item.title || item.label || 'Informação'}</strong><span className="cv-mt-0.5 cv-block cv-text-xs cv-leading-5 cv-text-[#d9e7e4]">{item.value || item.detail || item.text || '—'}</span></div>)}</BoundedItems></div>}
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

function SourceFavicon({src, domain}) {
  const [failed, setFailed] = useState(false);
  const initial = (domain || 'F').slice(0, 1).toUpperCase();
  return <span className="cv-source-result__favicon">{src && !failed
    ? <img src={safeUrl(src)} alt="" loading="lazy" onError={() => setFailed(true)}/>
    : <span aria-hidden="true">{initial}</span>}</span>;
}

function sourceFailure(item) {
  const detail = String(item?.detail || item?.content || '');
  return ['failed', 'blocked', 'unavailable'].includes(String(item?.read_status || '').toLowerCase())
    || /\b(?:error|erro)\s*(?:40[0134]|429|5\d\d)|bad request|cannot process the request|access denied|unauthorized/i.test(detail);
}

function sourceDomain(item) {
  const href = safeUrl(item?.url);
  try { return href ? new URL(href).hostname.replace(/^www\./, '') : ''; } catch (_) { return ''; }
}

function SourcesBlock({block, onPrompt, onOpenResource}) {
  const items = Array.isArray(block.items) ? block.items : block.resource ? [block.resource] : [];
  const usableItems = items.filter(item => !sourceFailure(item));
  const recommendedIds = usableItems.filter(item => {
    const domain = sourceDomain(item);
    return /(^|\.)gov\.br$|(^|\.)edu\.br$|unidas\.com\.br$/i.test(domain);
  }).slice(0, 3).map(item => item.id);
  const [selected, setSelected] = useState(recommendedIds);
  const [copied, setCopied] = useState(false);
  if (!items.length) return null;
  const selectedItems = usableItems.filter(item => selected.includes(item.id));
  const compiledText = JSON.stringify(selectedItems.slice(0, 8).map(item => ({
    source_id: item.id, title: item.title || 'Fonte', url: item.url || '',
    content: String(item.content || item.detail || '').slice(0, 1200),
  })));
  const toggle = item => setSelected(current => current.includes(item.id) ? current.filter(id => id !== item.id) : [...current, item.id]);
  const selectRecommended = () => setSelected(recommendedIds);
  const compile = () => onPrompt?.('Responda ao pedido original usando as fontes selecionadas. Organize a resposta em fatos comprovados, linha do tempo quando fizer sentido e lacunas; não invente informações.', {type: 'web_sources', label: 'Fontes selecionadas', text: compiledText});
  const draft = () => onPrompt?.('Crie um rascunho editável a partir das fontes selecionadas. Organize um título e os parágrafos em texto fiel ao conteúdo, sem inventar informações.', {type: 'web_sources', label: 'Fontes para o rascunho', text: compiledText});
  const copy = async () => {
    const readable = selectedItems.map(item => [item.title || 'Fonte', item.url, item.content || item.detail].filter(Boolean).join('\n')).join('\n\n');
    try { await navigator.clipboard?.writeText(readable); setCopied(true); window.setTimeout(() => setCopied(false), 1600); } catch (_) {}
  };
  return <section className="cv-source-group cv-mt-5">
    <div className="cv-source-group__header">
      <div><strong>{block.title || 'Fontes consultadas'}</strong><span>{items.length} resultado{items.length === 1 ? '' : 's'} · priorize fontes oficiais e institucionais</span></div>
      {selectedItems.length > 0 && <span className="cv-source-group__count">{selectedItems.length} selecionada{selectedItems.length === 1 ? '' : 's'}</span>}
    </div>
    <div className="cv-source-group__guide"><span>{recommendedIds.length ? 'Comece pelas fontes oficiais identificadas e revise a seleção antes de continuar.' : 'Nenhuma fonte oficial foi identificada automaticamente. Escolha manualmente as referências úteis.'}</span>{recommendedIds.length > 0 && <button type="button" onClick={selectRecommended}>Selecionar oficiais</button>}</div>
    <div className="cv-source-group__list">
      <BoundedItems items={items} label="fontes">{visible => visible.map((item, index) => {
        const href = safeUrl(item?.url);
        const unavailable = sourceFailure(item);
        const active = !unavailable && selected.includes(item.id);
        const domain = sourceDomain(item);
        return <div key={item.id || index} className={`cv-source-result ${active ? 'is-selected' : ''} ${unavailable ? 'is-unavailable' : ''}`}>
          <details className="cv-source-card">
            <summary>
              <button type="button" disabled={unavailable} className="cv-source-result__select" onClick={event => { event.preventDefault(); event.stopPropagation(); toggle(item); }} aria-pressed={active}>
                <span className="cv-source-result__check" aria-hidden="true">{active ? '✓' : ''}</span>
                <span className="cv-source-result__select-label">{active ? 'Selecionada' : 'Selecionar'}</span>
              </button>
              <SourceFavicon src={item.favicon} domain={domain}/>
              <span className="cv-source-result__copy"><b>{item.title || item.name || item.label || 'Fonte'}</b><small>{domain || item.kind || 'Fonte externa'}</small></span>
              {unavailable && <span className="cv-source-result__status">Leitura indisponível</span>}
              <span className="cv-source-card__chevron" aria-hidden="true">⌄</span>
            </summary>
            <div className="cv-source-card__body">
              <p>{unavailable ? 'O site não permitiu a leitura automática. Você ainda pode abrir o endereço original.' : item.detail || 'Conteúdo disponível para apoiar a próxima resposta.'}</p>
              {item.published_at && <small className="cv-source-card__date">Atualizado em {item.published_at}</small>}
              <footer className="cv-source-card__footer">
                <span>{unavailable ? 'Não incluída' : active ? 'Incluída na seleção' : 'Fonte pública'}</span>
                {href && <button type="button" onClick={() => onOpenResource?.({...item, url: href, kind: 'Link público'})} className="cv-source-result__open" aria-label={`Abrir ${item.title || 'fonte'} no leitor`}>Abrir no leitor <Icon name="external" size={12}/></button>}
              </footer>
            </div>
          </details>
        </div>;
      })}</BoundedItems>
    </div>
    {selectedItems.length > 0 && <div className="cv-source-group__actions"><button type="button" onClick={compile} className="is-primary">Continuar com {selectedItems.length} fonte{selectedItems.length === 1 ? '' : 's'}</button><button type="button" onClick={draft}>Criar rascunho</button><button type="button" onClick={copy}>{copied ? 'Copiado' : 'Copiar referências'}</button></div>}
  </section>;
}

function NoteBlock({block, tone = 'neutral'}) {
  const colors = tone === 'warning' ? 'cv-note-block--warning cv-text-[#e8c4c6]' : 'cv-note-block--neutral cv-text-[#a9bfbb]';
  return <aside className={`cv-note-block cv-mt-5 cv-text-xs cv-leading-5 ${colors}`}>
    <strong className="cv-block cv-font-semibold">{block.title || (tone === 'warning' ? 'Atenção' : 'Premissa')}</strong>
    <span className="cv-mt-0.5 cv-block">{block.text || block.detail || block.summary}</span>
  </aside>;
}

function QuestionsBlock({block, onPrompt}) {
  const items = Array.isArray(block.items) ? block.items : [];
  return <section className="cv-inline-questions cv-mt-6">
    <span className="cv-inline-questions__label">{block.title || 'Para continuar'}</span>
    <div><BoundedItems items={items} label="perguntas">{visible => visible.map((item, index) => {
      const label = typeof item === 'string' ? item : item.title || item.label || item.question;
      const contextText = typeof item === 'string' ? item : item.prompt || item.question || label;
      return <button key={item.id || index} type="button" onClick={() => onPrompt('', {type: 'question', label: 'Respondendo', text: contextText})} className="cv-inline-question"><span>{label}</span><small>Responder</small></button>;
    })}</BoundedItems></div>
  </section>;
}

function DecisionBlock({block, onPrompt}) {
  const recommended = block.items.find(item => item.recommended);
  const [selected, setSelected] = useState(recommended?.id || '');
  const choice = block.items.find(item => item.id === selected);
  return <section className="cv-inline-decision cv-mt-6">
    <BlockHeader block={block}/>
    <div className="cv-inline-decision__options"><BoundedItems items={block.items} label="opções">{visible => visible.map(item => <button key={item.id} type="button" onClick={() => setSelected(item.id)} aria-pressed={selected === item.id} className="cv-inline-decision__option">
      <span className={`cv-mt-1 cv-grid cv-h-4 cv-w-4 cv-flex-none cv-place-items-center cv-rounded-full cv-border ${selected === item.id ? 'cv-border-teal cv-bg-teal' : 'cv-border-white/25'}`}>{selected === item.id && <i className="cv-h-1.5 cv-w-1.5 cv-rounded-full cv-bg-[#06211e]"/>}</span>
      <span className="cv-min-w-0 cv-flex-1"><strong className="cv-flex cv-items-center cv-gap-2 cv-text-sm cv-font-medium">{item.title}{item.recommended && <small className="cv-rounded-full cv-bg-teal/10 cv-px-2 cv-py-0.5 cv-text-[10px] cv-font-semibold cv-text-[#65d8cb]">Recomendada</small>}</strong>{item.detail && <small className="cv-mt-1 cv-block cv-text-xs cv-leading-5 cv-text-[#8ba39f]">{item.detail}</small>}</span>
    </button>)}</BoundedItems></div>
    {choice && <button type="button" onClick={() => onPrompt(choice.prompt || `Use a opção “${choice.title}” e continue o trabalho.`)} className="cv-inline-decision__continue">Continuar com {choice.title}</button>}
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
    <div className="cv-grid cv-gap-2"><BoundedItems items={block.items} label="itens">{visible => visible.map(item => { const chosen = checked.has(item.id); const done = item.state === 'done'; return <button key={item.id} type="button" aria-pressed={chosen} onClick={() => toggle(item.id)} className={`cv-checklist-row cv-flex cv-w-full cv-items-start cv-gap-3 cv-rounded-xl cv-border-0 cv-px-3 cv-py-3 cv-text-left ${chosen ? 'cv-bg-white/[.045]' : 'cv-bg-transparent hover:cv-bg-white/[.025]'}`}>
      <span className={`cv-mt-0.5 cv-grid cv-h-5 cv-w-5 cv-flex-none cv-place-items-center cv-rounded-full cv-border ${done ? 'cv-border-teal/70 cv-bg-teal/15 cv-text-teal' : item.state === 'blocked' ? 'cv-border-[#ff7d83]/60 cv-text-[#ff9ca1]' : 'cv-border-white/20 cv-text-transparent'}`}>{done ? <Icon name="check" size={12}/> : item.state === 'blocked' ? '!' : '•'}</span>
      <span className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-sm cv-font-medium cv-text-[#e4efed]">{item.title}</strong>{item.detail && <small className="cv-mt-1 cv-block cv-text-xs cv-leading-5 cv-text-[#819b97]">{item.detail}</small>}</span>
      {chosen && <span className="cv-mt-1 cv-text-[10px] cv-font-semibold cv-text-teal">Selecionado</span>}
    </button>; })}</BoundedItems></div>
    {!!selected.length && <button type="button" onClick={() => onPrompt(checklistPrompt(selected))} className="cv-mt-3 cv-rounded-lg cv-border cv-border-white/10 cv-bg-transparent cv-px-3.5 cv-py-2.5 cv-text-xs cv-font-semibold hover:cv-bg-white/[.04]">Continuar com {selected.length === 1 ? 'este item' : `${selected.length} itens`}</button>}
  </section>;
}

function InsightsBlock({block, onPrompt}) {
  return <section className="cv-response-block cv-response-points cv-mt-5"><BlockHeader block={block}/><div className="cv-grid"><BoundedItems items={block.items} label="pontos">{visible => visible.map((item, index) => {
    const content = <><span className="cv-response-point__marker" aria-hidden="true"/><span className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-sm cv-font-medium">{item.title}</strong>{item.detail && <small className="cv-mt-1 cv-block cv-text-xs cv-leading-5 cv-text-[#819b97]">{item.detail}</small>}</span>{item.prompt && <span className="cv-response-point__action">Explorar</span>}</>;
    return item.prompt
      ? <button key={item.id || index} type="button" onClick={() => onPrompt(item.prompt)} className="cv-response-point is-actionable">{content}</button>
      : <div key={item.id || index} className="cv-response-point">{content}</div>;
  })}</BoundedItems></div></section>;
}

function MetricsBlock({block, onPrompt}) {
  return <section className="cv-response-block cv-metrics-block cv-mt-5"><BlockHeader block={block}/><div className="cv-grid cv-grid-cols-2 cv-gap-x-6 cv-gap-y-4 sm:cv-grid-cols-3"><BoundedItems items={block.items} label="métricas">{visible => visible.map(item => { const body = <><strong className="cv-block cv-text-xl cv-font-semibold cv-tracking-[-.03em] cv-text-[#edf7f5]">{item.value || '—'}</strong><span className="cv-mt-1 cv-block cv-text-xs cv-text-[#819b97]">{item.title}</span>{item.detail && <small className="cv-mt-1 cv-block cv-text-[10px] cv-leading-4 cv-text-[#657f7b]">{item.detail}</small>}</>; return item.prompt ? <button key={item.id} type="button" onClick={() => onPrompt(item.prompt)} className="cv-metric-item cv-border-0 cv-bg-transparent cv-p-0 cv-text-left">{body}<small className="cv-mt-2 cv-block cv-text-[10px] cv-font-semibold cv-text-teal">Analisar</small></button> : <div key={item.id} className="cv-metric-item">{body}{safeUrl(item.url) && <a href={safeUrl(item.url)} target="_blank" rel="noreferrer" className="cv-mt-2 cv-block cv-text-[10px] cv-font-semibold cv-text-teal cv-no-underline">Ver fonte</a>}</div>; })}</BoundedItems></div></section>;
}

function FilesBlock({block, onOpenResource}) {
  return <section className="cv-response-block cv-files-block cv-mt-5"><BlockHeader block={block}/><div className="cv-grid cv-gap-2"><BoundedItems items={block.items} label="arquivos">{visible => visible.map(item => <button key={item.id} type="button" onClick={() => onOpenResource?.(item)} className="cv-file-row cv-flex cv-w-full cv-items-center cv-gap-3 cv-rounded-xl cv-border-0 cv-bg-transparent cv-p-2 cv-text-left"><span className="cv-grid cv-h-9 cv-w-9 cv-flex-none cv-place-items-center cv-rounded-lg cv-bg-white/[.05] cv-text-[#79b9b1]"><Icon name="file" size={16}/></span><span className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-sm cv-font-medium">{item.title}</strong><small className="cv-mt-0.5 cv-block cv-text-[11px] cv-text-[#78918d]">{item.kind || 'Arquivo'}{item.detail ? ` · ${item.detail}` : ''}</small></span><span className="cv-text-[10px] cv-font-semibold cv-text-teal">Abrir</span></button>)}</BoundedItems></div></section>;
}

function ImagesBlock({block}) {
  return <section className="cv-response-block cv-mt-5"><BlockHeader block={block}/><div className="cv-grid cv-grid-cols-1 cv-gap-3 sm:cv-grid-cols-2 lg:cv-grid-cols-3"><BoundedItems items={block.items || []} label="imagens">{visible => visible.map(item => { const image = safeUrl(item.url); const source = safeUrl(item.source_url); return image ? <figure key={item.id} className="cv-m-0 cv-overflow-hidden cv-rounded-xl cv-border cv-border-white/[.08] cv-bg-white/[.03]"><img src={image} alt={item.title || 'Imagem relacionada'} loading="lazy" className="cv-aspect-[4/3] cv-w-full cv-object-cover"/><figcaption className="cv-p-2"><strong className="cv-block cv-truncate cv-text-xs">{item.title}</strong>{source && <a href={source} target="_blank" rel="noreferrer" className="cv-mt-1 cv-block cv-text-[10px] cv-text-teal">Ver fonte</a>}</figcaption></figure> : null; })}</BoundedItems></div></section>;
}

function StepsBlock({block, onPrompt}) {
  return <section className="cv-response-block cv-mt-5"><BlockHeader block={block}/><ol className="cv-m-0 cv-list-none cv-p-0"><BoundedItems items={block.items} label="etapas">{visible => visible.map((item, index) => <li key={item.id} className="cv-relative cv-flex cv-gap-3 cv-pb-4 last:cv-pb-0">{index < visible.length - 1 && <i className="cv-absolute cv-left-[7px] cv-top-5 cv-h-[calc(100%-16px)] cv-w-px cv-bg-white/10"/>}<span className={`cv-mt-1 cv-h-4 cv-w-4 cv-flex-none cv-rounded-full cv-border-2 ${item.state === 'done' ? 'cv-border-teal cv-bg-teal' : item.state === 'active' ? 'cv-animate-pulse cv-border-teal' : item.state === 'blocked' ? 'cv-border-[#ff7d83]' : 'cv-border-white/20'}`}/><span className="cv-min-w-0 cv-flex-1"><strong className="cv-block cv-text-sm cv-font-medium">{item.title}</strong>{item.detail && <small className="cv-mt-1 cv-block cv-text-xs cv-leading-5 cv-text-[#819b97]">{item.detail}</small>}{item.prompt && item.state !== 'done' && <button type="button" onClick={() => onPrompt(item.prompt)} className="cv-mt-2 cv-border-0 cv-bg-transparent cv-p-0 cv-text-[10px] cv-font-semibold cv-text-teal">Continuar esta etapa</button>}</span></li>)}</BoundedItems></ol></section>;
}

export function ResponseBlocks({blocks, onPrompt, onOpenResource}) {
  return <>{(blocks || []).map((block, index) => {
    const key = `${block.type}-${index}`;
    if (block.type === 'summary') return <SummaryBlock key={key} block={block}/>;
    if (block.type === 'entity') return <EntityBlock key={key} block={block}/>;
    if (block.type === 'activity' || block.type === 'progress') return <ActivityBlock key={key} block={block}/>;
    if (block.type === 'source' || block.type === 'sources' || block.type === 'source_group') return <SourcesBlock key={key} block={block} onPrompt={onPrompt} onOpenResource={onOpenResource}/>;
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
