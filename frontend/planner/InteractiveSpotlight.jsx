import React, {useEffect, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {catalogDetailUrl, itemKey} from './Catalog.jsx';

const LIMIT = 6;
const INTERVAL = 3800;
// Drag-like pieces show a sliding hand; the rest show a tap.
const DRAG = /drag|swipe|wipe|reveal|scratch|carrou?sel|gallery|360|spin|cards|path/i;

const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/**
 * Top of the Interativos shelf: what these pieces are, and a few of them in motion (their real covers cycling like a GIF,
 * with the gesture the person makes). "Testar a peça" opens the live creative.
 */
export function InteractiveSpotlight({records, urls, selection}) {
  const featured = records.filter(item => item.image_url && item.creative_url).slice(0, LIMIT);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (paused || featured.length < 2 || reducedMotion()) return undefined;
    const timer = window.setInterval(() => setIndex(value => (value + 1) % featured.length), INTERVAL);
    return () => window.clearInterval(timer);
  }, [paused, featured.length]);
  if (!featured.length) return null;

  const current = featured[Math.min(index, featured.length - 1)];
  const key = itemKey(current);
  const selected = selection.isSelected('interativos', key);
  const gesture = DRAG.test(current.name) ? 'drag' : 'tap';
  return <section className="ix-spot" aria-labelledby="ix-spot-title" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
    <div className="ix-spot__copy">
      <span className="ix-spot__eyebrow">Interativos</span>
      <h2 id="ix-spot-title">Peças que a pessoa toca, arrasta e joga</h2>
      <p>O banner deixa de ser só visto: a pessoa gira, raspa, arrasta ou responde. Isso segura a atenção por mais tempo e devolve
        dados de interação para otimizar a campanha.</p>
      <div className="ix-spot__now" aria-live="polite">
        <strong>{current.name}</strong>
        {current.purpose && <em>{current.purpose}</em>}
        <span>{current.description}</span>
      </div>
      <div className="ix-spot__actions">
        <CaduButton href={current.creative_url} target="_blank" rel="noreferrer noopener"><Icon name="external" size={16}/>Testar a peça</CaduButton>
        <CaduButton variant="secondary" href={catalogDetailUrl(urls, 'interativos', current)}>Ver ficha</CaduButton>
        <CaduButton variant="tertiary" onClick={() => selection.toggle('interativos', key)}>
          <Icon name={selected ? 'check' : 'plus'} size={16}/>{selected ? 'No plano' : 'Adicionar ao plano'}</CaduButton>
      </div>
    </div>
    <div className="ix-spot__stage">
      <div className="ix-spot__phone" aria-hidden="true">
        {featured.map((item, position) => <img key={itemKey(item)} src={item.image_url} alt=""
          className={position === index ? 'is-current' : ''}/>)}
        <span key={`${key}-${gesture}`} className={`ix-spot__hand ix-spot__hand--${gesture}`}><svg width="28" height="28" viewBox="0 0 24 24" fill="#fff" stroke="#101828" strokeWidth="1.4" strokeLinejoin="round">
          <path d="M9 11V5.5a1.5 1.5 0 0 1 3 0V10m0-.5V8.5a1.5 1.5 0 0 1 3 0V11m0-1a1.5 1.5 0 0 1 3 0v4.5A6.5 6.5 0 0 1 11.5 21h-.6a6 6 0 0 1-4.6-2.2L3.5 15.3a1.6 1.6 0 0 1 2.4-2.1L9 15.5V11"/></svg></span>
      </div>
      <ol className="ix-spot__thumbs" aria-label="Interativos em destaque">
        {featured.map((item, position) => <li key={itemKey(item)}>
          <button type="button" aria-label={`Mostrar ${item.name}`} aria-current={position === index ? 'true' : undefined}
            className={position === index ? 'is-current' : ''} onClick={() => setIndex(position)}><img src={item.image_url} alt=""/></button>
        </li>)}
      </ol>
    </div>
  </section>;
}
