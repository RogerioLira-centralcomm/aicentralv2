import React, {useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {SelectionButton} from './PlannerUi.jsx';
import {catalogDetailUrl} from './Catalog.jsx';

/** A place as a shelf item: its photo, where it is, how many people pass, and one action. No prices: media is quoted. */
export function PlaceCard({item, urls, selected, onToggle}) {
  const [failed, setFailed] = useState(false);
  const photo = item.image_url && !failed;
  const stats = [['users', item.traffic_label || 'Movimento', item.traffic], ['pulse', 'Audiência', item.audience]].filter(([, , value]) => value);
  return <article className={`planner-card channel-card place-card${selected ? ' is-selected' : ''}`}>
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'places', item)} aria-label={`Ver ${item.name}`}/>
    <span className={`channel-card__photo${photo ? '' : ' is-logo'}`}>
      {photo ? <img src={item.image_url} alt="" loading="lazy" onError={() => setFailed(true)}/> : <Icon name="browser" size={32}/>}
      {item.category && <span className="channel-card__badge">{item.category}</span>}
    </span>
    <div className="channel-card__body">
      {item.city && <span className="channel-card__role">{item.city}</span>}
      <strong className="planner-card__title">{item.name}</strong>
      <span className="planner-card__text">{item.description || 'Ponto de mídia com circulação medida.'}</span>
      {stats.length > 0 && <dl className="channel-card__stats">{stats.slice(0, 3).map(([icon, label, value]) => <div key={label}>
        <Icon name={icon} size={16}/><span><dt>{label}</dt><dd title={value}>{value}</dd></span></div>)}</dl>}
      <div className="channel-card__foot"><SelectionButton size="md" quiet selected={selected} onToggle={onToggle}/></div>
    </div>
  </article>;
}
