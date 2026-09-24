const CONTENT_KEYS = ['content', 'answer', 'text', 'output'];

function decode(value, depth = 0) {
  if (depth > 5 || value == null) return value;
  if (typeof value === 'string') {
    const clean = value.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
    if (!/^(?:\{|\[|"\s*[\[{])/.test(clean)) return value;
    try { return decode(JSON.parse(clean), depth + 1); } catch (_) { return value; }
  }
  if (Array.isArray(value)) return value;
  if (typeof value !== 'object') return value;
  for (const key of CONTENT_KEYS) {
    if (!Object.prototype.hasOwnProperty.call(value, key)) continue;
    const nested = decode(value[key], depth + 1);
    if (typeof nested === 'string' || (nested && typeof nested === 'object')) return nested;
  }
  return value;
}

function markdownInline(value) {
  return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*(.+?)\*/g, '<em>$1</em>');
}

function markdownToHtml(markdown) {
  const lines = String(markdown || '').replace(/\r/g, '').split('\n');
  const output = [];
  let list = '';
  const closeList = () => { if (list) { output.push(`</${list}>`); list = ''; } };
  for (const line of lines) {
    const heading = line.match(/^\s*(#{1,6})\s+(.+)$/);
    const bullet = line.match(/^\s*[-*+]\s+(.+)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (heading) { closeList(); const level = Math.min(heading[1].length, 4); output.push(`<h${level}>${markdownInline(heading[2])}</h${level}>`); }
    else if (bullet || numbered) {
      const kind = bullet ? 'ul' : 'ol';
      if (list !== kind) { closeList(); list = kind; output.push(`<${kind}>`); }
      output.push(`<li>${markdownInline((bullet || numbered)[1])}</li>`);
    } else if (!line.trim()) closeList();
    else { closeList(); output.push(`<p>${markdownInline(line)}</p>`); }
  }
  closeList();
  return output.join('');
}

function meetingSections(markdown) {
  const sections = [];
  let current = null;
  for (const line of String(markdown || '').split(/\r?\n/)) {
    const heading = line.match(/^\s*#{1,3}\s+(.+)$/);
    if (heading) {
      if (current) sections.push(current);
      current = {key: heading[1].trim(), value: ''};
    } else if (current && line.trim()) current.value += `${current.value ? '\n' : ''}${line.trim()}`;
  }
  if (current) sections.push(current);
  return sections;
}

export function normalizeArtifactContent(content = {}, artifactType = '') {
  const decodedRoot = decode(content);
  const originalHasFields = Array.isArray(content?.fields) || Array.isArray(content?.sections);
  const source = {...(originalHasFields
    ? content
    : decodedRoot && typeof decodedRoot === 'object' && !Array.isArray(decodedRoot) ? decodedRoot
    : content && typeof content === 'object' && !Array.isArray(content) ? content : {})};
  const rootText = !originalHasFields && typeof decodedRoot === 'string' && decodedRoot.trim()
    ? decodedRoot
    : decode(source.text ?? source.answer ?? source.output);
  if (!originalHasFields && typeof rootText === 'string' && rootText.trim() && (typeof content === 'string' || rootText !== content)) {
    if (artifactType === 'meeting_agenda' || artifactType === 'meeting_summary') {
      const fields = meetingSections(rootText.trim()).filter((field, index) => !(index === 0 && /^pauta|^resumo/i.test(field.key)));
      if (fields.length) return {...source, summary: '', fields};
    }
    source.html = markdownToHtml(rootText.trim());
    delete source.summary;
    delete source.text;
    delete source.answer;
    return source;
  }
  const candidates = [source.html, source.summary, source.text, source.answer].filter(value => value != null && value !== '');
  for (const candidate of candidates) {
    const decoded = decode(candidate);
    if (typeof decoded === 'string' && decoded.trim() && (typeof candidate !== 'string' || decoded.trim() !== candidate.trim())) {
      if (artifactType === 'meeting_agenda' || artifactType === 'meeting_summary') {
        const fields = meetingSections(decoded.trim()).filter((field, index) => !(index === 0 && /^pauta|^resumo/i.test(field.key)));
        if (fields.length) {
          source.summary = '';
          source.fields = fields;
          delete source.html;
          delete source.text;
          delete source.answer;
          return source;
        }
      }
      source.html = markdownToHtml(decoded.trim());
      delete source.summary;
      delete source.text;
      delete source.answer;
      return source;
    }
    if (decoded && typeof decoded === 'object' && !Array.isArray(decoded)) {
      const fields = Array.isArray(decoded.fields) ? decoded.fields : Array.isArray(decoded.sections) ? decoded.sections : null;
      if (fields) {
        source.summary = decoded.summary || source.summary || '';
        source.fields = fields.map((field, index) => ({key: String(field.key || field.title || field.heading || `Seção ${index + 1}`), value: String(field.value || field.content || field.text || '')}));
        delete source.html;
        return source;
      }
      return {...source, summary: '', html: ''};
    }
  }
  if (Array.isArray(source.fields)) {
    const fields = source.fields.map((field, index) => ({
      key: String(field?.key || field?.title || `Seção ${index + 1}`),
      value: normalizeFieldValue(field?.value),
    }));
    if ((artifactType === 'meeting_agenda' || artifactType === 'meeting_summary') && fields.length === 1) {
      const parsed = meetingSections(fields[0].value).filter((field, index) => !(index === 0 && /^pauta|^resumo/i.test(field.key)));
      if (parsed.length) return {...source, summary: source.summary || '', fields: parsed};
    }
    return {...source, fields};
  }
  return source;
}

function normalizeFieldValue(value) {
  const decoded = decode(value);
  if (typeof decoded === 'string') return decoded;
  if (Array.isArray(decoded)) return decoded.map(item => typeof item === 'string' ? item : JSON.stringify(item)).join('\n');
  if (decoded && typeof decoded === 'object') {
    const sections = Array.isArray(decoded.sections) ? decoded.sections : Array.isArray(decoded.items) ? decoded.items : null;
    if (sections) return sections.map(item => {
      if (typeof item === 'string') return `- ${item}`;
      const heading = item.title || item.heading || item.key;
      const body = item.content || item.value || item.text || '';
      return `${heading ? `### ${heading}\n` : ''}${body}`.trim();
    }).join('\n\n');
    return CONTENT_KEYS.map(key => decoded[key]).find(item => typeof item === 'string') || '';
  }
  return String(value ?? '');
}
