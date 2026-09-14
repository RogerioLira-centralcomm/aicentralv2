const base = require('./tailwind.config.js');
module.exports = {
  ...base,
  prefix: 'vs-',
  content: ['./aicentralv2/templates/parametros/_mc_video.html', './aicentralv2/static/js/cadu-video/*.js'],
  corePlugins: { preflight: false },
  plugins: [],
};
