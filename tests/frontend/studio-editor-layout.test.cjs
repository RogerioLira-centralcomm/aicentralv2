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
  const cases=[['vazio',null],['peça válida',good]];
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
        const lib=Array.from({length:10},(_,i)=>({id:'a'+i,asset_url:STILL,url:STILL,title:'Imagem do projeto '+(i+1),name:'Imagem do projeto '+(i+1)}));return route.fulfill({json:{success:true,data:{items:[],runs:[],personal_assets:lib,assets:lib,library:lib}}});});
      await page.goto('http://studio.test/');
      await page.locator('.se-toolbar').waitFor();await page.waitForTimeout(900);
      const m=await page.evaluate(()=>{const r=e=>{const b=document.querySelector(e).getBoundingClientRect();return {top:Math.round(b.top),height:Math.round(b.height),width:Math.round(b.width)}};return {nav:r('.csu-navbar'),toolbar:r('.se-toolbar'),stage:r('.se-stage'),main:r('.se-main'),layout:r('.se-layout')}});
      const where=`${label}, ${width}px`;
      assert.ok(m.toolbar.top-(m.nav.top+m.nav.height)<=4,`barra logo abaixo do topo (${where}): ${JSON.stringify(m)}`);
      assert.ok(Math.abs(m.main.height-m.layout.height)<=2,`coluna central ocupa a altura toda (${where}): ${JSON.stringify(m)}`);
      assert.ok(Math.abs(m.toolbar.width-m.main.width)<=2,`barra com a largura do palco (${where})`);
      assert.ok(m.stage.height>=m.main.height-m.toolbar.height-4,`palco ocupa o resto (${where}): ${JSON.stringify(m)}`);
      const rail=await page.evaluate(()=>{const r=document.querySelector('.se-left-rail'),sc=document.querySelector('.se-rail-scroll');return {width:Math.round(r.getBoundingClientRect().width),overflowX:sc.scrollWidth>sc.clientWidth+1,open:[...document.querySelectorAll('.se-rail-block.is-open .se-rail-block__toggle span')].map(n=>n.textContent)}});
      assert.ok(rail.width>=275,`sidebar com pelo menos 275px (${where}): ${rail.width}`);
      assert.equal(rail.overflowX,false,`sem rolagem lateral na sidebar (${where})`);
      assert.equal(rail.open.length,1,`uma seção aberta por vez (${where}): ${rail.open}`);
      if(label==='vazio')assert.ok(/Imagens/.test(rail.open[0]),`sem peça, a seção aberta é a das imagens (${where}): ${rail.open}`);
      if(label==='peça válida')assert.equal(rail.open[0],'Versões',`com peça, a seção aberta é a das versões (${where})`);
      if(label==='peça válida'){
        const size=await page.locator('.se-filesize').innerText();
        assert.match(size,/^\d+([.,]\d+)? (KB|MB)$/,`tamanho do arquivo ao lado de largura e altura (${where}): ${size}`);
        const box=await page.evaluate(()=>{const f=document.querySelector('.se-filesize').getBoundingClientRect(),h=document.querySelector('input[aria-label="Altura"]').getBoundingClientRect(),q=document.querySelector('.se-output-picker').getBoundingClientRect();const apart=(a,b)=>a.right<=b.left+1||b.right<=a.left+1||a.bottom<=b.top+1||b.bottom<=a.top+1;return {afterHeight:f.left>=h.right-1||f.top>=h.bottom-1,clearOfHeight:apart(f,h),clearOfQuality:apart(f,q),visible:f.width>20&&f.height>10}});
        assert.deepEqual(box,{afterHeight:true,clearOfHeight:true,clearOfQuality:true,visible:true},`tamanho do arquivo sem sobrepor os campos (${where})`);
      }
      if(label==='vazio'){
        assert.equal(await page.locator('.se-upload-stage').count(),1,`palco vazio mostra a área para soltar imagem (${where})`);
        assert.equal(await page.locator('.se-stage-broken').count(),0,'sem peça falsa de "Imagem de referência"');
        assert.equal(await page.locator('.se-rail-item').count(),0,'sem versões fantasma');
      }
      if(label==='vazio'){
        await page.locator('.se-rail-block .se-asset-grid button').first().click();
        await page.waitForTimeout(500);
        const after=await page.evaluate(()=>[...document.querySelectorAll('.se-rail-block.is-open .se-rail-block__toggle span')].map(n=>n.textContent));
        assert.deepEqual(after,['Versões'],`ao escolher uma imagem a lista de imagens recolhe (${where}): ${after}`);
        assert.equal(await page.locator('.se-upload-stage').count(),0,'a imagem escolhida abre no palco');
      }
      assert.deepEqual(errors,[]);
      await page.close();
    }
  }
  console.log('PASS Editor (página real do portal): barra no topo e palco preenchendo a coluna em 2 estados e 2 larguras');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
