import React from 'react';
import {Icon} from './Icon';

/**
 * Descoberta da Home. `mode` decide o quanto mostrar:
 *  - full: cartões com imagem e texto + guias (conta nova, desktop);
 *  - compact: cartões menores, sem guias (conta com trabalho em andamento);
 *  - mobile: só imagem e título, em grade 2x2.
 */
const GUIDE_SOLUTION = {plano: 'planner', radar: 'planner', studio: 'studio', reports: 'connect'};

export function HomeExplore({explore, mode = 'full', solutions = {}}) {
  // Only offer what this account can open: the server already filters `solutions` by access.
  const items = solutions.planner ? explore?.items || [] : [];
  if (!items.length) return null;
  const guides = mode === 'full' ? (explore.guides || []).filter(guide => solutions[GUIDE_SOLUTION[guide.id]]) : [];
  return <section className={`cadu-ds-home-explore is-${mode}`} aria-label="Explore o Planner">
    <header><h2>{mode === 'full' ? 'Explore o Planner' : 'Descubra'}</h2></header>
    <div className="cadu-ds-home-explore__grid">
      {items.map(item => <a key={item.id} className={`cadu-ds-home-explore__card is-${item.id}`} href={item.href}>
        <img src={mode === 'full' ? item.image : item.icon || item.image} alt="" loading="lazy" decoding="async"/>
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
  const list = items.slice(0, isMobile ? 2 : 6);
  if (!list.length) return null;
  return <section className="cadu-ds-home-continue" aria-label="Continue de onde parou">
    <header><h2>Continue de onde parou</h2></header>
    <div>{list.map(item => <a key={item.key} href={item.href || '#'} onClick={item.href ? undefined : event => { event.preventDefault(); onOpen?.(item.raw); }}>
      <span className="cadu-ds-home-continue__kind">{item.kind}</span><b>{item.title}</b>{item.context && <small>{item.context}</small>}
    </a>)}</div>
  </section>;
}

const RELATIVE = new Intl.RelativeTimeFormat('pt-BR', {numeric: 'auto'});
function since(iso) {
  const time = Date.parse(iso || '');
  if (!time) return '';
  const days = Math.round((time - Date.now()) / 86400000);
  if (Math.abs(days) >= 1) return RELATIVE.format(days, 'day');
  const hours = Math.round((time - Date.now()) / 3600000);
  return hours ? RELATIVE.format(hours, 'hour') : 'agora';
}

const PULSE_ICON = {reports: 'table', studio: 'compose', plans: 'history', radar: 'pulse'};
const PULSE_ORDER = ['radar', 'studio', 'plans', 'reports'];

function PulseDetail({card}) {
  const detail = card.detail || {};
  if (card.id === 'studio') return <div className="cadu-ds-home-pulse__thumbs">{(detail.thumbs || []).map(src => <img key={src} src={src} alt="" loading="lazy"/>)}{detail.more > 0 && <i>+{detail.more}</i>}</div>;
  if (card.id === 'radar') return <ul>{(detail.radars || []).map(radar => <li key={radar.title}><span>{radar.title}</span><small>{since(radar.at)}</small></li>)}</ul>;
  if (card.id === 'plans') return <p><b>{detail.title}</b><small>{detail.items} {detail.items === 1 ? 'item' : 'itens'} · {since(detail.updatedAt)}</small></p>;
  return <p><b>{detail.title}</b><small>atualizado {since(detail.updatedAt)}</small></p>;
}

/** "Em andamento": um fato real por solução que a conta pode abrir. No mobile, só os dois mais urgentes e sem detalhe visual. */
export function HomePulse({cards = [], solutions = {}, isMobile = false, emptyImage = ''}) {
  const visible = cards.filter(card => solutions[card.solution]).sort((a, b) => PULSE_ORDER.indexOf(a.id) - PULSE_ORDER.indexOf(b.id));
  if (!visible.length) return emptyImage ? <section className="cadu-ds-home-pulse is-empty" aria-label="Em andamento"><img src={emptyImage} alt="" loading="lazy"/><div><h2>Nada em andamento ainda</h2><p>Quando você começar um plano, um criativo ou um relatório, o resumo aparece aqui.</p></div></section> : null;
  const list = isMobile ? visible.slice(0, 2) : visible;
  return <section className={`cadu-ds-home-pulse${isMobile ? ' is-mobile' : ''}`} aria-label="Em andamento">
    <header><h2>Em andamento</h2>{!isMobile && <p>O que mudou desde sua última visita.</p>}</header>
    <div className="cadu-ds-home-pulse__grid">{list.map(card => <a key={card.id} className={`cadu-ds-home-pulse__card is-${card.id}`} href={card.href}>
      <span className="cadu-ds-home-pulse__head"><Icon name={PULSE_ICON[card.id] || 'table'} size={16}/>{card.title}</span>
      <strong>{card.id === 'radar' && !card.count ? 'Sem novidades' : `${card.count} ${card.noun}`}</strong><small>{card.caption}</small>
      {!isMobile && <PulseDetail card={card}/>}
      <span className="cadu-ds-home-explore__cta">{card.cta}<Icon name="chevron" size={14}/></span>
    </a>)}</div>
  </section>;
}
