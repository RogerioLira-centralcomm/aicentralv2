export function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function scriptText(script) {
  return ((script || {}).beats || []).map((beat, index) => (
    `Cena ${index + 1} — ${beat.purpose || "beat"}\nVisual: ${beat.visual || ""}\nMovimento: ${beat.motion || ""}\nTrava: ${beat.hold || ""}${beat.spoken ? `\nFala: ${beat.spoken}` : ""}`
  )).join("\n\n");
}

export function parseScript(text, fallback, scenes = []) {
  const blocks = String(text || "").split(/\n\s*\n/).map((item) => item.trim()).filter(Boolean);
  if (!blocks.length) return fallback;
  const beats = blocks.map((block, index) => {
    const lines = block.split("\n");
    const head = lines[0] || "";
    const purpose = (head.split("—")[1] || fallback?.beats?.[index]?.purpose || "beat").trim();
    const pick = (label) => {
      const line = lines.find((row) => row.toLowerCase().startsWith(label));
      return line ? line.slice(label.length).trim() : "";
    };
    return {
      id: scenes[index]?.id || fallback?.beats?.[index]?.id || `scene-${index + 1}`,
      purpose,
      visual: pick("visual:") || fallback?.beats?.[index]?.visual || "",
      motion: pick("movimento:") || fallback?.beats?.[index]?.motion || "",
      hold: pick("trava:") || fallback?.beats?.[index]?.hold || "",
      spoken: pick("fala:") || fallback?.beats?.[index]?.spoken || "",
    };
  });
  return { beats };
}

export function formatMoney(quote) {
  if (!quote) return "";
  const brl = quote.estimated_cost_brl;
  const usd = quote.estimated_cost_usd;
  const res = quote.resolution || "";
  const parts = [];
  if (brl != null) parts.push(`R$ ${Number(brl).toFixed(2)}`);
  else if (usd != null) parts.push(`US$ ${Number(usd).toFixed(2)}`);
  if (res) parts.push(res);
  if (quote.voiceover_fits === false) parts.push("locução longa");
  return parts.join(" · ") || "Cotação pronta.";
}
