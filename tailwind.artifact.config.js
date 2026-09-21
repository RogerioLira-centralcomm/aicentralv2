/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./aicentralv2/static/css/tailwind/artifact-safelist.html'],
  // Keep this finite. The previous broad regex + responsive variants generated
  // an enormous candidate matrix and could leave the artifact build hanging.
  safelist: [
    'block', 'flex', 'grid', 'hidden', 'relative', 'absolute', 'sticky',
    'items-center', 'justify-center', 'justify-between', 'overflow-hidden',
    'w-full', 'h-full', 'min-h-full', 'max-w-full', 'mx-auto',
    'gap-1', 'gap-2', 'gap-3', 'gap-4', 'gap-6', 'gap-8',
    'p-2', 'p-3', 'p-4', 'p-6', 'px-3', 'px-4', 'py-2', 'py-3', 'py-4',
    'rounded-lg', 'rounded-xl', 'rounded-2xl', 'border', 'shadow-sm',
    'text-xs', 'text-sm', 'text-base', 'font-medium', 'font-semibold',
    'text-white', 'text-black', 'bg-white', 'bg-black', 'bg-transparent',
    'bg-[var(--cadu-brand-primary)]', 'bg-[var(--cadu-brand-secondary)]',
    'text-[var(--cadu-brand-primary)]', 'text-[var(--cadu-brand-secondary)]',
    'border-[var(--cadu-brand-primary)]', 'border-[var(--cadu-brand-secondary)]',
  ],
  theme: { extend: {} },
  plugins: [],
};
