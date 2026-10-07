import React from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {newPlanUrl} from './api.js';

const ART = '/static/images/planner/illustrations/';

/** Full-width invitation between shelf rows. The art carries no text; the words are live. */
export function PlanBanner({urls}) {
  return <section className="plan-banner" aria-label="Planejar com ajuda" style={{backgroundImage: `url(${ART}banner-planejar.webp)`}}>
    <div className="plan-banner__copy">
      <h2>Não sabe por onde começar?</h2>
      <p>Conte o objetivo e o Cadu monta o plano com você: canais, formatos e audiências.</p>
    </div>
    <CaduButton href={newPlanUrl(urls)}>Planejar<Icon name="chevron" size={16}/></CaduButton>
  </section>;
}

/** Empty shelf: the mascot, a plain sentence and the way out. */
export function ShelfEmpty({title, description, action}) {
  return <div className="shelf-empty" role="status">
    <img src={`${ART}mascote-planner.webp`} alt="" loading="lazy"/>
    <h2>{title}</h2>
    <p>{description}</p>
    {action}
  </div>;
}
