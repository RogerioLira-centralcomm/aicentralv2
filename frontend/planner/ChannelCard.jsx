import React, {useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {LogoTile, SelectionButton} from './PlannerUi.jsx';
import {catalogDetailUrl} from './Catalog.jsx';

const percent = value => Number(value) > 0 ? `${String(Number(value)).replace('.', ',')}%` : '';

/** Channel as a shelf item: real photo, identity, the numbers that help choose, and one action. No prices: media is quoted. */
export function ChannelCard({item, urls, selected, onToggle}) {
  const [imageFailed, setImageFailed] = useState(false);
  const photo = item.image_url && !imageFailed;
  const metrics = [['Alcance', item.audience], ['Viewability', percent(item.viewability)], ['Conclusão', percent(item.completion_rate)]]
    .filter(([, value]) => value).slice(0, 3);
  return <article className={`planner-card channel-card${selected ? ' is-selected' : ''}`}>
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'canais', item)} aria-label={`Ver canal ${item.name}`}/>
    {photo && <span className="channel-card__photo">
      <img src={item.image_url} alt="" loading="lazy" onError={() => setImageFailed(true)}/>
      {item.category && <span className="channel-card__badge">{item.category}</span>}
      {selected && <span className="planner-card__inplan"><Icon name="check" size={12}/>No plano</span>}
    </span>}
    <div className="channel-card__body">
      <span className="planner-card__identity">
        <LogoTile src={item.logo_path} name={item.name} icon="share" size="sm" color={item.cor}/>
        {!photo && item.category && <span className="planner-card__eyebrow">{item.category}</span>}
        {!photo && selected && <span className="planner-card__inplan"><Icon name="check" size={12}/>No plano</span>}
      </span>
      <strong className="planner-card__title">{item.name}</strong>
      {item.role && <span className="channel-card__role">{item.role}</span>}
      <span className="planner-card__text">{item.description || 'Referência para apoiar as decisões do plano.'}</span>
      {metrics.length > 0 && <dl className="channel-card__metrics">{metrics.map(([label, value]) => <div key={label}><dt>{label}</dt><dd title={value}>{value}</dd></div>)}</dl>}
      <div className="channel-card__actions"><SelectionButton selected={selected} onToggle={onToggle}/></div>
    </div>
  </article>;
}
