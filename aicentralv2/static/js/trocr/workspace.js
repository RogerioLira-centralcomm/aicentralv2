/* Loaded on demand. Asset identifiers, masks and jobs stay in the private workspace. */
export async function openWorkspace(api) {
  const root = document.getElementById('mcSwap');
  if (root.querySelector('#trocrWorkspace')) return;
  const client = String(api.state.clientId || '');
  const run = api.state.runId;
  if (!client || !run || !api.baseVersion()?.image) throw new Error('Escolha uma marca e abra uma peça primeiro.');
  const context = `${client}:${run}`;
  const intent = api.intent && typeof api.intent === 'object' ? api.intent : null;
  const current = () => context === `${api.state.clientId}:${api.state.runId}`;
  const apiRoot = document.getElementById('mcCaduBar')?.dataset.mcApiRoot || '/parametros/api';
  const endpoint = `${apiRoot}/format-lab/swap/editor/`;
  const url = (path) => `${endpoint}${path}?client_id=${encodeURIComponent(client)}`;
  const assetUrl = (id, thumb = false) => `${url(`assets/${id}/content`)}${thumb ? '&thumbnail=1' : ''}`;
  const call = async (path, body) => {
    const form = body instanceof FormData;
    const response = await fetch(url(path), {method: body ? 'POST' : 'GET', credentials: 'same-origin',
      headers: {...(body && !form ? {'Content-Type': 'application/json'} : {}), 'X-Trocr-CSRF-Token': api.state.csrf},
      body: body ? (form ? body : JSON.stringify(body)) : undefined});
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || 'Não foi possível salvar.');
    if (!current()) throw new Error('A marca ou peça mudou. Abra o editor novamente.');
    return data.data;
  };
  const refineInstruction = async (instruction) => {
    if (!instruction) return {original_instruction:'', refined_instruction:''};
    try {
      const response = await fetch(`${apiRoot}/format-lab/swap/instruction`, {method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json','X-Trocr-CSRF-Token':api.state.csrf}, body:JSON.stringify({client_id:client,instruction})});
      const data=await response.json();
      if(!response.ok||!data.success)return {original_instruction:instruction,refined_instruction:instruction};
      return data.data;
    } catch (_error) {
      return {original_instruction:instruction,refined_instruction:instruction};
    }
  };
  const upload = async (blob, name) => {
    if (blob.size > 20 * 1024 * 1024) throw new Error('Limite de 20 MB por imagem.');
    const form = new FormData(); form.append('file', blob, name);
    return call('assets', form);
  };
  let doc = await call(`documents/${encodeURIComponent(run)}`) || {id: run, revision: 0, operations: [], history: [], campaign_id: null};
  let campaigns = await call('campaigns');
  let busy = false, dirty = false, closed = false, painting = false, selected = -1, job = null;
  let mask = document.createElement('canvas'), maskCtx = mask.getContext('2d', {willReadFrequently: true});
  const panel = document.createElement('section');
  panel.id = 'trocrWorkspace'; panel.className = 'trocr-workspace'; panel.setAttribute('aria-label', 'Edição por elemento');
  panel.innerHTML = `<header><strong>Editar elemento</strong><button type="button" data-close aria-label="Fechar edição por elemento">×</button></header>
    <details class="trocr-campaign-fold"><summary data-campaign-summary>Campanha</summary><label>Campanha<select data-campaign><option value="">Sem campanha</option></select></label>
    <div class="trocr-workspace-row"><button type="button" data-new-campaign>Nova campanha</button><button type="button" data-edit-campaign>Gerenciar</button></div>
    <label>Peças da campanha<select data-pieces><option value="">Peça atual</option></select></label>
    </details><p data-base></p><button type="button" data-use-base>Atualizar base</button><p data-status role="status" aria-live="polite"></p>
    <details class="trocr-selection-tools" data-selection-panel open><summary>1. Selecionar</summary><p>Clique para sugerir o contorno por cor. Revise os limites luminosos antes de gerar.</p><div class="trocr-workspace-row"><button type="button" data-point-add aria-pressed="false" title="Contorno por ponto (W)">Ponto</button><button type="button" data-point-remove aria-pressed="false" hidden>Ponto −</button></div>
    <div class="trocr-workspace-row"><button type="button" data-paint aria-pressed="false" title="Pincel (B)">Pincel</button><button type="button" data-erase aria-pressed="false" hidden>Excluir −</button><button type="button" data-lasso aria-pressed="false" title="Laço livre (L)">Laço</button><button type="button" data-rectangle aria-pressed="false" title="Retângulo (M)">Retângulo</button></div>
    <label>Modo<select data-selection-mode><option value="include">Adicionar à seleção</option><option value="exclude">Subtrair da seleção</option></select></label>
    <label>Cor da marcação <input data-selection-color type="color" value="#087f6b"><small>Afeta somente a visualização no palco.</small></label>
    <label data-point-controls hidden>Tolerância de cor <input data-tolerance type="number" min="1" max="120" value="48" aria-label="Tolerância de cor"><small>Menor: limita a área. Maior: inclui mais tons. Vale para o próximo clique.</small></label>
    <label data-brush-controls hidden>Pincel <output data-radius-label>24 px</output><input data-radius type="range" min="1" max="120" value="24"></label>
    <div class="trocr-workspace-row"><button type="button" data-selection-undo disabled aria-label="Desfazer seleção">↶</button><button type="button" data-selection-redo disabled aria-label="Refazer seleção">↷</button><button type="button" data-invert>Inverter</button><button type="button" data-clear>Limpar</button></div>
    <button type="button" data-lift>Ver recorte</button><div data-lift-preview hidden></div>
    <details class="trocr-selection-help"><summary>Atalhos</summary><p>B pincel · L laço · M retângulo · W ponto<br>Alt/Option: subtrair · Shift: adicionar<br>[ e ]: tamanho · ⌘/Ctrl Z: desfazer<br>Escape: sair da ferramenta</p></details><button type="button" data-confirm-selection>Usar seleção</button></details><h3 class="trocr-agent-heading">2. Pedir a mudança</h3>
    <label>Elemento<select data-role><option value="person">Pessoa</option><option value="product">Produto</option><option value="background">Fundo</option><option value="text">Texto</option><option value="logo">Logo</option><option value="graphic">Grafismo</option></select></label>
    <label>Ação<select data-action><option value="replace">Substituir seleção com referência</option><option value="erase">Apagar e reconstruir</option><option value="recreate">Recriar somente a seleção</option><option value="cutout">Isolar em PNG transparente</option><option value="fill">Aplicar cor sólida</option><option value="similarity">Recriar peça inteira por similaridade</option><option value="protect">Proteger região</option><option value="extract">Separar em camada</option><option value="text">Tornar texto editável</option></select></label>
    <p class="trocr-input-contract" data-input-contract aria-live="polite">Imagem 1 é a peça original. Imagem 2 orienta somente o elemento selecionado.</p>
    <div data-reference-tools><label>Imagem 2 · referência da mudança <input data-reference type="file" accept="image/png,image/jpeg,image/webp"></label>
    <label>Biblioteca da campanha<select data-library><option value="">Selecionar referência</option></select></label>
    <button type="button" data-save-reference>Guardar referência na campanha</button>
    <img data-thumb hidden alt="Referência selecionada" width="64" height="64"></div>
    <label data-color-label hidden>Cor sólida <input data-background-color type="color" value="#ffffff"></label>
    <label data-background-style-label hidden>Direção do fundo<select data-background-style><option value="">Descrever manualmente</option><option value="clean-studio">Estúdio limpo</option><option value="brand-gradient">Gradiente da marca</option><option value="paper">Papel sutil</option><option value="color-wash">Lavagem de cor</option><option value="editorial">Editorial premium</option><option value="office">Escritório realista</option><option value="nature">Ambiente natural</option><option value="architecture">Arquitetura</option><option value="dark-studio">Estúdio escuro</option><option value="bright-seamless">Fundo claro contínuo</option></select></label>
    <label data-brand-confirm-label hidden><input data-brand-confirm type="checkbox"> Confirmo que desejo alterar ou remover a identidade desta marca</label>
    <label>Instrução<textarea data-instruction maxlength="2000" rows="2" placeholder="Descreva somente o que deve mudar na área selecionada"></textarea></label>
    <button type="button" data-add>Adicionar operação com esta máscara</button>
    <ol data-operations></ol><ul data-protected></ul><button type="button" data-save>Salvar trabalho</button>
    <button type="button" data-generate>Gerar operações</button><button type="button" data-retry hidden>Repetir etapas pendentes</button><button type="button" data-cancel hidden>Cancelar próximas etapas</button>
    <details><summary>Gerar canais</summary><fieldset data-format-list><legend>Destinos</legend><label><input type="checkbox" value="16:9"> 16:9 · YouTube / CTV</label><label><input type="checkbox" value="1:1"> 1:1 · Feed</label><label><input type="checkbox" value="9:16"> 9:16 · Stories / Reels</label><label><input type="checkbox" value="4:5"> 4:5 · Feed</label></fieldset><button type="button" data-format-generate>Gerar destinos selecionados</button><div data-format-results></div></details>
    <details><summary>Revisões da peça</summary><button type="button" data-revisions>Consultar revisões salvas</button><ul data-revision-list></ul></details>
    <details data-layers-panel><summary>Camadas e efeitos</summary>
    <select data-layer-select aria-label="Camada selecionada"></select>
    <label><input data-layer-visible type="checkbox" checked> Visível</label><label><input data-layer-protected type="checkbox"> Proteger</label>
    <label><input data-snap type="checkbox"> Encaixe em 8 px</label>
    <div class="trocr-layer-grid"><label>X<input data-layer-x type="number"></label><label>Y<input data-layer-y type="number"></label><label>Largura<input data-layer-width type="number" min="1" max="8000"></label><label>Altura<input data-layer-height type="number" min="1" max="8000"></label></div>
    <label>Opacidade<input data-layer-opacity type="range" min="0" max="1" step="0.05"></label>
    <label>Sombra<input data-layer-shadow type="range" min="0" max="30"></label><label>Contorno<input data-layer-outline type="range" min="0" max="20"></label>
    <div data-text-controls hidden><label>Texto<textarea data-layer-text maxlength="1000"></textarea></label><p>Fonte: Open Sans</p><label>Tamanho<input data-layer-font_size type="number" min="6" max="500"></label><label>Cor<input data-layer-color type="color"></label><label>Alinhamento<select data-layer-align><option value="left">Esquerda</option><option value="center">Centro</option><option value="right">Direita</option></select></label><label>Espaçamento<input data-layer-spacing type="number" min="0" max="100"></label></div>
    <button type="button" data-layer-up>Trazer à frente</button><button type="button" data-layer-down>Enviar atrás</button><button type="button" data-layer-undo>Desfazer</button><button type="button" data-layer-redo>Refazer</button>
    <button type="button" data-layer-preview>Atualizar prévia</button><a data-layer-export hidden download="trocr-camadas.png">Exportar composição</a><img data-layer-image hidden alt="Prévia da composição" style="width:100%">
    </details><div data-results></div>`;
  root.append(panel);
  const $ = (q) => panel.querySelector(q);
  if (intent) {
    const role = ['person', 'product', 'background'].includes(intent.role) ? intent.role : 'product';
    $('[data-role]').value = role;
    $('[data-action]').value = intent.action === 'erase' ? 'erase' : 'replace';
    $('[data-instruction]').value = intent.action === 'erase'
      ? `Apagar ${String(intent.label || 'este item').toLocaleLowerCase()} e reconstruir o fundo de forma natural.`
      : `Trocar ${String(intent.label || 'este item').toLocaleLowerCase()} preservando o restante da peça.`;
  }
  const overlay = document.createElement('canvas'); overlay.className = 'trocr-mask-overlay'; overlay.hidden = true;
  document.querySelector('#mcSwapImage').parentElement.append(overlay);
  const cursor=document.createElement('div');cursor.className='trocr-brush-cursor';cursor.hidden=true;document.body.append(cursor);
  const ctx = overlay.getContext('2d');
  let tool = '', reference = null, lastPoint = null, drawFrame=0, maskDirty=false;
  let selectionUndo=[],selectionRedo=[],gesturePoints=[],gestureSubtract=false;
  $('[data-selection-color]').value=api.state.selectionColor||'#087f6b';
  const selectionRgb=()=>{const hex=$('[data-selection-color]').value||'#087f6b';return [parseInt(hex.slice(1,3),16),parseInt(hex.slice(3,5),16),parseInt(hex.slice(5,7),16)];};
  function snapshotSelection(){
    selectionUndo.push(mask.toDataURL('image/png'));selectionRedo=[];
    while(selectionUndo.length>20||selectionUndo.reduce((n,s)=>n+s.length,0)>16_000_000)selectionUndo.shift();
    selectionButtons();
  }
  function selectionButtons(){
    $('[data-selection-undo]').disabled=busy||!selectionUndo.length;
    $('[data-selection-redo]').disabled=busy||!selectionRedo.length;
  }
  async function travelSelection(redo=false){
    if(busy||selecting||painting)return;
    const from=redo?selectionRedo:selectionUndo,to=redo?selectionUndo:selectionRedo;
    if(!from.length)return;to.push(mask.toDataURL('image/png'));
    const image=new Image();image.src=from.pop();await image.decode();maskCtx.drawImage(image,0,0,mask.width,mask.height);
    dirty=true;maskDirty=true;overlay.hidden=false;redraw();selectionButtons();status('Seleção alterada localmente.');
  }
  const subtracting=event=>event.altKey?true:event.shiftKey?false:(tool==='exclude'||tool==='point-exclude'||$('[data-selection-mode]').value==='exclude');
  function cursorAt(event){
    const r=overlay.getBoundingClientRect(),diameter=Number($('[data-radius]').value)*2*r.width/mask.width;
    cursor.hidden=!['include','exclude'].includes(tool)||busy;cursor.style.width=cursor.style.height=`${Math.max(2,diameter)}px`;
    cursor.style.left=`${event.clientX}px`;cursor.style.top=`${event.clientY}px`;cursor.classList.toggle('is-subtracting',subtracting(event));
  }
  function scheduleDraw(){if(!drawFrame)drawFrame=requestAnimationFrame(()=>{drawFrame=0;redraw();});}
  const status = (text) => { $('[data-status]').textContent = text; };
  const safe = (fn) => async () => { try { await fn(); } catch (error) { status(error.message); } };
  function renderCampaigns() {
    const select = $('[data-campaign]'); select.replaceChildren(new Option('Sem campanha', ''));
    campaigns.forEach((c) => select.add(new Option(c.name + (c.archived ? ' · arquivada' : ''), c.id)));
    select.value = doc.campaign_id || '';
    $('[data-campaign-summary]').textContent=campaigns.find(c=>c.id===doc.campaign_id)?.name||'Sem campanha';
    const campaignId=doc.campaign_id;
    call('documents').then(documents=>{
      if(closed||doc.campaign_id!==campaignId)return;
      const pieces=$('[data-pieces]');pieces.replaceChildren(new Option('Peça atual',''));
      const known=new Set(documents.map(d=>d.id));
      const rows=[...documents,...(api.state.runs||[]).filter(r=>!known.has(r.run_id)).map(r=>({id:r.run_id,name:r.name,campaign_id:null}))];
      rows.filter(d=>(d.campaign_id||null)===(campaignId||null)&&d.id!==run).forEach(d=>pieces.add(new Option(d.name||d.id,d.id)));
    }).catch(error=>status(error.message));
    const library = $('[data-library]'); library.replaceChildren(new Option('Selecionar referência', ''));
    (campaigns.find((c) => c.id === doc.campaign_id)?.references || []).forEach((id, i) => library.add(new Option(`Referência ${i + 1}`, id)));
  }
  function render() {
    $('[data-base]').textContent = doc.base_version ? `Base: ${doc.base_version} · ${doc.width} × ${doc.height}` : 'Defina a base para selecionar uma região.';
    $('[data-generate]').disabled = busy || !doc.operations?.length;
    $('[data-layers-panel]').hidden = !doc.layers?.length;
    $('[data-format-generate]').disabled=busy || !!doc.operations?.length;
    ['up','down','undo','redo','preview'].forEach(key=>{$(`[data-layer-${key}]`).disabled=busy;});
    $('[data-add]').disabled = busy || !doc.base_asset;
    $('[data-save]').disabled = busy;
    $('[data-cancel]').hidden = !busy;
    $('[data-retry]').hidden = !doc.last_job || busy;
    panel.querySelectorAll('input,select,textarea,[data-use-base],[data-new-campaign],[data-edit-campaign],[data-clear],[data-save-reference]').forEach(node => {node.disabled=busy;});
    const protection=$('[data-protected]');protection.replaceChildren();
    (doc.protected_masks||[]).forEach((item,i)=>{const meta=typeof item==='string'?{mask_asset:item,role:'legado'}:item;const row=document.createElement('li'),button=document.createElement('button');button.textContent=`Região protegida ${i+1} · ${meta.role||'sem classificação'} · liberar`;button.disabled=busy;button.onclick=safe(async()=>{doc.protected_masks.splice(i,1);dirty=true;await save();render();});row.append(button);protection.append(row);});
    const list = $('[data-operations]'); list.replaceChildren();
    (doc.operations || []).forEach((op, index) => {
      const li = document.createElement('li');
      const view = document.createElement('button'); view.type = 'button';
      view.textContent = `${index + 1}. ${{replace:'Substituir',erase:'Apagar',recreate:'Recriar',cutout:'PNG transparente',fill:'Cor sólida',similarity:'Similaridade global',extract:'Camada',text:'Texto editável'}[op.action]} · ${{person:'Pessoa',product:'Produto',background:'Fundo',text:'Texto',logo:'Logo',graphic:'Grafismo'}[op.role]}`;
      view.disabled=busy;
      view.onclick = safe(async () => { selected = index; if(op.mask_asset)await loadMask(op.mask_asset); });
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remover'; remove.disabled = busy;
      remove.onclick = safe(async () => { doc.operations.splice(index, 1); dirty = true; await save(); render(); });
      li.append(view, remove); list.append(li);
    });
  }
  async function save() {
    let maskAsset=doc.selection?.mask_asset||null;
    if(maskDirty){const blob=await new Promise(resolve=>mask.toBlob(resolve,'image/png'));maskAsset=(await upload(blob,'Seleção em edição.png')).id;maskDirty=false;}
    doc.ui={tolerance:$('[data-tolerance]').value,radius:$('[data-radius]').value,selectionMode:$('[data-selection-mode]').value};
    doc.selection={mask_asset:maskAsset,role:$('[data-role]').value,action:$('[data-action]').value,instruction:$('[data-instruction]').value,reference_asset:reference?.id||null,
      background_color:$('[data-background-color]').value,background_style:$('[data-background-style]').value,
      explicit_brand_change:$('[data-brand-confirm]').checked};
    const saved = await call(`documents/${encodeURIComponent(run)}`, doc);
    doc = saved; dirty = false; status('Trabalho salvo.');
  }
  async function useBase() {
    if (busy) throw new Error('Aguarde a operação em processamento.');
    const base = api.baseVersion();
    const response = await fetch(base.image, {credentials:'same-origin'});
    if (!response.ok) throw new Error('Não foi possível abrir a base.');
    const asset = await upload(await response.blob(), 'Base da peça.png');
    if (doc.base_asset && doc.base_asset !== asset.id && doc.operations.length) {
      throw new Error('Remova as operações da base anterior antes de trocar a imagem. Suas máscaras foram preservadas.');
    }
    if(doc.base_asset!==asset.id){doc.protected_masks=[];Object.values(doc.formats||{}).forEach(f=>{f.stale=true;});}
    doc.base_asset = asset.id; doc.base_version = base.id; doc.width = asset.width; doc.height = asset.height;
    selectionUndo=[];selectionRedo=[];selectionButtons();resetMask();
    if (Array.isArray(intent?.box) && intent.box.length === 4) {
      const [x1,y1,x2,y2] = intent.box.map(Number);
      if ([x1,y1,x2,y2].every(Number.isFinite) && x2 > x1 && y2 > y1) {
        maskCtx.fillStyle = '#fff';
        maskCtx.fillRect(Math.max(0, x1), Math.max(0, y1), Math.min(mask.width, x2) - Math.max(0, x1), Math.min(mask.height, y2) - Math.max(0, y1));
        maskDirty = true; overlay.hidden = false; redraw();
        status('A região identificada foi pré-selecionada. Ajuste o contorno antes de gerar.');
      }
    }
    dirty = true; await save(); render();
  }
  function resetMask(clearDraft=true) {
    if(clearDraft){doc.selection={};maskDirty=false;}
    mask.width = doc.width || 1; mask.height = doc.height || 1;
    maskCtx.fillStyle = '#000'; maskCtx.fillRect(0, 0, mask.width, mask.height);
    redraw();
  }
  function redraw() {
    const img = document.getElementById('mcSwapImage');
    const rect = img.getBoundingClientRect(), parent = img.parentElement.getBoundingClientRect();
    const scale = Math.min(rect.width / (img.naturalWidth || 1), rect.height / (img.naturalHeight || 1));
    const width = img.naturalWidth * scale, height = img.naturalHeight * scale;
    overlay.style.left = `${rect.left - parent.left + (rect.width-width)/2}px`;
    overlay.style.top = `${rect.top - parent.top + (rect.height-height)/2}px`;
    overlay.style.width = `${width}px`; overlay.style.height = `${height}px`;
    overlay.width = Math.max(1,Math.round(width)); overlay.height = Math.max(1,Math.round(height));
    ctx.drawImage(mask,0,0,overlay.width,overlay.height);
    const pixels = ctx.getImageData(0, 0, overlay.width, overlay.height);
    const ctxPixels=new Uint8ClampedArray(pixels.data);
    const [markR,markG,markB]=selectionRgb();
    for (let i=0;i<pixels.data.length;i+=4) { const alpha = pixels.data[i]; const pixel=i/4,x=pixel%overlay.width,y=Math.floor(pixel/overlay.width);
      const edge=alpha>127 && (x===0||y===0||x===overlay.width-1||y===overlay.height-1||ctxPixels[i-4]<128||ctxPixels[i+4]<128||ctxPixels[i-overlay.width*4]<128||ctxPixels[i+overlay.width*4]<128);
      pixels.data[i]=markR; pixels.data[i+1]=markG; pixels.data[i+2]=markB; pixels.data[i+3]=edge?255:Math.round(alpha*.18); }
    ctx.putImageData(pixels, 0, 0);
    if(gesturePoints.length && ['lasso','rectangle'].includes(tool)){
      const sx=overlay.width/mask.width,sy=overlay.height/mask.height,first=gesturePoints[0],last=gesturePoints.at(-1);
      ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.setLineDash([4,3]);ctx.beginPath();
      if(tool==='rectangle')ctx.rect(first.x*sx,first.y*sy,(last.x-first.x)*sx,(last.y-first.y)*sy);
      else{ctx.moveTo(first.x*sx,first.y*sy);gesturePoints.slice(1).forEach(p=>ctx.lineTo(p.x*sx,p.y*sy));ctx.closePath();}
      ctx.stroke();ctx.setLineDash([]);
    }
  }
  async function loadMask(id, validate = () => true) {
    const image = new Image(); image.src = assetUrl(id); await image.decode();
    if (!validate()) throw new Error('A seleção mudou durante a leitura. Sua alteração foi mantida; clique novamente.');
    mask.width = image.width; mask.height = image.height; maskCtx.drawImage(image, 0, 0);
    doc.selection={...(doc.selection||{}),mask_asset:id};maskDirty=false;overlay.hidden = false; redraw();
  }
  async function setTool(value) {
    if(busy||selecting)return;
    if (!doc.base_asset || api.baseVersion()?.id !== doc.base_version) {
      status('Selecione e visualize a versão base antes de pintar.'); return;
    }
    if(api.state.activeId!==doc.base_version){try{await api.focusBase();status('Base exibida para selecionar com precisão.');}catch(error){status(error.message);return;}}
    tool = tool === value ? '' : value; overlay.hidden = !tool; overlay.style.pointerEvents = tool ? 'auto' : 'none';
    $('[data-paint]').setAttribute('aria-pressed', String(tool === 'include'));
    $('[data-erase]').setAttribute('aria-pressed', String(tool === 'exclude'));
    $('[data-point-add]').setAttribute('aria-pressed',String(tool==='point-include'));
    $('[data-point-remove]').setAttribute('aria-pressed',String(tool==='point-exclude'));
    $('[data-lasso]').setAttribute('aria-pressed',String(tool==='lasso'));$('[data-rectangle]').setAttribute('aria-pressed',String(tool==='rectangle'));
    $('[data-point-controls]').hidden=!tool.startsWith('point-');
    $('[data-brush-controls]').hidden=!['include','exclude'].includes(tool);
    cursor.hidden=true;redraw();
  }
  function point(event) {
    const r = overlay.getBoundingClientRect();
    return {x: Math.max(0,Math.min(mask.width,(event.clientX-r.left)*mask.width/r.width)), y: Math.max(0,Math.min(mask.height,(event.clientY-r.top)*mask.height/r.height))};
  }
  function stroke(event) {
    if (!painting) return;
    dirty=true;maskDirty=true;
    const p = point(event);
    if(['lasso','rectangle'].includes(tool)){gesturePoints.push(p);scheduleDraw();return;}
    maskCtx.strokeStyle = subtracting(event) ? '#000' : '#fff';
    maskCtx.lineWidth = Number($('[data-radius]').value)*2; maskCtx.lineCap='round';
    maskCtx.beginPath(); maskCtx.moveTo(lastPoint?.x ?? p.x, lastPoint?.y ?? p.y); maskCtx.lineTo(p.x+.01,p.y+.01); maskCtx.stroke(); lastPoint=p;
    scheduleDraw();
  }
  let selecting=false;
  overlay.onpointerdown = async (event) => {
    if (!tool || busy || selecting) return;
    if(tool.startsWith('point-')){
      event.preventDefault();selecting=true;const p=point(event),base=doc.base_asset,selectionBefore=mask.toDataURL();
      try{
        status('Lendo contorno…');
        await save();
        const result=await call('selection',{base_asset:base,mask_base:base,mask_asset:doc.selection?.mask_asset,point:{x:p.x/mask.width,y:p.y/mask.height},tolerance:Number($('[data-tolerance]').value),mode:subtracting(event)?'exclude':'include'});
        if(doc.base_asset!==base)throw new Error('A base mudou. Revise a seleção.');
        await loadMask(result.mask_asset,()=>{
          if(closed || !current() || doc.base_asset!==base || mask.toDataURL()!==selectionBefore)return false;
          snapshotSelection();return true;
        });dirty=true;await save();status(result.warning || `Seleção: ${Math.round(result.coverage*100)}% da imagem. Revise os limites; use Alt/Option para subtrair ou desfaça o último ponto.`);
      }catch(error){status(error.message);}finally{selecting=false;}
      return;
    } event.preventDefault();snapshotSelection();gesturePoints=[];gestureSubtract=subtracting(event);overlay.setPointerCapture(event.pointerId); painting=true;stroke(event); };
  overlay.onpointermove=event=>{cursorAt(event);stroke(event);};
  overlay.onpointerleave=()=>{cursor.hidden=true;};
  overlay.onpointerup=()=>{
    if(painting&&gesturePoints.length>1){
      const first=gesturePoints[0],last=gesturePoints.at(-1);maskCtx.fillStyle=gestureSubtract?'#000':'#fff';maskCtx.beginPath();
      if(tool==='rectangle')maskCtx.rect(first.x,first.y,last.x-first.x,last.y-first.y);
      else{maskCtx.moveTo(first.x,first.y);gesturePoints.slice(1).forEach(p=>maskCtx.lineTo(p.x,p.y));maskCtx.closePath();}
      maskCtx.fill();dirty=true;maskDirty=true;
    }
    painting=false;lastPoint=null;gesturePoints=[];scheduleDraw();selectionButtons();
  };
  overlay.onpointercancel=()=>{painting=false;lastPoint=null;gesturePoints=[];travelSelection().catch(error=>status(error.message));};
  const resize = new ResizeObserver(scheduleDraw); resize.observe(document.getElementById('mcSwapImage'));
  $('[data-point-add]').onclick=()=>setTool('point-include');$('[data-point-remove]').onclick=()=>setTool('point-exclude');
  $('[data-paint]').onclick=() => setTool('include'); $('[data-erase]').onclick=() => setTool('exclude');
  $('[data-clear]').onclick=()=>{snapshotSelection();resetMask();dirty=true;maskDirty=true;};
  $('[data-lasso]').onclick=()=>setTool('lasso');$('[data-rectangle]').onclick=()=>setTool('rectangle');
  $('[data-selection-undo]').onclick=safe(()=>travelSelection());$('[data-selection-redo]').onclick=safe(()=>travelSelection(true));
  $('[data-radius]').oninput=()=>{$('[data-radius-label]').value=`${$('[data-radius]').value} px`;};
  $('[data-invert]').onclick=()=>{
    if(busy)return;snapshotSelection();const pixels=maskCtx.getImageData(0,0,mask.width,mask.height);
    for(let i=0;i<pixels.data.length;i+=4){pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=255-pixels.data[i];}
    maskCtx.putImageData(pixels,0,0);dirty=true;maskDirty=true;overlay.hidden=false;redraw();
  };
  $('[data-lift]').onclick=()=>{
    const target=$('[data-lift-preview]');if(!target.hidden){target.hidden=true;return;}
    const preview=document.createElement('canvas');preview.width=240;preview.height=Math.round(240*mask.height/mask.width);
    const alpha=document.createElement('canvas');alpha.width=preview.width;alpha.height=preview.height;const a=alpha.getContext('2d');a.drawImage(mask,0,0,alpha.width,alpha.height);
    const pixels=a.getImageData(0,0,alpha.width,alpha.height);for(let i=0;i<pixels.data.length;i+=4)pixels.data[i+3]=pixels.data[i];a.putImageData(pixels,0,0);
    const p=preview.getContext('2d');p.drawImage(document.getElementById('mcSwapImage'),0,0,preview.width,preview.height);p.globalCompositeOperation='destination-in';p.drawImage(alpha,0,0);
    target.replaceChildren(preview);target.hidden=false;
  };
  $('[data-confirm-selection]').onclick=()=>{
    const pixels=maskCtx.getImageData(0,0,mask.width,mask.height).data;
    if(!pixels.some((value,index)=>index%4===0&&value>0)){status('Selecione uma região na imagem primeiro.');return;}
    tool='';cursor.hidden=true;overlay.style.pointerEvents='none';$('[data-selection-panel]').open=false;$('[data-action]').focus();status('Seleção pronta. Escolha o que deseja mudar.');
  };
  $('[data-use-base]').onclick=safe(useBase);
  $('[data-reference]').onchange=safe(async () => {
    const file=$('[data-reference]').files[0]; if (!file) return;
    reference=await upload(file, file.name);dirty=true; $('[data-thumb]').src=assetUrl(reference.id,true); $('[data-thumb]').hidden=false;
  });
  $('[data-library]').onchange=() => {dirty=true;reference={id:$('[data-library]').value}; $('[data-thumb]').src=assetUrl(reference.id,true); $('[data-thumb]').hidden=!reference.id;};
  function syncOperationUi(){
    const action=$('[data-action]').value,role=$('[data-role]').value;
    const allowed={replace:['person','product','background','text','logo','graphic'],erase:['person','product','background','text','logo','graphic'],recreate:['person','product','background','text','logo','graphic'],cutout:['person','product','background','text','logo','graphic'],extract:['person','product','background','text','logo','graphic'],protect:['person','product','background','text','logo','graphic'],text:['text'],fill:['background'],similarity:['background','graphic']}[action]||[];
    Array.from($('[data-role]').options).forEach(option=>{option.disabled=!allowed.includes(option.value);});
    if(!allowed.includes(role)){$('[data-role]').value=allowed[0];}
    const activeRole=$('[data-role]').value;
    const needsReference=['replace','similarity'].includes(action);
    $('[data-reference-tools]').hidden=!needsReference;
    $('[data-color-label]').hidden=action!=='fill';
    $('[data-background-style-label]').hidden=!(activeRole==='background'&&action==='recreate');
    const brandMutation=activeRole==='logo'&&['replace','erase','recreate'].includes(action);
    $('[data-brand-confirm-label]').hidden=!brandMutation;
    if(!brandMutation)$('[data-brand-confirm]').checked=false;
    $('[data-input-contract]').textContent=action==='similarity'
      ? 'Mudança global: proteja primeiro logo ou wordmark. Imagem 2 orienta o estilo; a marca protegida continua idêntica.'
      : 'Imagem 1 é a peça original. Imagem 2 orienta somente o elemento selecionado.';
    $('[data-input-contract]').classList.toggle('is-global',action==='similarity');
  }
  $('[data-role]').onchange=()=>{dirty=true;syncOperationUi();};
  $('[data-selection-color]').oninput=()=>{api.state.selectionColor=$('[data-selection-color]').value;root.style.setProperty('--trocr-selection-color',api.state.selectionColor);try{localStorage.setItem('cx-trocr-selection-color',api.state.selectionColor);}catch(_){}redraw();};
  $('[data-instruction]').oninput=()=>{dirty=true;};
  $('[data-action]').onchange=() => { dirty=true; syncOperationUi(); };
  $('[data-add]').onclick=safe(async () => {
    if (api.baseVersion()?.id !== doc.base_version) throw new Error('A base mudou. Revise a seleção.');
    if (doc.layers?.length && ['extract','text'].includes($('[data-action]').value)) throw new Error('Exporte a composição e abra como nova base antes de separar novas camadas.');
    const action=$('[data-action]').value;
    if (['replace','similarity'].includes(action) && !reference?.id) throw new Error('Anexe a Imagem 2 para esta operação.');
    if(action==='similarity' && !(doc.protected_masks||[]).some(item=>typeof item==='object'&&['logo','wordmark'].includes(item.role))) throw new Error('Proteja uma região e classifique o elemento como Logo antes de recriar a peça inteira.');
    if($('[data-role]').value==='logo'&&['replace','erase','recreate'].includes(action)&&!$('[data-brand-confirm]').checked) throw new Error('Confirme explicitamente a alteração da identidade da marca.');
    const pixels=maskCtx.getImageData(0,0,mask.width,mask.height).data;
    const hasMask=pixels.some((value,index) => index%4===0 && value>0);
    if (!hasMask && action!=='similarity') throw new Error('Pinte a região antes de adicionar a operação.');
    let asset=null;
    if(hasMask){const blob=await new Promise(resolve=>mask.toBlob(resolve,'image/png'));asset=await upload(blob,'Máscara.png');}
    if(action==='protect'){
      doc.protected_masks=[...(doc.protected_masks||[]),{mask_asset:asset.id,role:$('[data-role]').value,label:$('[data-role]').selectedOptions[0]?.textContent||'Região'}];dirty=true;await save();resetMask();render();return;
    }
    const style=$('[data-background-style]').value;
    const originalInstruction=$('[data-instruction]').value.trim();
    status('Organizando a instrução sem alterar sua intenção…');
    const instructionResult=await refineInstruction(originalInstruction);
    const instruction=String(instructionResult.refined_instruction||originalInstruction).trim();
    doc.operations.push({base_asset:doc.base_asset,mask_asset:asset?.id||null,role:$('[data-role]').value,action,
      reference_asset:['replace','similarity'].includes(action)?reference.id:null,
      reference_role:action==='similarity'?'similarity_reference':(action==='replace'?'selected_element_reference':null),
      background_color:action==='fill'?$('[data-background-color]').value:null,
      background_preset:action==='recreate'&&$('[data-role]').value==='background'?style:null,
      explicit_brand_change:$('[data-brand-confirm]').checked,instruction,original_instruction:originalInstruction,
      primary_reference_role:'source_of_truth'});
    dirty=true; reference=null; $('[data-reference]').value=''; $('[data-thumb]').hidden=true; resetMask(); await save(); render();
  });
  $('[data-save]').onclick=safe(save);
  $('[data-save-reference]').onclick=safe(async () => {
    const campaign=campaigns.find(c=>c.id===doc.campaign_id);
    if(!campaign || !reference?.id)throw new Error('Selecione uma campanha e anexe uma referência primeiro.');
    await call(`campaigns/${campaign.id}`,{...campaign,references:[...new Set([...(campaign.references||[]),reference.id])]});
    campaigns=await call('campaigns');renderCampaigns();status('Referência guardada na biblioteca da campanha.');
  });
  $('[data-retry]').onclick=safe(async()=>{
    if(busy||!doc.last_job)return;
    const previous=await call(`jobs/${doc.last_job}`);
    const operationKey=op=>[op.base_asset,op.mask_asset||null,op.reference_asset||null,op.reference_role||null,op.role,op.action,op.instruction||'',op.background_color||null,op.background_preset||null,op.explicit_brand_change===true];
    if(previous.operations[0]?.action!=='format' && JSON.stringify(previous.operations.map(operationKey))!==JSON.stringify(doc.operations.map(operationKey)))throw new Error('O pedido foi alterado. Gere as novas operações; a tentativa anterior permanece no histórico.');
    job=await call(`jobs/${doc.last_job}/retry`,{});doc.active_job=job.id;await save();await follow(job.id);
  });
  $('[data-pieces]').onchange=()=>{const id=$('[data-pieces]').value;if(!id)return;if(dirty){status('Salve a edição antes de abrir outra peça.');return;}window.location.assign(`/studio/modelagem-criativos/trocar?client=${encodeURIComponent(client)}&run=${encodeURIComponent(id)}`);};
  $('[data-campaign]').onchange=safe(async () => {doc.campaign_id=$('[data-campaign]').value||null;dirty=true;await save();renderCampaigns();});
  async function campaignDialog(existing) {
    const dialog=document.createElement('dialog'); dialog.className='trocr-campaign-dialog';
    dialog.innerHTML='<form method="dialog"><h2>Campanha</h2><label>Nome<input name="name" maxlength="120" required></label><label>Objetivo<textarea name="objective" maxlength="1000"></textarea></label><label><input name="archived" type="checkbox"> Arquivada</label><p role="alert"></p><button value="cancel" formnovalidate>Cancelar</button><button value="save">Salvar</button></form>';
    const form=dialog.querySelector('form'); form.elements.name.value=existing?.name||'';form.elements.objective.value=existing?.objective||'';form.elements.archived.checked=existing?.archived||false;
    const opener=document.activeElement; document.body.append(dialog);dialog.showModal();
    form.onsubmit=async event=>{if(event.submitter?.value!=='save')return;event.preventDefault();try{
      const campaign=await call('campaigns',{...existing,name:form.elements.name.value,objective:form.elements.objective.value,archived:form.elements.archived.checked});
      campaigns=await call('campaigns');doc.campaign_id=campaign.id;dirty=true;await save();renderCampaigns();dialog.close();
    }catch(error){dialog.querySelector('[role=alert]').textContent=error.message;}};
    dialog.onclose=()=>{dialog.remove();opener?.focus();};
  }
  $('[data-new-campaign]').onclick=()=>campaignDialog(null);
  $('[data-edit-campaign]').onclick=()=>campaignDialog(campaigns.find(c=>c.id===doc.campaign_id));
  function resultCard(record) {
    const row=document.createElement('div'), img=document.createElement('img'), link=document.createElement('a');
    img.src=assetUrl(record.result_asset,true);img.alt='Resultado da edição';img.width=100;
    link.href=assetUrl(record.result_asset);link.download='trocr.png';link.textContent='Exportar PNG';
    const compare=document.createElement('button');compare.textContent='Comparar';compare.onclick=()=>{
      const dialog=document.createElement('dialog');dialog.className='trocr-comparison';
      [record.base_asset,record.result_asset].forEach((id,i)=>{const figure=document.createElement('figure'),caption=document.createElement('figcaption'),image=document.createElement('img');caption.textContent=i?'Resultado':'Base';image.src=assetUrl(id);image.alt=caption.textContent;figure.append(caption,image);dialog.append(figure);});
      const close=document.createElement('button');close.textContent='Fechar';close.onclick=()=>dialog.close();dialog.append(close);document.body.append(dialog);dialog.showModal();dialog.onclose=()=>{dialog.remove();compare.focus();};
    };
    row.append(img,compare,link);$('[data-results]').prepend(row);
  }
  async function follow(id) {
    busy=true;render();
    try {
      while (!closed && current()) {
        job=await call(`jobs/${id}`);
        status(`${{queued:'Na fila',running:'Gerando',succeeded:'Concluído',failed:'Falhou',cancelled:'Cancelado'}[job.status]} · etapa ${job.step}/${job.operations.length}${job.error?' · '+job.error:''}`);
        if (!['queued','running'].includes(job.status)) break;
        if (job.status==='running' && Date.now()/1000-job.started_at>600) {
          status('A etapa ainda não confirmou o resultado. O pedido está salvo. Reabra mais tarde para consultar; não reenvie para evitar cobrança duplicada.'); return;
        }
        await new Promise(resolve=>setTimeout(resolve,1800));
      }
      if (closed || !current()) return;
      if (job.status==='succeeded') {
        const record={job_id:job.id,base_asset:job.base_asset,result_asset:job.result_asset};
        if (!doc.history.some(h=>h.job_id===job.id)) doc.history.push(record);
        const formatResults=job.results.filter(r=>r.operation.action==='format');
        if(formatResults.length){
          doc.formats=doc.formats||{};formatResults.forEach(r=>{doc.formats[r.operation.aspect_ratio]={asset_id:r.result_asset,base_asset:job.base_asset,stale:false};});renderFormats();
        }
        const createdLayers=job.results.filter(r=>r.layer).map(r=>r.layer);
        if(createdLayers.length){doc.layers=[...(doc.layers||[]),...createdLayers];doc.layer_base=job.result_asset;renderLayers();}
        doc.operations=[];doc.active_job=null;doc.last_job=null;doc.operation_id=null;reference=null;resetMask();dirty=true;await save();resultCard(record);
        await api.acceptResult(assetUrl(job.result_asset), job);
      } else if (['failed','cancelled'].includes(job.status)) {
        doc.active_job=null;doc.last_job=job.id;doc.operation_id=null;dirty=true;await save();status('Os anexos e máscaras continuam disponíveis. '+(job.error||'Operação cancelada.'));
      }
    } finally {busy=false;render();}
  }
  $('[data-format-generate]').onclick=safe(async()=>{
    if(busy||doc.operations.length)return;
    const ratios=Array.from(panel.querySelectorAll('[data-format-list] input:checked'),n=>n.value);
    if(!ratios.length)throw new Error('Selecione ao menos um destino.');
    busy=true;render();
    try{
      const base=doc.layers?.length?(await call('render',{base_asset:doc.layer_base,layers:doc.layers})).id:doc.base_asset;
      const operations=ratios.map(r=>({base_asset:base,action:'format',role:'background',aspect_ratio:r,instruction:''}));
      doc.operation_id=doc.operation_id||crypto.randomUUID().replaceAll('-','');await save();
      job=await call('jobs',{operation_id:doc.operation_id,base_asset:base,operations,protected_masks:doc.protected_masks||[]});doc.active_job=job.id;await save();await follow(job.id);
    }finally{busy=false;render();}
  });
  $('[data-generate]').onclick=safe(async () => {
    if(busy)return;
    if(api.baseVersion()?.id!==doc.base_version)throw new Error('A base mudou. Revise as máscaras.');
    busy=true;render();
    try {
      doc.operation_id=doc.operation_id||crypto.randomUUID().replaceAll('-','');dirty=true;await save();
      job=await call('jobs',{operation_id:doc.operation_id,base_asset:doc.base_asset,operations:doc.operations,protected_masks:doc.protected_masks||[]});
      doc.active_job=job.id;dirty=true;await save();await follow(job.id);
    } finally {busy=false;render();}
  });
  $('[data-cancel]').onclick=safe(async()=>{if(job){await call(`jobs/${job.id}/cancel`,{});status('Cancelamento solicitado. A etapa atual pode já estar em processamento.');}});
  function close() {if(dirty){status('Salve o trabalho antes de fechar.');return;}closed=true;resize.disconnect();overlay.remove();cursor.remove();panel.remove();document.removeEventListener('keydown',escape,true);window.removeEventListener('beforeunload',protectUnload);document.getElementById('trocrOpenWorkspace')?.focus();}
  function escape(event){
    if(document.querySelector('dialog[open]')||!root.contains(event.target))return;
    const editing=event.target.matches('input,textarea,select,[contenteditable]');
    if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='s'){
      event.preventDefault();event.stopImmediatePropagation();if(!busy)safe(save)();return;
    }
    if(editing)return;
    if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='z'){
      event.preventDefault();event.stopImmediatePropagation();safe(()=>travelSelection(event.shiftKey))();return;
    }
    if(event.key==='Escape'){
      event.preventDefault();event.stopImmediatePropagation();
      if(tool){tool='';painting=false;gesturePoints=[];overlay.style.pointerEvents='none';cursor.hidden=true;redraw();status('Seleção mantida. Escolha a ação ao lado.');}else close();return;
    }
    if(event.metaKey||event.ctrlKey||event.altKey||busy)return;
    const shortcut={b:'include',l:'lasso',m:'rectangle',w:'point-include'}[event.key.toLowerCase()];
    if(shortcut){event.preventDefault();setTool(shortcut);}
    if(event.key==='['||event.key===']'){event.preventDefault();$('[data-radius]').value=Math.max(1,Math.min(120,Number($('[data-radius]').value)+(event.key===']'?2:-2)));$('[data-radius]').oninput();}
  }
  function protectUnload(event){if(dirty){event.preventDefault();event.returnValue='';}}
  window.addEventListener('beforeunload',protectUnload);
  document.addEventListener('keydown',escape,true);$('[data-close]').onclick=close;
  function renderFormats(){
    const target=$('[data-format-results]');target.replaceChildren();
    Object.entries(doc.formats||{}).forEach(([ratio,format])=>{const link=document.createElement('a');link.href=assetUrl(format.asset_id);link.download=`trocr-${ratio.replace(':','x')}.png`;link.textContent=`${ratio} · ${format.stale?'Desatualizado':'Exportar'}`;target.append(link,document.createElement('br'));});
  }
  function staleFormats(){Object.values(doc.formats||{}).forEach(f=>{f.stale=true;});renderFormats();}
  const layerKeys=['x','y','width','height','opacity','shadow','outline','text','font_size','color','align','spacing','visible','protected'];
  let layerUndo=[],layerRedo=[];
  function layerSnapshot(){layerUndo.push(JSON.stringify(doc.layers||[]));if(layerUndo.length>60)layerUndo.shift();layerRedo=[];}
  function renderLayers(){
    const select=$('[data-layer-select]'),previous=select.value;select.replaceChildren();
    (doc.layers||[]).forEach((layer,i)=>select.add(new Option(`${i+1}. ${layer.kind==='text'?'Texto':'Imagem'}`,layer.id)));
    if((doc.layers||[]).some(l=>l.id===previous))select.value=previous;
    const layer=(doc.layers||[]).find(l=>l.id===select.value);
    if(!layer)return;
    layerKeys.forEach(key=>{const node=$(`[data-layer-${key}]`);if(node.type==='checkbox')node.checked=key==='visible'?layer[key]!==false:layer[key]===true;else node.value=layer[key]??({opacity:1,color:'#ffffff',font_size:48,align:'left'}[key]??0);node.disabled=layer.protected&&key!=='protected';});
    $('[data-text-controls]').hidden=layer.kind!=='text';
    $('[data-layer-undo]').disabled=!layerUndo.length;$('[data-layer-redo]').disabled=!layerRedo.length;
  }
  $('[data-layer-select]').onchange=renderLayers;
  layerKeys.forEach(key=>{$(`[data-layer-${key}]`).onchange=()=>{
    const layer=(doc.layers||[]).find(l=>l.id===$('[data-layer-select]').value);if(!layer)return;
    layerSnapshot();const node=$(`[data-layer-${key}]`);let value=node.type==='checkbox'?node.checked:(['text','color','align'].includes(key)?node.value:Number(node.value));
    if(['x','y'].includes(key)&&$('[data-snap]').checked)value=Math.round(value/8)*8;
    layer[key]=value;dirty=true;staleFormats();renderLayers();$('[data-layer-export]').hidden=true;status('Edição local. Atualize a prévia e salve o trabalho.');
  };});
  ['up','down'].forEach(direction=>{$(`[data-layer-${direction}]`).onclick=()=>{const index=doc.layers.findIndex(l=>l.id===$('[data-layer-select]').value),next=index+(direction==='up'?1:-1);if(next<0||next>=doc.layers.length||doc.layers[index].protected)return;layerSnapshot();[doc.layers[index],doc.layers[next]]=[doc.layers[next],doc.layers[index]];dirty=true;renderLayers();};});
  $('[data-layer-undo]').onclick=()=>{if(layerUndo.length){layerRedo.push(JSON.stringify(doc.layers));doc.layers=JSON.parse(layerUndo.pop());dirty=true;renderLayers();}};
  $('[data-layer-redo]').onclick=()=>{if(layerRedo.length){layerUndo.push(JSON.stringify(doc.layers));doc.layers=JSON.parse(layerRedo.pop());dirty=true;renderLayers();}};
  $('[data-layer-preview]').onclick=safe(async()=>{const asset=await call('render',{base_asset:doc.layer_base,layers:doc.layers});$('[data-layer-image]').src=assetUrl(asset.id);$('[data-layer-image]').hidden=false;$('[data-layer-export]').href=assetUrl(asset.id);$('[data-layer-export]').hidden=false;await save();});
  $('[data-revisions]').onclick=safe(async()=>{
    const rows=await call(`revisions/${encodeURIComponent(run)}`),list=$('[data-revision-list]');list.replaceChildren();
    rows.forEach(row=>{const item=document.createElement('li'),link=document.createElement('a');link.textContent=`Revisão ${row.revision} · ${new Date(row.updated_at*1000).toLocaleString()}`;link.download=`trocr-revisao-${row.revision}.json`;link.href='data:application/json;charset=utf-8,'+encodeURIComponent(JSON.stringify(row,null,2));item.append(link);list.append(item);});
    if(!rows.length)list.textContent='Nenhuma revisão anterior salva.';
  });
  renderCampaigns();resetMask(false);render();renderLayers();renderFormats();doc.history.forEach(resultCard);
  if(doc.ui){$('[data-tolerance]').value=doc.ui.tolerance||48;$('[data-radius]').value=doc.ui.radius||24;$('[data-selection-mode]').value=doc.ui.selectionMode||'include';}
  if(doc.selection){
    ['role','action','instruction'].forEach(key=>{if(doc.selection[key])$(`[data-${key}]`).value=doc.selection[key];});
    if(doc.selection.background_color)$('[data-background-color]').value=doc.selection.background_color;
    if(doc.selection.background_style)$('[data-background-style]').value=doc.selection.background_style;
    $('[data-brand-confirm]').checked=doc.selection.explicit_brand_change===true;
    if(doc.selection.reference_asset){reference={id:doc.selection.reference_asset};$('[data-thumb]').src=assetUrl(reference.id,true);$('[data-thumb]').hidden=false;}
    if(doc.selection.mask_asset)await loadMask(doc.selection.mask_asset);
  }
  syncOperationUi();
  if(!doc.base_asset)await useBase();
  if(doc.active_job)follow(doc.active_job).catch(error=>status(error.message));
}
