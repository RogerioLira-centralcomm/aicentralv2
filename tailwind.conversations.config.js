/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./frontend/conversations-v2/**/*.{js,jsx}'],
  prefix: 'cv-',
  corePlugins: {preflight: false},
  theme: {
    extend: {
      colors: {
        ink: '#071012',
        panel: '#0b1518',
        raised: '#101e21',
        teal: '#20c7b5',
        mist: '#9bb1ae',
      },
      boxShadow: {
        composer: '0 18px 54px rgba(0, 0, 0, .28)',
      },
    },
  },
  plugins: [],
};
