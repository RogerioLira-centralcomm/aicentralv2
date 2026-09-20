import React from 'react';

export function ResumeCard({item, onOpen}) {
  return <article className="cadu-ds-resume-card"><button type="button" onClick={() => onOpen?.(item)}><div className="cadu-ds-resume-preview">{item.previewUrl ? <img src={item.previewUrl} alt=""/> : <span>{item.preview || 'Visualização indisponível'}</span>}</div><div className="cadu-ds-resume-copy"><b>{item.title}</b><small>{item.context}</small><em>{item.status}</em></div><i aria-hidden="true">›</i></button></article>;
}

export function ResumeCardCollection({items = [], onOpen, title = 'Continue de onde parou', actionLabel = 'Ver atividade recente', onOpenActivity}) {
  if (!items.length) return null;
  return <section className="cadu-ds-resume-collection"><h2>{title}</h2><div>{items.slice(0, 3).map(item => <ResumeCard key={item.id} item={item} onOpen={onOpen}/>)}</div>{onOpenActivity && <button type="button" className="cadu-ds-text-action" onClick={onOpenActivity}>{actionLabel} ›</button>}</section>;
}
