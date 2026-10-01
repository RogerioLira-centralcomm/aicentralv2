import React from 'react';

/** Page title for product surfaces: optional way back, one heading, one line of context and the page actions. */
export function CaduPageHeader({title, description, back = null, actions = null, meta = null, className = ''}) {
  return <header className={`cadu-ds-page-header ${className}`.trim()}>
    {back && <a className="cadu-ds-page-header__back" href={back.href}><span aria-hidden="true">←</span>{back.label}</a>}
    <div className="cadu-ds-page-header__row">
      <div className="cadu-ds-page-header__copy">
        <h1>{title}</h1>
        {description && <p>{description}</p>}
        {meta && <div className="cadu-ds-page-header__meta">{meta}</div>}
      </div>
      {actions && <div className="cadu-ds-page-header__actions">{actions}</div>}
    </div>
  </header>;
}
