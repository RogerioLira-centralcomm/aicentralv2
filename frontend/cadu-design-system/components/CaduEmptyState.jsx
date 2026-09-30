import React from 'react';

/** First-use and no-result states: a short message and, when it helps, the next action. */
export function CaduEmptyState({illustration = null, title, description, action = null, className = ''}) {
  return <div className={`cadu-ds-empty ${className}`.trim()}>
    {illustration}
    {title && <strong>{title}</strong>}
    {description && <p>{description}</p>}
    {action}
  </div>;
}
