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

const INLINE_MARKDOWN_PATTERN = /(\*\*[^*\n]+\*\*|(?<![\w])__[^_\n]+__(?![\w])|\*[^*\n]+\*|(?<![\w])_[^_\n]+_(?![\w])|~~[^~\n]+~~|`[^`\n]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g;

export function splitInlineMarkdown(value) {
  return String(value || '').split(INLINE_MARKDOWN_PATTERN);
}
