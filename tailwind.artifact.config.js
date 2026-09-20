/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./aicentralv2/static/css/tailwind/artifact-safelist.html'],
  safelist: [
    { pattern: /^(container|block|inline-block|flex|grid|hidden|relative|absolute|sticky|overflow-hidden|overflow-auto|truncate|whitespace-nowrap)$/ },
    { pattern: /^(items|justify|content|self|place)-(start|end|center|between|around|evenly|stretch|baseline)$/ },
    { pattern: /^(flex|grid)-((row|col)(-reverse)?|cols-([1-6])|rows-([1-6]))$/ },
    { pattern: /^(w|h|min-h|max-w|max-h|size)-((full|screen|auto|fit|min|max)|(\d+\/\d+)|(\d+))$/ },
    { pattern: /^(m|mx|my|mt|mr|mb|ml|p|px|py|pt|pr|pb|pl|gap|space-x|space-y)-(0|1|2|3|4|5|6|8|10|12|16|20|24|32|40|48|auto)$/ },
    { pattern: /^(rounded|border|shadow)(-(none|sm|md|lg|xl|2xl|full|[trblxy])?)?$/ },
    { pattern: /^(text|bg|border|from|via|to)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950)$/ },
    { pattern: /^(text|bg|border)-(white|black|transparent|current|inherit)$/ },
    { pattern: /^(text|font|leading|tracking)-(xs|sm|base|lg|xl|2xl|3xl|4xl|5xl|6xl|7xl|8xl|9xl|thin|extralight|light|normal|medium|semibold|bold|extrabold|black|tight|snug|relaxed|loose|tighter|wide|wider|widest)$/ },
    { pattern: /^(uppercase|lowercase|capitalize|normal-case|italic|not-italic|underline|no-underline|antialiased|subpixel-antialiased)$/ },
    { pattern: /^(object)-(contain|cover|fill|none|scale-down)$/ },
    { pattern: /^(divide|ring|opacity|z|duration|ease|transition)-.*/ },
    'bg-[var(--cadu-brand-primary)]', 'bg-[var(--cadu-brand-secondary)]',
    'text-[var(--cadu-brand-primary)]', 'text-[var(--cadu-brand-secondary)]',
    'border-[var(--cadu-brand-primary)]', 'border-[var(--cadu-brand-secondary)]',
  ],
  theme: { extend: {} },
  plugins: [],
};
