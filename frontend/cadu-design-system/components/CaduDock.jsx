import React, {useCallback, useState} from 'react';
import {VisualIdentity} from './VisualIdentity';

export function DockDropZone({children, onDropItem, label = 'Fixar na dock'}) {
  const [active, setActive] = useState(false);
  const drop = useCallback(event => {
    event.preventDefault(); setActive(false);
    const raw = event.dataTransfer.getData('application/x-cadu-item');
    if (!raw) return;
    try { onDropItem?.(JSON.parse(raw)); } catch (_) { /* Ignore data from another application. */ }
  }, [onDropItem]);
  return <div className={`cadu-ds-dock-drop ${active ? 'is-active' : ''}`} onDragEnter={() => setActive(true)} onDragLeave={() => setActive(false)} onDragOver={event => event.preventDefault()} onDrop={drop} aria-label={label}>{children}</div>;
}

export function DockBrandShortcut({brand, projectCount = 0, active = false, onOpen, onDragStart, onDropShortcut}) {
  return <button type="button" draggable onDragStart={event => onDragStart?.(event, brand)} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); event.stopPropagation(); onDropShortcut?.(event, brand); }} onClick={() => onOpen?.(brand)} aria-label={`Abrir marca ${brand.name}`} data-tooltip={brand.name} className={`cadu-ds-dock-brand ${active ? 'is-active' : ''}`}>
    <VisualIdentity src={brand.logoUrl} initials={brand.visualInitials} label={brand.name} color={brand.visualColor}/>
    {projectCount > 1 && <i aria-label={`${projectCount} projetos fixados`}>{projectCount}</i>}
  </button>;
}

export function DockResourceShortcut({item, pinned = false, onOpen, onDragStart, onDropShortcut}) {
  return <button type="button" draggable onDragStart={event => onDragStart?.(event, item)} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); event.stopPropagation(); onDropShortcut?.(event, item); }} onClick={() => onOpen?.(item)} aria-label={`Abrir ${item.title}`} data-tooltip={item.title} className="cadu-ds-dock-resource">
    <VisualIdentity src={item.previewUrl} initials={item.visualInitials} label={item.title} color={item.visualColor}/>{pinned && <i aria-label="Fixado">●</i>}
  </button>;
}

export function DockUsageRing({percent, onOpen}) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  return <button type="button" className="cadu-ds-usage-ring" style={{'--cadu-usage': `${value * 3.6}deg`}} onClick={onOpen} data-tooltip="Créditos e consumo" aria-label={`Utilização de créditos: ${value}%`}><span>{value}%</span></button>;
}

export function CaduDock({onNewConversation, brands = [], resources = [], shortcutItems = [], usagePercent, userAvatar, userInitials = 'C', onOpenBrand, onOpenResource, onDropItem, onReorderShortcuts, onOpenUsage}) {
  const writePayload = (event, payload) => { event.dataTransfer.effectAllowed = 'copy'; event.dataTransfer.setData('application/x-cadu-item', JSON.stringify(payload)); };
  const items = shortcutItems.length ? shortcutItems : [...brands, ...resources];
  const dockBrands = items.filter(item => item.kind === 'brand');
  const dockResources = items.filter(item => item.kind !== 'brand');
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
    <button type="button" className="cadu-ds-dock-new" onClick={onNewConversation} aria-label="Nova conversa" data-tooltip="Nova conversa">+</button>
    <div className="cadu-ds-dock-context" aria-label="Marcas e projetos fixados"><DockDropZone onDropItem={onDropItem}>{dockBrands.slice(0, 6).map(item => <DockBrandShortcut key={item.shortcutId || item.id} brand={item} projectCount={item.projectCount} active={item.active} onOpen={onOpenBrand} onDragStart={writePayload} onDropShortcut={reorder}/>)}</DockDropZone>
      <div className="cadu-ds-dock-resources">{dockResources.slice(0, 6).map(item => <DockResourceShortcut key={item.shortcutId || item.id} item={item} pinned={item.pinned} onOpen={onOpenResource} onDragStart={writePayload} onDropShortcut={reorder}/>)}</div></div>
    <div className="cadu-ds-dock-bottom"><DockUsageRing percent={usagePercent} onOpen={onOpenUsage}/><button type="button" className="cadu-ds-dock-avatar-button" onClick={onOpenUsage} aria-label="Abrir conta" data-tooltip="Conta e perfil">{userAvatar ? <img className="cadu-ds-dock-avatar" src={userAvatar} alt=""/> : <span className="cadu-ds-dock-avatar cadu-ds-dock-avatar--fallback">{userInitials}</span>}</button></div>
  </aside>;
}
