// Editor na página real do portal (cadu_studio/trocr.html + CSS do portal): a barra de ferramentas fica
// logo abaixo do topo e o palco ocupa o resto, com palco vazio, arquivo ausente e peça válida.
// O CSS do portal tem `.portal main { margin:auto }`; sem a correção a coluna central virava um item
// centralizado e do tamanho do conteúdo, e a barra flutuava no meio da tela.
const {chromium}=require('./studio-browser.cjs');
const {execFileSync}=require('child_process');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
execFileSync(fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python3',['tests/frontend/render-studio-editor-fixture.py'],{stdio:'inherit'});
const HTML=fs.readFileSync('tests/frontend/.fixtures/studio-editor/index.html','utf8');
const STILL='/static/images/cadu/brand-icons/studio-192.png';
const bad={id:'v1',name:'Imagem de referência',url:'http://studio.test/missing.png',dataUrl:'http://studio.test/missing.png',status:'draft'};
const good={id:'v2',name:'Peça',url:STILL,dataUrl:STILL,status:'draft'};
(async()=>{
  const browser=await chromium.launch({headless:true});
  const cases=[['vazio',null],['arquivo ausente',bad],['peça válida',good]];
  for(const width of [1704,1280]){
    for(const [label,asset] of cases){
      const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      if(asset)await page.addInitScript(([k,v])=>localStorage.setItem(k,v),['cadu-studio-editor-v1:default',JSON.stringify({asset,versions:[asset],selectedId:asset.id,prompt:'',format:'4:5',outputSize:{width:1080,height:1350,format:'4:5'},quality:'draft',zoom:100})]);
      await page.route('https://**',route=>route.fulfill({status:200,contentType:'text/css',body:''}));
      await page.route('http://studio.test/**',async route=>{const url=new URL(route.request().url()),p=url.pathname;
        if(p==='/')return route.fulfill({contentType:'text/html',body:HTML});
        if(p==='/missing.png')return route.fulfill({status:404,body:''});
        if(p.startsWith('/static/'))return fs.existsSync('aicentralv2'+p)?route.fulfill({path:path.resolve('aicentralv2'+p)}):route.fulfill({status:404,body:''});
        return route.fulfill({json:{success:true,data:{items:[],runs:[],personal_assets:[],assets:[]}}});});
      await page.goto('http://studio.test/');
      await page.locator('.se-toolbar').waitFor();await page.waitForTimeout(900);
      const m=await page.evaluate(()=>{const r=e=>{const b=document.querySelector(e).getBoundingClientRect();return {top:Math.round(b.top),height:Math.round(b.height),width:Math.round(b.width)}};return {nav:r('.csu-navbar'),toolbar:r('.se-toolbar'),stage:r('.se-stage'),main:r('.se-main'),layout:r('.se-layout')}});
      const where=`${label}, ${width}px`;
      assert.ok(m.toolbar.top-(m.nav.top+m.nav.height)<=4,`barra logo abaixo do topo (${where}): ${JSON.stringify(m)}`);
      assert.ok(Math.abs(m.main.height-m.layout.height)<=2,`coluna central ocupa a altura toda (${where}): ${JSON.stringify(m)}`);
      assert.ok(Math.abs(m.toolbar.width-m.main.width)<=2,`barra com a largura do palco (${where})`);
      assert.ok(m.stage.height>=m.main.height-m.toolbar.height-4,`palco ocupa o resto (${where}): ${JSON.stringify(m)}`);
      if(label==='vazio'){
        assert.equal(await page.locator('.se-upload-stage').count(),1,`palco vazio mostra a área para soltar imagem (${where})`);
        assert.equal(await page.locator('.se-stage-broken').count(),0,'sem peça falsa de "Imagem de referência"');
        assert.equal(await page.locator('.se-rail-item').count(),0,'sem versões fantasma');
      }
      assert.deepEqual(errors,[]);
      await page.close();
    }
  }
  console.log('PASS Editor (página real do portal): barra no topo e palco preenchendo a coluna em 3 estados e 2 larguras');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
