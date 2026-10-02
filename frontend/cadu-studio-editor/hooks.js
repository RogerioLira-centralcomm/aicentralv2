import {useEffect, useState} from 'react';

export function formatBytes(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value <= 0) return '';
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toLocaleString('pt-BR', {maximumFractionDigits: 1})} MB`;
  return `${Math.max(1, Math.round(value / 1024)).toLocaleString('pt-BR')} KB`;
}

const cache = new Map();

// Size in bytes of the image on the stage: computed for data URLs, read from the response headers
// otherwise (HEAD first; a full download only when the server hides Content-Length).
export function useAssetBytes(url) {
  const [bytes, setBytes] = useState(() => (url ? cache.get(url) ?? null : null));
  useEffect(() => {
    if (!url) { setBytes(null); return undefined; }
    if (cache.has(url)) { setBytes(cache.get(url)); return undefined; }
    let active = true;
    const done = value => { cache.set(url, value); if (active) setBytes(value); };
    setBytes(null);
    if (url.startsWith('data:')) {
      const comma = url.indexOf(',');
      done(comma < 0 ? null : Math.round(((url.length - comma - 1) * 3) / 4));
      return () => { active = false; };
    }
    (async () => {
      try {
        const head = await fetch(url, {method: 'HEAD', credentials: 'same-origin'});
        const length = Number(head.headers.get('content-length'));
        if (head.ok && length > 0) return done(length);
        const full = await fetch(url, {credentials: 'same-origin'});
        if (!full.ok) return done(null);
        return done((await full.blob()).size || null);
      } catch (_error) {
        return done(null);
      }
    })();
    return () => { active = false; };
  }, [url]);
  return bytes;
}

const sizeCache = new Map();

// Natural pixel size of an image URL (null while loading or when it cannot be read).
export function useImageDimensions(url) {
  const [size, setSize] = useState(() => (url ? sizeCache.get(url) ?? null : null));
  useEffect(() => {
    if (!url) { setSize(null); return undefined; }
    if (sizeCache.has(url)) { setSize(sizeCache.get(url)); return undefined; }
    let active = true;
    const image = new Image();
    image.onload = () => { const value = {width: image.naturalWidth, height: image.naturalHeight}; sizeCache.set(url, value); if (active) setSize(value); };
    image.onerror = () => { sizeCache.set(url, null); if (active) setSize(null); };
    image.src = url;
    return () => { active = false; };
  }, [url]);
  return size;
}
