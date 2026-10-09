// Formatos do quadro e receitas por tipo de criação (texto extra enviado ao diretor junto do pedido).

// Formatos de página e ilustração são do Quadro; social e display vêm do catálogo de formatos do Studio (o mesmo que o
// compositor por código conhece), injetado pelo template.
const OWN = [
  {key: 'landscape-16x9', label: 'Paisagem 16:9', width: 1920, height: 1080, ratio: '16:9', channel: 'livre', group: 'Página e livre'},
  {key: 'page-desktop', label: 'Página desktop', width: 1440, height: 1024, ratio: '1440:1024', channel: 'livre', group: 'Página e livre'},
  {key: 'page-mobile', label: 'Página mobile', width: 390, height: 844, ratio: '390:844', channel: 'livre', group: 'Página e livre'},
  {key: 'illustration-1x1', label: 'Ilustração 1:1', width: 1024, height: 1024, ratio: '1:1', channel: 'livre', group: 'Página e livre'},
  {key: 'spot-3x2', label: 'Spot de interface 3:2', width: 1536, height: 1024, ratio: '3:2', channel: 'livre', group: 'Página e livre'},
  {key: 'spot-1x1', label: 'Spot de interface 1:1', width: 1024, height: 1024, ratio: '1:1', channel: 'livre', group: 'Página e livre'},
];
const FALLBACK = [
  {format_key: 'feed-4x5', label: 'Feed 4:5', width: 1080, height: 1350, kind: 'social'}, {format_key: 'feed-1x1', label: 'Feed 1:1', width: 1080, height: 1080, kind: 'social'},
  {format_key: 'story-9x16', label: 'Stories', width: 1080, height: 1920, kind: 'social'}, {format_key: 'linkedin-landscape', label: 'LinkedIn', width: 1200, height: 627, kind: 'social'},
  {format_key: 'iab-medium', label: 'Medium rectangle', width: 300, height: 250, kind: 'banner'}, {format_key: 'iab-billboard', label: 'Billboard', width: 970, height: 250, kind: 'banner'},
];
const gcd = (a, b) => b ? gcd(b, a % b) : a;
const ratioOf = (w, h) => { const d = gcd(w, h) || 1; return `${w / d}:${h / d}`; };

function fromCatalog(catalog) {
  const source = Array.isArray(catalog) && catalog.length ? catalog : FALLBACK;
  const seen = new Set();
  return source.filter(item => ['social', 'banner'].includes(item.kind || 'banner') && item.width && item.height && !/video|reels|shorts/.test(item.format_key))
    .filter(item => !seen.has(item.format_key) && seen.add(item.format_key))
    .map(item => ({key: item.format_key, label: item.kind === 'social' || /\d+\s*[×x]\s*\d+/.test(item.label) ? item.label : `${item.label.replace(new RegExp(`\\s*${item.width}$`), '')} ${item.width}×${item.height}`, width: item.width, height: item.height,
      ratio: ratioOf(item.width, item.height), channel: item.kind === 'social' ? 'social' : 'display', group: item.kind === 'social' ? 'Social' : 'Display (IAB)'}));
}

export let FORMATS = [...fromCatalog(null), ...OWN];
export function setCatalog(catalog) { FORMATS = [...fromCatalog(catalog), ...OWN]; }
export const formatGroups = () => ['Social', 'Display (IAB)', 'Página e livre'].map(group => [group, FORMATS.filter(item => item.group === group)]).filter(([, items]) => items.length);
export const formatByKey = key => FORMATS.find(item => item.key === key) || FORMATS.find(item => item.key === 'feed-4x5') || FORMATS[0];

/** Desdobramento sugerido conforme o tipo da série. */
export const UNFOLD_DEFAULT = {
  anuncio: ['feed-4x5', 'story-9x16', 'iab-medium', 'iab-halfpage', 'iab-billboard', 'iab-leaderboard'],
  post: ['feed-4x5', 'feed-1x1', 'story-9x16'], ilustracao_interface: ['spot-1x1'], ilustracao: ['feed-1x1', 'landscape-16x9'],
  landing_vendas: ['page-mobile'], landing_institucional: ['page-mobile'], site: ['page-mobile'],
};

export const DEFAULT_FORMAT = {
  anuncio: 'feed-4x5', ilustracao_interface: 'spot-3x2', ilustracao: 'illustration-1x1', landing_vendas: 'page-desktop', landing_institucional: 'page-desktop', site: 'page-desktop', post: 'feed-4x5',
};

const RECIPES = {
  anuncio: '',
  ilustracao: 'TIPO DE CRIAÇÃO: ilustração de um set (não é anúncio). Sem texto, sem números, sem logo, sem moldura de anúncio. Uma ideia por imagem, fundo limpo. Use cores e motivos da marca.',
  landing_vendas: 'TIPO DE CRIAÇÃO: mockup de landing page de VENDAS, a tela inteira de um site (sem moldura de navegador, sem dispositivo). Hierarquia de conversão: menu simples, herói com oferta e CTA, prova social, benefícios em blocos, CTA repetido. Textos curtos e legíveis, tipografia e cores da marca.',
  landing_institucional: 'TIPO DE CRIAÇÃO: mockup de landing page INSTITUCIONAL, a tela inteira de um site (sem moldura de navegador). Marca, propósito, números de credibilidade, seções limpas; sem pressão de oferta. Tipografia e cores da marca.',
  site: 'TIPO DE CRIAÇÃO: mockup de uma tela de SITE (sem moldura de navegador). Header, navegação, grid e componentes consistentes entre as telas do mesmo site. Tipografia e cores da marca.',
  post: 'TIPO DE CRIAÇÃO: post orgânico de rede social (não é anúncio pago): conversa com a comunidade no tom de voz da marca, sem cara de banner; pouco texto na imagem.',
};

/** Receita do tipo, mais a âncora de consistência quando a série já tem peça aprovada. */
export function recipeFor(type, {anchor = false, rules = ''} = {}) {
  const parts = [RECIPES[type] || ''];
  if (anchor) parts.push('CONSISTÊNCIA: a referência de estilo é a âncora desta série. Copie dela só o estilo (traço, peso das linhas, paleta, tipografia, acabamento e componentes visuais). NÃO copie o objeto, o assunto, a composição nem o layout: o conteúdo desta peça é o do pedido.');
  if (rules) parts.push(`REGRAS DA SÉRIE: ${rules}`);
  return parts.filter(Boolean).join('\n');
}

/** Ilustração sai sem logo e sem texto aplicados por código (ativo neutro); o resto é peça da marca. */
export const intentFor = type => type === 'ilustracao' ? 'neutral_asset' : type === 'ilustracao_interface' ? 'brand_asset' : 'branded_creative';

/** Âncora da série como referência só de estilo (o pipeline aceita imagens geradas pelo próprio Studio). */
export const anchorReference = version => {
  const url = String(version?.base || version?.url || '').split('?')[0];
  return url.startsWith('/static/uploads/creative_generated/') ? {id: `anchor-${version.id}`, url, role: 'style', source: 'project', label: 'Âncora de estilo da série'} : null;
};
