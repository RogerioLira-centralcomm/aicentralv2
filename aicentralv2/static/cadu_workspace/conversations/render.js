/* Deliberately bounded Markdown subset. Raw model HTML is never trusted. */
(() => {
  'use strict';
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const visible = value => String(value || '').replace(/<(think|thinking|analysis)\b[^>]*>[\s\S]*?(?:<\/\1\s*>|$)/gi, '');
  function inline(value) {
    const tokens = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\n]+\*|\[[^\]\n]+\]\([^\s)]+\))/g;
    let output = '', position = 0;
    for (const match of value.matchAll(tokens)) {
      output += escape(value.slice(position, match.index));
      const token = match[0];
      if (token.startsWith('`')) output += '<code>' + escape(token.slice(1, -1)) + '</code>';
      else if (token.startsWith('**')) output += '<strong>' + escape(token.slice(2, -2)) + '</strong>';
      else if (token.startsWith('*')) output += '<em>' + escape(token.slice(1, -1)) + '</em>';
      else {
        const link = token.match(/^\[([^\]]+)\]\((.+)\)$/);
        // No relative, data, javascript or embedded image URLs from model output.
        output += /^https?:\/\//i.test(link[2])
          ? '<a target="_blank" rel="noopener noreferrer" href="' + escape(link[2]) + '">' + escape(link[1]) + '</a>'
          : escape(token);
      }
      position = match.index + token.length;
    }
    return output + escape(value.slice(position));
  }
  const cells = line => line.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim());
  function html(value) {
    const lines = visible(value).replace(/\r\n?/g, '\n').split('\n');
    const result = [];
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (!line.trim()) continue;
      const fence = line.match(/^\s*```(.*)$/);
      if (fence) {
        const code = [];
        while (++i < lines.length && !/^\s*```\s*$/.test(lines[i])) code.push(lines[i]);
        result.push('<figure class="conversation-code"><figcaption>' + escape(fence[1].trim() || 'Código') + '</figcaption><pre><code>' + escape(code.join('\n')) + '</code></pre></figure>');
      } else if (line.includes('|') && lines[i + 1]?.includes('|') && cells(lines[i + 1]).every(cell => /^:?-{3,}:?$/.test(cell))) {
        const headers = cells(line); i++;
        let rows = '';
        while (i + 1 < lines.length && lines[i + 1].includes('|') && lines[i + 1].trim()) {
          const row = cells(lines[++i]);
          rows += '<tr>' + headers.map((_, index) => '<td>' + inline(row[index] || '') + '</td>').join('') + '</tr>';
        }
        result.push('<div class="conversation-table" tabindex="0" role="region" aria-label="Tabela da resposta"><table><thead><tr>' + headers.map(cell => '<th scope="col">' + inline(cell) + '</th>').join('') + '</tr></thead><tbody>' + rows + '</tbody></table></div>');
      } else if (/^#{1,6}\s/.test(line)) {
        result.push('<h4>' + inline(line.replace(/^#{1,6}\s+/, '')) + '</h4>');
      } else if (/^\s*(?:[-*+] |\d+\. )/.test(line)) {
        const ordered = /^\s*\d+\./.test(line), tag = ordered ? 'ol' : 'ul';
        const pattern = ordered ? /^\s*\d+\.\s+/ : /^\s*[-*+]\s+/;
        const items = [];
        do { items.push('<li>' + inline(lines[i].replace(pattern, '')) + '</li>'); i++; } while (i < lines.length && pattern.test(lines[i]));
        i--; result.push('<' + tag + '>' + items.join('') + '</' + tag + '>');
      } else if (/^>\s?/.test(line)) result.push('<blockquote>' + inline(line.replace(/^>\s?/, '')) + '</blockquote>');
      else result.push('<p>' + inline(line) + '</p>');
    }
    return result.join('');
  }
  function streamingHtml(value) {
    // Render the same safe Markdown subset while tokens arrive. A partial
    // table is deliberately presented as a table being assembled instead of
    // exposing its Markdown pipes to the reader.
    const source = visible(value).replace(/\r\n?/g, '\n');
    const lines = source.split('\n');
    const tableStart = lines.findIndex((line, index) => line.includes('|') &&
      lines[index + 1]?.includes('|') && cells(lines[index + 1]).every(cell => /^:?-{3,}:?$/.test(cell)));
    if (tableStart < 0) return html(source);
    const before = lines.slice(0, tableStart).join('\n');
    const headers = cells(lines[tableStart]);
    const body = lines.slice(tableStart + 2).filter(line => line.includes('|') && line.trim()).map(cells);
    const table = '<div class="conversation-table conversation-table--building" tabindex="0" role="region" aria-label="Tabela sendo montada">'
      + '<div class="conversation-table-progress"><span></span>Montando tabela</div>'
      + '<table><thead><tr>' + headers.map(cell => '<th scope="col">' + inline(cell) + '</th>').join('')
      + '</tr></thead><tbody>' + body.map(row => '<tr>' + headers.map((_, index) => '<td>' + inline(row[index] || '') + '</td>').join('') + '</tr>').join('')
      + '</tbody></table></div>';
    return html(before) + table;
  }
  function render(node, value, streaming = false) {
    node.classList.add('conversation-rich');
    if (streaming) node.innerHTML = streamingHtml(value);
    else node.innerHTML = html(value); // Only locally generated, escaped, allowlisted markup.
  }
  function fileLink(value) {
    if (typeof value !== 'string' || /[\s\\]/.test(value)) return null;
    try {
      const url = new URL(value);
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? value : null;
    } catch (_) { return null; }
  }
  function renderFiles(node, files) {
    if (!Array.isArray(files)) return;
    files.slice(0, 100).forEach(file => {
      if (!file || typeof file !== 'object') return;
      const row = document.createElement('small');
      const name = typeof file.name === 'string' ? file.name : 'Arquivo';
      const url = fileLink(file.url);
      if (url) {
        const link = document.createElement('a');
        link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        link.textContent = 'Abrir ' + name;
        link.setAttribute('aria-label', 'Abrir ' + name + ' em nova aba');
        row.append(link);
      } else row.textContent = name + ' — sem link disponível';
      node.append(row);
    });
  }
  globalThis.CaduConversationRenderer = {html, visible, render, fileLink, renderFiles};
})();
