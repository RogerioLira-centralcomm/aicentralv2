// Modelo da mesa: séries → peças → versões, guardado em `metadata.board` da sessão do Studio.
// O layout é derivado do modelo (nunca salvo), exceto as posições que o usuário fixou à mão (`piece.pin`).

export const uid = prefix => `${prefix}_${(crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}${Math.random()}`).replace(/-/g, '').slice(0, 12)}`;

export const TYPES = {
  anuncio: {label: 'Anúncio', icon: 'midia', hint: 'Peças de mídia com texto, oferta, CTA e logo aplicados por código.'},
  ilustracao_interface: {label: 'Ilustração de interface', icon: 'concorrentes', hint: 'Spots 3D suaves para telas e cards: um agrupamento, fundo transparente, sem texto. O designer monta o resto.'},
  ilustracao: {label: 'Ilustrações', icon: 'pauta', hint: 'Set de ícones, spots ou cenas. A primeira aprovada vira o estilo das outras.'},
  landing_vendas: {label: 'Landing de vendas', icon: 'investimento', hint: 'Mockup de página com herói, oferta, prova, benefícios e CTA.'},
  landing_institucional: {label: 'Landing institucional', icon: 'regulacao', hint: 'Mockup de página de marca: propósito, credibilidade, sem pressão de oferta.'},
  site: {label: 'Site', icon: 'concorrentes', hint: 'Série de telas. A home aprovada guia header, grid e tipografia das outras.'},
  post: {label: 'Post orgânico', icon: 'tendencias', hint: 'Feed, carrossel e story com o tom de voz da marca.'},
};

export const emptyBoard = () => ({v: 1, series: [], camera: null});

export function newSeries(board, {id, title, type = 'anuncio', rules = ''}) {
  const series = {id: id || uid('s'), title: title || 'Nova série', type, rules, pieces: [], created_at: Date.now()};
  return [{...board, series: [...board.series, series]}, series];
}

export function newPiece(board, seriesId, {id, title, format, origin = null}) {
  const piece = {id: id || uid('p'), title: title || format?.label || 'Peça', format, star: null, versions: [], origin, pin: null, created_at: Date.now()};
  return [mapSeries(board, seriesId, series => ({...series, pieces: [...series.pieces, piece]})), piece];
}

export function addVersion(board, pieceId, version) {
  const entry = {id: uid('v'), status: 'pending', created_at: Date.now(), ...version};
  return [mapPiece(board, pieceId, piece => ({...piece, versions: [...piece.versions, entry]})), entry];
}

export function patchVersion(board, versionId, patch) {
  return mapAllPieces(board, piece => {
    if (!piece.versions.some(item => item.id === versionId)) return piece;
    const versions = piece.versions.map(item => item.id === versionId ? {...item, ...patch} : item);
    // A primeira versão pronta vira a base (★) da peça; depois a base só muda quando o usuário manda.
    const ready = versions.find(item => item.id === versionId);
    const star = piece.star || (ready?.status === 'ready' ? versionId : null);
    return {...piece, versions, star};
  });
}

export const setStar = (board, pieceId, versionId) => mapPiece(board, pieceId, piece => ({...piece, star: versionId}));
export const setAnchor = (board, seriesId, versionId) => mapSeries(board, seriesId, series => ({...series, anchor: versionId}));
export const pinPiece = (board, pieceId, pin) => mapPiece(board, pieceId, piece => ({...piece, pin}));
export const unpinAll = board => mapAllPieces(board, piece => ({...piece, pin: null}));
export const retireVersions = (board, ids, retired = true) => mapAllPieces(board, piece => ({...piece, versions: piece.versions.map(item => ids.has(item.id) ? {...item, retired} : item)}));

function mapSeries(board, id, fn) { return {...board, series: board.series.map(series => series.id === id ? fn(series) : series)}; }
function mapAllPieces(board, fn) { return {...board, series: board.series.map(series => ({...series, pieces: series.pieces.map(fn)}))}; }
function mapPiece(board, id, fn) { return mapAllPieces(board, piece => piece.id === id ? fn(piece) : piece); }

export function findVersion(board, versionId) {
  for (const series of board.series) for (const piece of series.pieces) {
    const version = piece.versions.find(item => item.id === versionId);
    if (version) return {series, piece, version};
  }
  return null;
}

export const starOf = piece => piece.versions.find(item => item.id === piece.star) || piece.versions.find(item => item.status === 'ready') || piece.versions[piece.versions.length - 1] || null;

// ---- Layout automático --------------------------------------------------------------------------------------------
// Grade fixa: cada peça é uma coluna de largura constante; a série reserva espaço para a primeira fileira de versões,
// assim um ajuste novo não empurra as séries de baixo.
export const L = {pad: 40, head: 76, label: 36, cardW: 280, maxCardH: 400, colGap: 56, versionGap: 28, thumbW: 132, thumbGap: 16, thumbLabel: 22, seriesGap: 72};

const cardHeight = (format, width) => {
  const w = Number(format?.width) || 1, h = Number(format?.height) || 1;
  return Math.max(90, Math.min(width === L.cardW ? L.maxCardH : L.maxCardH * width / L.cardW, Math.round(width * h / w)));
};

/** Posição de cada série, peça e versão. Variações e adaptações entram logo depois da peça de origem, ligadas por linha. */
export function layout(board) {
  const nodes = [], links = [], bands = [];
  let y = 0;
  for (const series of board.series) {
    const ordered = orderPieces(series.pieces);
    const top = y + L.pad + L.head + L.label;
    let x = L.pad, tallest = 0;
    const at = {};
    for (const piece of ordered) {
      const live = piece.versions.filter(item => !item.retired);
      const star = live.find(item => item.id === piece.star) || live[live.length - 1];
      const others = live.filter(item => item !== star).reverse();
      const cardH = cardHeight(piece.format, L.cardW), thumbH = cardHeight(piece.format, L.thumbW);
      const px = piece.pin ? piece.pin.x : x, py = piece.pin ? piece.pin.y : top;
      nodes.push(star ? {kind: 'version', id: star.id, piece, series, version: star, star: true, x: px, y: py, w: L.cardW, h: cardH}
        : {kind: 'empty', id: piece.id, piece, series, x: px, y: py, w: L.cardW, h: cardH});
      const rowH = L.thumbLabel + thumbH + L.thumbGap;
      others.forEach((version, index) => {
        nodes.push({kind: 'version', id: version.id, piece, series, version, star: false,
          x: px + (index % 2) * (L.thumbW + L.thumbGap), y: py + cardH + L.versionGap + L.thumbLabel + Math.floor(index / 2) * rowH, w: L.thumbW, h: thumbH});
      });
      // Reserva sempre uma fileira de versões: o primeiro ajuste não muda a altura da série.
      const colH = cardH + L.versionGap + Math.max(1, Math.ceil(others.length / 2)) * rowH;
      at[piece.id] = {x: px, y: py, w: L.cardW, h: cardH};
      if (piece.origin?.piece && at[piece.origin.piece]) links.push({from: at[piece.origin.piece], to: at[piece.id], kind: piece.origin.kind});
      if (!piece.pin) { x += L.cardW + L.colGap; tallest = Math.max(tallest, colH); }
    }
    const height = L.pad + L.head + L.label + Math.max(tallest, L.maxCardH * 0.6) + L.pad;
    bands.push({series, x: 0, y, w: Math.max(x - L.colGap + L.pad, 640), h: height});
    y += height + L.seriesGap;
  }
  return {nodes, links, bands, bounds: boundsOf(nodes, bands)};
}

function orderPieces(pieces) {
  const roots = pieces.filter(piece => !piece.origin?.piece || !pieces.some(other => other.id === piece.origin.piece));
  const out = [];
  const visit = piece => { out.push(piece); pieces.filter(child => child.origin?.piece === piece.id).forEach(visit); };
  roots.forEach(visit);
  return out;
}

function boundsOf(nodes, bands) {
  const boxes = [...nodes, ...bands];
  if (!boxes.length) return {x: 0, y: 0, w: 800, h: 600};
  const x0 = Math.min(...boxes.map(b => b.x)), y0 = Math.min(...boxes.map(b => b.y));
  const x1 = Math.max(...boxes.map(b => b.x + b.w)), y1 = Math.max(...boxes.map(b => b.y + b.h));
  return {x: x0, y: y0, w: x1 - x0, h: y1 - y0};
}
