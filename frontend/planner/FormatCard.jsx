import React from 'react';
import {FormatPreview} from './FormatPreview.jsx';
import {LogoTile, SelectionButton} from './PlannerUi.jsx';
import {catalogDetailUrl} from './Catalog.jsx';

/**
 * A format as a shelf item: the piece drawn to scale on a quiet stage (a real
 * reference image when the catalog has one), its size and type, where it runs
 * and one clear action. No prices: media is quoted.
 */
export function FormatCard({item, urls, selected, onToggle}) {
  const places = item.runs_on || [];
  return <article className={`planner-card channel-card format-card${selected ? ' is-selected' : ''}`}>
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'formatos', item)} aria-label={`Ver formato ${item.name}`}/>
    <span className="format-card__stage">
      {item.image_url ? <img src={item.image_url} alt="" loading="lazy"/> : <FormatPreview dimensions={item.dimensions} name={item.name} type={item.format_type}/>}
    </span>
    <div className="channel-card__body">
      <strong className="planner-card__title">{item.name}</strong>
      <span className="format-card__chips">
        {item.dimensions && <span>{String(item.dimensions).split(/\s*[|;]\s*/)[0]}</span>}
        {item.format_type && <span>{item.format_type}</span>}
      </span>
      {places.length > 0 && <span className="format-card__runs"><small>Roda em</small>
        {places.slice(0, 4).map(place => <LogoTile key={place.name} src={place.logo} name={place.name} icon="share" size="xs"/>)}
        {places.length > 4 && <small>+{places.length - 4}</small>}</span>}
      <div className="channel-card__foot"><SelectionButton size="md" quiet selected={selected} onToggle={onToggle}/></div>
    </div>
  </article>;
}
