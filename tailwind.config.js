/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./aicentralv2/templates/**/*.html",
    "./aicentralv2/static/**/*.js"
  ],
  theme: {
    extend: {
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