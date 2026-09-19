import React from 'react';

export function CaduSurface({as: Element = 'section', tone = 'default', children, className = '', ...props}) {
  return <Element className={`cadu-ds-surface cadu-ds-surface--${tone} ${className}`} {...props}>{children}</Element>;
}
