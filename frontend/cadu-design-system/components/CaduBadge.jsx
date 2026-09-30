import React from 'react';

/** Compact status label. The tone maps to semantic tokens, never to a fixed color. */
export function CaduBadge({tone = 'neutral', children, className = '', ...props}) {
  return <span className={`cadu-ds-badge cadu-ds-badge--${tone} ${className}`.trim()} {...props}>{children}</span>;
}
