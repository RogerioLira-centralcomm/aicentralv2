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

export function DockBrandShortcut({brand, projectCount = 0, active = false, onOpen, onDragStart}) {
  return <button type="button" draggable onDragStart={event => onDragStart?.(event, {type: 'brand', id: brand.id, brandRef: brand.id})} onClick={() => onOpen?.(brand)} aria-label={`Abrir marca ${brand.name}`} data-tooltip={brand.name} className={`cadu-ds-dock-brand ${active ? 'is-active' : ''}`}>
    <VisualIdentity src={brand.logoUrl} initials={brand.visualInitials} label={brand.name} color={brand.visualColor}/>
    {projectCount > 1 && <i aria-label={`${projectCount} projetos fixados`}>{projectCount}</i>}
  </button>;
}

export function DockResourceShortcut({item, pinned = false, onOpen, onDragStart}) {
  return <button type="button" draggable onDragStart={event => onDragStart?.(event, {type: item.kind, id: item.id, brandRef: item.brandRef, projectRef: item.projectRef})} onClick={() => onOpen?.(item)} aria-label={`Abrir ${item.title}`} data-tooltip={item.title} className="cadu-ds-dock-resource">
    <VisualIdentity src={item.previewUrl} initials={item.visualInitials} label={item.title} color={item.visualColor}/>{pinned && <i aria-label="Fixado">●</i>}
  </button>;
}

export function DockUsageRing({percent, onOpen}) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  return <button type="button" className="cadu-ds-usage-ring" style={{'--cadu-usage': `${value * 3.6}deg`}} onClick={onOpen} data-tooltip="Créditos e consumo" aria-label={`Utilização de créditos: ${value}%`}><span>{value}%</span></button>;
}

function OrganizeIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h14M5 12h14M5 18h14"/><circle cx="8" cy="6" r="1.6"/><circle cx="15" cy="12" r="1.6"/><circle cx="11" cy="18" r="1.6"/></svg>;
}

export function CaduDock({onNewConversation, onManageShortcuts, brands = [], resources = [], shortcutItems = [], usagePercent, userAvatar, userInitials = 'C', onOpenBrand, onOpenResource, onDropItem, onOpenUsage}) {
  const writePayload = (event, payload) => { event.dataTransfer.effectAllowed = 'copy'; event.dataTransfer.setData('application/x-cadu-item', JSON.stringify(payload)); };
  const items = shortcutItems.length ? shortcutItems : [...brands, ...resources];
  const dockBrands = items.filter(item => item.kind === 'brand');
  const dockResources = items.filter(item => item.kind !== 'brand');
  return <aside className="cadu-ds-dock" aria-label="Atalhos do Workspace">
    <button type="button" className="cadu-ds-dock-new" onClick={onNewConversation} aria-label="Nova conversa" data-tooltip="Nova conversa">+</button>
    <button type="button" className="cadu-ds-dock-organize" onClick={onManageShortcuts} aria-label="Organizar atalhos" data-tooltip="Organizar atalhos"><OrganizeIcon/></button>
    <div className="cadu-ds-dock-context" aria-label="Marcas e projetos fixados"><DockDropZone onDropItem={onDropItem}>{dockBrands.slice(0, 5).map(item => <DockBrandShortcut key={item.shortcutId || item.id} brand={item} projectCount={item.projectCount} active={item.active} onOpen={onOpenBrand} onDragStart={writePayload}/>)}</DockDropZone>
      <div className="cadu-ds-dock-resources">{dockResources.slice(0, 5).map(item => <DockResourceShortcut key={item.shortcutId || item.id} item={item} pinned={item.pinned} onOpen={onOpenResource} onDragStart={writePayload}/>)}</div></div>
    <div className="cadu-ds-dock-bottom"><DockUsageRing percent={usagePercent} onOpen={onOpenUsage}/><button type="button" className="cadu-ds-dock-avatar-button" onClick={onOpenUsage} aria-label="Abrir conta" data-tooltip="Conta e perfil">{userAvatar ? <img className="cadu-ds-dock-avatar" src={userAvatar} alt=""/> : <span className="cadu-ds-dock-avatar cadu-ds-dock-avatar--fallback">{userInitials}</span>}</button></div>
  </aside>;
}
