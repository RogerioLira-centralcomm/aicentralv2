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
  plugins: [require("daisyui")],
  daisyui: {
    themes: [
      {
        centralcomm: {
          "primary": "#1E4D4F",
          "primary-focus": "#153638",
          "primary-content": "#ffffff",
          "secondary": "#F3B71B",
          "secondary-focus": "#d4a018",
          "secondary-content": "#ffffff",
          "accent": "#9CCF31",
          "accent-focus": "#8ab82c",
          "accent-content": "#ffffff",
          "neutral": "#3d4451",
          "neutral-focus": "#2a2e37",
          "neutral-content": "#ffffff",
          "base-100": "#ffffff",
          "base-200": "#F8F9FA",
          "base-300": "#DEE2E6",
          "base-content": "#1f2937",
          "info": "#2094f3",
          "success": "#28A745",
          "warning": "#FFC107",
          "error": "#DC3545",
        },
      },
      "light",
      "dark",
      "corporate",
    ],
  },
}