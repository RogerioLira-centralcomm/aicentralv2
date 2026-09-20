import React, {useCallback, useEffect, useId, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {VisualIdentity} from './VisualIdentity';
import {Icon} from './Icon';

function DockTooltip({label, children}) {
  const anchorRef = useRef(null);
  const tooltipId = useId();
  const [position, setPosition] = useState(null);

  const updatePosition = useCallback(() => {
    const rect = anchorRef.current?.getBoundingClientRect();
    if (!rect) return;
    // The dock is a compact vertical shelf. Its label belongs above the item,
    // not beside it where it competes with the workspace content.
    setPosition({left: Math.round(rect.left + rect.width / 2), top: Math.round(rect.top - 9)});
  }, []);
  const open = event => {
    children.props.onPointerEnter?.(event);
    updatePosition();
  };
  const close = event => {
    children.props.onPointerLeave?.(event);
    setPosition(null);
  };
  const focus = event => {
    children.props.onFocus?.(event);
    updatePosition();
  };
  const blur = event => {
    children.props.onBlur?.(event);
    setPosition(null);
  };

  useEffect(() => {
    if (!position) return undefined;
    const dismiss = () => setPosition(null);
    window.addEventListener('scroll', dismiss, true);
    window.addEventListener('resize', dismiss);
    return () => {
      window.removeEventListener('scroll', dismiss, true);
      window.removeEventListener('resize', dismiss);
    };
  }, [position]);

  return <>{React.cloneElement(children, {
    ref: anchorRef,
    'aria-describedby': position ? tooltipId : undefined,
    onPointerEnter: open,
    onPointerLeave: close,
    onFocus: focus,
    onBlur: blur,
  })}{position && createPortal(<span id={tooltipId} role="tooltip" className="cadu-ds-dock-tooltip" style={position}>{label}</span>, document.body)}</>;
}

export function DockDropZone({children, onDropItem, label = 'Fixar na dock'}) {
  const [active, setActive] = useState(false);
  const drop = useCallback(event => {
    event.preventDefault(); setActive(false);
    const raw = event.dataTransfer.getData('application/x-cadu-item');
    if (!raw) return;
    try { onDropItem?.(JSON.parse(raw)); } catch (_) { /* Ignore data from another application. */ }
  }, [onDropItem]);
  const enabled = typeof onDropItem === 'function';
  return <div className={`cadu-ds-dock-drop ${active ? 'is-active' : ''}`} onDragEnter={enabled ? () => setActive(true) : undefined} onDragLeave={enabled ? () => setActive(false) : undefined} onDragOver={enabled ? event => event.preventDefault() : undefined} onDrop={enabled ? drop : undefined} aria-label={enabled ? label : undefined}>{children}</div>;
}

export function DockBrandShortcut({brand, projectCount = 0, active = false, onOpen, onDragStart, onDropShortcut}) {
  const draggable = typeof onDragStart === 'function';
  const droppable = typeof onDropShortcut === 'function';
  return <DockTooltip label={brand.name}><button type="button" draggable={draggable} onDragStart={draggable ? event => onDragStart(event, brand) : undefined} onDragOver={droppable ? event => event.preventDefault() : undefined} onDrop={droppable ? event => { event.preventDefault(); event.stopPropagation(); onDropShortcut(event, brand); } : undefined} onClick={() => onOpen?.(brand)} aria-label={`Abrir marca ${brand.name}`} aria-current={active ? 'page' : undefined} className={`cadu-ds-dock-brand ${active ? 'is-active' : ''}`}>
    <VisualIdentity src={brand.logoUrl} initials={brand.visualInitials} label={brand.name} color={brand.visualColor}/>
    {projectCount > 1 && <i aria-label={`${projectCount} projetos fixados`}>{projectCount}</i>}
  </button></DockTooltip>;
}

export function DockResourceShortcut({item, pinned = false, active = false, onOpen, onDragStart, onDropShortcut}) {
  const draggable = typeof onDragStart === 'function';
  const droppable = typeof onDropShortcut === 'function';
  return <DockTooltip label={item.title}><button type="button" draggable={draggable} onDragStart={draggable ? event => onDragStart(event, item) : undefined} onDragOver={droppable ? event => event.preventDefault() : undefined} onDrop={droppable ? event => { event.preventDefault(); event.stopPropagation(); onDropShortcut(event, item); } : undefined} onClick={() => onOpen?.(item)} aria-label={`Abrir ${item.title}`} aria-current={active ? 'page' : undefined} className={`cadu-ds-dock-resource ${active ? 'is-active' : ''}`}>
    <VisualIdentity src={item.previewUrl} initials={item.visualInitials} label={item.title} color={item.visualColor}/>{pinned && <i aria-label="Fixado">●</i>}
  </button></DockTooltip>;
}

export function DockUsageRing({percent, onOpen}) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  const formatted = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1}).format(value);
  return <DockTooltip label="Créditos e consumo"><button type="button" className="cadu-ds-usage-ring" style={{'--cadu-usage': `${value * 3.6}deg`}} onClick={onOpen} aria-label={`Utilização de créditos: ${formatted}%`}><span>{formatted}%</span></button></DockTooltip>;
}

