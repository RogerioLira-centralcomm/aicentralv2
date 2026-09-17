/* Deliberately bounded Markdown subset. Raw model HTML is never trusted. */
(() => {
  'use strict';
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const visible = value => String(value || '')
    .replace(/<(think|thinking|analysis)\b[^>]*>[\s\S]*?(?:<\/\1\s*>|$)/gi, '')
    .replace(/<!--SMART_DOC:([\s\S]*?)(-->|$)/gi, (match, raw, ending) => {
      // A SmartDoc envelope is a legacy provider convention, never customer
      // facing chat syntax. While it streams, hide the incomplete envelope;
      // once complete, keep its draft as ordinary editable Markdown.
      if (ending !== '-->') return '';
      try {
        const draft = JSON.parse(raw);
        const content = typeof draft?.conteudo === 'string' ? draft.conteudo.trim() : '';
        const title = typeof draft?.titulo === 'string' ? draft.titulo.trim().slice(0, 250) : '';
        return content ? '\n\n' + (title ? '# ' + title + '\n\n' : '') + content + '\n\n' : '';
      } catch (_) { return ''; }
    });
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
  const tableStartsAt = (lines, index) => Boolean(lines[index]?.includes('|') && lines[index + 1]?.includes('|') &&
    cells(lines[index + 1]).every(cell => /^:?-{3,}:?$/.test(cell)));
  function tableHtml(headers, rows, building = false) {
    const progress = building ? '<div class="conversation-table-progress"><span></span>Montando tabela</div>' : '';
    // Seven narrow columns make people pan across a spreadsheet in the middle
    // of a conversation. Preserve every value, but change the presentation to
    // labelled records once a table crosses the reading-width limit.
    if (headers.length > 6) {
      const records = rows.map(row => {
        const title = inline(row[0] || 'Item');
        const details = headers.slice(1).map((header, index) => {
          const value = row[index + 1] || '';
          return value ? '<div><dt>' + inline(header) + '</dt><dd>' + inline(value) + '</dd></div>' : '';
        }).join('');
        return '<article><h5>' + title + '</h5><dl>' + details + '</dl></article>';
      }).join('');
      return '<section class="conversation-table conversation-table--stacked" tabindex="0" role="region" aria-label="Resumo estruturado da tabela">'
        + progress + records + '</section>';
    }
    const body = rows.map(row => '<tr>' + headers.map((_, index) => '<td>' + inline(row[index] || '') + '</td>').join('') + '</tr>').join('');
    return '<div class="conversation-table' + (building ? ' conversation-table--building' : '') + '" tabindex="0" role="region" aria-label="Tabela da resposta">'
      + progress + '<table><thead><tr>' + headers.map(cell => '<th scope="col">' + inline(cell) + '</th>').join('')
      + '</tr></thead><tbody>' + body + '</tbody></table></div>';
  }
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
      } else if (tableStartsAt(lines, i)) {
        const headers = cells(line); i++;
        const rows = [];
        while (i + 1 < lines.length && lines[i + 1].includes('|') && lines[i + 1].trim()) {
          // A new header immediately followed by its delimiter begins another
          // table even when the model forgot an empty Markdown line.
          if (tableStartsAt(lines, i + 1)) break;
          rows.push(cells(lines[++i]));
        }
        result.push(tableHtml(headers, rows));
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
    const tableStart = lines.findIndex((_, index) => tableStartsAt(lines, index));
    if (tableStart < 0) return html(source);
    const before = lines.slice(0, tableStart).join('\n');
    const headers = cells(lines[tableStart]);
    const nextTable = lines.findIndex((_, index) => index > tableStart && tableStartsAt(lines, index));
    const currentTableEnd = nextTable < 0 ? lines.length : nextTable;
    const body = lines.slice(tableStart + 2, currentTableEnd).filter(line => line.includes('|') && line.trim()).map(cells);
    const table = tableHtml(headers, body, true);
    return html(before) + table + (nextTable < 0 ? '' : html(lines.slice(nextTable).join('\n')));
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
