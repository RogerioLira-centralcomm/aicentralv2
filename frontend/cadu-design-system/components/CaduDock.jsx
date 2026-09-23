import React, {useCallback, useEffect, useId, useRef, useState} from 'react';
import './CaduDock.css';
import {createPortal} from 'react-dom';
import {VisualIdentity} from './VisualIdentity';
import {Icon} from './Icon';
import {CaduSolutionSwitcher} from './WorkspaceSelectors';
import {workspaceSolutionItems} from '../workspaceSolutions';
import {useWorkspaceNotifications} from './WorkspaceNotifications';
import {completeDockOrder, insertionIndexFromCenters, reorderAtInsertion} from '../dockPlacement.mjs';
import {dockExternalPresentation, dockProviderLogo} from '../dockExternal.mjs';

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

function safeExternalUrl(value) {
  try {
    const url = new URL(String(value || '').trim());
    return url.protocol === 'https:' && !url.username && !url.password && (!url.port || url.port === '443') ? url.href : '';
  } catch (_) { return ''; }
}

function normalizeDockItem(item) {
  if (!item || typeof item !== 'object') return null;
  const rawKind = String(item.kind || item.type || '').toLowerCase();
  const kind = rawKind === 'external' ? 'external' : rawKind === 'brand' || (!rawKind && item.brandRef && !item.projectRef) ? 'brand' : isDockResource(item) ? 'resource' : 'project';
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
    href: kind === 'external' ? safeExternalUrl(item.href || item.url) : item.href,
    logoUrl: kind === 'external' ? dockProviderLogo(item.href || item.url) || item.logoUrl : item.logoUrl,
    dockBackground: /^#[0-9a-f]{6}$/i.test(String(item.dockBackground || '')) ? item.dockBackground : '',
    dockSize: ['small','medium','large'].includes(item.dockSize) ? item.dockSize : 'medium',
  };
}

