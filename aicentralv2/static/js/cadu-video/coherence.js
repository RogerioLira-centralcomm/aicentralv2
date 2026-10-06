// Checagem antes de gerar o vídeo: só regras locais, sem custo. Erro bloqueia; aviso pede confirmação.
export const WORDS_PER_SECOND = 4;
const norm = (text) => String(text || "").toLowerCase().replace(/\s+/g, " ").trim();
const words = (text) => (String(text || "").match(/\S+/g) || []).length;
const plural = (n, one, many) => (n === 1 ? one : many);

export function coherenceIssues({ scenes = [], beatFor = () => ({}), draftBeats = [], duration = 8, mode = "storyboard", aspects = {}, wordsPerSecond = WORDS_PER_SECOND, selectedId = "" } = {}) {
  const issues = [];
  const push = (level, code, message, sceneId = "") => issues.push({ level, code, message, sceneId });
  const hasImage = (scene) => !scene.broken && Boolean(scene.image_url || scene.thumb_url);
  if (mode === "single_image") {
    const scene = scenes.find((row) => row.id === selectedId);
    if (scene && !hasImage(scene)) push("error", "no-image", "A imagem escolhida está indisponível. Escolha outra peça.", scene.id);
    return issues;
  }
  const total = scenes.length;
  scenes.forEach((scene, index) => {
    const number = index + 1;
    const beat = beatFor(scene.id) || {};
    if (!hasImage(scene)) push("error", "no-image", `Cena ${number} sem imagem disponível. Troque a imagem ou remova a cena.`, scene.id);
    if (!norm(beat.visual) && !norm(beat.motion)) push("warn", "empty-beat", `Cena ${number} sem descrição visual nem de movimento: o modelo vai improvisar.`, scene.id);
  });
  const pending = draftBeats.length;
  if (pending) push("warn", "draft-pending", `${pending} ${plural(pending, "cena do rascunho ainda está", "cenas do rascunho ainda estão")} sem imagem e não ${plural(pending, "entra", "entram")} no vídeo.`);
  const ratios = [...new Set(scenes.map((scene) => aspects[scene.id]).filter(Boolean))];
  if (ratios.length > 1) push("warn", "aspect-mix", `As imagens têm proporções diferentes (${ratios.join(", ")}). Elas serão ajustadas ao formato escolhido e podem ser cortadas.`);
  const seen = new Map();
  scenes.forEach((scene, index) => {
    const key = norm((beatFor(scene.id) || {}).visual);
    if (!key) return;
    if (seen.has(key)) push("warn", "duplicate-visual", `Cenas ${seen.get(key) + 1} e ${index + 1} descrevem o mesmo visual.`, scene.id);
    else seen.set(key, index);
  });
  const seconds = Number(duration) || 0;
  if (total > 1 && seconds) {
    const each = seconds / total;
    if (each < 1.5) push("warn", "too-short", `${total} cenas em ${seconds}s: cada uma dura só ${each.toFixed(1)}s. Aumente a duração ou use menos cenas.`);
    let totalWords = 0;
    scenes.forEach((scene, index) => {
      const spoken = words((beatFor(scene.id) || {}).spoken);
      totalWords += spoken;
      const fits = Math.floor(each * wordsPerSecond);
      if (spoken > fits && spoken > 3) push("warn", "speech-scene", `Cena ${index + 1}: ${spoken} palavras para ~${each.toFixed(1)}s (cabem cerca de ${fits}).`, scene.id);
    });
    if (totalWords > seconds * wordsPerSecond) push("warn", "speech-total", `A fala toda tem ${totalWords} palavras e não cabe em ${seconds}s (cerca de ${Math.floor(seconds * wordsPerSecond)}).`);
  }
  if (total > 1) {
    const first = (beatFor(scenes[0].id) || {}).purpose, last = (beatFor(scenes[total - 1].id) || {}).purpose;
    if (first && first !== "hook") push("warn", "arc-start", "A primeira cena não é uma abertura.", scenes[0].id);
    if (last && !["end", "offer"].includes(last)) push("warn", "arc-end", "A última cena não fecha a história.", scenes[total - 1].id);
  }
  return issues.sort((a, b) => (a.level === b.level ? 0 : a.level === "error" ? -1 : 1));
}