export function CaduDock({onNewConversation, brands = [], resources = [], shortcutItems = [], usagePercent, onOpenBrand, onOpenResource, onDropItem, onReorderShortcuts, onOpenUsage}) {
  const writePayload = (event, payload) => { event.dataTransfer.effectAllowed = 'copy'; event.dataTransfer.setData('application/x-cadu-item', JSON.stringify(payload)); };
  const items = shortcutItems.length ? shortcutItems : [...brands, ...resources];
  const dockBrands = items.filter(item => item.kind === 'brand');
  const dockResources = items.filter(item => item.kind !== 'brand');
  const canReorder = typeof onReorderShortcuts === 'function';
  const reorder = (event, target) => {
    const raw = event.dataTransfer.getData('application/x-cadu-item');
    try {
      const source = JSON.parse(raw);
      if (!source?.id || source.id === target.id) return;
      const next = [...items];
      const from = next.findIndex(item => item.shortcutId === source.shortcutId || item.id === source.id);
      const to = next.findIndex(item => item.shortcutId === target.shortcutId || item.id === target.id);
      if (from < 0 || to < 0) return;
      next.splice(to, 0, next.splice(from, 1)[0]);
      onReorderShortcuts?.(next);
    } catch (_) { /* The outer drop zone handles items originating elsewhere. */ }
  };
  return <aside className="cadu-ds-dock" aria-label="Atalhos do Workspace">
    <DockTooltip label="Novo chat"><button type="button" className="cadu-ds-dock-new" onClick={onNewConversation} aria-label="Novo chat"><Icon name="newChat" size={18}/></button></DockTooltip>
    <div className="cadu-ds-dock-context" aria-label="Marcas e projetos fixados"><DockDropZone onDropItem={onDropItem}>{dockBrands.map(item => <DockBrandShortcut key={item.shortcutId || item.id} brand={item} projectCount={item.projectCount} active={item.active} onOpen={onOpenBrand} onDragStart={canReorder ? writePayload : undefined} onDropShortcut={canReorder ? reorder : undefined}/>)}</DockDropZone>
      <div className="cadu-ds-dock-resources">{dockResources.map(item => <DockResourceShortcut key={item.shortcutId || item.id} item={item} pinned={item.pinned} active={item.active} onOpen={onOpenResource} onDragStart={canReorder ? writePayload : undefined} onDropShortcut={canReorder ? reorder : undefined}/>)}</div></div>
    <div className="cadu-ds-dock-bottom">{usagePercent != null && <DockUsageRing percent={usagePercent} onOpen={onOpenUsage}/>}</div>
  </aside>;
}
