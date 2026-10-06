// O nginx serve /static/ como imutável por 30 dias: sem hash na URL de cada módulo o navegador mistura
// a entrada nova com módulos antigos. Aqui o import map do servidor é aplicado ao editor real.
const {chromium,ensureEditorFixture,FIXTURE,PYTHON}=require('./studio-browser.cjs');
ensureEditorFixture();
const fs=require('fs'),assert=require('node:assert/strict'),{execFileSync}=require('child_process');
const tag=execFileSync(process.env.PYTHON||'.venv/bin/python',['-c',"from aicentralv2.static_modules import import_map_tag;print(import_map_tag('aicentralv2/static','js/mc-cadu-video.js'))"],{encoding:'utf8'}).trim();
assert.ok(tag.startsWith('<script type="importmap">'));
(async()=>{
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[],requested=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'||/import ?map/i.test(m.text()))errors.push(m.text())});
await page.route('http://studio.test/**',async route=>{
const url=new URL(route.request().url()),path=url.pathname;
if(path==='/'){const html=fs.readFileSync(FIXTURE+'/index.html','utf8').replace('<link rel="stylesheet"',tag+'<link rel="stylesheet"').replace('src="/static/js/mc-cadu-video.js"','src="/static/js/mc-cadu-video.js?v=entry"');return route.fulfill({contentType:'text/html',body:html});}
if(path.startsWith('/static/')){if(path.endsWith('.js'))requested.push(url.pathname+url.search);return route.fulfill({path:'aicentralv2'+path});}
if(path==='/clip.mp4')return route.fulfill({path:FIXTURE+'/clip.mp4',contentType:'video/mp4'});
let data={};
if(path.endsWith('/swap/library'))data={items:[]};
if(path.endsWith('/clips'))data={items:[]};
if(path.endsWith('/sounds'))data={items:[]};
if(path.endsWith('/projects'))data={items:[]};
if(path.endsWith('/capabilities'))data={model:'seedance',durations:[4,8],qualities:{draft:'720p',production:'720p'},skills:{}};
return route.fulfill({json:{success:true,data}});
});
await page.goto('http://studio.test/?client=1');
await page.waitForFunction(()=>document.querySelector('#mcVideoLibrary'));
await page.waitForTimeout(800);
const modules=requested.filter(u=>u.includes('/cadu-video/')||u.includes('/trocr/')||u.includes('media-progress'));
assert.ok(modules.length>=20,'módulos carregados: '+modules.length);
assert.ok(modules.every(u=>/\?v=[0-9a-f]{10}$/.test(u)),'sem hash: '+modules.filter(u=>!/\?v=[0-9a-f]{10}$/.test(u)).join(', '));
const bare=modules.map(u=>u.split('?')[0]);
assert.equal(new Set(bare).size,bare.length,'módulo carregado mais de uma vez: '+bare.filter((u,i)=>bare.indexOf(u)!==i).join(', '));
assert.deepEqual(errors,[]);
console.log('PASS import map: '+modules.length+' módulos com hash, cada um carregado uma vez, sem erros');
await browser.close();
})();
