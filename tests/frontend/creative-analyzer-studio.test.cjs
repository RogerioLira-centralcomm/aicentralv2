const { chromium } = require('/Users/apololira/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const id = '6d71570e-959c-49de-b829-8ad201a71464';
  const html = `<!doctype html><html><head>
    <link rel="stylesheet" href="/static/css/creative-analyzer-studio.css">
    <link rel="stylesheet" href="/static/css/creative-analyzer-share.css">
    <link rel="stylesheet" href="/static/css/creative-analyzer-interactive.css">
  </head><body><div class="studio-analyzer" id="creativeAnalyzer" data-client-id="174"
    data-history-url="/studio/api/analyzer/history" data-projects-url="/studio/api/analyzer/projects"
    data-create-url="/studio/api/analyzer/analyses" data-detail-root="/studio/api/analyzer/analyses/"
    data-library-still-url="/library" data-library-video-url="/clips" data-image-editor-url="/imagem"
    data-video-editor-url="/video" data-share-suffix="/share" data-csrf="csrf" data-analysis-id="${id}">
    <main class="analyzer-main"><form id="analyzerUpload"><select id="analyzerProject" name="project_ref"><option value="">Sem projeto</option></select><input id="analyzerFile" type="file"><button type="submit">Analisar criativo</button></form>
    <section class="analyzer-result" id="analyzerResult" hidden></section>
    <section class="analyzer-history"><p id="analyzerStatus"></p><div class="analyzer-projects" id="analyzerGrid"></div><button id="analyzerMore" hidden></button></section>
    </main></div><script src="/static/js/creative-analyzer-studio.js"></script></body></html>`;
  const analysis = {
    public_id: id, original_name: 'Campanha de verão.png', media_type: 'image', thumbnail_url: '/thumb.png',
    result_json: {
      score: { geral: 82, clareza: 78, impacto_visual: 88 },
      attention_analysis: { attention_score: 81, hook_score: 76, visual_hierarchy: {
        first_fixation: 'Produto', sequence: [
          { element: 'Produto', x: 48, y: 42 }, { element: 'Oferta', x: 29, y: 68 }, { element: 'CTA', x: 72, y: 83 },
        ],
      } },
      message: { value_proposition: 'Oferta direta' }, audience: { life_moment: 'Verão' },
      performance_prediction: { best_channel: 'Instagram' }, recommendations: [{ action: 'Ampliar CTA' }],
    },
  };
  await page.route('http://studio.test/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: html });
    if (path.startsWith('/static/')) return route.fulfill({ path: `aicentralv2${path}` });
    if (path === '/thumb.png') return route.fulfill({ path: 'tests/fixtures/creatives/arraial-1x1.png', contentType: 'image/png' });
    if (path.endsWith('/projects')) return route.fulfill({ json: { items: [{ ref: 'ci:summer', name: 'Campanha de verão' }] } });
    if (path.endsWith('/history')) return route.fulfill({ json: { items: [
      { source: 'studio', source_uuid: id, name: 'Campanha de verão.png', media_type: 'image', score: 82, project_ref: 'ci:summer', project_name: 'Campanha de verão', result_url: `/analyzer/${id}`, thumbnail: '/thumb.png' },
      { source: 'legacy', name: 'Filme anterior.mp4', media_type: 'video', score: 70, opens_legacy: true, project_name: 'Acervo anterior', result_url: 'https://cadu.test/creative-analyzer/old' },
    ], next_offset: null } });
    if (path.endsWith(id)) return route.fulfill({ json: { analysis } });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('http://studio.test/');
  await page.waitForSelector('.analyzer-attention-point');
  assert.equal(await page.locator('.analyzer-attention-point').count(), 3);
  assert.deepEqual(await page.locator('.analyzer-project-group h3').allTextContents(), ['Campanha de verão', 'Acervo anterior']);
  assert.equal(await page.locator('#analyzerProject option').count(), 2);
  assert.equal(await page.getByRole('button', { name: 'Adicionar à Biblioteca' }).count(), 1);
  assert.equal(await page.getByRole('button', { name: 'Abrir editor de imagem' }).count(), 1);
  for (const width of [1280, 760, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true, `overflow at ${width}px`);
  }
  await page.screenshot({ path: '/private/tmp/creative-analyzer-phase4.png', fullPage: true });
  assert.deepEqual(errors, []);
  console.log('PASS project shelves, attention path, editor actions and 390–1280px layout');
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
