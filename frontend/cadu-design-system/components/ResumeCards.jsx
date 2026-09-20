import React from 'react';
import {VisualIdentity} from './VisualIdentity';

export function ResumeCard({item, featured = false, onOpen}) {
  const typeLabel = {conversation: 'Conversa', artifact: 'Artefato', plan: 'Plano', source: 'Fonte', project: 'Projeto'}[item.kind] || 'Trabalho';
  return <article className="cadu-ds-resume-row"><button type="button" onClick={() => onOpen?.(item)}>{item.previewUrl ? <VisualIdentity src={item.previewUrl} initials="" label="" color={item.visualColor}/> : <span className="cadu-ds-resume-type" aria-hidden="true">{typeLabel.slice(0, 1)}</span>}<span className="cadu-ds-resume-copy"><small>{typeLabel}{item.context ? ` · ${item.context}` : ''}</small><b>{item.title}</b><em>{item.status}</em></span><i aria-hidden="true">›</i></button></article>;
}

export function ResumeCardCollection({items = [], onOpen, title = 'Continue de onde parou', actionLabel = 'Ver atividade recente', onOpenActivity}) {
  if (!items.length) return null;
  return <section className="cadu-ds-resume-collection"><header><h2>{title}</h2>{onOpenActivity && <button type="button" className="cadu-ds-text-action" onClick={onOpenActivity}>{actionLabel} ›</button>}</header><div>{items.slice(0, 5).map((item, index) => <ResumeCard key={item.id} item={item} featured={index === 0} onOpen={onOpen}/>)}</div></section>;
}
