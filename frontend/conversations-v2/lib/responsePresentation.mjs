const BLOCK_PREFIX = /^(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>|```|~~~|\|)/;
const SENTENCE_BOUNDARY = /(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9])/u;

export function formatResponseParagraphs(value, targetChars = 430) {
  const text = String(value || '').trim();
  if (!text) return '';
  const formatProse = prose => prose.split(/\n{2,}/).flatMap(block => {
    const trimmed = block.trim();
    if (BLOCK_PREFIX.test(trimmed) || trimmed.includes('\n') || trimmed.length <= targetChars) return [trimmed];
    const sentences = trimmed.split(SENTENCE_BOUNDARY).filter(Boolean);
    if (sentences.length < 2) return [trimmed];
    const groups = [];
    let current = '';
    for (const sentence of sentences) {
      const candidate = current ? `${current} ${sentence}` : sentence;
      if (current && candidate.length > targetChars) {
        groups.push(current);
        current = sentence;
      } else current = candidate;
    }
    if (current) groups.push(current);
    return groups;
  }).join('\n\n');

  const sections = [];
  let prose = [];
  let fence = [];
  let fenceMarker = '';
  const flushProse = () => {
    const formatted = formatProse(prose.join('\n').trim());
    if (formatted) sections.push(formatted);
    prose = [];
  };
  for (const line of text.split('\n')) {
    const marker = line.trim().match(/^(```|~~~)/)?.[1] || '';
    if (!fenceMarker && marker) {
      flushProse();
      fenceMarker = marker;
      fence = [line];
    } else if (fenceMarker) {
      fence.push(line);
      if (marker === fenceMarker) {
        sections.push(fence.join('\n'));
        fence = [];
        fenceMarker = '';
      }
    } else prose.push(line);
  }
  if (fence.length) sections.push(fence.join('\n'));
  flushProse();
  return sections.join('\n\n');
}
