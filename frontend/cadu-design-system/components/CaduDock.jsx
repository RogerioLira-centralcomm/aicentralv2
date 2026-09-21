import React, {useCallback, useEffect, useId, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {VisualIdentity} from './VisualIdentity';
import {Icon} from './Icon';
import {CaduSolutionSwitcher} from './WorkspaceSelectors';
import {workspaceSolutionItems} from '../workspaceSolutions';

function DockTooltip({label, children}) {
  const anchorRef = useRef(null);
  const tooltipId = useId();
  const [position, setPosition] = useState(null);

  const updatePosition = useCallback(() => {
    const rect = anchorRef.current?.getBoundingClientRect();
    if (!rect) return;
    // Keep labels in the open space beside the dock so they never cover the
    // workspace or get clipped by the compact vertical shelf.
    setPosition({left: Math.round(rect.right + 10), top: Math.round(rect.top + rect.height / 2)});
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

function readDockPayload(event) {
  const raw = event.dataTransfer?.getData('application/x-cadu-item') || event.dataTransfer?.getData('text/plain');
  if (!raw) return null;
  try { return JSON.parse(raw); } catch (_) { return null; }
}

function allowDockDrop(event) {
  event.preventDefault();
  event.stopPropagation();
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
}

function avatarSource(value, bootstrap) {
  const raw = String(value || bootstrap?.user?.avatar || bootstrap?.user?.photoUrl || bootstrap?.user?.photo_url || bootstrap?.user?.foto_url || bootstrap?.user?.picture || '').trim();
  if (raw) {
    if (/^static\//i.test(raw)) return `/${raw}`;
    if (/^(?:https?:|data:|blob:|\/)/i.test(raw)) return raw;
    return `/${raw}`;
  }
  return '';
}

function avatarFallbackSource(bootstrap, userName) {
  const badges = ['badge-comet.png', 'badge-ribbon.png', 'badge-orbit.png', 'badge-prism.png', 'badge-sunburst.png', 'badge-sphere.png'];
  const configured = String(bootstrap?.user?.avatarBadge || '').trim();
  const badge = configured || badges[Array.from(String(userName || '')).reduce((total, character) => total + character.charCodeAt(0), 0) % badges.length];
  return `/static/images/cadu/avatars/${badge}`;
}

const DOCK_RESOURCE_KINDS = new Set(['resource', 'file', 'image', 'artifact', 'video', 'media_plan', 'report', 'analysis', 'link']);
const isDockResource = item => Boolean(item?.resourceRef) || DOCK_RESOURCE_KINDS.has(String(item?.kind || item?.type || '').toLowerCase());

function normalizeDockItem(item) {
  if (!item || typeof item !== 'object') return null;
  const rawKind = String(item.kind || item.type || '').toLowerCase();
  const kind = rawKind === 'brand' || (!rawKind && item.brandRef && !item.projectRef) ? 'brand' : isDockResource(item) ? 'resource' : 'project';
  const rawId = item.id || item.ref || item.projectRef || item.brandRef || item.resourceRef;
  if (!rawId) return null;
  const id = String(rawId);
  const title = String(item.title || item.name || item.projectName || 'Atalho').trim() || 'Atalho';
  const brandRef = kind === 'brand'
    ? String(item.brandRef || (id.startsWith('studio:') ? id : `studio:${id}`))
    : item.brandRef;
  const projectRef = kind === 'project'
    ? String(item.projectRef || item.ref || (id.startsWith('ci:') ? id : `ci:${id}`))
    : item.projectRef;
  const resourceRef = kind === 'resource'
    ? String(item.resourceRef || id.replace(/^resource:/, ''))
    : item.resourceRef;
  return {
    ...item,
    id,
    kind,
    title,
    name: item.name || title,
    brandRef,
    projectRef,
    resourceRef,
  };
}

export function DockDropZone({children, onDropItem, label = 'Fixar na dock'}) {
  const [active, setActive] = useState(false);
  const drop = useCallback(event => {
    allowDockDrop(event); setActive(false);
    const payload = readDockPayload(event);
    if (payload && payload.dockSource !== 'dock') onDropItem?.(payload);
  }, [onDropItem]);
  const enabled = typeof onDropItem === 'function';
  return <div className={`cadu-ds-dock-drop ${active ? 'is-active' : ''}`} onDragEnter={enabled ? () => setActive(true) : undefined} onDragLeave={enabled ? () => setActive(false) : undefined} onDragOver={enabled ? event => { event.preventDefault(); if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'; } : undefined} onDrop={enabled ? drop : undefined} aria-label={label}>{children}</div>;
}

export function DockBrandShortcut({brand, projectCount = 0, active = false, dropTarget = false, dropComplete = false, onOpen, onDragStart, onDropShortcut, onDragEnter, onDragLeave}) {
  const draggable = typeof onDragStart === 'function';
  const droppable = typeof onDropShortcut === 'function';
  return <DockTooltip label={brand.name}><button type="button" draggable={draggable} onDragStart={draggable ? event => onDragStart(event, brand) : undefined} onDragEnter={droppable ? event => { allowDockDrop(event); onDragEnter?.(brand); } : undefined} onDragLeave={droppable ? () => onDragLeave?.(brand) : undefined} onDragOver={droppable ? allowDockDrop : undefined} onDrop={droppable ? event => { allowDockDrop(event); onDropShortcut(event, brand); } : undefined} onClick={() => onOpen?.(brand)} aria-label={`Abrir marca ${brand.name}`} aria-current={active ? 'page' : undefined} className={`cadu-ds-dock-brand ${active ? 'is-active' : ''} ${dropTarget ? 'is-drop-target' : ''} ${dropComplete ? 'is-drop-complete' : ''}`}>
    <VisualIdentity src={brand.logoUrl || brand.logo_url || brand.dockLogoUrl || brand.previewUrl} initials={brand.visualInitials || brand.name} label={brand.name} color={brand.visualColor} variant={brand.visualVariant} imageTreatment="brand"/>
    {projectCount > 1 && <i aria-label={`${projectCount} projetos fixados`}>{projectCount}</i>}
  </button></DockTooltip>;
}

export function DockResourceShortcut({item, active = false, dropTarget = false, dropComplete = false, onOpen, onDragStart, onDropShortcut, onDragEnter, onDragLeave}) {
  const draggable = typeof onDragStart === 'function';
  const droppable = typeof onDropShortcut === 'function';
  const resource = isDockResource(item);
  return <DockTooltip label={item.title}><button type="button" draggable={draggable} onDragStart={draggable ? event => onDragStart(event, item) : undefined} onDragEnter={droppable ? event => { allowDockDrop(event); onDragEnter?.(item); } : undefined} onDragLeave={droppable ? () => onDragLeave?.(item) : undefined} onDragOver={droppable ? allowDockDrop : undefined} onDrop={droppable ? event => { allowDockDrop(event); onDropShortcut(event, item); } : undefined} onClick={() => onOpen?.(item)} aria-label={`Abrir ${item.title}`} aria-current={active ? 'page' : undefined} className={`cadu-ds-dock-resource ${resource ? 'cadu-ds-dock-resource--file' : ''} ${active ? 'is-active' : ''} ${dropTarget ? 'is-drop-target' : ''} ${dropComplete ? 'is-drop-complete' : ''}`}>
    <VisualIdentity src={item.logoUrl || item.logo_url || item.dockLogoUrl || item.previewUrl} initials={item.visualInitials || item.title || item.name} label={item.title || item.name} color={item.visualColor} variant={item.visualVariant}/>{Number(item.unreadCount || 0) > 0 && <i className="is-unread" aria-label={`${item.unreadCount} notificações não lidas`}>{Number(item.unreadCount) > 9 ? '9+' : item.unreadCount}</i>}
  </button></DockTooltip>;
}

export function DockUsageRing({percent, onOpen}) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  const formatted = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1}).format(value);
  return <DockTooltip label="Créditos e consumo"><button type="button" className="cadu-ds-usage-ring" style={{'--cadu-usage': `${value * 3.6}deg`}} onClick={onOpen} aria-label={`Utilização de créditos: ${formatted}%`}><span>{formatted}%</span></button></DockTooltip>;
}

export function CaduDock({logo, homeUrl, bootstrap, sharedDock = false, conversationMode = false, userName = 'Minha conta', userAvatar, userInitials, accountOpen = false, accountMenu, accountUrl, onOpenAccount, onNewConversation, brands = [], resources = [], shortcutItems = [], usagePercent, onOpenBrand, onOpenResource, onDropItem, onReorderShortcuts, onOpenUsage}) {
  const writePayload = (event, payload) => {
    const serialized = JSON.stringify({...payload, dockSource: 'dock'});
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('application/x-cadu-item', serialized);
    event.dataTransfer.setData('text/plain', serialized);
  };
  const isWorkspaceSurface = sharedDock || Boolean(bootstrap?.homeMode || bootstrap?.projectMode || bootstrap?.brandMode || bootstrap?.brandsMode || bootstrap?.projectsMode || bootstrap?.accountMode);
  const isControlled = typeof onReorderShortcuts === 'function';
  const [managedItems, setManagedItems] = useState(() => shortcutItems);
  const [dropTargetId, setDropTargetId] = useState('');
  const [dropCompleteId, setDropCompleteId] = useState('');
  useEffect(() => {
    if (!isControlled) setManagedItems(shortcutItems);
  }, [isControlled, shortcutItems]);
  // Catalog pages sometimes provide their complete brand/project lists as a
  // fallback, while the API returns persisted shortcuts with an explicit
  // kind. Normalize both shapes here so every surface renders one identical
  // dock and every project remains a real project shortcut.
  const items = (isControlled ? shortcutItems : managedItems).map(normalizeDockItem).filter(Boolean);
  const shortcutIdentity = item => item?.shortcutId || `${item?.kind || 'item'}:${item?.id}`;
  const dockBrands = items.filter(item => item.kind === 'brand');
  const dockProjects = items.filter(item => item.kind !== 'brand' && !isDockResource(item));
  const dockResourceItems = items.filter(item => item.kind !== 'brand' && isDockResource(item));
  const projectsForBrand = brand => dockProjects.filter(project => String(project.brandRef || '') === String(brand.brandRef || brand.id || ''));
  const linkedProjectIds = new Set(dockBrands.flatMap(brand => projectsForBrand(brand).map(project => shortcutIdentity(project))));
  const orphanProjects = dockProjects.filter(project => !linkedProjectIds.has(shortcutIdentity(project)));
  const canReorder = isControlled || isWorkspaceSurface;
  const persistManagedOrder = async next => {
    const before = managedItems;
    setManagedItems(next);
    const endpoint = bootstrap?.endpoints?.dockShortcuts || '/workspace/api/dock/shortcuts';
    const token = bootstrap?.csrf || document.querySelector('meta[name="csrf-token"]')?.content || '';
    try {
      const explicit = [];
      for (const item of next) {
        if (item.shortcutId) { explicit.push(item); continue; }
        const resource = isDockResource(item);
        const kind = item.kind === 'brand' ? 'brand' : resource ? 'resource' : 'project';
        const targetRef = kind === 'brand' ? item.id : resource ? item.resourceRef || item.id : item.projectRef || item.id;
        const response = await fetch(endpoint, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': token}, body: JSON.stringify({shortcut_type: kind, target_ref: targetRef, project_ref: item.projectRef || null, brand_ref: item.brandRef || null})});
        if (!response.ok) throw new Error('Não foi possível salvar a ordem da dock.');
        const data = await response.json();
        explicit.push({...item, shortcutId: data.shortcut?.id, pinned: true});
      }
      setManagedItems(explicit);
      const response = await fetch(`${endpoint}/order`, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': token}, body: JSON.stringify({ids: explicit.map(item => item.shortcutId)})});
      if (!response.ok) throw new Error('Não foi possível salvar a ordem da dock.');
    } catch (_) {
      setManagedItems(before);
    }
  };
  const handleReorder = next => isControlled ? onReorderShortcuts?.(next) : persistManagedOrder(next);
  const reorder = (event, target) => {
    const source = readDockPayload(event);
    if (!source?.id || source.id === target.id) return;
    const identity = item => item.shortcutId || `${item.kind || 'item'}:${item.id}`;
    const sourceIdentity = source.shortcutId || `${source.kind || 'item'}:${source.id}`;
    const targetIdentity = target.shortcutId || `${target.kind || 'item'}:${target.id}`;
    const next = [...items];
    const from = next.findIndex(item => identity(item) === sourceIdentity);
    const to = next.findIndex(item => identity(item) === targetIdentity);
    if (from < 0 || to < 0) return;
    next.splice(to, 0, next.splice(from, 1)[0]);
    handleReorder(next);
    setDropTargetId('');
    const targetId = shortcutIdentity(target);
    setDropCompleteId(targetId);
    window.setTimeout(() => setDropCompleteId(current => current === targetId ? '' : current), 260);
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        const audio = new AudioContext();
        const oscillator = audio.createOscillator();
        const gain = audio.createGain();
        oscillator.type = 'sine'; oscillator.frequency.value = 620;
        gain.gain.setValueAtTime(0.045, audio.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.075);
        oscillator.connect(gain).connect(audio.destination);
        oscillator.start(); oscillator.stop(audio.currentTime + 0.075);
        oscillator.addEventListener('ended', () => audio.close(), {once: true});
      }
    } catch (_) { /* feedback is optional */ }
  };
  const markDropTarget = item => setDropTargetId(shortcutIdentity(item));
  const clearDropTarget = item => setDropTargetId(current => current === shortcutIdentity(item) ? '' : current);
  const solutions = bootstrap ? workspaceSolutionItems(bootstrap) : [];
  const resolvedAvatar = avatarSource(userAvatar, bootstrap);
  const fallbackAvatar = avatarFallbackSource(bootstrap, userName);
  const resolvedUsagePercent = usagePercent ?? bootstrap?.usagePercent ?? bootstrap?.usage_percent ?? bootstrap?.home?.usagePercent ?? 0;
  // The avatar owns the account menu. A direct account URL is opt-in so the
  // presence of the usage route cannot bypass Perfil, Agência and Créditos.
  const resolvedAccountUrl = accountUrl;
  const openUsage = () => {
    const usageUrl = bootstrap?.urls?.usage || bootstrap?.urls?.credits;
    if (usageUrl) {
      window.location.assign(usageUrl);
      return;
    }
    onOpenUsage?.();
  };
  const avatar = <VisualIdentity src={resolvedAvatar || fallbackAvatar} fallbackSrc={resolvedAvatar ? fallbackAvatar : ''} initials={userInitials || userName} label={userName} color="#1b6d64" imageAlt={`Foto de ${userName}`}/>;
  return <aside className={`cadu-ds-dock ${conversationMode ? 'cadu-ds-dock--conversation' : 'cadu-ds-dock--workspace'}`} aria-label="Atalhos do Workspace">
    <div className="cadu-ds-dock-solution"><CaduSolutionSwitcher logo={logo} solutions={solutions} activeId="workspace"/></div>
    <DockTooltip label="Novo chat"><button type="button" className="cadu-ds-dock-new" onClick={onNewConversation} aria-label="Novo chat"><Icon name="newChat" size={18}/></button></DockTooltip>
    {homeUrl && <DockTooltip label="Início"><a href={homeUrl} className="cadu-ds-dock-home" aria-label="Ir para o início"><Icon name="home" size={18}/></a></DockTooltip>}
    <DockDropZone onDropItem={onDropItem} label="Fixar marca, projeto ou recurso"><div className="cadu-ds-dock-context" aria-label="Atalhos do Workspace">
      <section className="cadu-ds-dock-section cadu-ds-dock-section--brands" aria-label="Marcas e projetos fixados">{dockBrands.map(brand => <div className="cadu-ds-dock-brand-tree" key={brand.shortcutId || brand.id}><DockBrandShortcut brand={brand} projectCount={brand.projectCount} active={brand.active} dropTarget={dropTargetId === shortcutIdentity(brand)} dropComplete={dropCompleteId === shortcutIdentity(brand)} onOpen={onOpenBrand} onDragStart={canReorder ? writePayload : undefined} onDragEnter={markDropTarget} onDragLeave={clearDropTarget} onDropShortcut={canReorder ? reorder : undefined}/>{projectsForBrand(brand).map(project => <DockResourceShortcut key={project.shortcutId || project.id} item={project} pinned={project.pinned} active={project.active} dropTarget={dropTargetId === shortcutIdentity(project)} dropComplete={dropCompleteId === shortcutIdentity(project)} onOpen={onOpenResource} onDragStart={canReorder ? writePayload : undefined} onDragEnter={markDropTarget} onDragLeave={clearDropTarget} onDropShortcut={canReorder ? reorder : undefined}/>)}</div>)}</section>
      {orphanProjects.length > 0 && <section className="cadu-ds-dock-section cadu-ds-dock-section--projects" aria-label="Projetos fixados">{orphanProjects.map(item => <DockResourceShortcut key={item.shortcutId || item.id} item={item} pinned={item.pinned} active={item.active} dropTarget={dropTargetId === shortcutIdentity(item)} dropComplete={dropCompleteId === shortcutIdentity(item)} onOpen={onOpenResource} onDragStart={canReorder ? writePayload : undefined} onDragEnter={markDropTarget} onDragLeave={clearDropTarget} onDropShortcut={canReorder ? reorder : undefined}/>)}</section>}
      {dockResourceItems.length > 0 && <section className="cadu-ds-dock-section cadu-ds-dock-section--resources" aria-label="Recursos fixados">{dockResourceItems.map(item => <DockResourceShortcut key={item.shortcutId || item.id} item={item} pinned={item.pinned} active={item.active} dropTarget={dropTargetId === shortcutIdentity(item)} onOpen={onOpenResource} onDragStart={canReorder ? writePayload : undefined} onDragEnter={markDropTarget} onDragLeave={clearDropTarget} onDropShortcut={canReorder ? reorder : undefined}/>)}</section>}
    </div></DockDropZone>
    <div className="cadu-ds-dock-bottom"><DockUsageRing percent={resolvedUsagePercent} onOpen={openUsage}/><div className="cadu-ds-dock-account-wrap"><DockTooltip label={`Conta de ${userName}`}>{resolvedAccountUrl ? <a href={resolvedAccountUrl} className="cadu-ds-dock-avatar-button cadu-ds-dock-avatar-link" aria-label={`Abrir uso e conta de ${userName}`}>{avatar}</a> : <button type="button" className="cadu-ds-dock-avatar-button" onClick={onOpenAccount} aria-label={`Abrir conta de ${userName}`} aria-haspopup="menu" aria-expanded={accountOpen}>{avatar}</button>}</DockTooltip>{!resolvedAccountUrl && accountMenu}</div></div>
  </aside>;
}
