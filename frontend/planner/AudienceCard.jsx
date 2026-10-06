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

/**
 * Audience as a shelf item: the size leads, the platform it is bought on is
 * the visual, and one clear action. No prices: media is quoted.
 */
export function AudienceCard({item, urls, selected, onToggle}) {
  const [imageFailed, setImageFailed] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);
  const photo = item.image_url && !imageFailed;
  const logo = item.platform_logo && !logoFailed;
  const figure = audienceFigure(item);
  const traits = [item.perfil_socioeconomico && `Classe ${item.perfil_socioeconomico}`, item.propensao_compra && `Compra: ${item.propensao_compra}`].filter(Boolean);
  return <article className={`planner-card channel-card audience-card${selected ? ' is-selected' : ''}`}>
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'audiencias', item)} aria-label={`Ver audiência ${item.name}`}/>
    <span className={`channel-card__photo audience-card__art${photo ? '' : ' is-logo'}`}>
      {photo ? <img src={item.image_url} alt="" loading="lazy" onError={() => setImageFailed(true)}/>
        : logo ? <img className="channel-card__logo" src={item.platform_logo} alt="" loading="lazy" onError={() => setLogoFailed(true)}/>
          : <Icon name="users" size={32}/>}
      {item.category && <span className="channel-card__badge">{item.category}</span>}
      {photo && logo && <span className="channel-card__mark"><img src={item.platform_logo} alt="" onError={() => setLogoFailed(true)}/></span>}
    <span className="channel-card__cta"><SelectionButton size="md" selected={selected} onToggle={onToggle}/></span>
    </span>
    <div className="channel-card__body">
      {item.platform && <span className="channel-card__role">{item.platform}</span>}
      <strong className="planner-card__title">{item.name}</strong>
      <span className="planner-card__text">{item.description || 'Público para apoiar as decisões do plano.'}</span>
      {(figure || traits.length > 0) && <div className="audience-card__numbers">
        {figure && <div className="audience-card__size"><strong>{figure}</strong><span>de pessoas</span></div>}
        {traits.length > 0 && <ul>{traits.map(value => <li key={value}>{value}</li>)}</ul>}
      </div>}
    </div>
  </article>;
}
