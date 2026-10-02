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

export const FORMAT_LABELS = {'9:16': 'Vertical 9:16', '4:5': 'Vertical 4:5', '1:1': 'Quadrado 1:1', '16:9': 'Horizontal 16:9'};

const FORMAT_RATIOS = {'4:5': 4 / 5, '1:1': 1, '9:16': 9 / 16, '16:9': 16 / 9};

// Nearest Studio format for a piece's pixel size.
export function nearestFormat(width, height) {
  const ratio = Number(width) / Number(height);
  if (!Number.isFinite(ratio) || ratio <= 0) return '';
  return Object.entries(FORMAT_RATIOS).reduce((best, [key, value]) => Math.abs(Math.log(value / ratio)) < Math.abs(Math.log(FORMAT_RATIOS[best] / ratio)) ? key : best, '1:1');
}

// One-to-one adaptations offered for a piece: horizontal ones become vertical and vice versa.
export function adaptTargets(width, height) {
  const ratio = Number(width) / Number(height);
  if (!Number.isFinite(ratio) || ratio <= 0) return [];
  if (ratio > 1.15) return ['9:16', '4:5'];
  if (ratio < 0.87) return ['16:9', '1:1'];
  return ['9:16', '16:9'];
}

export const ADAPT_INSTRUCTION = target => `Adapte esta peça para o formato ${target}, mantendo todos os elementos, textos, logo e cores, apenas reorganizando o layout para a nova proporção.`;
