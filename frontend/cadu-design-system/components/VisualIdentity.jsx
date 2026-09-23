import React, {useEffect, useState} from 'react';

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
export function VisualIdentity({src, initials, label, color, variant, className = '', imageAlt = '', fallbackSrc = '', imageTreatment = '', fallbackContent = null}) {
  const [imageFailed, setImageFailed] = useState(false);
  const [fallbackFailed, setFallbackFailed] = useState(false);
  useEffect(() => {
    setImageFailed(false);
    setFallbackFailed(false);
  }, [src, fallbackSrc]);
  const showImage = Boolean(src) && !imageFailed;
  const showFallbackImage = Boolean(fallbackSrc) && !fallbackFailed;
  const variantNumber = Number.isFinite(Number(variant)) ? ((Number(variant) % 10) + 10) % 10 : null;
  const variantClass = !showImage && !showFallbackImage && variantNumber !== null ? ` cadu-ds-visual-identity--v${variantNumber + 1}` : '';
  const imageClass = imageTreatment ? ` cadu-ds-visual-identity--${imageTreatment}` : '';
  const identityValue = String(initials || '').trim().length > 1 ? initials : (label || initials);
  // Missing evidence gets a neutral UI token, never a fabricated brand color.
  return <span className={`cadu-ds-visual-identity${variantClass}${imageClass} ${className}`} style={{'--cadu-identity-color': color || '#71807d'}} title={label || undefined}>
    {showImage
      ? <img src={src} alt={imageAlt} onError={() => setImageFailed(true)}/>
      : showFallbackImage
        ? <img src={fallbackSrc} alt={imageAlt} onError={() => setFallbackFailed(true)}/>
      : fallbackContent || <span aria-hidden="true">{initialsFor(identityValue)}</span>}
  </span>;
}
