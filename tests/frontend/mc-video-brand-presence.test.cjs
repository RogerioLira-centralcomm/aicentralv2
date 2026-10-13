// Vídeo · presença da marca: o painel mostra logo, cores e fonte; o nível escolhido vai ao diretor e marca as cenas;
// cada cena pode ser ajustada; a imagem da cena leva a marcação; textos e legendas usam a fonte e as cores da marca.
const {chromium,ensureEditorFixture,FIXTURE,ARTIFACTS}=require('./studio-browser.cjs');
ensureEditorFixture();
const fs=require('fs'),assert=require('node:assert/strict');
const KIT={name:'Cemig',logo_url:'/static/images/canais/prime-video.svg',logo_count:1,primary_color:'#176b5e',has_references:true,
  palette:[{hex:'#176b5e',name:'verde-azulado escuro'},{hex:'#f2b705',name:'amarelo'}],
  font:{family:'Montserrat',url:'/static/fonts/brand/Montserrat-Bold.ttf',source:'bundled',requested:''}};
const MARKS={none:p=>'none',discreet:p=>'none',balanced:p=>['offer','proof'].includes(p)?'badge':'none',strong:p=>'badge'};
async function open(browser,kit){
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],posted=[],images=[];
  page.on('pageerror',e=>errors.push(e.message));
  const dialogs=[];page.on('dialog',d=>{dialogs.push(d.message());d.accept();});
  await page.route('http://studio.test/**',async route=>{
    const url=new URL(route.request().url()),path=url.pathname;
    if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(FIXTURE+'/index.html','utf8')});
    if(path.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+path});
    if(path==='/clip.mp4')return route.fulfill({path:FIXTURE+'/clip.mp4',contentType:'video/mp4'});
    let data={};
    if(path.endsWith('/brand-kit'))data=kit;
    if(path.endsWith('/swap/library'))data={items:url.searchParams.get('media')==='video'?[{id:'clip1',name:'Clipe',video_url:'/clip.mp4'}]:[1,2,3].map(n=>({id:'p'+n,name:'Peça '+n,image_url:'/static/images/canais/prime-video.svg',thumb_url:'/static/images/canais/prime-video.svg'}))};
    if(path.endsWith('/agent/storyboard')){
      const body=JSON.parse(route.request().postData());posted.push(body);
      const rows=[['hook','Família na sala'],['offer','Roteador em destaque'],['end','Fachada da loja']];
      data={brand_presence:body.brand_presence,style:body.style,warnings:[],concept:{ideia:'A fibra que some da sala',gancho:'Um cabo cortado',arco:'Do caos à calma'},
        beats:rows.map(([purpose,visual],i)=>({id:'beat-'+(i+1),purpose,visual,shot:['detalhe','médio','geral'][i],setting:['Sala à noite','Cozinha','Fachada'][i],motion:'push-in',hold:'',transition:'cut',spoken:'Fala '+(i+1),
        brand:body.brand_presence==='none'?'none':i===rows.length-1?'signature':MARKS[body.brand_presence](purpose)}))};
    }
    if(path.endsWith('/agent/storyboard/image')){const body=JSON.parse(route.request().postData());if(body.dry_run)data={credits_per_image:120,credits_with_reference:150,brand_reference:true};else{images.push(body);data={image_url:'/static/images/canais/prime-video.svg?n='+images.length,scene_id:'p'+images.length,run_id:'run-1',charged_credits:150};}}
    if(path.endsWith('/clips'))data={items:[]};
    if(path.endsWith('/sounds'))data={items:[]};
    if(path.endsWith('/projects'))data=route.request().method()==='POST'?{id:'project',revision:1,document:JSON.parse(route.request().postData()).document}:{items:[]};
    if(path.endsWith('/video-project'))data={project:{active_clip_id:'clip1'}};
    if(path.endsWith('/inspect')||path.endsWith('/tasks'))data={has_audio:true,waveform:[.3,.8,.2],frames:[]};
    if(path.endsWith('/capabilities'))data={model:'seedance',durations:[4,8],qualities:{draft:'720p',production:'720p'},skills:{}};
    return route.fulfill({json:{success:true,data}});
  });
  await page.goto('http://studio.test/?client=1&clip=clip1');
  await page.waitForFunction(()=>document.querySelector('#mcSwapVideo')?.videoWidth===320);
  return {page,errors,posted,images,dialogs};
}
const marks=page=>page.$$eval('#mcVideoDraft [data-draft-field="brand"]',rows=>rows.map(row=>row.value));
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const {page,errors,posted,images,dialogs}=await open(browser,KIT);
  // 1. O que vem da marca, antes de montar: logo, cores, fonte; "Discreta" já vem escolhida.
  await page.waitForFunction(()=>document.querySelector('#mcVideoBrandKit img'));
  assert.equal(await page.locator('#mcVideoBrandKit .mc-video-brand-swatch').count(),2);
  assert.match(await page.locator('#mcVideoBrandKit').innerText(),/Montserrat · fonte da marca/);
  assert.equal(await page.locator('input[name="mcVideoBrandPresence"]:checked').getAttribute('value'),'discreet');
  assert.match(await page.locator('#mcVideoBrandHint').innerText(),/só na assinatura do fechamento/);
  // 2. A pessoa escolhe o nível; ele vai ao diretor e as cenas chegam marcadas.
  await page.click('.mc-video-brand-levels label:has-text("Equilibrada")');
  await page.selectOption('#mcVideoDraftStyle','illustration');
  await page.fill('#mcVideoBriefing','Anúncio de internet fibra para famílias, com oferta e loja no fim.');
  await page.click('#mcVideoDraftBtn');
  await page.waitForFunction(()=>document.querySelectorAll('#mcVideoDraft .mc-draft-card').length===3);
  assert.equal(posted[0].brand_presence,'balanced');assert.equal(posted[0].style,'illustration');
  // O conceito do diretor aparece antes das cenas; plano e ambiente de cada cena são editáveis.
  assert.match(await page.locator('#mcVideoConcept').innerText(),/A fibra que some da sala[\s\S]*Um cabo cortado/);
  assert.deepEqual(await page.$$eval('#mcVideoDraft [data-draft-field="shot"]',rows=>rows.map(row=>row.value)),['detalhe','médio','geral']);
  await page.fill('[data-draft="beat-2"] [data-draft-field="setting"]','Cozinha de manhã');
  assert.deepEqual(await marks(page),['none','badge','signature']);
  // 3. Trocar o nível remarca o rascunho; ajustar uma cena vale só para ela.
  await page.click('.mc-video-brand-levels label:has-text("Forte")');
  assert.deepEqual(await marks(page),['badge','badge','signature']);
  await page.selectOption('[data-draft="beat-1"] [data-draft-field="brand"]','none');
  assert.deepEqual(await marks(page),['none','badge','signature']);
  // Com ajuste manual, trocar o nível pede confirmação antes de refazer as cenas.
  await page.click('.mc-video-brand-levels label:has-text("Equilibrada")');
  assert.match(dialogs.at(-1),/inclusive as que você ajustou/);
  assert.deepEqual(await marks(page),['none','badge','signature']);
  // 4. A imagem de cada cena leva a marcação; com referência da marca, a prévia cobra a referência desde a 1ª.
  await page.click('#mcVideoDraftGenerate');
  await page.waitForFunction(()=>document.querySelectorAll('#mcVideoDraft .mc-draft-card').length===0);
  assert.match(dialogs.at(-1),/cerca de 150 tokens cada \(total ≈ 450\)/);
  assert.deepEqual(images.map(image=>image.beat.brand),['none','badge','signature']);
  assert.deepEqual(images.map(image=>[image.style,image.beat.shot]),[['illustration','detalhe'],['illustration','médio'],['illustration','geral']]);
  assert.equal(images[1].beat.setting,'Cozinha de manhã');
  // 5. A marcação segue para a sequência e para o editor da cena, que pode trocá-la.
  const script=await page.evaluate(async()=>{const {state,beatFor}=await import('/static/js/cadu-video/state.js');return state.scenes.map(scene=>beatFor(scene.id)?.brand);});
  assert.deepEqual(script,['none','badge','signature']);
  assert.equal(await page.locator('#mcVideoBeatBrand').inputValue(),'signature');
  await page.selectOption('#mcVideoBeatBrand','badge');
  assert.equal(await page.evaluate(async()=>{const {state,beatFor}=await import('/static/js/cadu-video/state.js');return beatFor(state.selectedSceneId).brand;}),'badge');
  await page.locator('#mcVideoBrand').screenshot({path:ARTIFACTS+'/video-brand-presence.png'});
  // 6. Texto novo nasce na fonte da marca; as cores da marca são sugestões dos seletores de cor.
  const text=await page.evaluate(async()=>{
    document.getElementById('mcStudioAddText').click();
    const {state}=await import('/static/js/cadu-video/state.js');
    return {font:state.edit.layers.at(-1).font,colors:[...document.querySelectorAll('#mcBrandColors option')].map(option=>option.value)};
  });
  assert.equal(text.font,'fonts/brand/Montserrat-Bold.ttf');
  assert.deepEqual(text.colors,['#ffffff','#000000','#176b5e','#f2b705']);
  await page.waitForFunction(()=>[...document.fonts].some(font=>font.family.startsWith('StudioBrand_')&&font.status==='loaded'));
  // 7. "Legenda da marca": fonte da marca e caixa na cor principal, com texto legível.
  await page.waitForFunction(()=>document.querySelector('#mcCaptionStyle [data-caption-brand]'));
  const caption=await page.evaluate(async()=>{
    document.querySelector('#mcCaptionStyle [data-caption-brand]').click();
    const {state}=await import('/static/js/cadu-video/state.js');
    return state.composition?.caption_style;
  });
  assert.equal(caption.font,'brand');assert.equal(caption.brand_font,'fonts/brand/Montserrat-Bold.ttf');
  assert.equal(caption.background,'#176b5e');assert.equal(caption.color,'#ffffff');
  assert.deepEqual(errors,[]);
  // 8. Marca sem logo: o painel avisa antes de gerar.
  const bare=await open(browser,{...KIT,logo_url:'',logo_count:0,font:{family:'Open Sans',url:'/static/fonts/brand/OpenSans-Bold.ttf',source:'fallback'}});
  await bare.page.waitForFunction(()=>/não tem logo cadastrado/.test(document.getElementById('mcVideoBrandHint')?.textContent||''));
  assert.match(await bare.page.locator('#mcVideoBrandKit').innerText(),/Sem logo/);
  assert.deepEqual(bare.errors,[]);
  console.log('PASS presença da marca: kit visível, nível vai ao diretor, remarca e ajuste por cena, imagem leva a marcação, fonte e cores da marca em textos e legendas, aviso sem logo');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
