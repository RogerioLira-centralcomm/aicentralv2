import React from 'react';
import {Icon} from './Icon';

/**
 * Descoberta da Home. `mode` decide o quanto mostrar:
 *  - full: cartões com imagem e texto + guias (conta nova, desktop);
 *  - compact: cartões menores, sem guias (conta com trabalho em andamento);
 *  - mobile: só imagem e título, em grade 2x2.
 */
export function HomeExplore({explore, mode = 'full'}) {
  const items = explore?.items || [];
  if (!items.length) return null;
  const guides = mode === 'full' ? explore.guides || [] : [];
  return <section className={`cadu-ds-home-explore is-${mode}`} aria-label="Explore o Planner">
    {mode !== 'mobile' && <header><h2>{mode === 'full' ? 'Explore o Planner' : 'Explore'}</h2></header>}
    <div className="cadu-ds-home-explore__grid">
      {items.map(item => <a key={item.id} className={`cadu-ds-home-explore__card is-${item.id}`} href={item.href}>
        <img src={item.image} alt="" loading="lazy" decoding="async"/>
        <span className="cadu-ds-home-explore__label">{item.title}</span>
        {mode !== 'mobile' && <b>{item.headline}</b>}
        {mode === 'full' && <small>{item.text}</small>}
        {mode !== 'mobile' && <span className="cadu-ds-home-explore__cta">{item.cta}<Icon name="chevron" size={14}/></span>}
      </a>)}
    </div>
    {guides.length > 0 && <div className="cadu-ds-home-guides"><header><h2>Comece por aqui</h2><p>Atalhos para o primeiro resultado em cada solução.</p></header>
      <div>{guides.map(guide => <a key={guide.id} href={guide.href}><span><b>{guide.title}</b><small>{guide.text}</small></span><Icon name="chevron" size={16}/></a>)}</div>
    </div>}
  </section>;
}

/** Retomada para quem já tem conversas, projetos ou marcas. */
export function HomeContinue({items, isMobile, onOpen}) {
  const list = items.slice(0, isMobile ? 3 : 6);
  if (!list.length) return null;
  return <section className="cadu-ds-home-continue" aria-label="Continue de onde parou">
    <header><h2>Continue de onde parou</h2></header>
    <div>{list.map(item => <a key={item.key} href={item.href || '#'} onClick={item.href ? undefined : event => { event.preventDefault(); onOpen?.(item.raw); }}>
      <span className="cadu-ds-home-continue__kind">{item.kind}</span><b>{item.title}</b>{item.context && <small>{item.context}</small>}
    </a>)}</div>
  </section>;
}
