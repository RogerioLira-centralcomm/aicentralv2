import React, {useEffect, useState} from 'react';
import './WorkspaceEntityPortal.css';
import {Icon} from './Icon';

export function EntityNavigator({label, items = [], context, children, identity, activeId: controlledActiveId}) {
  const [observedActiveId, setObservedActiveId] = useState(() => items[0]?.target || items[0]?.id || '');
  const activeId = controlledActiveId || observedActiveId;
  useEffect(() => {
    if (controlledActiveId) return undefined;
    const sections = items.map(item => document.getElementById(item.target || item.id)).filter(Boolean);
    if (!sections.length || typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      if (visible[0]?.target?.id) setObservedActiveId(visible[0].target.id);
    }, {rootMargin: '-12% 0px -70% 0px', threshold: [0, .12, .35]});
    sections.forEach(section => observer.observe(section));
    return () => observer.disconnect();
  }, [items, controlledActiveId]);
  return <aside className="cadu-ds-entity-nav" aria-label={`Navegação de ${label}`}>
    {identity && <div className="cadu-ds-entity-nav__identity">{identity}</div>}
    {!identity && <span className="cadu-ds-entity-nav__label">{label}</span>}
    <nav>{items.map(item => { const target = item.target || item.id; const selected = activeId === item.id || activeId === target; return <a key={item.id} href={item.href || `#${target}`} className={selected ? 'is-active' : ''} aria-current={selected ? 'page' : undefined}><Icon name={item.icon || 'file'} size={14}/><span>{item.label}</span>{Number.isFinite(item.count) && item.count > 0 && <small>{item.count}</small>}</a>; })}</nav>
    {context && <div className="cadu-ds-entity-nav__context">{context}</div>}
    {children && <div className="cadu-ds-entity-nav__actions">{children}</div>}
  </aside>;
}

function RailGroup({title, items = [], onReorder, maxVisible, moreHref, moreLabel, prominent = false}) {
  const [expanded, setExpanded] = useState(false);
  const [draggedId, setDraggedId] = useState('');
  if (!items.length) return null;
  const limit = Number.isFinite(maxVisible) ? Math.max(0, maxVisible) : 5;
  const visible = maxVisible ? items.slice(0, limit) : expanded ? items : items.slice(0, limit);
  const move = (item, offset) => {
    const from = items.findIndex(candidate => String(candidate.id) === String(item.id));
    const to = Math.max(0, Math.min(items.length - 1, from + offset));
    if (from < 0 || from === to) return;
    const next = [...items]; next.splice(to, 0, next.splice(from, 1)[0]); onReorder?.(next);
  };
  const drop = target => {
    const from = items.findIndex(item => String(item.id) === draggedId);
    const to = items.findIndex(item => String(item.id) === String(target.id));
    if (from < 0 || to < 0 || from === to) return;
    const next = [...items]; next.splice(to, 0, next.splice(from, 1)[0]); setDraggedId(''); onReorder?.(next);
  };
  return <section className={`cadu-ds-entity-rail__group${prominent ? ' is-prominent' : ''}`}><header><h3>{title}</h3><span>{items.length}</span></header><div>{visible.map((item, index) => {
    const content = <>{item.previewUrl ? <img src={item.previewUrl} alt="" loading="lazy"/> : item.icon ? <Icon name={item.icon} size={15}/> : null}<span><b>{item.title || item.name || `Item ${index + 1}`}</b>{item.detail && <small>{item.detail}</small>}{item.origin && <em>{item.origin}</em>}</span>{item.href && <i aria-hidden="true">↗</i>}</>;
    const row = item.href ? <a href={item.href} target={item.external ? '_blank' : undefined} rel={item.external ? 'noreferrer' : undefined}>{content}</a> : <div>{content}</div>;
    return onReorder ? <article key={item.id || item.href || index} className={`cadu-ds-entity-rail__sortable${draggedId === String(item.id) ? ' is-dragging' : ''}`} draggable onDragStart={() => setDraggedId(String(item.id))} onDragEnd={() => setDraggedId('')} onDragOver={event => event.preventDefault()} onDrop={() => drop(item)}>{row}<span className="cadu-ds-entity-rail__order"><button type="button" disabled={index === 0} onClick={() => move(item,-1)} aria-label={`Mover ${item.title} para cima`}>↑</button><button type="button" disabled={index === items.length - 1} onClick={() => move(item,1)} aria-label={`Mover ${item.title} para baixo`}>↓</button></span></article> : React.cloneElement(row, {key:item.id || item.href || index, className:item.previewUrl ? 'has-preview' : ''});
  })}</div>{moreHref && items.length > limit ? <a className="cadu-ds-entity-rail__expand" href={moreHref}>{moreLabel || 'Ver todos'}</a> : !maxVisible && items.length > limit && <button type="button" className="cadu-ds-entity-rail__expand" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'Mostrar menos' : `Ver todos (${items.length})`}</button>}</section>;
}

export function EntityContextRail({title = 'Em destaque', action, groups = [], primaryGroup, children, className = ''}) {
  return <aside className={`cadu-ds-entity-rail ${className}`.trim()} aria-label={title}><header className="cadu-ds-entity-rail__header"><span>{title}</span>{action}</header>{primaryGroup && <RailGroup key={primaryGroup.title} {...primaryGroup}/>}{children}{groups.map(group => <RailGroup key={group.title} {...group}/>)}</aside>;
}

export function BrandCompletion({score = 0, missing = [], breakdown = [], processing = false, onAudit, onEdit}) {
  const normalized = Math.max(0, Math.min(100, Number(score) || 0));
  const ready = normalized >= 40;
  return <section className={`cadu-ds-brand-completion${ready ? ' is-ready' : ''}`} id="completar">
    <div className="cadu-ds-brand-completion__score"><strong>{normalized}%</strong><span>completude da base</span></div>
    <div className="cadu-ds-brand-completion__body"><span>{ready ? 'Cobertura consolidada' : 'Próximo ganho de qualidade'}</span><h2>{ready ? 'A marca já orienta projetos e criação' : 'Complete os sinais que ainda fazem diferença'}</h2><p>{missing.length ? `Priorize: ${missing.slice(0, 3).join(', ')}.` : 'A auditoria preserva as lacunas sem bloquear os dados comprovados.'}</p>{breakdown.length > 0 && <div className="cadu-ds-brand-completion__map" aria-label="Cobertura por dimensão">{breakdown.map(item => { const pct = Math.max(0, Math.min(100, Math.round((Number(item.score) || 0) * 100 / Math.max(1, Number(item.max) || 1)))); return <div key={item.id}><span><b>{item.label}</b><small>{item.score}/{item.max}</small></span><i><em style={{width:`${pct}%`}}/></i></div>; })}</div>}</div>
    <div className="cadu-ds-brand-completion__actions"><button type="button" className="is-primary" disabled={processing} onClick={onAudit}>{processing ? 'Análise em andamento' : ready ? 'Atualizar análise' : 'Executar análise completa'}</button><button type="button" onClick={onEdit}>Editar dados</button></div>
  </section>;
}
