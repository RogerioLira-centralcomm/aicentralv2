import React, {useEffect, useState} from 'react';
import './planner-shelf.css';

/**
 * Title and filters of a shelf on ONE row (the page's only h1): the name and a count on the left, the filter bar filling the
 * middle and, outside the bar, the small view tools. Narrow screens stack them. No image: the cards below carry the visuals.
 */
export function ShelfHeader({title, description, bar = null, tools = null}) {
  return <header className="shelf-head">
    <div className="shelf-head__title">
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </div>
    {bar && <div className="shelf-head__bar">{bar}</div>}
    {tools && <div className="shelf-head__tools">{tools}</div>}
  </header>;
}

/** Right-hand index of a grouped shelf: jumps to a group and follows the scroll (same look as the detail pages' index). */
export function ShelfIndex({items, label = 'Nesta página'}) {
  const [current, setCurrent] = useState(items[0]?.id);
  const ids = items.map(item => item.id).join('|');
  useEffect(() => {
    if (!('IntersectionObserver' in window)) return undefined;
    const observer = new IntersectionObserver(entries => {
      const top = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (top) setCurrent(top.target.id);
    }, {rootMargin: '-96px 0px -60% 0px'});
    ids.split('|').forEach(id => { const node = document.getElementById(id); if (node) observer.observe(node); });
    return () => observer.disconnect();
  }, [ids]);
  return <aside className="pd-index shelf-index"><strong>{label}</strong>
    <nav className="pd-index__nav" aria-label="Grupos desta página">{items.map(item => <a key={item.id} href={`#${item.id}`} className={current === item.id ? 'is-active' : ''}
      aria-current={current === item.id ? 'true' : undefined}
      onClick={event => { event.preventDefault(); document.getElementById(item.id)?.scrollIntoView({behavior: 'smooth', block: 'start'}); setCurrent(item.id); }}>
      {item.label}<span>{item.count}</span></a>)}</nav>
  </aside>;
}
