import React, {useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {SelectionButton} from './PlannerUi.jsx';
import {catalogDetailUrl} from './Catalog.jsx';

/** "86,6 mi" from the numeric size; the stored text only when it is itself a short figure. */
export function audienceFigure(item) {
  const size = Number(item.audience_size);
  if (size > 0) return size.toLocaleString('pt-BR', {notation: 'compact', maximumFractionDigits: 1});
  const text = String(item.audience || item.tamanho || '').trim();
  return /\d/.test(text) && text.length <= 14 ? text : '';
}

const AGE_BANDS = [['idade_18_24', '18-24'], ['idade_25_34', '25-34'], ['idade_35_44', '35-44'], ['idade_45_mais', '45+']];

/** The age band that holds most of the audience, from the stored shares; nothing when they are missing. */
function dominantAge(item) {
  const best = AGE_BANDS.map(([key, label]) => [Number(item[key]) || 0, label]).sort((a, b) => b[0] - a[0])[0];
  return best && best[0] > 0 ? `${best[1]} anos` : '';
}

/** The numbers that help choose, each with its small standard icon; a missing one is left out, never invented. */
function audienceStats(item, figure) {
  return [
    ['users', 'Público', figure],
    ['wallet', 'Perfil', item.perfil_socioeconomico && `Classe ${item.perfil_socioeconomico}`],
    ['calendar', 'Idade', dominantAge(item)],
  ].filter(([, , value]) => value);
}

/**
 * Audience as a shelf item, same anatomy as the channel card: the photo leads, the add button appears on hover,
 * the channel it is bought on is the logo mark. No chips inside chips: facts are icon + label + value. No prices.
 */
export function AudienceCard({item, urls, selected, onToggle}) {
  const [imageFailed, setImageFailed] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);
  const photo = item.image_url && !imageFailed;
  const logo = item.platform_logo && !logoFailed;
  const stats = audienceStats(item, audienceFigure(item));
  return <article className={`planner-card channel-card audience-card${selected ? ' is-selected' : ''}`}>
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'audiencias', item)} aria-label={`Ver audiência ${item.name}`}/>
    <span className={`channel-card__photo audience-card__art${photo ? '' : ' is-logo'}`}>
      {photo ? <img src={item.image_url} alt="" loading="lazy" onError={() => setImageFailed(true)}/>
        : logo ? <img className="channel-card__logo" src={item.platform_logo} alt="" loading="lazy" onError={() => setLogoFailed(true)}/>
          : <Icon name="users" size={32}/>}
      {item.category && <span className="channel-card__badge">{item.category}</span>}
      {photo && logo && <span className="channel-card__mark" title={item.platform}><img src={item.platform_logo} alt={item.platform || ''} onError={() => setLogoFailed(true)}/></span>}
      <span className="channel-card__cta"><SelectionButton size="md" selected={selected} onToggle={onToggle}/></span>
    </span>
    <div className="channel-card__body">
      {item.platform && !logo && <span className="channel-card__role">{item.platform}</span>}
      <strong className="planner-card__title">{item.name}</strong>
      <span className="planner-card__text">{item.description || 'Público para apoiar as decisões do plano.'}</span>
      {stats.length > 0 && <dl className="channel-card__stats audience-card__stats">{stats.map(([icon, label, value]) => <div key={label}>
        <Icon name={icon} size={16}/><span><dt>{label}</dt><dd>{value}</dd></span></div>)}</dl>}
    </div>
  </article>;
}
