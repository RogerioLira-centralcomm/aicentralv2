import React, {Fragment, useEffect, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {moduleUrl, newPlanUrl} from './api.js';

const ART = '/static/images/planner/illustrations/';

const BANNERS = {
  planejar: {title: 'Não sabe por onde começar?', text: 'Conte o objetivo e o Cadu monta o plano com você: canais, formatos e audiências.', label: 'Planejar', href: urls => newPlanUrl(urls)},
  formatos: {title: 'Qual formato combina com a sua mensagem?', text: 'Veja tamanhos, exemplos e especificações antes de pedir o material.', label: 'Conhecer formatos', href: urls => moduleUrl(urls, 'formatos')},
  canais: {title: 'Onde a sua marca pode aparecer?', text: 'Compare canais por alcance e perfil de público e escolha onde investir.', label: 'Explorar canais', href: urls => moduleUrl(urls, 'canais')},
};

/** Full-width invitation between shelf rows. The art carries no text; the words are live. `variant` picks the pitch and where it leads. */
export function PlanBanner({urls, variant = 'planejar'}) {
  const banner = BANNERS[variant] || BANNERS.planejar;
  return <section className="plan-banner" aria-label={banner.title} style={{backgroundImage: `url(${ART}banner-planejar.webp)`}}>
    <div className="plan-banner__copy">
      <h2>{banner.title}</h2>
      <p>{banner.text}</p>
    </div>
    <CaduButton href={banner.href(urls)}>{banner.label}<Icon name="chevron" size={16}/></CaduButton>
  </section>;
}

/** Number of columns the browser actually lays a grid out in (follows the screen, not a guess). */
function useColumns(ref) {
  const [columns, setColumns] = useState(4);
  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    const measure = () => setColumns(Math.max(1, getComputedStyle(node).gridTemplateColumns.split(' ').filter(Boolean).length));
    measure();
    if (!('ResizeObserver' in window)) return undefined;
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref]);
  return columns;
}

/**
 * A shelf grid with an invitation after every two rows (8 cards on four columns, 6 on three, 4 on a single column),
 * rotating through `variants`. The banner never closes the shelf: it only goes between cards.
 */
export function ShelfGrid({items, render, urls, variants = ['planejar'], className = 'planner-grid planner-grid--channels', ...rest}) {
  const ref = useRef(null);
  const columns = useColumns(ref);
  const every = columns === 1 ? 4 : columns * 2;
  return <div ref={ref} className={className} {...rest}>
    {items.map((item, index) => <Fragment key={index}>
      {render(item, index)}
      {(index + 1) % every === 0 && index < items.length - 1 && <div className="planner-grid__span"><PlanBanner urls={urls} variant={variants[(Math.floor((index + 1) / every) - 1) % variants.length]}/></div>}
    </Fragment>)}
  </div>;
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
