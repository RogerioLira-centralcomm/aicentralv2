import React, {useEffect, useRef, useState} from 'react';
import {VisualIdentity} from './VisualIdentity';
import {CaduDialog} from './CaduDialog';

export function AgentActionDrop({action, onOpen, onDragStart}) {
  if (!action) return null;
  return <button type="button" draggable className="cadu-ds-agent-action" onClick={() => onOpen?.(action)} onDragStart={event => { event.dataTransfer.setData('application/x-cadu-item', JSON.stringify({type: 'agent_action', id: action.id})); onDragStart?.(event, action); }}><b>{action.title}</b><small>{action.summary}</small><span>Usar no chat</span></button>;
}

export function ActivityDrawer({open, title = 'Atividade recente', items = [], onClose, onOpenItem}) {
  if (!open) return null;
  return <CaduDialog className="cadu-ds-activity-drawer" label={title} closeOnBackdrop onClose={onClose}><header><h2>{title}</h2><button type="button" onClick={onClose} aria-label="Fechar atividade">×</button></header><div>{items.map(item => <button key={item.id} type="button" onClick={() => onOpenItem?.(item)}><span>{item.icon || '•'}</span><p><b>{item.title}</b><small>{item.detail}</small></p><time>{item.time}</time></button>)}</div></CaduDialog>;
}

export function ShortcutManagerDialog({open, items = [], onClose, onToggle, onReorder}) {
  const [draggedId, setDraggedId] = useState('');
  if (!open) return null;
  const dropOn = target => {
    if (!draggedId || draggedId === target.id) return;
    const pinned = items.filter(item => item.pinned);
    const from = pinned.findIndex(item => item.id === draggedId);
    const to = pinned.findIndex(item => item.id === target.id);
    if (from < 0 || to < 0) return;
    pinned.splice(to, 0, pinned.splice(from, 1)[0]);
    onReorder?.(pinned);
  };
  return <CaduDialog className="cadu-ds-shortcut-dialog" label="Personalizar dock" onClose={onClose}><header><div><h2>Atalhos da dock</h2><p>Marcas automáticas precisam de logo. Projetos e recursos entram quando você escolher ou arrastar.</p></div><button type="button" onClick={onClose} aria-label="Fechar">×</button></header><div className="cadu-ds-shortcut-grid">{items.map(item => <article key={item.id} draggable={item.pinned} onDragStart={() => setDraggedId(item.id)} onDragEnd={() => setDraggedId('')} onDragOver={event => item.pinned && event.preventDefault()} onDrop={() => dropOn(item)} className={item.pinned ? 'is-pinned' : ''}><VisualIdentity src={item.logoUrl || item.previewUrl} initials={item.visualInitials} label={item.title} color={item.visualColor}/><b>{item.title}</b><button type="button" onClick={() => onToggle?.(item)}>{item.pinned ? 'Remover' : 'Adicionar'}</button></article>)}</div></CaduDialog>;
}

