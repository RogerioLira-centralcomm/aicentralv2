export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export const QUALITY_LABEL = {
  reliable: "Confiável",
  review_edge: "Revisar borda",
  leak: "Possível vazamento",
  incomplete: "Objeto incompleto",
  text_overlap: "Texto sobreposto",
  low_res: "Baixa resolução",
  duplicate: "Duplicado",
  approved: "Aprovado",
  unplaced: "Sem caixa",
  placed: "Posicionado",
};

export const ROLE_LABEL = {
  person: "Pessoa",
  product: "Produto",
  logo: "Logo",
  graphic: "Grafismo",
  badge: "Selo",
  background: "Fundo",
  headline: "Headline",
  support: "Apoio",
  price: "Preço",
  cta: "CTA",
  legal: "Legal",
  date: "Data",
  venue: "Local",
};

export const PROVENANCE_LABEL = {
  original: "Original",
  cutout: "Recorte original",
  recorte_original: "Recorte original",
  extracted: "Recorte original",
  html: "HTML",
  generated: "Gerado por IA",
  reconstructed: "Original",
  upload: "Upload manual",
};

export function qualityLabel(value) {
  return QUALITY_LABEL[value] || value || "";
}

export function provenanceLabel(value) {
  return PROVENANCE_LABEL[value] || value || "";
}

export function assetUrl(path) {
  return String(path || "");
}

export function layerBox(layer) {
  const box = layer?.bbox || {};
  return {
    x: Number(box.x || 0),
    y: Number(box.y || 0),
    w: Number(box.w || box.width || 0),
    h: Number(box.h || box.height || 0),
  };
}

export function hitLayer(layers, x, y) {
  const ordered = [...(layers || [])]
    .filter((item) => item.visible !== false && item.role !== "background")
    .sort((a, b) => Number(b.z_index || 0) - Number(a.z_index || 0));
  return ordered.find((item) => {
    const box = layerBox(item);
    return x >= box.x && y >= box.y && x <= box.x + box.w && y <= box.y + box.h;
  }) || null;
}

export function cloneLayers(layers) {
  return JSON.parse(JSON.stringify(layers || []));
}

export function composeScene(state) {
  const scene = state?.scene && typeof state.scene === "object"
    ? structuredClone(state.scene)
    : { schema_version: "2.0", canvas: {}, layers: [] };
  const byId = new Map((state?.layers || []).map((item) => [item.id, item]));
  scene.layers = (scene.layers || []).map((layer) => {
    const live = byId.get(layer.id);
    if (!live) return layer;
    const box = layerBox(live);
    return {
      ...layer,
      visible: live.visible !== false,
      z_index: live.z_index ?? layer.z_index,
      label: live.label || layer.label,
      text: live.text || layer.text,
      x: box.w || box.h ? box.x : layer.x,
      y: box.w || box.h ? box.y : layer.y,
      width: box.w || layer.width,
      height: box.h || layer.height,
      asset_path: live.png_path || layer.asset_path,
    };
  });
  if (state?.creative) {
    scene.creative_id = state.creative.id;
    scene.canvas = {
      ...(scene.canvas || {}),
      width: state.creative.width || scene.canvas?.width || 0,
      height: state.creative.height || scene.canvas?.height || 0,
    };
  }
  return scene;
}
