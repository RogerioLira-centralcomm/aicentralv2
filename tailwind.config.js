/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./aicentralv2/templates/**/*.html",
    "./aicentralv2/static/**/*.js"
  ],
  theme: {
    extend: {
      /*
       * CentralX Typography Scale — use ONLY these sizes across the system.
       * xs   12px — metadata labels, badges, timestamps
       * sm   14px — menu items, dropdown, secondary body text
       * base 16px — default body, inputs, paragraphs
       * lg   18px — subtitles, secondary highlight values
       * xl   20px — card values (e.g. "R$ 0,00")
       * 2xl  24px — page titles (e.g. "Meus Reembolsos")
       * RULE: no text below 12px (xs).
       */
      fontSize: {
        xs:   ['0.75rem',  { lineHeight: '1.25' }],
        sm:   ['0.875rem', { lineHeight: '1.375' }],
        base: ['1rem',     { lineHeight: '1.5' }],
        lg:   ['1.125rem', { lineHeight: '1.5' }],
        xl:   ['1.25rem',  { lineHeight: '1.375' }],
        '2xl':['1.5rem',   { lineHeight: '1.25' }],
      },
      colors: {
        primary: '#3B82F6',
        'primary-light': '#60A5FA',
        'primary-dark': '#2563EB',
        'text-primary': '#1F2937',
        border: '#E5E7EB',
        'accent-yellow': '#F59E0B'
      }
    }
  },
  plugins: [],
}