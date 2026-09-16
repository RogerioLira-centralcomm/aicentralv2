export function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function scriptText(script) {
  return ((script || {}).beats || []).map((beat, index) => (
    `Cena ${index + 1} — ${beat.purpose || "beat"}\nVisual: ${beat.visual || ""}\nMovimento: ${beat.motion || ""}\nTransição: ${beat.transition || "cut"}\nTrava: ${beat.hold || ""}${beat.spoken ? `\nFala: ${beat.spoken}` : ""}`
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
      transition: pick("transição:") || fallback?.beats?.[index]?.transition || "cut",
      hold: pick("trava:") || fallback?.beats?.[index]?.hold || "",
      spoken: pick("fala:") || fallback?.beats?.[index]?.spoken || "",
    };
  });
  return { beats };
}

export function formatMoney(quote) {
  if (!quote) return "";
  const tokens = Number(quote.estimated_tokens || 0);
  const res = quote.resolution || "";
  const parts = [];
  if (tokens) parts.push(`${tokens.toLocaleString('pt-BR')} créditos de tokens`);
  if (res) parts.push(res);
  if (quote.voiceover_fits === false) parts.push("locução longa");
  return parts.join(" · ") || "Estimativa em tokens pronta.";
}

export function newId(){
  return typeof crypto.randomUUID==='function'?crypto.randomUUID():Array.from(crypto.getRandomValues(new Uint8Array(16)),value=>value.toString(16).padStart(2,'0')).join('');
}
