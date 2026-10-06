import React from 'react';
import {FormatPreview} from './FormatPreview.jsx';
import {SelectionButton} from './PlannerUi.jsx';
import {moduleUrl} from './api.js';

/** Formats drawn to scale, each with its own way into the plan. */
export function FormatCards({formats, urls, selection, empty = 'Ainda não há formatos cadastrados.'}) {
  if (!formats?.length) return <p className="planner-muted">{empty}</p>;
  return <ul className="pd-formats">{formats.map(format => <li key={format.id}>
    <a href={`${moduleUrl(urls, 'formatos')}/${format.id}`}>
      <FormatPreview dimensions={format.dimensions} name={format.name} type={format.format_type}/>
      <strong>{format.name}</strong>
      <small>{[format.format_type, format.dimensions].filter(Boolean).join(' · ')}</small>
    </a>
    <SelectionButton size="md" quiet selected={selection.isSelected('formatos', format.id)} onToggle={() => selection.toggle('formatos', format.id)}/>
  </li>)}</ul>;
}
