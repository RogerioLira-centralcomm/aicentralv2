import React, {useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {SelectionButton} from './PlannerUi.jsx';
import {catalogDetailUrl} from './Catalog.jsx';

const percent = value => Number(value) > 0 ? `${String(Number(value)).replace('.', ',')}%` : '';

/**
 * Channel as a shelf item. One number leads (the reach, when it is a number);
 * the rest is quiet. The foot is fixed so every card ends on the same line.
 * No prices: media is quoted.
 */
export function ChannelCard({item, urls, selected, onToggle}) {
  const [imageFailed, setImageFailed] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);
  const photo = item.image_url && !imageFailed;
  const logo = item.logo_path && !logoFailed;
  const stats = [['Viewability', percent(item.viewability)], ['Conclusão', percent(item.completion_rate)]].filter(([, value]) => value);
  const formats = Number(item.formats_count) || 0;
  return <article className={`planner-card channel-card${selected ? ' is-selected' : ''}`}>
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'canais', item)} aria-label={`Ver canal ${item.name}`}/>
    <span className={`channel-card__photo${photo ? '' : ' is-logo'}`}>
      {photo ? <img src={item.image_url} alt="" loading="lazy" onError={() => setImageFailed(true)}/>
        : logo ? <img className="channel-card__logo" src={item.logo_path} alt="" loading="lazy" onError={() => setLogoFailed(true)}/>
          : <Icon name="share" size={32}/>}
      {item.category && <span className="channel-card__badge">{item.category}</span>}
      {selected && <span className="planner-card__inplan"><Icon name="check" size={12}/>No plano</span>}
    </span>
    <div className="channel-card__body">
      {item.role && <span className="channel-card__role">{item.role}</span>}
      <strong className="planner-card__title">{item.name}</strong>
      <span className="planner-card__text">{item.description || 'Referência para apoiar as decisões do plano.'}</span>
      <div className="channel-card__numbers">
        {item.reach_figure ? <p className="channel-card__reach"><strong>{item.reach_figure}</strong><span>{item.reach_unit || 'de alcance'}</span></p> : <p className="channel-card__reach is-empty"/>}
        {stats.length > 0 && <dl className="channel-card__stats">{stats.map(([label, value]) => <div key={label}><dd>{value}</dd><dt>{label}</dt></div>)}</dl>}
      </div>
      <div className="channel-card__foot">
        <span className="channel-card__formats">{formats > 0 ? `${formats} ${formats === 1 ? 'formato' : 'formatos'}` : 'Formatos sob consulta'}</span>
        <SelectionButton quiet selected={selected} onToggle={onToggle}/>
      </div>
    </div>
  </article>;
}
