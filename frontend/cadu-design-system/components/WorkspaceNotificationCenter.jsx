import React, {useState} from 'react';
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

export function WorkspaceNotificationCenter({items = [], onClose, onOpenItem}) {
  const [filter, setFilter] = useState('all');
  const pending = items.filter(item => item.kind === 'approval' || item.kind === 'attention').length;
  const visible = filter === 'attention' ? items.filter(item => item.kind === 'approval' || item.kind === 'attention') : filter === 'complete' ? items.filter(item => item.kind === 'complete') : items;
  return <CaduDialog className="cadu-ds-notification-center" label="Notificações" onClose={onClose}>
    <header><div><p>Atividade do Workspace</p><h2>Notificações</h2><span>{pending ? `${pending} item${pending === 1 ? '' : 's'} aguardando você` : 'Análises, arquivos e aprovações em um só lugar'}</span></div><button type="button" onClick={onClose} aria-label="Fechar notificações">×</button></header>
    <nav aria-label="Filtros de notificações">{[['all','Tudo'],['attention','Aguardando você'],['complete','Concluído']].map(([id,label]) => <button type="button" key={id} className={filter === id ? 'is-active' : ''} onClick={() => setFilter(id)}>{label}</button>)}</nav>
    <div className="cadu-ds-notification-center__list">{visible.length ? visible.map(item => { const itemMetrics = metrics(item); return <button type="button" key={item.id} className={`is-${item.kind || 'complete'}`} onClick={() => onOpenItem?.(item)}><span className="cadu-ds-notification-center__icon"><Icon name={item.kind === 'approval' ? 'pulse' : item.kind === 'attention' || item.kind === 'failure' ? 'history' : item.kind === 'progress' ? 'pulse' : 'file'} size={17}/></span><span className="cadu-ds-notification-center__body"><span className="cadu-ds-notification-center__meta"><small>{kindLabel[item.kind] || 'Atualização'}{item.context ? ` · ${item.context}` : ''}</small><time>{dateLabel(item.updatedAt || item.createdAt)}</time></span><b>{item.title}</b>{item.detail && <em>{item.detail}</em>}{itemMetrics.length > 0 && <span className="cadu-ds-notification-center__metrics">{itemMetrics.map(([value,label]) => <span key={label}><strong>{value}</strong><small>{label}</small></span>)}</span>}</span><i aria-hidden="true">›</i></button>; }) : <p>{items.length ? 'Nenhuma atividade neste filtro.' : 'Quando uma análise começar, um arquivo for processado ou uma aprovação estiver pronta, você acompanhará tudo aqui.'}</p>}</div>
  </CaduDialog>;
}
