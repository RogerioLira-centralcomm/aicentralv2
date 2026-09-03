module.exports = {
  plugins: {
    // Precisa vir ANTES do tailwindcss para resolver os @import em input.css
    // (ex.: @import "./enterprise-system.css";). Sem isso, o build gerado
    // por `npm run build` não inclui o design system vanilla.
    "postcss-import": {},
    tailwindcss: {},
    autoprefixer: {},
  },
};