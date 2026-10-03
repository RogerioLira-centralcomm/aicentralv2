// The public Super Tag (source and the minified file actually served): collects without a consent step, honours an
// explicit opt-out, marks form submits as valid/invalid, captures who converted without sensitive fields, drops a
// batch the server refuses with 4xx and sends the remaining events by beacon on pagehide even with a fetch in flight.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const base = 'https://reports.example.test/connect/public/supertag/v1/lead-ui';
const cors = {'Access-Control-Allow-Origin': 'https://example.test', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type'};

const FORM = `<form id="f" data-cadu-form="contato" action="/obrigado" onsubmit="event.preventDefault()">
  <input name="nome" autocomplete="name" value="Maria da Silva">
  <input type="email" name="your-email" value="maria@example.com">
  <input type="tel" name="celular" value="(11) 98888-7777">
  <input name="empresa" value="ACME Ltda">
  <input name="interesse" value="Plano anual">
  <input type="password" name="senha" value="segredo123">
  <input name="cpf" value="123.456.789-09">
  <input name="documento" value="123.456.789-09">
  <input name="cc_num" autocomplete="cc-number" value="4111111111111111">
  <input type="hidden" name="token" value="abc">
  <input name="website" value="spam" style="position:absolute;left:-9999px">
  <div aria-hidden="true"><input name="interesse2" value="robo"></div>
  <input name="observacao" data-cadu-ignore value="nao ler">
  <button>Enviar</button>
</form>
<form id="g" novalidate onsubmit="event.preventDefault()"><input name="email" type="email" required value=""><button>Enviar</button></form>`;

async function run(browser, file) {
  const page = await browser.newPage({viewport: {width: 800, height: 600}});
  const events = [], leads = [], errors = [];
  let refuseFirst = true;
  page.on('pageerror', error => errors.push(error.message));
  await page.route('https://example.test/**', route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/tag.js') return route.fulfill({contentType: 'text/javascript', body: fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_connect', file), 'utf8')});
    return route.fulfill({contentType: 'text/html', body: `<!doctype html><html><head><meta charset="utf-8"></head><body>${FORM}
      <script async src="https://example.test/tag.js" data-cadu-site="lead-ui" data-cadu-config="${base}/config.json"></script></body></html>`});
  });
  await page.route(`${base}/config.json`, route => route.fulfill({headers: cors, json: {site_id: 'lead-ui', config_version: 1, visibility_enabled: false, audience_days: 90,
    form_capture: {enabled: true, fields: ['empresa', 'interesse', 'interesse2', 'senha', 'cpf', 'website', 'observacao']}}}));
  await page.route(`${base}/collect`, route => {
    if (route.request().method() === 'OPTIONS') return route.fulfill({status: 204, headers: cors});
    const batch = JSON.parse(route.request().postData()).events;
    if (refuseFirst) { refuseFirst = false; batch.forEach(item => events.push({...item, refused: true})); return route.fulfill({status: 400, headers: cors, json: {error: 'x'}}); }
    batch.forEach(item => events.push(item));
    return route.fulfill({status: 202, headers: cors, json: {accepted: batch.length}});
  });
  await page.route(`${base}/lead`, route => {
    if (route.request().method() === 'OPTIONS') return route.fulfill({status: 204, headers: cors});
    leads.push(JSON.parse(route.request().postData()));
    return route.fulfill({status: 202, headers: cors, json: {accepted: 1}});
  });
  await page.goto('https://example.test/');
  await page.waitForFunction(() => window.CaduSuperTag && window.CaduSuperTag.getSessionId());
  // The first batch (page_view) is refused with 400 and must be dropped, not resent.
  await page.evaluate(() => window.CaduSuperTag.trackEvent('primeiro'));
  for (let i = 0; i < 70 && !events.length; i++) await page.waitForTimeout(100);
  await page.locator('#f button').click();
  await page.locator('#g button').click();
  for (let i = 0; i < 70 && events.filter(item => item.kind === 'form_submit').length < 2; i++) await page.waitForTimeout(100);
  for (let i = 0; i < 30 && !leads.length; i++) await page.waitForTimeout(100);
  const refused = events.filter(item => item.refused).map(item => item.event_id);
  await page.waitForTimeout(5500);
  const resent = events.filter(item => !item.refused && refused.includes(item.event_id));

  // Opt-out: nothing else is collected.
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('cadu:consent', {detail: {analytics: false}})));
  const before = events.length;
  await page.evaluate(() => window.CaduSuperTag.trackEvent('depois_do_optout'));
  await page.waitForTimeout(5500);
  const afterOptOut = events.slice(before).filter(item => item.event_name === 'depois_do_optout');
  const optedOutId = await page.evaluate(() => window.CaduSuperTag.getVisitorId());
  await page.close();

  assert.deepEqual(errors, [], `${file}: sem erros de JavaScript`);
  assert.ok(refused.length > 0, `${file}: primeiro lote recusado`);
  assert.deepEqual(resent, [], `${file}: lote recusado com 4xx não é reenviado`);
  assert.ok(events.every(item => !('consent' in item)), `${file}: eventos não carregam consentimento`);
  const submits = events.filter(item => item.kind === 'form_submit');
  assert.equal(submits.length, 2, `${file}: dois envios de formulário`);
  assert.deepEqual(submits[0].data, {valid: true, form_id: 'contato'}, `${file}: envio válido`);
  assert.deepEqual(submits[1].data, {valid: false}, `${file}: envio inválido marcado`);
  assert.equal(leads.length, 1, `${file}: só o envio válido gera contato`);
  const lead = leads[0];
  assert.equal(lead.event_id, submits[0].event_id, `${file}: contato ligado ao evento do envio`);
  assert.equal(lead.name, 'Maria da Silva');
  assert.equal(lead.email, 'maria@example.com');
  assert.equal(lead.phone, '(11) 98888-7777');
  assert.deepEqual(lead.fields, {empresa: 'ACME Ltda', interesse: 'Plano anual'}, `${file}: só campos extras seguros e visíveis`);
  assert.equal(lead.path, '/');
  const raw = JSON.stringify(lead);
  for (const secret of ['segredo123', '123.456.789-09', '4111111111111111', 'abc"', 'spam', 'robo', 'nao ler']) {
    assert.ok(!raw.includes(secret), `${file}: não envia ${secret}`);
  }
  assert.deepEqual(afterOptOut, [], `${file}: opt-out explícito interrompe a coleta`);
  assert.equal(optedOutId, null, `${file}: sem identificador depois do opt-out`);
}

