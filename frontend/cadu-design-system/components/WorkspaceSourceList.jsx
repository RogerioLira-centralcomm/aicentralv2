import React from 'react';
import {Icon} from './Icon';

export function WorkspaceSourceList({items = []}) {
  const sources = items.filter(item => item?.title || item?.href);
  if (!sources.length) return null;
  return <details className="cadu-ds-source-list" open={sources.length <= 3}>
    <summary><span><Icon name="external" size={14}/><b>{sources.length} {sources.length === 1 ? 'fonte consultada' : 'fontes consultadas'}</b></span><i>Ver fontes</i></summary>
    <div>
      {sources.slice(0, 8).map((source, index) => source.href ? <a key={`${source.href}-${index}`} href={source.href} target="_blank" rel="noreferrer"><span>{index + 1}</span><strong>{source.title || 'Fonte'}</strong><Icon name="external" size={13}/></a> : <span key={`${source.title}-${index}`}><span>{index + 1}</span><strong>{source.title || 'Fonte'}</strong></span>)}
    </div>
  </details>;
}
