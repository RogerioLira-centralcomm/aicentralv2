// Editor: cada versão mostra o tamanho real (L × A · KB/MB) no lugar de "Rascunho/Nova"; o modo Selecionar
// baixa as versões escolhidas num .zip válido e remove da sessão só depois de confirmar.
const {chromium}=require('./studio-browser.cjs');
const {execFileSync}=require('child_process');
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('node:assert/strict');
execFileSync(fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python3',['tests/frontend/render-studio-editor-fixture.py'],{stdio:'inherit'});
const HTML=fs.readFileSync('tests/frontend/.fixtures/studio-editor/index.html','utf8');
const STILL='http://studio.test/static/images/cadu/brand-icons/studio-192.png';
const versions=['Peça original','Desdobramento · Vertical 4:5','Cemig – 2ª via'].map((name,i)=>({id:'v'+i,name,url:`${STILL}?v=${i}`,dataUrl:`${STILL}?v=${i}`,status:i===1?'new':'draft'}));
(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1500,height:950},acceptDownloads:true}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(([k,v])=>localStorage.setItem(k,v),['cadu-studio-editor-v1:default:none',JSON.stringify({asset:versions[0],versions,selectedId:'v0',prompt:'',format:'1:1',outputSize:{width:1080,height:1080,format:'1:1'},quality:'draft',zoom:100})]);
  await page.route('https://**',route=>route.fulfill({status:200,contentType:'text/css',body:''}));
  await page.route('http://studio.test/**',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;
    if(p==='/')return route.fulfill({contentType:'text/html',body:HTML});
    if(p.startsWith('/static/'))return fs.existsSync('aicentralv2'+p)?route.fulfill({path:path.resolve('aicentralv2'+p),...(p.endsWith('.png')?{contentType:'image/png'}:{})}):route.fulfill({status:404,body:''});
    return route.fulfill({json:{success:true,data:{items:[],runs:[],personal_assets:[],assets:[]}}});});
  await page.goto('http://studio.test/');
  await page.getByRole('button',{name:/Continuar sessão em aberto/}).click({timeout:2500}).catch(()=>{});
  await page.locator('.se-vrow').first().waitFor();await page.waitForTimeout(900);

  const facts=await page.locator('.se-vrow__facts').allInnerTexts();
  assert.equal(facts.length,3);
  assert.ok(facts.every(text=>/^\d+ × \d+ · \d+([.,]\d+)? (KB|MB)$/.test(text)),`tamanho real em cada versão: ${JSON.stringify(facts)}`);
  assert.equal(await page.locator('.se-vrow').getByText(/Rascunho|^Nova$/).count(),0,'sem status de rascunho/nova');
  const thumb=await page.locator('.se-vrow__main img').first().boundingBox();
  assert.ok(thumb.width>=70,'miniatura maior');

  await page.locator('.se-left-rail').getByRole('button',{name:'Selecionar'}).click();
  await page.getByRole('toolbar',{name:/Ações nas versões/}).getByText('Todas').click();
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Baixar (3)'}).click()]);
  const file=path.join(os.tmpdir(),`versoes-${Date.now()}.zip`);
  await download.saveAs(file);
  const names=JSON.parse(execFileSync(fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python3',['-c',`import zipfile,json,sys;z=zipfile.ZipFile(sys.argv[1]);assert z.testzip() is None;print(json.dumps(z.namelist()))`,file]).toString());
  assert.deepEqual(names,['peca-original.png','desdobramento-vertical-4-5.png','cemig-2a-via.png'],'zip válido com um arquivo por versão');
  assert.match(download.suggestedFilename(),/^cadu-studio-versoes-\d{4}-\d{2}-\d{2}\.zip$/);

  await page.locator('.se-vrow__check').nth(2).uncheck();
  await page.getByRole('button',{name:'Remover (2)'}).click();
  await page.getByRole('alertdialog').getByText(/continuam salvas na Biblioteca/).waitFor();
  assert.equal(await page.locator('.se-vrow').count(),3,'nada é removido antes de confirmar');
  await page.getByRole('alertdialog').getByRole('button',{name:'Remover'}).click();
  await page.waitForTimeout(300);
  assert.deepEqual(await page.locator('.se-vrow__copy b').allInnerTexts(),['Cemig – 2ª via']);
  assert.deepEqual(errors,[]);
  console.log('PASS Editor: tamanho real nas versões, baixar em .zip e remover com confirmação');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
