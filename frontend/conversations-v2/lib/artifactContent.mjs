// Provider envelopes sometimes survive inside older draft artifacts. Follow
// only their content-bearing keys; presentation metadata such as `ui` must
// never be rendered as part of the editable document.
const CONTENT_KEYS = ['content', 'answer', 'text', 'output', 'structured_output', 'artifact_patch'];

function decode(value, depth = 0) {
  if (depth > 12 || value == null) return value;
  if (typeof value === 'string') {
    const clean = value.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
    if (/^\{\\"(?:text|answer|content|output)\\"/.test(clean)) {
      try {
        const unwrapped = JSON.parse(`"${clean}"`);
        return decode(JSON.parse(unwrapped), depth + 1);
      } catch (_) { /* Try the regular JSON paths below. */ }
    }
    if (!/^(?:\{|\[|"\s*[\[{])/.test(clean)) {
      return /\\n|\\r/.test(value) && /(?:^|\\n)\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s)/.test(value)
        ? value.replace(/\\r\\n|\\n|\\r/g, '\n')
        : value;
    }
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

function userFacingText(value, depth = 0) {
  if (depth > 8 || value == null) return '';
  const decoded = decode(value, depth);
  if (typeof decoded === 'string') {
    const text = decoded.trim();
    if (!text) return '';
    // Providers occasionally put the complete transport envelope in a field.
    // Peel only known content keys; never display `ui`, citations, or patch metadata.
    if (/^[{]/.test(text)) {
      try { return userFacingText(JSON.parse(text), depth + 1); } catch (_) { /* Plain text that starts with a brace. */ }
    }
    return text.replace(/\\r\\n|\\n|\\r/g, '\n');
  }
  if (Array.isArray(decoded)) return decoded.map(item => userFacingText(item, depth + 1)).filter(Boolean).join('\n');
  if (!decoded || typeof decoded !== 'object') return '';
  const textPayload = decoded.text && typeof decoded.text === 'object' ? decoded.text.content : decoded.text;
  for (const candidate of [textPayload, decoded.answer, decoded.content, decoded.output, decoded.structured_output]) {
    const text = userFacingText(candidate, depth + 1);
    if (text) return text;
  }
  return '';
}

function markdownInline(value) {
  const escape = input => String(input || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  let text = String(value || '');
  const protectedParts = [];
  const protect = html => `\u0000${protectedParts.push(html) - 1}\u0000`;
  text = text.replace(/!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/gi, (_, alt, url) => protect(`<img alt="${escape(alt)}" src="${escape(url)}">`));
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/gi, (_, label, url) => protect(`<a href="${escape(url)}" rel="noreferrer">${escape(label)}</a>`));
  text = escape(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>').replace(/_(.+?)_/g, '<em>$1</em>')
    .replace(/~~(.+?)~~/g, '<del>$1</del>');
  return text.replace(/\u0000(\d+)\u0000/g, (_, index) => protectedParts[Number(index)] || '');
}

function markdownToHtml(markdown) {
  const lines = String(markdown || '').replace(/\r/g, '').split('\n');
  const output = [];
  let list = '';
  let code = null;
  let codeLines = [];
  const closeList = () => { if (list) { output.push(`</${list}>`); list = ''; } };
  const tableCells = line => line.trim().replace(/^\||\|$/g, '').split(/(?<!\\)\|/).map(cell => cell.replace(/\\\|/g, '|').trim());
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const fence = line.match(/^\s*(```+|~~~+)(.*)$/);
    if (fence) {
      closeList();
      if (code) { output.push(`<pre><code>${codeLines.join('\n').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</code></pre>`); code = null; codeLines = []; }
      else code = fence[1][0];
      continue;
    }
    if (code) { codeLines.push(line); continue; }
    const heading = line.match(/^\s*(#{1,6})\s+(.+)$/);
    const bullet = line.match(/^\s*[-*+]\s+(.+)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (line.includes('|') && /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1] || '')) {
      closeList();
      const headers = tableCells(line);
      output.push(`<table><thead><tr>${headers.map(cell => `<th>${markdownInline(cell)}</th>`).join('')}</tr></thead><tbody>`);
      index += 2;
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        const cells = tableCells(lines[index]);
        output.push(`<tr>${headers.map((_, cellIndex) => `<td>${markdownInline(cells[cellIndex] || '')}</td>`).join('')}</tr>`);
        index += 1;
      }
      output.push('</tbody></table>');
      index -= 1;
      continue;
    }
    if (heading) { closeList(); const level = Math.min(heading[1].length, 4); output.push(`<h${level}>${markdownInline(heading[2])}</h${level}>`); }
    else if (bullet || numbered) {
      const kind = bullet ? 'ul' : 'ol';
      if (list !== kind) { closeList(); list = kind; output.push(`<${kind}>`); }
      output.push(`<li>${markdownInline((bullet || numbered)[1])}</li>`);
    } else if (!line.trim()) closeList();
    else if (/^\s*(?:---+|___+|\*\*\*+)\s*$/.test(line)) { closeList(); output.push('<hr>'); }
    else if (/^\s*>/.test(line)) { closeList(); output.push(`<blockquote><p>${markdownInline(line.replace(/^\s*>\s?/, ''))}</p></blockquote>`); }
    else { closeList(); output.push(`<p>${markdownInline(line)}</p>`); }
  }
  if (code) output.push(`<pre><code>${codeLines.join('\n').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</code></pre>`);
  closeList();
  return output.join('');
}

function meetingSections(markdown) {
  const sections = [];
  let current = null;
  for (const line of String(markdown || '').split(/\r?\n/)) {
    const heading = line.match(/^\s*#{1,3}\s+(.+)$/);
    const numbered = line.match(/^\s*(\d{1,2})[).;:]\s+(.+)$/);
    if (heading) {
      if (current) sections.push(current);
      current = {key: heading[1].trim(), value: ''};
    } else if (numbered) {
      if (current) sections.push(current);
      current = {key: numbered[2].replace(/[.;:]$/, '').trim(), value: ''};
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
  if (!source.html && !source.summary && !source.fields && !source.sections && typeof source.source_markdown === 'string' && source.source_markdown.trim()) {
    source.html = markdownToHtml(source.source_markdown);
    return source;
  }
  const rootText = !originalHasFields && userFacingText(decodedRoot)
    ? userFacingText(decodedRoot)
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
    const visibleText = userFacingText(candidate);
    if (visibleText && (typeof decoded === 'object' || (typeof candidate === 'string' && visibleText !== candidate.trim()))) {
      if (artifactType === 'meeting_agenda' || artifactType === 'meeting_summary') {
        const fields = meetingSections(visibleText).filter((field, index) => !(index === 0 && /^pauta|^resumo/i.test(field.key)));
        if (fields.length) {
          source.summary = '';
          source.fields = fields;
          delete source.html;
          delete source.text;
          delete source.answer;
          return source;
        }
      }
      source.html = markdownToHtml(visibleText);
      delete source.summary;
      delete source.text;
      delete source.answer;
      return source;
    }
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
        source.summary = normalizeFieldValue(decoded.summary ?? source.summary) || '';
        source.fields = fields.map((field, index) => ({
          ...(field && typeof field === 'object' ? field : {}),
          key: String(field?.key || field?.title || field?.heading || `Seção ${index + 1}`),
          value: normalizeFieldValue(field?.value ?? field?.content ?? field?.text),
        }));
        if ((artifactType === 'meeting_agenda' || artifactType === 'meeting_summary') && source.fields.length === 1) {
          const parsed = meetingSections(source.fields[0].value).filter((field, index) => !(index === 0 && /^pauta|^resumo/i.test(field.key)));
          if (parsed.length) source.fields = parsed;
        }
        delete source.html;
        return source;
      }
      return {...source, summary: '', html: ''};
    }
  }
  const rawFields = Array.isArray(source.fields) ? source.fields : Array.isArray(source.sections) ? source.sections : null;
  if (rawFields) {
    const fields = rawFields.map((field, index) => ({
      ...(field && typeof field === 'object' ? field : {}),
      key: String(field?.key || field?.title || `Seção ${index + 1}`),
      value: normalizeFieldValue(field?.value ?? field?.content ?? field?.text),
    }));
    if ((artifactType === 'meeting_agenda' || artifactType === 'meeting_summary') && fields.length === 1) {
      const parsed = meetingSections(fields[0].value).filter((field, index) => !(index === 0 && /^pauta|^resumo/i.test(field.key)));
      if (parsed.length) return {...source, summary: normalizeFieldValue(source.summary) || '', fields: parsed};
    }
    return {...source, fields, summary: normalizeFieldValue(source.summary) || ''};
  }
  return source;
}

function normalizeFieldValue(value) {
  const decoded = decode(value);
  if (typeof decoded === 'string') return userFacingText(decoded) || decoded;
  if (Array.isArray(decoded)) return decoded.map(item => typeof item === 'string' ? item : JSON.stringify(item)).join('\n');
  if (decoded && typeof decoded === 'object') {
    const sections = Array.isArray(decoded.sections) ? decoded.sections : Array.isArray(decoded.items) ? decoded.items : null;
    if (sections) return sections.map(item => {
      if (typeof item === 'string') return `- ${item}`;
      const heading = item.title || item.heading || item.key;
      const body = item.content || item.value || item.text || '';
      return `${heading ? `### ${heading}\n` : ''}${body}`.trim();
    }).join('\n\n');
    return userFacingText(decoded);
  }
  return String(value ?? '');
}
