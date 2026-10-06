// Ambiente local para ver as telas do Workspace sem login e sem banco.
// Uso: node tests/visual/workspace/serve.mjs  ->  http://localhost:5199/  (lista as telas)
import http from 'node:http';
import {readFileSync, existsSync, statSync} from 'node:fs';
import {resolve, extname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {pages} from './fixtures.mjs';

const root = resolve(fileURLToPath(new URL('../../../', import.meta.url)));
const staticDir = join(root, 'aicentralv2/static');
const port = Number(process.env.PORT || 5199);
const types = {'.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.woff2': 'font/woff2', '.json': 'application/json'};
const css = ['css/cadu-portals.css', 'css/cadu-shell-tokens.css', 'css/cadu-product-switch.css', 'css/cadu-nav-compact.css', 'css/cadu-app-sidebar.css', 'css/cadu-theme.css', 'cadu_workspace/conversations/react/app.css', 'cadu_workspace/untitled/workspace-kit.css'];
const img = name => `/static/images/cadu/products/${name}-icon.png`;

const page = ({bootstrap, rootClass = 'cv-home-root'}) => `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Workspace (fixture)</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
${css.map(href => `<link rel="stylesheet" href="/static/${href}">`).join('\n')}
<script src="/static/js/cadu-theme.js" data-theme-mode="light" data-theme-skin="workspace" data-theme-scope="workspace-conversations" data-theme-default="light"></script></head>
<body class="portal portal--workspace" data-product="workspace" data-authenticated="true"><main id="content" class="portal-content--workspace-react">
<div id="cadu-conversations-v2-root" class="${rootClass}"></div>
<script id="cadu-conversations-v2-bootstrap" type="application/json">${JSON.stringify({caduMark: img('cadu'), solutionIcons: {workspace: img('cadu'), planner: img('planner'), studio: img('studio'), connect: img('connect'), skills: img('skills')}, csrf: 'x', ...bootstrap}).replace(/</g, '\\u003c')}</script>
<script type="module" src="/static/cadu_workspace/conversations/react/app.js"></script></main></body></html>`;

http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  if (url.pathname.startsWith('/static/')) {
    const file = join(staticDir, decodeURIComponent(url.pathname.slice(8)));
    if (!file.startsWith(staticDir) || !existsSync(file) || !statSync(file).isFile()) { res.writeHead(404).end('not found'); return; }
    res.writeHead(200, {'content-type': types[extname(file)] || 'application/octet-stream'}).end(readFileSync(file));
    return;
  }
  const name = url.pathname.slice(1);
  if (pages[name]) { res.writeHead(200, {'content-type': 'text/html; charset=utf-8'}).end(page(pages[name])); return; }
  if (url.pathname.startsWith('/workspace/api') || url.pathname.startsWith('/api')) { res.writeHead(200, {'content-type': 'application/json'}).end('{}'); return; }
  res.writeHead(200, {'content-type': 'text/html; charset=utf-8'}).end(`<h1>Telas</h1><ul>${Object.keys(pages).map(key => `<li><a href="/${key}">${key}</a></li>`).join('')}</ul>`);
}).listen(port, () => console.log(`Workspace fixtures em http://localhost:${port}/`));