async function pagehideRace(browser, file) {
  // A fetch is still pending when the page is hidden: the beacon must go out anyway.
  const page = await browser.newPage();
  const beaconed = [];
  await page.route('https://example.test/**', route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/tag.js') return route.fulfill({contentType: 'text/javascript', body: fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_connect', file), 'utf8')});
    return route.fulfill({contentType: 'text/html', body: `<!doctype html><html><body><p>x</p>
      <script async src="https://example.test/tag.js" data-cadu-site="lead-ui" data-cadu-config="${base}/config.json"></script></body></html>`});
  });
  await page.route(`${base}/config.json`, route => route.fulfill({headers: cors, json: {site_id: 'lead-ui', config_version: 1, visibility_enabled: false, audience_days: 90}}));
  await page.route(`${base}/collect`, () => { /* never answers: the fetch stays in flight */ });
  await page.addInitScript(() => {
    const original = navigator.sendBeacon.bind(navigator);
    window.__beacons = [];
    navigator.sendBeacon = (url, data) => { data.text().then(text => window.__beacons.push(JSON.parse(text))); return true; };
    void original;
  });
  await page.goto('https://example.test/');
  await page.waitForFunction(() => window.CaduSuperTag && window.CaduSuperTag.getSessionId());
  // Ten events trigger an immediate fetch, which never completes.
  await page.evaluate(() => { for (let i = 0; i < 10; i++) window.CaduSuperTag.trackEvent('e' + i); });
  await page.evaluate(() => window.CaduSuperTag.trackConversion('depois'));
  await page.evaluate(() => window.dispatchEvent(new Event('pagehide')));
  await page.waitForTimeout(300);
  beaconed.push(...await page.evaluate(() => window.__beacons.flatMap(item => item.events)));
  await page.close();
  assert.ok(beaconed.some(item => item.kind === 'conversion' && item.event_name === 'depois'), `${file}: beacon sai mesmo com fetch em andamento`);
  assert.ok(beaconed.some(item => item.kind === 'page_leave'), `${file}: saída de página enviada`);
}

async function main() {
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  for (const file of ['cadu-supertag-v1.js', 'cadu-supertag-v1.min.js']) {
    await run(browser, file);
    await pagehideRace(browser, file);
  }
  await browser.close();
  console.log('supertag-leads: ok');
}
main().catch(error => { console.error(error); process.exit(1); });
