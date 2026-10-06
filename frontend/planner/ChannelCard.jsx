import React, {useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {LogoTile, SelectionButton} from './PlannerUi.jsx';
import {catalogDetailUrl} from './Catalog.jsx';

const percent = value => Number(value) > 0 ? `${String(Number(value)).replace('.', ',')}%` : '';

/** The three numbers that help choose; a missing one is left out, never invented. */
function channelStats(item) {
  return [
    ['users', 'Alcance', item.reach_figure],
    ['pulse', 'Viewability', percent(item.viewability)],
    ['check', 'Conclusão', percent(item.completion_rate)],
  ].filter(([, , value]) => value);
}

function Stats({item}) {
  const stats = channelStats(item);
  if (!stats.length) return null;
  return <dl className="channel-card__stats">{stats.map(([icon, label, value]) => <div key={label}>
    <Icon name={icon} size={16}/><span><dt>{label}</dt><dd>{value}</dd></span></div>)}</dl>;
}

/**
 * Channel as a shelf item: real photo (or the logo when there is none), the
 * numbers that help choose and one clear action. No prices: media is quoted.
 */
export function ChannelCard({item, urls, selected, onToggle, quoteUrl}) {
  const [imageFailed, setImageFailed] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);
  const photo = item.image_url && !imageFailed;
  const logo = item.logo_path && !logoFailed;
  return <article className={`planner-card channel-card${selected ? ' is-selected' : ''}`}>
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'canais', item)} aria-label={`Ver canal ${item.name}`}/>
    <span className={`channel-card__photo${photo ? '' : ' is-logo'}`}>
      {photo ? <img src={item.image_url} alt="" loading="lazy" onError={() => setImageFailed(true)}/>
        : logo ? <img className="channel-card__logo" src={item.logo_path} alt="" loading="lazy" onError={() => setLogoFailed(true)}/>
          : <Icon name="share" size={32}/>}
      {photo && logo && <span className="channel-card__mark"><img src={item.logo_path} alt="" onError={() => setLogoFailed(true)}/></span>}
      {item.category && <span className="channel-card__badge">{item.category}</span>}
      {item.measurable && <span className="channel-card__measurable">Mensurável</span>}
      {photo && item.image_illustrative && <span className="channel-card__illustration">Ilustração</span>}
    </span>
    <div className="channel-card__body">
      {item.role && <span className="channel-card__role">{item.role}</span>}
      <strong className="planner-card__title">{item.name}</strong>
      <span className="planner-card__text">{item.description || 'Referência para apoiar as decisões do plano.'}</span>
      <Stats item={item}/>
      <div className="channel-card__foot">
        <SelectionButton size="md" quiet selected={selected} onToggle={onToggle}/>
      </div>
    </div>
  </article>;
}

/** Same channel, one dense row for comparing at a glance. */
export function ChannelRow({item, urls, selected, onToggle, quoteUrl}) {
  return <article className={`channel-row${selected ? ' is-selected' : ''}`}>
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'canais', item)} aria-label={`Ver canal ${item.name}`}/>
    <LogoTile src={item.logo_path} name={item.name} icon="share" size="md" color={item.cor}/>
    <span className="channel-row__main">
      <strong>{item.name}</strong>
      <small>{[item.category, item.role].filter(Boolean).join(' · ')}</small>
    </span>
    <span className="channel-row__text">{item.description}</span>
    <Stats item={item}/>
    <span className="channel-row__actions"><SelectionButton size="md" quiet selected={selected} onToggle={onToggle}/></span>
  </article>;
}
