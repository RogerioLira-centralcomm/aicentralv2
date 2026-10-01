// The public Super Tag (source and the minified file actually served) sends the whole-document position of a click.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const base = 'https://reports.example.test/connect/public/supertag/v1/doc-ui';
const cors = {'Access-Control-Allow-Origin': 'https://example.test', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type'};

async function run(browser, file) {
  const page = await browser.newPage({viewport: {width: 800, height: 600}});
  const clicks = [];
  const errors = [];
  page.on('pageerror', error => errors.push(error.message)); if (process.env.DEBUG_TAG) { page.on('console', m => console.log('CONSOLE', m.text())); page.on('requestfailed', r => console.log('FAILED', r.url(), r.failure()?.errorText)); }
  await page.route('https://example.test/**', route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/tag.js') return route.fulfill({contentType: 'text/javascript', body: fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_connect', file), 'utf8')});
    return route.fulfill({contentType: 'text/html', body: `<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0}.tall{height:3000px;position:relative}a{position:absolute;left:400px;top:2400px;width:100px;height:40px;display:block}</style></head>
      <body><div class="tall"><a href="/x" data-cadu-element="cta-fundo">Comprar</a></div>
      <script>document.addEventListener("click", function (e) { e.preventDefault(); });</script>
      <script async src="https://example.test/tag.js" data-cadu-site="doc-ui" data-cadu-config="${base}/config.json" data-cadu-consent="manual"></script></body></html>`});
  });
  await page.route(`${base}/config.json`, route => route.fulfill({headers: cors, json: {site_id: 'doc-ui', config_version: 1, consent_required: false, consent_mode: 'auto', visibility_enabled: false, audience_days: 90}}));
  await page.route(`${base}/collect`, route => {
    if (route.request().method() === 'OPTIONS') return route.fulfill({status: 204, headers: cors});
    for (const item of JSON.parse(route.request().postData()).events) { if (process.env.DEBUG_TAG) console.log('EVENT', item.kind, JSON.stringify(item.data)); if (item.kind === 'click') clicks.push(item); }
    return route.fulfill({status: 202, headers: cors, json: {accepted: 1}});
  });
  await page.route(`${base}/consent`, route => route.fulfill({status: 204, headers: cors}));
  await page.goto('https://example.test/');
  await page.waitForFunction(() => window.CaduSuperTag);
  await page.evaluate(() => window.CaduSuperTag.setConsent(true));
  await page.waitForTimeout(500);
  await page.evaluate(() => window.scrollTo(0, 2200));
  await page.waitForTimeout(200);
  await page.locator('a').click({position: {x: 50, y: 20}});
  // The tag flushes its buffer every 5 s.
  for (let i = 0; i < 90 && !clicks.length; i++) await page.waitForTimeout(100);
  await page.close();
  assert.deepEqual(errors, [], `${file}: sem erros de JavaScript`);
  assert.equal(clicks.length, 1, `${file}: um clique enviado`);
  return clicks[0].data;
}

async function main() {
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  for (const file of ['cadu-supertag-v1.js', 'cadu-supertag-v1.min.js']) {
    const data = await run(browser, file);
    // The link sits at (400..500, 2400..2440) of a 3000 px page; the click lands at (450, 2420) in the document.
    assert.equal(data.element_id, 'cta-fundo', `${file}: identifica o elemento`);
    assert.equal(data.dh, 3000, `${file}: altura do documento`);
    assert.equal(data.dx, Math.round(450 / 800 * 1000), `${file}: posição horizontal no documento`);
    assert.equal(data.dy, Math.round(2420 / 3000 * 1000), `${file}: posição vertical no documento, não no viewport`);
    assert.ok(data.y < 1000 && data.y > 0 && data.x === Math.round(450 / 800 * 1000), `${file}: mantém a posição no viewport`);
  }
  await browser.close();
  console.log('supertag-document-position: ok');
}
main().catch(error => { console.error(error); process.exit(1); });
