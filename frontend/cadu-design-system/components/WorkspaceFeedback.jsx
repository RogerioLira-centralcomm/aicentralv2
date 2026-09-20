import React, {useState} from 'react';
import {VisualIdentity} from './VisualIdentity';
import {CaduDialog} from './CaduDialog';

export function AgentActionDrop({action, onOpen, onDragStart}) {
  if (!action) return null;
  return <button type="button" draggable className="cadu-ds-agent-action" onClick={() => onOpen?.(action)} onDragStart={event => { event.dataTransfer.setData('application/x-cadu-item', JSON.stringify({type: 'agent_action', id: action.id})); onDragStart?.(event, action); }}><b>{action.title}</b><small>{action.summary}</small><span>Usar no chat</span></button>;
}

export function ActivityDrawer({open, title = 'Atividade recente', items = [], onClose, onOpenItem}) {
  if (!open) return null;
  return <aside className="cadu-ds-activity-drawer" role="dialog" aria-modal="true" aria-label={title}><header><h2>{title}</h2><button type="button" onClick={onClose} aria-label="Fechar atividade">×</button></header><div>{items.map(item => <button key={item.id} type="button" onClick={() => onOpenItem?.(item)}><span>{item.icon || '•'}</span><p><b>{item.title}</b><small>{item.detail}</small></p><time>{item.time}</time></button>)}</div></aside>;
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
  return <CaduDialog className="cadu-ds-shortcut-dialog" label="Personalizar dock" onClose={onClose}><header><div><h2>Atalhos da dock</h2><p>Arraste para ordenar. Marcas e projetos com logo aparecem na barra.</p></div><button type="button" onClick={onClose} aria-label="Fechar">×</button></header><div className="cadu-ds-shortcut-grid">{items.map(item => <article key={item.id} draggable={item.pinned} onDragStart={() => setDraggedId(item.id)} onDragEnd={() => setDraggedId('')} onDragOver={event => item.pinned && event.preventDefault()} onDrop={() => dropOn(item)} className={item.pinned ? 'is-pinned' : ''}><VisualIdentity src={item.logoUrl || item.previewUrl} initials={item.visualInitials} label={item.title} color={item.visualColor}/><b>{item.title}</b><button type="button" onClick={() => onToggle?.(item)}>{item.pinned ? 'Remover' : 'Adicionar'}</button></article>)}</div></CaduDialog>;
}

export function WorkspaceAccountMenu({open, onClose, user = {}, links = {}, onManageShortcuts}) {
  if (!open) return null;
  return <CaduDialog className="cadu-ds-account-menu" label="Conta e gestão" onClose={onClose}><header><div className="cadu-ds-account-menu__identity"><b>{user.name || 'Minha conta'}</b>{user.email && <small>{user.email}</small>}</div><button type="button" onClick={onClose} aria-label="Fechar conta">×</button></header><nav aria-label="Conta e gestão">
    <a href={links.profile}>Perfil</a><a href={links.usage}>Créditos e consumo</a><a href={links.plans}>Planos</a><a href={links.team}>Equipe</a>{links.observability && <a href={links.observability}>Observabilidade</a>}
  </nav><footer><button type="button" onClick={onManageShortcuts}>Personalizar atalhos</button><a href={links.logout}>Sair</a></footer></CaduDialog>;
}

export function WorkspaceAccountControl({user = {}, onOpen}) {
  const name = user.name || 'Minha conta';
  return <button type="button" className="cadu-ds-home-account cadu-ds-home-account--identity" onClick={onOpen} aria-label={`Abrir conta de ${name}`} aria-haspopup="dialog">
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
