export const FORMATS = ['4:5', '1:1', '9:16', '16:9'];
export const ASSET_DRAG_TYPE = 'application/x-cadu-studio-asset';

export function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('Não foi possível abrir a imagem.'));
    reader.readAsDataURL(file);
  });
}

export function imageSize(url) {
  return new Promise(resolve => {
    const image = new Image();
    image.onload = () => resolve({width: image.naturalWidth || 1600, height: image.naturalHeight || 900});
    image.onerror = () => resolve({width: 1600, height: 900});
    image.src = url;
  });
}

export function browserImageUrl(value) {
  const raw = String(value || '').trim();
  if (!raw || raw.startsWith('data:') || raw.startsWith('blob:')) return raw;
  try {
    const parsed = new URL(raw, window.location.origin);
    if (parsed.pathname.startsWith('/static/') || parsed.pathname.startsWith('/parametros/')) return `${window.location.origin}${parsed.pathname}${parsed.search}`;
    return parsed.href;
  } catch {
    return raw;
  }
}
