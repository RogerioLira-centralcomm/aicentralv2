import React, {useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {SelectionButton} from './PlannerUi.jsx';
import {catalogDetailUrl} from './Catalog.jsx';

const percent = value => Number(value) > 0 ? `${String(Number(value)).replace('.', ',')}%` : '';

/** Channel as a shelf item: real photo, identity, the numbers that help choose, and one action. No prices: media is quoted. */
export function ChannelCard({item, urls, selected, onToggle}) {
  const [imageFailed, setImageFailed] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);
  const photo = item.image_url && !imageFailed;
  const metrics = [['Alcance', item.audience], ['Viewability', percent(item.viewability)], ['Conclusão', percent(item.completion_rate)]]
    .filter(([, value]) => value).slice(0, 3);
  const logo = item.logo_path && !logoFailed;
  const inPlan = selected && <span className="planner-card__inplan"><Icon name="check" size={12}/>No plano</span>;
  return <article className={`planner-card channel-card${selected ? ' is-selected' : ''}`}>
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'canais', item)} aria-label={`Ver canal ${item.name}`}/>
    <span className={`channel-card__photo${photo ? '' : ' is-logo'}`} style={!photo && item.cor ? {'--channel-tint': item.cor} : undefined}>
      {photo ? <img src={item.image_url} alt="" loading="lazy" onError={() => setImageFailed(true)}/>
        : logo ? <img className="channel-card__logo" src={item.logo_path} alt="" loading="lazy" onError={() => setLogoFailed(true)}/>
          : <Icon name="share" size={32}/>}
      {item.category && <span className="channel-card__badge">{item.category}</span>}
      {inPlan}
    </span>
    <div className="channel-card__body">
      <strong className="planner-card__title">{item.name}</strong>
      {item.role && <span className="channel-card__role">{item.role}</span>}
      <span className="planner-card__text">{item.description || 'Referência para apoiar as decisões do plano.'}</span>
      {metrics.length > 0 && <dl className="channel-card__metrics">{metrics.map(([label, value]) => <div key={label}><dt>{label}</dt><dd title={value}>{value}</dd></div>)}</dl>}
      <div className="channel-card__actions"><SelectionButton size="md" selected={selected} onToggle={onToggle}/></div>
    </div>
  </article>;
}
