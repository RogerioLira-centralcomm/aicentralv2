// Criar: a biblioteca da sidebar mostra a miniatura e leva o endereço original no pedido e na pré-visualização grande.
const {chromium}=require('./studio-browser.cjs');
const {execFileSync}=require('child_process');
const fs=require('fs'),assert=require('node:assert/strict');
execFileSync(fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python3',['tests/frontend/render-studio-create-fixture.py'],{stdio:'inherit'});
const HTML=fs.readFileSync('tests/frontend/.fixtures/studio-create/index.html','utf8');
const STILL='/static/images/cadu/brand-icons/studio-192.png';
const FULL='/static/uploads/creative_generated/abc123.png',THUMB='/media/studio/480/creative_generated/abc123.png';
const projects=[{id:'p1',name:'Projeto',client_id:174,brand_name:'Marca',brand_context:{name:'Marca',palette:['#6D4AFF'],logo_url:STILL,assets:{logo:[STILL],logos:[]}}}];
const items=[
  {id:'a',image_url:FULL,thumb_url:THUMB,name:'Com miniatura'},
  {id:'b',asset_url:'/parametros/api/media/assets/7/content',thumb_url:'/parametros/api/media/assets/7/content?w=480',kind:'reference',title:'Só asset_url'},
  {id:'c',image_url:'https://cdn.example/c.png',name:'Sem miniatura'},
];
(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://cdnjs.cloudflare.com/**',route=>route.fulfill({contentType:'text/css',body:''}));
  await page.route('https://fonts.googleapis.com/**',route=>route.fulfill({contentType:'text/css',body:''}));
  await page.route('http://studio.test/**',async route=>{
    const url=new URL(route.request().url()),path=url.pathname,ok=data=>route.fulfill({json:{success:true,data}});
    if(path==='/')return route.fulfill({contentType:'text/html',body:HTML});
    if(path.startsWith('/static/'))return fs.existsSync('aicentralv2'+path)?route.fulfill({path:'aicentralv2'+path}):route.fulfill({status:404,body:''});
    if(path.endsWith('/project-contexts'))return ok({items:projects});
    if(path.endsWith('/studio/csrf'))return ok({token:'t'});
    if(path.endsWith('/creation-history'))return ok({items,runs:[],reference_masks:[]});
    if(path.endsWith('/library-sessions'))return ok({items:[],personal_assets:items,reference_masks:[]});
    if(path==='/workspace/api/creditos/resumo')return route.fulfill({json:{configured:true,monthly:1000,available:640}});
    return ok({items:[],runs:[],personal_assets:[]});
  });
  await page.goto('http://studio.test/');
  await page.locator('#libraryGrid .reference-card').first().waitFor({state:'attached'});
  const cards=await page.locator('#libraryGrid .reference-card').evaluateAll(nodes=>nodes.map(node=>({background:node.style.backgroundImage,url:node.dataset.referenceUrl})));
  assert.equal(cards.length,3);
  // The card paints the reduced copy; the request and the large preview keep the original.
  assert.match(cards[0].background,/\/media\/studio\/480\/creative_generated\/abc123\.png/);
  assert.equal(cards[0].url,FULL);
  assert.match(cards[1].background,/media\/assets\/7\/content\?w=480/);
  assert.equal(cards[1].url,'/parametros/api/media/assets/7/content');
  // Without a reduced copy the original is the fallback, so nothing is left blank.
  assert.match(cards[2].background,/cdn\.example\/c\.png/);
  assert.deepEqual(errors,[]);
  console.log('PASS Criar: biblioteca da sidebar usa miniatura no cartão e o original no pedido');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