export function DockDropZone({children, onDropItem, onDragOverItem, onDragExit, label = 'Fixar na dock'}) {
  const [active, setActive] = useState(false);
  const drop = useCallback(event => {
    allowDockDrop(event); setActive(false);
    const payload = readDockPayload(event);
    onDropItem?.(payload, event);
  }, [onDropItem]);
  const enabled = typeof onDropItem === 'function';
  return <div className={`cadu-ds-dock-drop ${active ? 'is-active' : ''}`} onDragEnter={enabled ? () => setActive(true) : undefined} onDragLeave={enabled ? event => { const rect = event.currentTarget.getBoundingClientRect(); const inside = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom; if (!inside && !event.currentTarget.contains(event.relatedTarget)) { setActive(false); onDragExit?.(); } } : undefined} onDragOver={enabled ? event => { event.preventDefault(); event.stopPropagation(); if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'; onDragOverItem?.(event); } : undefined} onDrop={enabled ? drop : undefined} aria-label={label}>{children}</div>;
}

export function DockBrandShortcut({brand, projectCount = 0, active = false, dropTarget = false, dropComplete = false, onOpen, onDragStart, onDropShortcut, onDragEnter, onDragLeave}) {
  const draggable = typeof onDragStart === 'function';
  const droppable = typeof onDropShortcut === 'function';
  return <DockTooltip label={brand.name}><button type="button" draggable={draggable} onDragStart={draggable ? event => onDragStart(event, brand) : undefined} onDragEnter={droppable ? event => { allowDockDrop(event); onDragEnter?.(brand); } : undefined} onDragLeave={droppable ? () => onDragLeave?.(brand) : undefined} onDragOver={droppable ? allowDockDrop : undefined} onDrop={droppable ? event => { allowDockDrop(event); onDropShortcut(event, brand); } : undefined} onClick={() => onOpen?.(brand)} aria-label={`Abrir marca ${brand.name}`} aria-current={active ? 'page' : undefined} className={`cadu-ds-dock-brand ${active ? 'is-active' : ''} ${dropTarget ? 'is-drop-target' : ''} ${dropComplete ? 'is-drop-complete' : ''}`}>
    <VisualIdentity src={brand.dockLogoUrl || brand.logoUrl || brand.logo_url || brand.previewUrl} fallbackSrc={brand.dockLogoUrl ? brand.logoUrl || brand.logo_url || brand.previewUrl : ''} initials={brand.visualInitials || brand.name} label={brand.name} color={brand.dockBackground || brand.visualColor} variant={brand.visualVariant} imageTreatment="brand" className={`cadu-ds-dock-identity--${brand.dockSize || 'medium'} ${brand.dockBackground ? 'has-custom-background' : 'has-image-background'}`}/>
    {projectCount > 1 && <i aria-label={`${projectCount} projetos fixados`}>{projectCount}</i>}
  </button></DockTooltip>;
}

export function DockResourceShortcut({item, active = false, dropTarget = false, dropComplete = false, onOpen, onDragStart, onDropShortcut, onDragEnter, onDragLeave}) {
  const draggable = typeof onDragStart === 'function';
  const droppable = typeof onDropShortcut === 'function';
  const resource = isDockResource(item);
  return <DockTooltip label={item.title}><button type="button" draggable={draggable} onDragStart={draggable ? event => onDragStart(event, item) : undefined} onDragEnter={droppable ? event => { allowDockDrop(event); onDragEnter?.(item); } : undefined} onDragLeave={droppable ? () => onDragLeave?.(item) : undefined} onDragOver={droppable ? allowDockDrop : undefined} onDrop={droppable ? event => { allowDockDrop(event); onDropShortcut(event, item); } : undefined} onClick={() => onOpen?.(item)} aria-label={`Abrir ${item.title}`} aria-current={active ? 'page' : undefined} className={`cadu-ds-dock-resource ${resource ? 'cadu-ds-dock-resource--file' : ''} ${item.kind === 'external' && item.logoUrl ? dockProviderLogo(item.href) ? 'cadu-ds-dock-resource--provider' : 'cadu-ds-dock-resource--generated' : ''} ${active ? 'is-active' : ''} ${dropTarget ? 'is-drop-target' : ''} ${dropComplete ? 'is-drop-complete' : ''}`}>
    {item.kind === 'external' && !item.logoUrl ? <Icon name="link" size={23}/> : <VisualIdentity src={item.logoUrl || item.logo_url || item.dockLogoUrl || item.previewUrl} initials={item.visualInitials || item.title || item.name} label={item.title || item.name} color={item.dockBackground || item.visualColor} variant={item.visualVariant} className={`cadu-ds-dock-identity--${item.dockSize || 'medium'} ${item.dockBackground ? 'has-custom-background' : 'has-image-background'}`} fallbackContent={item.kind === 'external' ? <Icon name="link" size={23}/> : null}/>}{Number(item.unreadCount || 0) > 0 && <i className="is-unread" aria-label={`${item.unreadCount} notificações não lidas`}>{Number(item.unreadCount) > 9 ? '9+' : item.unreadCount}</i>}
  </button></DockTooltip>;
}

export function DockUsageRing({percent, onOpen}) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  const formatted = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1}).format(value);
  return <DockTooltip label="Créditos e consumo"><button type="button" className="cadu-ds-usage-ring" style={{'--cadu-usage': `${value * 3.6}deg`}} onClick={onOpen} aria-label={`Utilização de créditos: ${formatted}%`}><span>{formatted}%</span></button></DockTooltip>;
}

