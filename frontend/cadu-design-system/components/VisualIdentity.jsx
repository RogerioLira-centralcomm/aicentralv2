import React, {useState} from 'react';

function initialsFor(value, fallback = 'P') {
  const initials = String(value || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(word => word[0])
    .join('')
    .toUpperCase();
  return initials || fallback;
}

/** A resilient visual identity shared by brands, projects and people. */
export function VisualIdentity({src, initials, label, color, className = '', imageAlt = ''}) {
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = Boolean(src) && !imageFailed;
  return <span className={`cadu-ds-visual-identity ${className}`} style={{'--cadu-identity-color': color || '#176b5e'}} title={label || undefined}>
    {showImage
      ? <img src={src} alt={imageAlt} onError={() => setImageFailed(true)}/>
      : <span aria-hidden="true">{initialsFor(initials || label)}</span>}
  </span>;
}
