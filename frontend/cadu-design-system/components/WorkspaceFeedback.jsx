import React from 'react';

export function AgentActionDrop({action, onOpen, onDragStart}) {
  if (!action) return null;
  return <button type="button" draggable className="cadu-ds-agent-action" onClick={() => onOpen?.(action)} onDragStart={event => { event.dataTransfer.setData('application/x-cadu-item', JSON.stringify({type: 'agent_action', id: action.id})); onDragStart?.(event, action); }}><b>{action.title}</b><small>{action.summary}</small><span>Usar no chat</span></button>;
}

export function ActivityDrawer({open, title = 'Atividade recente', items = [], onClose, onOpenItem}) {
  if (!open) return null;
  return <aside className="cadu-ds-activity-drawer" role="dialog" aria-modal="true" aria-label={title}><header><h2>{title}</h2><button type="button" onClick={onClose} aria-label="Fechar atividade">×</button></header><div>{items.map(item => <button key={item.id} type="button" onClick={() => onOpenItem?.(item)}><span>{item.icon || '•'}</span><p><b>{item.title}</b><small>{item.detail}</small></p><time>{item.time}</time></button>)}</div></aside>;
}

export function ShortcutManagerDialog({open, items = [], onClose, onToggle, onMove}) {
  if (!open) return null;
  const pinnedCount = items.filter(item => item.pinned).length;
  return <dialog open className="cadu-ds-dialog" aria-label="Personalizar dock"><header><div><h2>Personalizar dock</h2><p>Fixe, remova ou reorganize seus atalhos.</p></div><button type="button" onClick={onClose} aria-label="Fechar">×</button></header><div className="cadu-ds-shortcut-list">{items.map((item, index) => <div key={item.id}><span>{item.title}</span><button type="button" onClick={() => onToggle?.(item)}>{item.pinned ? 'Remover' : 'Fixar'}</button><button type="button" disabled={!item.pinned || !index} onClick={() => onMove?.(item, -1)} aria-label={`Mover ${item.title} para cima`}>↑</button><button type="button" disabled={!item.pinned || index === pinnedCount - 1} onClick={() => onMove?.(item, 1)} aria-label={`Mover ${item.title} para baixo`}>↓</button></div>)}</div></dialog>;
}

export function WorkspaceAccountMenu({open, onClose, user = {}, links = {}, onManageShortcuts}) {
  if (!open) return null;
  return <dialog open className="cadu-ds-dialog cadu-ds-account-menu" aria-label="Conta e gestão"><header><div className="cadu-ds-account-menu__identity"><b>{user.name || 'Minha conta'}</b>{user.email && <small>{user.email}</small>}</div><button type="button" onClick={onClose} aria-label="Fechar conta">×</button></header><nav aria-label="Conta e gestão">
    <a href={links.profile}>Perfil</a><a href={links.usage}>Créditos e consumo</a><a href={links.plans}>Planos</a><a href={links.team}>Equipe</a>{links.observability && <a href={links.observability}>Observabilidade</a>}
  </nav><footer><button type="button" onClick={onManageShortcuts}>Personalizar atalhos</button><a href={links.logout}>Sair</a></footer></dialog>;
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
