import React from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {FormatPreview} from './FormatPreview.jsx';
import {moduleUrl} from './api.js';

/** Formats drawn to scale. The whole card picks it (one click, no button per card); details are a link. */
export function FormatCards({formats, urls, selection, empty = 'Ainda não há formatos cadastrados.'}) {
  if (!formats?.length) return <p className="planner-muted">{empty}</p>;
  const picked = formats.filter(format => selection.isSelected('formatos', format.id)).length;
  return <>
    <ul className="pd-formats pd-formats--pick">{formats.map(format => {
      const selected = selection.isSelected('formatos', format.id);
      return <li key={format.id} className={selected ? 'is-selected' : ''}>
        <button type="button" aria-pressed={selected} onClick={() => selection.toggle('formatos', format.id)}>
          <span className="pd-formats__tick" aria-hidden="true"><Icon name={selected ? 'check' : 'plus'} size={14}/></span>
          <FormatPreview dimensions={format.dimensions} name={format.name} type={format.format_type}/>
          <strong>{format.name}</strong>
          <small>{[format.format_type, format.dimensions].filter(Boolean).join(' · ')}</small>
        </button>
        <a href={`${moduleUrl(urls, 'formatos')}/${format.id}`}>Ver detalhes</a>
      </li>;
    })}</ul>
    <p className="pd-formats__hint" aria-live="polite">{picked ? `${picked} ${picked === 1 ? 'formato escolhido' : 'formatos escolhidos'}` : 'Toque nos formatos para escolher.'}</p>
  </>;
}
