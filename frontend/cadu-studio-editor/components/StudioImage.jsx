import React, {useEffect, useRef, useState} from 'react';
import {browserImageUrl} from '../shared';

export function StudioImage({src, alt = '', className = '', onUnavailable}) {
  const [failed, setFailed] = useState(false);
  const resolvedSrc = browserImageUrl(src);
  useEffect(() => setFailed(false), [resolvedSrc]);
  useEffect(() => { if (!resolvedSrc || failed) onUnavailable?.(); }, [resolvedSrc, failed]);
  if (!resolvedSrc || failed) return <span className={`se-image-fallback ${className}`} role="img" aria-label={alt}>Imagem indisponível</span>;
  return <img className={className} src={resolvedSrc} alt={alt} onError={() => setFailed(true)} />;
}
