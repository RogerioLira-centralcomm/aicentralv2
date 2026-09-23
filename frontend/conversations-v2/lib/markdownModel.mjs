const ESCAPED = {'*': '\uE000', '_': '\uE001', '`': '\uE002', '~': '\uE003'};
const RESTORED = {'\uE000': '*', '\uE001': '_', '\uE002': '`', '\uE003': '~'};

export function normalizeInlineMarkdown(value) {
  return String(value || '')
    .replace(/\\([*_`~])/g, (_, mark) => ESCAPED[mark])
    .replace(/\*\*([^*\n]+)\*(?!\*)/g, '*$1*')
    .replace(/(?<!\*)\*([^*\n]+)\*\*/g, '*$1*')
    .replace(/__([^_\n]+)_(?!_)/g, '_$1_')
    .replace(/(?<!_)_([^_\n]+)__/g, '_$1_');
}

export function restoreEscapedMarkdown(value) {
  return String(value || '').replace(/[\uE000-\uE003]/g, mark => RESTORED[mark]);
}

const INLINE_MARKDOWN_PATTERN = /(\*\*[^*\n]+\*\*|(?<![\w])__[^_\n]+__(?![\w])|\*[^*\n]+\*|(?<![\w])_[^_\n]+_(?![\w])|~~[^~\n]+~~|`[^`\n]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\)|https?:\/\/[^\s<]+)/g;

export function splitInlineMarkdown(value) {
  return String(value || '').split(INLINE_MARKDOWN_PATTERN);
}

export function splitTableRow(value) {
  let row = String(value || '').trim();
  if (row.startsWith('|')) row = row.slice(1);
  if (row.endsWith('|') && !row.endsWith('\\|')) row = row.slice(0, -1);
  const cells = [];
  let cell = '';
  for (let index = 0; index < row.length; index += 1) {
    const char = row[index];
    if (char === '\\' && row[index + 1] === '|') {
      cell += '|';
      index += 1;
    } else if (char === '|') {
      cells.push(cell.trim());
      cell = '';
    } else {
      cell += char;
    }
  }
  cells.push(cell.trim());
  return cells;
}

export function isTableDivider(value, columnCount) {
  const cells = splitTableRow(value);
  return columnCount >= 2 && cells.length === columnCount
    && cells.every(cell => /^:?-{3,}:?$/.test(cell));
}
