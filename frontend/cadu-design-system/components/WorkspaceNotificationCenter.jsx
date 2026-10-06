import React, {useState} from 'react';
import {CaduButton} from './CaduButton';
import {CaduDialog} from './CaduDialog';
import {Icon} from './Icon';
import './WorkspaceNotificationCenter.css';

const kindLabel = {complete: 'Concluído', attention: 'Requer atenção', approval: 'Aprovação', progress: 'Em andamento', failure: 'Não concluído'};

function dateLabel(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat('pt-BR', {day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit'}).format(date);
}

function metrics(item) {
  const data = item.action || {};
  return [
    data.pages_analyzed ? [data.pages_analyzed, 'páginas'] : null,
    data.sources_count ? [data.sources_count, 'fontes'] : null,
    data.assets_found ? [data.assets_found, 'ativos'] : null,
    data.fields_generated ? [data.fields_generated, 'dados gerados'] : null,
    data.estimated_hours_saved ? [`${data.estimated_hours_saved} h`, 'economizadas'] : null,
    data.cost_brl ? [`R$ ${Number(data.cost_brl).toFixed(2).replace('.', ',')}`, 'custo de IA'] : null,
    data.item_count ? [data.item_count, 'arquivos'] : null,
    data.processed_count ? [data.processed_count, 'processados'] : null,
  ].filter(Boolean);
}

export function WorkspaceNotificationCenter({items = [], onClose, onOpenItem, onMarkAllRead}) {
  const [filter, setFilter] = useState('all');
  const [markingRead, setMarkingRead] = useState(false);
  const unread = item => !item.readAt && (['unread','waiting_user','failed'].includes(item.status) || ['approval','attention','failure'].includes(item.kind));
  const pending = items.filter(unread).length;
  const visible = filter === 'attention' ? items.filter(item => item.kind === 'approval' || item.kind === 'attention') : filter === 'complete' ? items.filter(item => item.kind === 'complete') : items;
  const markAllRead = async () => {
    if (!onMarkAllRead || !pending || markingRead) return;
    setMarkingRead(true);
    try { await onMarkAllRead(); } finally { setMarkingRead(false); }
  };
  return <CaduDialog className="cadu-ds-notification-center" label="Notificações" onClose={onClose}>
    <header><div><p>Workspace</p><h2>Notificações</h2><span>{pending ? `${pending} não lida${pending === 1 ? '' : 's'}` : 'Você está em dia'}</span></div><CaduButton variant="tertiary" type="button" onClick={onClose} aria-label="Fechar notificações">×</CaduButton></header>
    <nav aria-label="Filtros de notificações">{[['all','Todas'],['attention','Aguardando você'],['complete','Concluídas']].map(([id,label]) => <button type="button" key={id} className={filter === id ? 'is-active' : ''} onClick={() => setFilter(id)}>{label}{id === 'all' && <span>{items.length}</span>}</button>)}</nav>
    <div className="cadu-ds-notification-center__list" aria-live="polite">{visible.length ? visible.map(item => { const itemMetrics = metrics(item); const isUnread = unread(item); return <button type="button" key={item.id} className={`is-${item.kind || 'complete'}${isUnread ? ' is-unread' : ''}`} onClick={() => onOpenItem?.(item)}><span className="cadu-ds-notification-center__icon"><Icon name={item.kind === 'approval' ? 'pulse' : item.kind === 'attention' || item.kind === 'failure' ? 'history' : item.kind === 'progress' ? 'pulse' : 'file'} size={17}/></span><span className="cadu-ds-notification-center__body"><span className="cadu-ds-notification-center__meta"><small>{kindLabel[item.kind] || 'Atualização'}{item.context ? ` · ${item.context}` : ''}</small><time>{dateLabel(item.updatedAt || item.createdAt)}</time></span><b>{item.title}</b>{item.detail && <em>{item.detail}</em>}{itemMetrics.length > 0 && <span className="cadu-ds-notification-center__metrics">{itemMetrics.map(([value,label]) => <span key={label}><strong>{value}</strong><small>{label}</small></span>)}</span>}</span><i className="cadu-ds-notification-center__unread" aria-label={isUnread ? 'Não lida' : undefined}>{isUnread ? '' : '›'}</i></button>; }) : <div className="cadu-ds-notification-center__empty"><span aria-hidden="true"><Icon name="pulse" size={20}/></span><strong>{items.length ? 'Nada por aqui' : 'Nenhuma notificação ainda'}</strong><p>{items.length ? 'Não há notificações nesta categoria.' : 'Quando uma análise, arquivo ou aprovação precisar da sua atenção, ela aparecerá aqui.'}</p></div>}</div>
    <footer><span>{pending ? `${pending} não lida${pending === 1 ? '' : 's'}` : 'Tudo lido'}</span><div><button type="button" className="is-secondary" onClick={onClose}>Fechar</button>{onMarkAllRead && <CaduButton variant="secondary" type="button" onClick={markAllRead} disabled={!pending || markingRead}>{markingRead ? 'Atualizando…' : '✓ Marcar tudo como lido'}</CaduButton>}</div></footer>
  </CaduDialog>;
}