function DockPicker({candidates, items, busy, query, onQueryChange, linkUrl, onLinkUrlChange, linkTitle, onLinkTitleChange, onSave, onClose}) {
  const [urlError, setUrlError] = useState('');
  const available = candidates.filter(item => !items.some(current => current.kind === item.kind && current.id === item.id) && item.title.toLocaleLowerCase('pt-BR').includes(query.trim().toLocaleLowerCase('pt-BR')));
  const submitLink = event => {
    event.preventDefault();
    const url = safeExternalUrl(linkUrl);
    if (!url) { setUrlError('Informe um endereço HTTPS válido, sem usuário ou senha.'); return; }
    setUrlError('');
    onSave({id:`external:${url}`, kind:'external', href:url, title:linkTitle.trim() || new URL(url).hostname});
  };
  return <div className="cadu-ds-dock-picker-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="cadu-ds-dock-picker" role="dialog" aria-modal="true" aria-labelledby="cadu-dock-picker-title">
      <header className="cadu-ds-dock-picker__header"><div><h2 id="cadu-dock-picker-title">Adicionar à dock</h2><p>Escolha uma marca ou projeto. Você poderá ordenar tudo diretamente na dock.</p></div><button type="button" className="cadu-ds-dock-picker__close" onClick={onClose} aria-label="Fechar"><Icon name="close" size={18}/></button></header>
      <div className="cadu-ds-dock-picker__content">
        <label className="cadu-ds-dock-picker__search"><span>Marcas e projetos</span><input autoFocus value={query} onChange={event => onQueryChange(event.target.value)} placeholder="Buscar marca ou projeto"/></label>
        <div className="cadu-ds-dock-picker__catalog" aria-label="Itens disponíveis">{available.length ? available.map(item => <button type="button" key={`${item.kind}:${item.id}`} disabled={busy} onClick={() => onSave(item)}><VisualIdentity src={item.logoUrl || item.previewUrl} initials={item.visualInitials || item.title} label={item.title} color={item.visualColor}/><span>{item.title}</span><Icon name="plus" size={16}/></button>) : <p className="cadu-ds-dock-picker__empty">{query ? 'Nenhum item corresponde à busca.' : 'Tudo o que está disponível já foi fixado.'}</p>}</div>
        <details className="cadu-ds-dock-picker__link"><summary>Adicionar um link externo</summary><form onSubmit={submitLink} noValidate><label><span>Endereço do link</span><input type="url" inputMode="url" value={linkUrl} onChange={event => { onLinkUrlChange(event.target.value); setUrlError(''); }} placeholder="https://trello.com/..." aria-invalid={Boolean(urlError)} aria-describedby={urlError ? 'cadu-dock-url-error' : undefined}/></label>{urlError && <p id="cadu-dock-url-error" className="cadu-ds-dock-picker__error" role="alert">{urlError}</p>}<label><span>Nome na dock <small>opcional</small></span><input value={linkTitle} onChange={event => onLinkTitleChange(event.target.value)} placeholder="Ex.: Quadro do Trello" maxLength="80"/></label><button type="submit" disabled={busy || !linkUrl.trim()}>Adicionar link</button></form><p className="cadu-ds-dock-picker__hint">Links abrem sem conectar sua conta ao Cadu.</p></details>
      </div>
    </section>
  </div>;
}

