// Enhanced measurement of the public Super Tag (source and the minified file actually served), installed with the
// one-line snippet (only data-cadu-site): page views incl. SPA, scroll, outbound links, downloads, mailto/tel/WhatsApp,
// forms and HTML5 video are detected without any data-cadu-* attribute, and each switch of config.enhanced is obeyed.
// Only the kind, the link host and the file extension leave the browser: never paths, query strings, numbers or e-mails.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '../..');
const base = 'https://reports.example.test/connect/public/supertag/v1/enh-ui';
const cors = {'Access-Control-Allow-Origin': 'https://example.test', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type'};
const SWITCHES = ['page_changes', 'scroll', 'clicks', 'outbound', 'contacts', 'downloads', 'forms', 'video'];

const PAGE = `<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0}main{height:4000px}a,button{display:block;margin:8px}</style></head><body><main>
  <a id="out" href="https://parceiro.com.br/oferta?email=ana@example.com#x">Parceiro</a>
  <a id="pdf" href="/arquivos/contrato-maria.pdf?token=segredo">Contrato</a>
  <a id="zip" href="https://cdn.outro.com/pacote.zip">Pacote</a>
  <a id="mail" href="mailto:ana@example.com?subject=oi">E-mail</a>
  <a id="tel" href="tel:+5511988887777">Ligar</a>
  <a id="wa" href="https://wa.me/5511988887777?text=ola">WhatsApp</a>
  <a id="int" href="/sobre?utm_source=x">Sobre</a>
  <form id="f" onsubmit="event.preventDefault()"><input name="nome" value="Ana"><button>Enviar</button></form>
  <video id="v" muted></video>
</main>
<script>document.addEventListener('click', function (e) { if (e.target.closest('a')) e.preventDefault(); });</script>
<script async src="https://reports.example.test/v1/supertag.js" data-cadu-site="enh-ui"></script></body></html>`;

async function run(browser, file, enhanced) {
  const page = await browser.newPage({viewport: {width: 800, height: 600}});
  const events = [], errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('https://example.test/**', route => route.fulfill({contentType: 'text/html', body: PAGE}));
  await page.route('https://reports.example.test/v1/supertag.js', route => route.fulfill({contentType: 'text/javascript',
    body: fs.readFileSync(path.join(root, 'aicentralv2/static/cadu_connect', file), 'utf8')}));
  await page.route(`${base}/config.json`, route => route.fulfill({headers: cors, json: {site_id: 'enh-ui', config_version: 2,
    visibility_enabled: false, audience_days: 90, form_capture: {enabled: false, fields: []}, ...(enhanced ? {enhanced} : {})}}));
  await page.route(`${base}/collect`, route => {
    if (route.request().method() === 'OPTIONS') return route.fulfill({status: 204, headers: cors});
    JSON.parse(route.request().postData()).events.forEach(item => events.push(item));
    return route.fulfill({status: 202, headers: cors, json: {accepted: 1}});
  });
  await page.route(`${base}/lead`, route => route.fulfill({status: 202, headers: cors, json: {accepted: 0}}));
  await page.goto('https://example.test/inicio');
  await page.waitForFunction(() => window.CaduSuperTag && window.CaduSuperTag.getSessionId());
  for (const id of ['out', 'pdf', 'zip', 'mail', 'tel', 'wa', 'int']) {
    await page.locator(`#${id}`).click();
    await page.waitForTimeout(300); // the tag ignores a second click within 250 ms
  }
  await page.locator('#f button').click();
  await page.evaluate(() => window.scrollTo(0, 3500));
  await page.waitForTimeout(150);
  await page.evaluate(() => { const video = document.getElementById('v'); video.dispatchEvent(new Event('play')); video.dispatchEvent(new Event('ended')); });
  await page.evaluate(() => { history.pushState({}, '', '/spa/passo-2?filtro=a'); history.replaceState({}, '', '/spa/passo-2?filtro=b'); });
  await page.waitForTimeout(100);
  const api = await page.evaluate(() => [window.CaduSuperTag.event('lead_enviado', {value: '10,5', currency: 'brl', email: 'ana@example.com'}),
    window.CaduSuperTag.event('compra', {value: 99.9, currency: 'BRL', conversion: true}), window.CaduSuperTag.event('nome inválido')]);
  await page.evaluate(() => window.dispatchEvent(new Event('pagehide')));
  for (let i = 0; i < 70 && !events.some(item => item.event_name === 'compra'); i++) await page.waitForTimeout(100);
  await page.waitForTimeout(300);
  await page.close();
  assert.deepEqual(errors, [], `${file}: sem erros de JavaScript`);
  assert.deepEqual(api, [true, true, false], `${file}: API event() estilo gtag`);
  const raw = JSON.stringify(events);
  for (const secret of ['ana@example.com', '988887777', 'segredo', 'contrato-maria', 'oferta', 'pacote', 'subject', 'filtro', 'text=ola', 'Ana"']) {
    assert.ok(!raw.includes(secret), `${file}: não envia ${secret}`);
  }
  assert.ok(events.every(item => !item.path.includes('?') && !item.path.includes('#')), `${file}: caminhos sem query string ou fragmento`);
  return events;
}

const of = (events, kind) => events.filter(item => item.kind === kind);

async function main() {
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_PATH ? {executablePath: process.env.CHROME_PATH} : {})});
  for (const file of ['cadu-supertag-v1.js', 'cadu-supertag-v1.min.js']) {
    // Config without `enhanced` (older sites): everything on.
    const on = await run(browser, file, null);
    assert.deepEqual(of(on, 'page_view').map(item => item.path), ['/inicio', '/spa/passo-2'], `${file}: página inicial e troca de rota SPA, sem duplicar no replaceState`);
    assert.deepEqual(of(on, 'outbound_click').map(item => item.data), [{link_host: 'parceiro.com.br'}], `${file}: link externo só com o domínio`);
    assert.deepEqual(of(on, 'file_download').map(item => item.data), [{file_ext: 'pdf'}, {file_ext: 'zip', link_host: 'cdn.outro.com'}], `${file}: downloads com extensão`);
    assert.deepEqual(of(on, 'contact_click').map(item => item.data), [{channel: 'email'}, {channel: 'phone'}], `${file}: e-mail e telefone sem o contato`);
    assert.equal(of(on, 'whatsapp_click').length, 1, `${file}: WhatsApp detectado sozinho`);
    assert.ok(of(on, 'whatsapp_click')[0].data.dh > 0, `${file}: WhatsApp continua no mapa de cliques`);
    assert.equal(of(on, 'click').length, 7, `${file}: demais links no mapa de cliques (o botão do formulário incluso)`);
    assert.equal(of(on, 'form_submit').length, 1, `${file}: envio de formulário`);
    assert.ok(of(on, 'scroll_depth').length > 0, `${file}: rolagem`);
    assert.deepEqual(of(on, 'video').map(item => item.data), [{action: 'start'}, {action: 'complete'}], `${file}: vídeo início e fim`);
    assert.deepEqual(of(on, 'custom_event').map(item => [item.event_name, item.data]), [['lead_enviado', {value: 10.5, currency: 'BRL'}]], `${file}: só valor e moeda viajam`);
    assert.deepEqual(of(on, 'conversion').map(item => [item.event_name, item.data]), [['compra', {value: 99.9, currency: 'BRL'}]], `${file}: conversão pela API`);

    // Every switch off: only the first page view and the API calls remain.
    const off = await run(browser, file, Object.fromEntries(SWITCHES.map(key => [key, false])));
    assert.deepEqual(of(off, 'page_view').map(item => item.path), ['/inicio'], `${file}: sem page_view de SPA com a troca de página desligada`);
    for (const kind of ['click', 'whatsapp_click', 'outbound_click', 'file_download', 'contact_click', 'form_submit', 'scroll_depth', 'video']) {
      assert.deepEqual(of(off, kind), [], `${file}: ${kind} desligado não gera evento`);
    }
    assert.equal(of(off, 'conversion').length, 1, `${file}: API continua funcionando`);

    // Only contacts off: WhatsApp falls back to a plain click, mailto/tel send nothing besides the click map.
    const noContacts = await run(browser, file, {contacts: false});
    assert.deepEqual(of(noContacts, 'contact_click'), [], `${file}: contatos desligados`);
    assert.deepEqual(of(noContacts, 'whatsapp_click'), [], `${file}: WhatsApp desligado`);
    assert.equal(of(noContacts, 'click').length, 8, `${file}: WhatsApp vira clique comum no mapa`);
    assert.equal(of(noContacts, 'outbound_click').length, 1, `${file}: outros interruptores intactos`);
  }
  await browser.close();
  console.log('supertag-enhanced: ok');
}
main().catch(error => { console.error(error); process.exit(1); });