export function WorkspaceAccountMenu({open, onClose, user = {}, links = {}, projects = [], brands = [], usagePercent = 0, onManageShortcuts}) {
  const menuRef = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const closeOutside = event => {
      const target = event.target instanceof Element ? event.target : null;
      const isAccountTrigger = target?.closest('.cadu-ds-home-account,.cadu-ds-dock-avatar-button');
      if (!menuRef.current?.contains(event.target) && !isAccountTrigger) onClose?.();
    };
    const closeOnEscape = event => { if (event.key === 'Escape') onClose?.(); };
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => { document.removeEventListener('pointerdown', closeOutside); document.removeEventListener('keydown', closeOnEscape); };
  }, [open, onClose]);
  if (!open) return null;
  const percent = Math.max(0, Math.min(100, Number(usagePercent) || 0));
  const usageLink = links.usage || links.credits || '/uso';
  const billingLink = links.billing || links.faturamento || '/faturas';
  const integrationsLink = links.integrations || '/integracoes';
  const projectItems = Array.isArray(projects) ? projects.filter(item => item?.href || item?.url) : [];
  const brandItems = Array.isArray(brands) ? brands.filter(item => item?.href || item?.url) : [];
  const itemHref = item => item.href || item.url;
  const itemLabel = (item, fallback) => item.name || item.title || fallback;
  return <div ref={menuRef} className="cadu-ds-account-menu" role="menu" aria-label="Conta e gestão">
    <header><div className="cadu-ds-account-menu__identity"><b>{user.name || 'Minha conta'}</b>{user.email && <small>{user.email}</small>}</div><span className="cadu-ds-account-menu__label">Conta</span></header>
    <nav aria-label="Conta e gestão">
      {links.agency && <a role="menuitem" href={links.agency}>Agência</a>}<a role="menuitem" href={links.profile}>Perfil</a><a role="menuitem" href={links.team}>Equipe</a><a role="menuitem" href={links.plans}>Planos</a><a role="menuitem" href={usageLink}>Créditos e consumo</a><a role="menuitem" href={billingLink}>Faturamento</a><a role="menuitem" href={integrationsLink}>Integrações</a>{links.observability && <a role="menuitem" href={links.observability}>Observabilidade</a>}
    </nav>
    {(brandItems.length > 0 || projectItems.length > 0) && <section className="cadu-ds-account-menu__catalog" aria-label="Projetos e marcas">
      {brandItems.length > 0 && <div className="cadu-ds-account-menu__catalog-group"><header><b>Marcas</b>{links.brands && <a href={links.brands}>Ver todas</a>}</header>{brandItems.map(item => <a className="cadu-ds-account-menu__catalog-item" role="menuitem" href={itemHref(item)} key={`brand-${item.id || itemHref(item)}`}><VisualIdentity src={item.logoUrl || item.previewUrl} initials={item.visualInitials || item.name} label={itemLabel(item, 'Marca')} color={item.visualColor}/><span><b>{itemLabel(item, 'Marca')}</b><small>{item.sector || item.summary || 'Abrir vitrine da marca'}</small></span></a>)}</div>}
      {projectItems.length > 0 && <div className="cadu-ds-account-menu__catalog-group"><header><b>Projetos</b>{links.projects && <a href={links.projects}>Ver todos</a>}</header>{projectItems.map(item => <a className="cadu-ds-account-menu__catalog-item" role="menuitem" href={itemHref(item)} key={`project-${item.id || itemHref(item)}`}><VisualIdentity src={item.previewUrl || item.logoUrl || item.dockLogoUrl} initials={item.visualInitials || item.name} label={itemLabel(item, 'Projeto')} color={item.visualColor}/><span><b>{itemLabel(item, 'Projeto')}</b><small>{item.brandName || item.description || 'Abrir vitrine do projeto'}</small></span></a>)}</div>}
    </section>}
    <section className="cadu-ds-account-menu__usage" aria-label="Uso de créditos"><div><span>Uso de créditos</span><strong>{new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1}).format(percent)}%</strong></div><div className="cadu-ds-account-menu__progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={percent}><i style={{width: `${percent}%`}}/></div><a href={usageLink}>Ver uso e histórico</a></section>
    <footer><button type="button" onClick={onManageShortcuts}>Personalizar dock</button><a href={links.logout}>Sair</a></footer>
  </div>;
}

export function WorkspaceAccountControl({user = {}, open = false, onOpen}) {
  const name = user.name || 'Minha conta';
  return <button type="button" className="cadu-ds-home-account cadu-ds-home-account--identity" onClick={onOpen} aria-label={`Abrir conta de ${name}`} aria-haspopup="menu" aria-expanded={open}>
    <VisualIdentity src={user.avatar} initials={name} label={name} color="#1b6d64"/>
    <span><strong>{name}</strong><small>{user.email || 'Conta e perfil'}</small></span>
    <i aria-hidden="true">⌄</i>
  </button>;
}

export function UndoToast({message, actionLabel = 'Desfazer', onUndo, onDismiss}) {
  if (!message) return null;
  return <div className="cadu-ds-undo-toast" role="status"><span>{message}</span>{onUndo && <button type="button" onClick={onUndo}>{actionLabel}</button>}<button type="button" onClick={onDismiss} aria-label="Fechar">×</button></div>;
}

export function PermissionState({title = 'Você não tem acesso a este conteúdo', detail, actionLabel, onAction}) {
  return <section className="cadu-ds-permission-state"><h2>{title}</h2>{detail && <p>{detail}</p>}{actionLabel && <button type="button" onClick={onAction}>{actionLabel}</button>}</section>;
}

export function LoadingSkeleton({lines = 3, className = ''}) {
  return <div className={`cadu-ds-skeleton ${className}`} aria-busy="true" aria-label="Carregando">{Array.from({length: lines}, (_, index) => <i key={index}/>)}</div>;
}
