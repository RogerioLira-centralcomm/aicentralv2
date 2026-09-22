import React, {useState} from 'react';
import {CaduDialog} from './CaduDialog';
import {Icon} from './Icon';

const kindLabel = {complete: 'Concluído', attention: 'Requer atenção', approval: 'Aprovação', progress: 'Em andamento'};

export function WorkspaceNotificationCenter({items = [], onClose, onOpenItem}) {
  const [filter, setFilter] = useState('all');
  const pending = items.filter(item => item.kind === 'approval' || item.kind === 'attention').length;
  const visible = filter === 'attention' ? items.filter(item => item.kind === 'approval' || item.kind === 'attention') : filter === 'complete' ? items.filter(item => item.kind === 'complete') : items;
  return <CaduDialog className="cadu-ds-notification-center" label="Notificações" onClose={onClose}>
    <header><div><p>Central de atividade</p><h2>Notificações</h2><span>{pending ? `${pending} item${pending === 1 ? '' : 's'} aguardando você` : 'Nenhuma decisão pendente'}</span></div><button type="button" onClick={onClose} aria-label="Fechar notificações">×</button></header>
    <nav aria-label="Filtros de notificações">{[['all','Todas'],['attention','Atenção'],['complete','Concluídas']].map(([id,label]) => <button type="button" key={id} className={filter === id ? 'is-active' : ''} onClick={() => setFilter(id)}>{label}</button>)}</nav>
    <div className="cadu-ds-notification-center__list">{visible.length ? visible.map(item => <button type="button" key={item.id} className={`is-${item.kind || 'complete'}`} onClick={() => onOpenItem?.(item)}><span className="cadu-ds-notification-center__icon"><Icon name={item.kind === 'approval' ? 'pulse' : item.kind === 'attention' ? 'history' : 'file'} size={15}/></span><span><small>{kindLabel[item.kind] || 'Atualização'}{item.context ? ` · ${item.context}` : ''}</small><b>{item.title}</b>{item.detail && <em>{item.detail}</em>}</span><i aria-hidden="true">›</i></button>) : <p>{items.length ? 'Nenhuma notificação neste filtro.' : 'Trabalhos concluídos, perguntas do agente e aprovações aparecerão aqui.'}</p>}</div>
  </CaduDialog>;
}
