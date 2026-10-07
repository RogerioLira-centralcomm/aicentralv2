import React, {useEffect, useState} from 'react';
import './planner-shelf.css';

const ART = '/static/images/planner/shelf/';

/**
 * Title of a shelf (Canais, Audiências, Formatos…) as a slim banner: the module's art, one title, one line of context.
 * It is the page's only h1; filters and results follow right below.
 */
export function ShelfBanner({kind, title, description, children = null}) {
  return <header className="shelf-banner" style={{'--shelf-art': `url("${ART}${kind}.webp")`}}>
    <div className="shelf-banner__copy">
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </div>
    {children && <div className="shelf-banner__side">{children}</div>}
  </header>;
}

/** Right-hand index of a grouped shelf: jumps to a group and follows the scroll (same look as the detail pages' index). */
export function ShelfIndex({items, label = 'Nesta página'}) {
  const [current, setCurrent] = useState(items[0]?.id);
  useEffect(() => {
    if (!('IntersectionObserver' in window)) return undefined;
    const observer = new IntersectionObserver(entries => {
      const top = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (top) setCurrent(top.target.id);
    }, {rootMargin: '-96px 0px -60% 0px'});
    items.forEach(item => { const node = document.getElementById(item.id); if (node) observer.observe(node); });
    return () => observer.disconnect();
  }, [items]);
  return <aside className="pd-rail shelf-index"><strong>{label}</strong>
    <nav className="pd-rail__nav" aria-label="Grupos desta página">{items.map(item => <a key={item.id} href={`#${item.id}`} className={current === item.id ? 'is-active' : ''}
      aria-current={current === item.id ? 'true' : undefined}
      onClick={event => { event.preventDefault(); document.getElementById(item.id)?.scrollIntoView({behavior: 'smooth', block: 'start'}); setCurrent(item.id); }}>
      {item.label}<span>{item.count}</span></a>)}</nav>
  </aside>;
}
