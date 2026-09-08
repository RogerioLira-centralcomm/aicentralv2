const vanilla = require("./tailwind.config.js");

/** Bundle temporário para Parâmetros, testes e páginas antigas. */
module.exports = {
  ...vanilla,
  content: [
    "./aicentralv2/templates/**/*.html",
    "./aicentralv2/static/**/*.js",
  ],
  plugins: [require("daisyui")],
  daisyui: {
    themes: [{
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
    }, "light", "dark", "corporate"],
  },
};
