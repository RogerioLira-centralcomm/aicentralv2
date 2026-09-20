import React, {useState} from 'react';

function initialsFor(value, fallback = 'P') {
  const words = String(value || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
  const initials = (words.length > 1
    ? words.slice(0, 2).map(word => word[0]).join('')
    : (words[0] || '').slice(0, 2)).toUpperCase();
  return initials || fallback;
}

/** A resilient visual identity shared by brands, projects and people. */
export function VisualIdentity({src, initials, label, color, variant, className = '', imageAlt = ''}) {
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = Boolean(src) && !imageFailed;
  const variantNumber = Number.isFinite(Number(variant)) ? ((Number(variant) % 10) + 10) % 10 : null;
  const variantClass = !showImage && variantNumber !== null ? ` cadu-ds-visual-identity--v${variantNumber + 1}` : '';
  const identityValue = String(initials || '').trim().length > 1 ? initials : (label || initials);
  return <span className={`cadu-ds-visual-identity${variantClass} ${className}`} style={{'--cadu-identity-color': color || '#176b5e'}} title={label || undefined}>
    {showImage
      ? <img src={src} alt={imageAlt} onError={() => setImageFailed(true)}/>
      : <span aria-hidden="true">{initialsFor(identityValue)}</span>}
  </span>;
}
