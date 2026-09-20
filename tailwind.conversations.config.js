/** @type {import('tailwindcss').Config} */
module.exports = {
  // The conversation composer is shared with the workspace home. Keep both
  // component trees in the scan so imported JSX utility classes are emitted
  // into the conversations bundle as well.
  content: [
    './frontend/conversations-v2/**/*.{js,jsx}',
    './frontend/cadu-design-system/**/*.{js,jsx}',
  ],
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
