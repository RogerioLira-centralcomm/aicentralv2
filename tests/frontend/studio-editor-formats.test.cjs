// Editor: uma peça horizontal vira vertical com um clique (um para um) e o desdobramento gera uma peça por
// formato. Em ambos o servidor recebe o formato de origem (aspect_hint), a instrução fixa de adaptação,
// nenhuma referência extra e o texto do campo de pedido não é reaproveitado.
const {chromium}=require('./studio-browser.cjs');
const {execFileSync}=require('child_process');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
execFileSync(fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python3',['tests/frontend/render-studio-editor-fixture.py'],{stdio:'inherit'});
const HTML=fs.readFileSync('tests/frontend/.fixtures/studio-editor/index.html','utf8');
execFileSync(fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python3',['-c',"from PIL import Image; Image.new('RGB',(1600,900),(40,120,90)).save('tests/frontend/.fixtures/horizontal-1600x900.png')"]);
const WIDE='http://studio.test/fixtures/horizontal.png';
const STILL='/static/images/cadu/brand-icons/studio-192.png';
const asset={id:'v1',name:'Peça horizontal',url:WIDE,dataUrl:WIDE,status:'draft'};
(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1500,height:950}}),tasks=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(([k,v])=>localStorage.setItem(k,v),['cadu-studio-editor-v1:default:none',JSON.stringify({asset,versions:[asset],selectedId:'v1',prompt:'Troque o CTA para Saiba mais',format:'16:9',outputSize:{width:1920,height:1080,format:'16:9'},quality:'draft',zoom:100,selectedGlobalReferences:['brand-reference-0']})]);
  await page.route('https://**',route=>route.fulfill({status:200,contentType:'text/css',body:''}));
  let taskId=0;
  await page.route('http://studio.test/**',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;
    if(p==='/')return route.fulfill({contentType:'text/html',body:HTML});
    if(p==='/fixtures/horizontal.png')return route.fulfill({path:path.resolve('tests/frontend/.fixtures/horizontal-1600x900.png'),contentType:'image/png'});
    if(p.startsWith('/static/'))return fs.existsSync('aicentralv2'+p)?route.fulfill({path:path.resolve('aicentralv2'+p)}):route.fulfill({status:404,body:''});
    const ok=data=>route.fulfill({json:{success:true,data}});
    if(p.endsWith('/studio/edit-quote'))return ok({estimated_tokens:22000});
    if(p.endsWith('/studio/tasks')&&req.method()==='POST'){tasks.push(JSON.parse(req.postData()).payload);return ok({id:'t'+(++taskId),status:'queued'});}
    if(/\/studio\/tasks\/t\d+$/.test(p))return ok({status:'ready',result:{image_url:STILL}});
    if(/\/sessions(\/[^/]+)?$/.test(p)&&req.method()!=='GET')return ok({id:'s1',revision:1,title:'Mesa',status:'active',assets:[]});
    return ok({items:[],runs:[],personal_assets:[],assets:[]});});
  await page.goto('http://studio.test/');
  await page.getByRole('button',{name:/Continuar sessão em aberto/}).click({timeout:2500}).catch(()=>{});
  await page.locator('.se-artboard img').waitFor();await page.waitForTimeout(600);

  // 1. Um para um: horizontal -> vertical
  await page.getByRole('button',{name:/Adaptar/}).click();
  const items=await page.locator('.se-adapt-menu [role=menuitem] b').allInnerTexts();
  assert.deepEqual(items,['Vertical 9:16','Vertical 4:5'],'peça horizontal oferece as versões verticais');
  await page.locator('.se-adapt-menu').getByText('~22 mil tokens').first().waitFor();
  if(process.env.MENU_SHOT)await page.screenshot({path:process.env.MENU_SHOT,clip:{x:250,y:55,width:1000,height:200}});
  await page.locator('.se-adapt-menu [role=menuitem]').first().click();
  await page.locator('.se-vrow__copy b',{hasText:'Vertical 9:16'}).waitFor({timeout:15000});
  const adapt=tasks[0];
  assert.equal(adapt.aspect_ratio,'9:16');
  assert.equal(adapt.aspect_hint,'16:9','o servidor sabe que a origem é horizontal e recompõe');
  assert.equal(adapt.output_width,1080);assert.equal(adapt.output_height,1920);
  assert.match(adapt.instruction,/Adapte esta peça para o formato 9:16/);
  assert.doesNotMatch(adapt.instruction,/CTA para Saiba mais/,'o texto do campo de pedido não é reaproveitado');
  assert.deepEqual(adapt.reference_images,[],'sem referências extras');
  assert.ok(await page.getByRole('button',{name:'Comparar'}).count(),'a versão adaptada pode ser comparada com a original');

  if(process.env.SHOT)await page.screenshot({path:process.env.SHOT});
  // 2. Desdobrar a partir da peça horizontal original
  await page.locator('.se-vrow__copy b',{hasText:'Peça horizontal'}).click();
  await page.waitForTimeout(400);
  await page.getByRole('button',{name:'Desdobrar'}).click();
  const dialog=page.getByRole('dialog');
  const active=await dialog.locator('.se-format-options button.is-active').allInnerTexts();
  assert.deepEqual(active,['Vertical 4:5','Quadrado 1:1','Vertical 9:16'],'todos os formatos menos o da própria peça');
  await dialog.getByText('3 peças · ~66 mil tokens').waitFor();
  await dialog.getByRole('button',{name:'Gerar 3 peças'}).click();
  await page.locator('.se-vrow__copy b',{hasText:'Desdobramento · Vertical 9:16'}).waitFor({timeout:20000});
  const expansion=tasks.slice(1);
  assert.deepEqual(expansion.map(item=>item.aspect_ratio),['4:5','1:1','9:16'],'uma peça por formato, sem repetir');
  assert.ok(expansion.every(item=>item.aspect_hint==='16:9'&&item.reference_images.length===0&&/Adapte esta peça/.test(item.instruction)));
  assert.deepEqual(errors,[]);
  console.log('PASS Editor: horizontal -> vertical em um clique e desdobramento com uma peça por formato');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
