import React from 'react';
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