export function CaduDock({logo, homeUrl, bootstrap, sharedDock = false, conversationMode = false, userName = 'Minha conta', userAvatar, userInitials, accountOpen = false, accountMenu, accountUrl, onOpenAccount, onNewConversation, brands = [], resources = [], shortcutItems = [], usagePercent, notifications = [], onOpenNotifications, onOpenBrand, onOpenResource, onDropItem, onReorderShortcuts, onShortcutAdded, onShortcutRemoved, onOpenUsage}) {
  const notificationCenter = useWorkspaceNotifications();
  const resolvedNotifications = notifications.length ? notifications : notificationCenter.pending;
  const openNotifications = onOpenNotifications || notificationCenter.open;
  const [liveUsagePercent, setLiveUsagePercent] = useState(null);
  useEffect(() => {
    let active = true;
    const refresh = () => fetch(bootstrap?.endpoints?.creditSummary || '/workspace/api/creditos/resumo', {credentials:'same-origin', headers:{Accept:'application/json'}})
      .then(response => response.ok ? response.json() : Promise.reject(new Error('credit summary unavailable')))
      .then(value => { if (active && Number.isFinite(Number(value.monthly_usage_percentage))) setLiveUsagePercent(Number(value.monthly_usage_percentage)); })
      .catch(() => {});
    refresh();
    const timer = window.setInterval(refresh, 60000);
    return () => { active = false; window.clearInterval(timer); };
  }, [bootstrap?.endpoints?.creditSummary]);
  const writePayload = (event, payload) => {
    const serialized = JSON.stringify({...payload, dockSource: 'dock'});
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('application/x-cadu-item', serialized);
    event.dataTransfer.setData('text/plain', serialized);
  };
  const isWorkspaceSurface = sharedDock || Boolean(bootstrap?.homeMode || bootstrap?.projectMode || bootstrap?.brandMode || bootstrap?.brandsMode || bootstrap?.projectsMode || bootstrap?.accountMode);
  const isControlled = typeof onReorderShortcuts === 'function';
  const [managedItems, setManagedItems] = useState(() => shortcutItems);
  const [draggedId, setDraggedId] = useState('');
  const [trashActive, setTrashActive] = useState(false);
  const [insertIndex, setInsertIndex] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState('');
  const [linkTitle, setLinkTitle] = useState('');
  const [candidateQuery, setCandidateQuery] = useState('');
  const [dockNotice, setDockNotice] = useState('');
  const [undoItem, setUndoItem] = useState(null);
  const [busy, setBusy] = useState(false);
  const [externalView, setExternalView] = useState(null);
  const [externalHint, setExternalHint] = useState(false);
  const [iconOverrides, setIconOverrides] = useState({});
  useEffect(() => {
    if (!externalView) return undefined;
    setExternalHint(false);
    const timer = window.setTimeout(() => setExternalHint(true), 4500);
    const onKey = event => { if (event.key === 'Escape') setExternalView(null); };
    window.addEventListener('keydown', onKey);
    return () => { window.clearTimeout(timer); window.removeEventListener('keydown', onKey); };
  }, [externalView]);
  useEffect(() => {
    if (!addOpen) return undefined;
    const onKey = event => {
      if (event.key === 'Escape') { setAddOpen(false); return; }
      if (event.key !== 'Tab') return;
      const focusable = [...document.querySelectorAll('.cadu-ds-dock-picker button:not(:disabled), .cadu-ds-dock-picker input:not(:disabled), .cadu-ds-dock-picker summary')];
      if (!focusable.length) return;
      if (event.shiftKey && document.activeElement === focusable[0]) { event.preventDefault(); focusable.at(-1).focus(); }
      else if (!event.shiftKey && document.activeElement === focusable.at(-1)) { event.preventDefault(); focusable[0].focus(); }
    };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); document.querySelector('.cadu-ds-dock-add')?.focus(); };
  }, [addOpen]);
  useEffect(() => {
    if (!undoItem) return undefined;
    const timer = window.setTimeout(() => setUndoItem(null), 6500);
    return () => window.clearTimeout(timer);
  }, [undoItem]);
  useEffect(() => {
    if (!isControlled) setManagedItems(shortcutItems);
  }, [isControlled, shortcutItems]);
  // Catalog pages sometimes provide their complete brand/project lists as a
  // fallback, while the API returns persisted shortcuts with an explicit
  // kind. Normalize both shapes here so every surface renders one identical
  // dock and every project remains a real project shortcut.
  const items = (isControlled ? shortcutItems : managedItems).map(value => normalizeDockItem({
    ...value, ...(iconOverrides[value?.shortcutId] || {}),
  })).filter(Boolean);
  const shortcutIdentity = item => item?.shortcutId || `${item?.kind || 'item'}:${item?.id}`;
  const endpoint = bootstrap?.endpoints?.dockShortcuts || '/workspace/api/dock/shortcuts';
  const token = bootstrap?.csrf || document.querySelector('meta[name="csrf-token"]')?.content || '';
  const unresolvedIconIds = items.filter(item => item.kind === 'external' && item.shortcutId && !dockProviderLogo(item.href) && !item.logoUrl).map(item => item.shortcutId).join('|');
  useEffect(() => {
    if (!unresolvedIconIds) return undefined;
    let active = true;
    const requestMissing = async () => {
      for (const shortcutId of unresolvedIconIds.split('|')) {
        if (!active) return;
        try {
          const response = await fetch(`${endpoint}/${shortcutId}/icon`, {method:'POST', credentials:'same-origin', headers:{'X-CSRF-Token':token, Accept:'application/json'}});
          if (!response.ok) { if (active) setIconOverrides(current => ({...current, [shortcutId]:{iconStatus:'failed'}})); continue; }
          const value = await response.json();
          if (active && value.status) setIconOverrides(current => ({...current, [shortcutId]:{iconStatus:value.status, logoUrl:value.icon_url || ''}}));
        } catch (_) { if (active) setIconOverrides(current => ({...current, [shortcutId]:{iconStatus:'failed'}})); }
      }
    };
    requestMissing();
    const timer = window.setInterval(requestMissing, 300000);
    return () => { active = false; window.clearInterval(timer); };
  }, [endpoint, token, unresolvedIconIds]);
  useEffect(() => {
    if (!items.some(item => item.kind === 'external' && ['queued','running','generating'].includes(item.iconStatus))) return undefined;
    let active = true;
    const refresh = async () => {
      try {
        const response = await fetch(endpoint, {credentials:'same-origin', headers:{Accept:'application/json'}});
        if (!response.ok) return;
        const data = await response.json();
        if (!active) return;
        setIconOverrides(current => {
          const next = {...current};
          for (const row of data.shortcuts || []) {
            const metadata = row.metadata || {};
            if (row.shortcut_type === 'external' && metadata.icon_status) {
              next[row.id] = {logoUrl:metadata.icon_url || '', iconStatus:metadata.icon_status};
            }
          }
          return next;
        });
      } catch (_) { /* A saved shortcut keeps its neutral icon while offline. */ }
    };
    const timer = window.setInterval(refresh, 4000);
    refresh();
    return () => { active = false; window.clearInterval(timer); };
  }, [endpoint, items.some(item => item.kind === 'external' && ['queued','running','generating'].includes(item.iconStatus))]);
  const candidates = [...(bootstrap?.home?.catalogBrands || brands), ...(bootstrap?.home?.projects || bootstrap?.projects || []), ...resources]
    .map(normalizeDockItem).filter(Boolean).filter((item, index, all) => all.findIndex(other => other.kind === item.kind && other.id === item.id) === index);
  const postOrder = async visibleIds => {
    const currentResponse = await fetch(endpoint, {credentials:'same-origin', headers:{Accept:'application/json'}});
    if (!currentResponse.ok) throw new Error('Não foi possível conferir os atalhos salvos.');
    const current = await currentResponse.json();
    const allIds = Array.isArray(current.shortcuts) ? current.shortcuts.map(item => item.id) : [];
    const response = await fetch(`${endpoint}/order`, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json', 'X-CSRF-Token':token}, body:JSON.stringify({ids:completeDockOrder(visibleIds, allIds)})});
    if (!response.ok) throw new Error('Não foi possível salvar a ordem da dock.');
  };
  const canReorder = isControlled || isWorkspaceSurface;
  const persistManagedOrder = async next => {
    const before = managedItems;
    setManagedItems(next);
    try {
      const explicit = [];
      for (const item of next) {
        if (item.shortcutId) { explicit.push(item); continue; }
        const resource = isDockResource(item);
        const kind = item.kind === 'brand' ? 'brand' : item.kind === 'external' ? 'external' : resource ? 'resource' : 'project';
        const targetRef = kind === 'brand' ? item.id : resource ? item.resourceRef || item.id : item.projectRef || item.id;
        const response = await fetch(endpoint, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': token}, body: JSON.stringify({shortcut_type: kind, target_ref: targetRef, project_ref: item.projectRef || null, brand_ref: item.brandRef || null, url:item.href, title:item.title})});
        if (!response.ok) throw new Error('Não foi possível salvar a ordem da dock.');
        const data = await response.json();
        explicit.push({...item, shortcutId: data.shortcut?.id, pinned: true});
      }
      setManagedItems(explicit);
      await postOrder(explicit.map(item => item.shortcutId));
    } catch (_) {
      setManagedItems(before);
      setDockNotice('A ordem não foi confirmada. Atualize a página para sincronizar a dock.');
    }
  };
  const handleReorder = next => isControlled ? onReorderShortcuts?.(next) : persistManagedOrder(next);
  const clearDrag = () => { setDraggedId(''); setInsertIndex(null); setTrashActive(false); };
  const locateInsertion = event => {
    const scrollSurface = event.currentTarget.querySelector('.cadu-ds-dock-context');
    if (scrollSurface) {
      const bounds = scrollSurface.getBoundingClientRect();
      if (event.clientY < bounds.top + 32) scrollSurface.scrollTop -= 12;
      else if (event.clientY > bounds.bottom - 32) scrollSurface.scrollTop += 12;
    }
    const entries = [...event.currentTarget.querySelectorAll('[data-dock-index]')];
    const centers = entries.map(entry => { const rect = entry.getBoundingClientRect(); return rect.top + rect.height / 2; });
    setInsertIndex(insertionIndexFromCenters(centers, event.clientY));
  };
  const saveItem = async (candidate, position = items.length) => {
    const item = normalizeDockItem(candidate);
    if (!item) { setDockNotice('Este item não pode ser fixado na dock.'); return; }
    if (items.length >= 32) { setDockNotice('A dock aceita até 32 atalhos.'); return; }
    if (items.some(current => current.kind === item.kind && (current.href && current.href === item.href || current.id === item.id))) { setDockNotice('Este atalho já está na dock.'); return; }
    const kind = item.kind === 'external' ? 'external' : item.kind === 'brand' ? 'brand' : isDockResource(item) ? 'resource' : 'project';
    const targetRef = kind === 'brand' ? item.id : kind === 'resource' ? item.resourceRef || item.id : item.projectRef || item.id;
    setBusy(true);
    let savedOnServer = false;
    try {
      const response = await fetch(endpoint, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json', 'X-CSRF-Token':token}, body:JSON.stringify({shortcut_type:kind, target_ref:targetRef, project_ref:item.projectRef || null, brand_ref:item.brandRef || null, url:item.href, title:item.title})});
      if (!response.ok) throw new Error('Não foi possível fixar este atalho.');
      const data = await response.json();
      savedOnServer = true;
      const saved = {...item, shortcutId:data.shortcut?.id, pinned:true};
      if (kind === 'external' && saved.shortcutId && !dockProviderLogo(saved.href)) {
        saved.iconStatus = 'queued';
        setIconOverrides(current => ({...current, [saved.shortcutId]:{iconStatus:'queued'}}));
      }
      const next = items.filter(value => value.shortcutId);
      next.splice(Math.min(position, next.length), 0, saved);
      if (isControlled) { onShortcutAdded?.(saved, next); } else { setManagedItems(next); }
      setAddOpen(false); setLinkUrl(''); setLinkTitle(''); setUndoItem(null); setDockNotice(`${item.title} fixado na dock.`);
      if (next.every(value => value.shortcutId)) {
        await postOrder(next.map(value => value.shortcutId));
      }
    } catch (error) { setDockNotice(savedOnServer ? 'O atalho foi fixado, mas a posição não foi confirmada. Atualize a página para sincronizar.' : error.message || 'Não foi possível fixar este atalho.'); }
    finally { setBusy(false); }
  };
  const dropAtInsertion = (payload, event) => {
    const index = insertIndex ?? items.length;
    clearDrag();
    if (payload?.dockSource === 'dock') {
      const next = reorderAtInsertion(items, payload.shortcutId || `${payload.kind}:${payload.id}`, index, shortcutIdentity);
      if (next.some((item, position) => item.id !== items[position]?.id)) handleReorder(next);
      return;
    }
    if (payload?.id) { saveItem(payload, index); return; }
    const html = event.dataTransfer?.getData('text/html') || '';
    const htmlImage = html ? new DOMParser().parseFromString(html, 'text/html').querySelector('img')?.src || '' : '';
    const raw = event.dataTransfer?.getData('text/uri-list') || event.dataTransfer?.getData('text/plain') || htmlImage;
    const url = safeExternalUrl(raw.split('\n').find(line => line && !line.startsWith('#')));
    if (url) { setLinkUrl(url); setLinkTitle(new URL(url).hostname.replace(/^www\./, '')); setAddOpen(true); }
    else if ([...(event.dataTransfer?.files || [])].some(file => file.type.startsWith('image/'))) setDockNotice('Para fixar uma imagem do computador, envie-a primeiro aos arquivos de um projeto. Imagens por URL podem ser soltas aqui.');
    else setDockNotice('Solte uma marca, projeto, recurso ou endereço HTTPS.');
  };
  const moveWithKeyboard = (item, direction) => {
    const from = items.findIndex(current => shortcutIdentity(current) === shortcutIdentity(item));
    const to = from + direction;
    if (from < 0 || to < 0 || to >= items.length) return;
    const next = [...items]; next.splice(to, 0, next.splice(from, 1)[0]); handleReorder(next);
  };
  const removeItem = async item => {
    if (!item.shortcutId) { setDockNotice('Este é um atalho sugerido. Fixe outro item para personalizar a dock.'); return; }
    setBusy(true);
    try {
      const response = await fetch(`${endpoint}/${item.shortcutId}`, {method:'DELETE', credentials:'same-origin', headers:{'X-CSRF-Token':token}});
      if (!response.ok) throw new Error('Não foi possível remover o atalho.');
      const next = items.filter(current => shortcutIdentity(current) !== shortcutIdentity(item));
      if (isControlled) onShortcutRemoved?.(item, next); else setManagedItems(next);
      setUndoItem(item);
      setDockNotice(`${item.title} removido da dock.`);
    } catch (error) { setDockNotice(error.message || 'Não foi possível remover o atalho.'); }
    finally { setBusy(false); }
  };
  const dropOnTrash = event => {
    event.preventDefault();
    event.stopPropagation();
    const item = items.find(current => shortcutIdentity(current) === draggedId);
    clearDrag();
    if (item) removeItem(item);
  };
  const openItem = item => {
    if (item.kind !== 'external') { if (item.kind === 'brand') onOpenBrand?.(item); else onOpenResource?.(item); return; }
    const presentation = dockExternalPresentation(item.href);
    if (!presentation) { setDockNotice('O endereço deste atalho não é válido.'); return; }
    let alwaysExternal = false;
    try { alwaysExternal = window.localStorage.getItem(`cadu:dock:external:${presentation.host}`) === '1'; } catch (_) { /* Storage is optional. */ }
    if (presentation.kind === 'external' || alwaysExternal) { window.open(presentation.url, '_blank', 'noopener,noreferrer'); return; }
    setExternalView({...presentation, title:item.title});
  };
  const solutions = bootstrap ? workspaceSolutionItems(bootstrap) : [];
  const resolvedAvatar = avatarSource(userAvatar, bootstrap);
  const fallbackAvatar = avatarFallbackSource(bootstrap, userName);
  const resolvedUsagePercent = liveUsagePercent ?? usagePercent ?? bootstrap?.usagePercent ?? bootstrap?.usage_percent ?? bootstrap?.home?.usagePercent ?? 0;
  const resolvedAccountMenu = React.isValidElement(accountMenu) ? React.cloneElement(accountMenu, {usagePercent: resolvedUsagePercent}) : accountMenu;
  // The avatar is the direct entry point to the persistent account sidebar.
  // Account navigation already exposes Perfil, Agência, Créditos and the
  // remaining sections, so an intermediate dropdown only duplicates it.
  const resolvedAccountUrl = accountUrl || bootstrap?.urls?.agency || bootstrap?.urls?.agencia || bootstrap?.urls?.profile || bootstrap?.urls?.perfil;
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
    <nav className="cadu-ds-dock-primary" aria-label="Navegação principal">
      {homeUrl && <DockTooltip label="Início"><a href={homeUrl} className="cadu-ds-dock-primary-action cadu-ds-dock-primary-action--home" aria-label="Ir para o início"><Icon name="home" size={18}/></a></DockTooltip>}
      <DockTooltip label="Nova conversa"><button type="button" className="cadu-ds-dock-primary-action cadu-ds-dock-primary-action--new" onClick={onNewConversation} aria-label="Criar nova conversa"><Icon name="newChat" size={18}/></button></DockTooltip>
    </nav>
    <DockDropZone onDropItem={dropAtInsertion} onDragOverItem={locateInsertion} onDragExit={() => setInsertIndex(null)} label="Reordenar ou fixar atalho"><div className="cadu-ds-dock-context cadu-ds-dock-context--live" aria-label="Atalhos do Workspace">
      <section className="cadu-ds-dock-section cadu-ds-dock-section--live" aria-label="Atalhos fixados">
        {items.map((item, index) => <React.Fragment key={shortcutIdentity(item)}>
          {insertIndex === index && <span className="cadu-ds-dock-insertion" aria-label={`Soltar na posição ${index + 1}`}/>}
          <div className={`cadu-ds-dock-shortcut${draggedId === shortcutIdentity(item) ? ' is-dragging' : ''}`} data-dock-index={index} onDragEnd={clearDrag} onKeyDown={event => { if (event.altKey && event.key === 'ArrowUp') { event.preventDefault(); moveWithKeyboard(item, -1); } if (event.altKey && event.key === 'ArrowDown') { event.preventDefault(); moveWithKeyboard(item, 1); } }}>
            {item.kind === 'brand' ? <DockBrandShortcut brand={item} active={item.active} onOpen={openItem} onDragStart={event => { writePayload(event, item); setDraggedId(shortcutIdentity(item)); }}/> : <DockResourceShortcut item={item} active={item.active} onOpen={openItem} onDragStart={event => { writePayload(event, item); setDraggedId(shortcutIdentity(item)); }}/>}
          </div>
        </React.Fragment>)}
        {insertIndex === items.length && <span className="cadu-ds-dock-insertion" aria-label={`Soltar na posição ${items.length + 1}`}/>}
        <DockTooltip label="Adicionar à dock"><button type="button" className="cadu-ds-dock-add" onClick={() => setAddOpen(true)} aria-label="Adicionar à dock" aria-haspopup="dialog"><Icon name="plus" size={17}/></button></DockTooltip>
        {draggedId && <div className={`cadu-ds-dock-trash${trashActive ? ' is-active' : ''}`} role="button" aria-label="Remover atalho da dock" onDragEnter={event => { event.preventDefault(); event.stopPropagation(); setTrashActive(true); setInsertIndex(null); }} onDragOver={event => { event.preventDefault(); event.stopPropagation(); if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'; }} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget)) setTrashActive(false); }} onDrop={dropOnTrash}><Icon name="trash" size={17}/><span>Remover</span></div>}
      </section>
    </div></DockDropZone>
    {dockNotice && <div className="cadu-ds-dock-notice" role="status">{dockNotice}{undoItem && <button type="button" onClick={() => { saveItem(undoItem); setUndoItem(null); }}>Desfazer</button>}<button type="button" onClick={() => { setDockNotice(''); setUndoItem(null); }} aria-label="Dispensar aviso">×</button></div>}
    {addOpen && createPortal(<DockPicker candidates={candidates} items={items} busy={busy} query={candidateQuery} onQueryChange={setCandidateQuery} linkUrl={linkUrl} onLinkUrlChange={setLinkUrl} linkTitle={linkTitle} onLinkTitleChange={setLinkTitle} onSave={saveItem} onClose={() => setAddOpen(false)}/>, document.body)}
    {externalView && createPortal(<section className="cadu-ds-dock-external-view" aria-label={`Visualização de ${externalView.title}`}><header className="cadu-ds-dock-external-view__bar"><div className="cadu-ds-dock-external-view__identity"><strong>{externalView.title}</strong><span>{externalView.host}</span></div><div className="cadu-ds-dock-external-view__actions"><a href={externalView.url} target="_blank" rel="noopener noreferrer">Abrir em nova aba</a><button type="button" onClick={() => setExternalView(null)} aria-label="Fechar visualização">Fechar</button></div></header><div className="cadu-ds-dock-external-view__content">{externalView.kind === 'image' ? <img src={externalView.url} alt={externalView.title} onError={() => setExternalHint(true)}/> : <iframe title={externalView.title} src={externalView.embedUrl} sandbox="allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox" referrerPolicy="strict-origin-when-cross-origin" onError={() => setExternalHint(true)}/>}</div>{externalHint && <footer className="cadu-ds-dock-external-view__help"><span>Se o serviço não aparecer ou pedir permissão, abra-o em outra aba.</span><a href={externalView.url} target="_blank" rel="noopener noreferrer">Abrir fora</a><button type="button" onClick={() => { try { window.localStorage.setItem(`cadu:dock:external:${externalView.host}`, '1'); } catch (_) { /* Storage is optional. */ } window.open(externalView.url, '_blank', 'noopener,noreferrer'); setExternalView(null); }}>Sempre abrir fora</button></footer>}</section>, document.body)}
    <div className="cadu-ds-dock-bottom">{openNotifications && <DockTooltip label="Notificações"><button type="button" className="cadu-ds-dock-notifications" onClick={openNotifications} aria-label="Abrir notificações"><Icon name="pulse" size={17}/>{resolvedNotifications.length > 0 && <i>{resolvedNotifications.length > 9 ? '9+' : resolvedNotifications.length}</i>}</button></DockTooltip>}<DockUsageRing percent={resolvedUsagePercent} onOpen={openUsage}/><div className="cadu-ds-dock-account-wrap"><DockTooltip label={`Conta de ${userName}`}>{resolvedAccountMenu ? <button type="button" className="cadu-ds-dock-avatar-button" onClick={onOpenAccount} aria-label={`Abrir conta de ${userName}`} aria-haspopup="menu" aria-expanded={accountOpen}>{avatar}</button> : <a href={resolvedAccountUrl} className="cadu-ds-dock-avatar-button cadu-ds-dock-avatar-link" aria-label={`Abrir conta de ${userName}`}>{avatar}</a>}</DockTooltip>{resolvedAccountMenu}</div></div>
  </aside>;
}
