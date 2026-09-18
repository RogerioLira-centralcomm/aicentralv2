(function () {
  const app = document.querySelector('.mc-studio-home');
  if (!app || !window.McStudioLibrary) return;
  const $ = id => document.getElementById(id);
  const list = $('studioItems');
  const status = $('studioStatus');
  const errors = $('studioErrors');
  const search = $('studioSearch');
  const more = $('studioMore');
  const projects = $('studioProjects');
  const store = window.McStudioLibrary.createStore(get, render);
  const selected = new Set();
  let visibleItems = [];
  let draggedId = '';
  const brandLinks = Array.from(app.querySelectorAll('[data-brand-link]'));
  brandLinks.forEach(link => { link.dataset.baseHref = link.getAttribute('href'); });

  function sync(event) {
    const select = $('mcCaduBarClient');
    const clientId = String(event.detail?.clientId || '');
    const context = event.detail?.error ? 'error' : clientId ? 'ready' : 'empty';
    $('studioBrandName').textContent = context === 'error' ? 'Marcas indisponíveis' : clientId ? select?.selectedOptions[0]?.textContent || 'Marca selecionada' : 'Selecione ou cadastre uma marca';
    if (store.state.clientId !== clientId || store.state.context !== context) search.value = '';
    brandLinks.forEach(link => {
      const url = new URL(link.dataset.baseHref, window.location.origin);
      if (clientId) url.searchParams.set('client', clientId);
      link.href = url.pathname + url.search;
    });
    store.context(clientId, context);
  }
  document.addEventListener('cadu:brand-ready', sync);
  document.addEventListener('cadu:brand-change', sync);
  // Navigation owns initial context validation; never fetch using stale storage here.
  if (window.McCaduContext) sync({ detail: window.McCaduContext });
  app.querySelectorAll('[data-media]').forEach(button => button.addEventListener('click', () => store.filter(button.dataset.media)));
  search.addEventListener('input', () => store.search(search.value));
  $('studioSort')?.addEventListener('change', event => store.sort(event.target.value));
  more.addEventListener('click', () => store.more());
  $('studioRefresh').addEventListener('click', () => {
    if (store.state.context === 'error') document.dispatchEvent(new CustomEvent('cadu:context-retry'));
    else store.retry();
  });

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = String(text);
    return element;
  }
  function render(state) {
    const view = store.view();
    list.replaceChildren();
    errors.replaceChildren();
    more.hidden = view.items.length >= view.total;
    list.setAttribute('aria-busy', String(view.loading));
    app.querySelectorAll('[data-media]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.media === state.media)));
    renderProjects(view.projects || [], state.project);
    if (state.context !== 'ready' || !state.clientId) {
      const text = state.context === 'loading' ? 'Carregando contexto da marca…' : state.context === 'error' ? 'Não foi possível carregar as marcas. Use Atualizar para tentar novamente.' : 'Nenhuma marca disponível. Cadastre uma marca para começar.';
      status.textContent = text;
      if (state.context === 'loading') skeleton();
      else empty('Sua produção começa com uma marca', text, app.dataset.brandManageUrl || '/workspace/app/marcas', 'Gerenciar marcas');
      return;
    }
    view.errors.forEach(media => {
      const box = node('div', 'studio-error');
      box.setAttribute('role', 'alert');
      box.append(node('span', '', `Não foi possível carregar ${media === 'video' ? 'os vídeos' : 'as imagens'} desta marca.`));
      const retry = node('button', 'studio-button', 'Tentar novamente');
      retry.type = 'button';
      retry.addEventListener('click', () => store.retry(media));
      box.append(retry); errors.append(box);
    });
    if (view.projectError) {
      const box = node('div', 'studio-error');
      box.setAttribute('role', 'alert');
      box.append(node('span', '', 'Não foi possível carregar as sessões por projeto. Os ativos da marca continuam disponíveis.'));
      const retry = node('button', 'studio-button', 'Tentar novamente');
      retry.type = 'button'; retry.addEventListener('click', () => store.retry());
      box.append(retry); errors.append(box);
    }
    status.textContent = view.loading ? 'Carregando biblioteca e sessões…' : `${view.items.length} de ${view.total} ativo(s)${state.query ? ' para esta busca' : ''}.${state.project === 'all' ? ' Todos os projetos.' : ' Sessão filtrada.'}`;
    view.items.forEach(item => list.append(card(item, state.clientId)));
    visibleItems = view.items;
    selected.forEach(id => { if(!view.items.some(item=>item.id===id))selected.delete(id); });
    renderSelection();
    if (view.loading) skeleton();
    else if (!view.total && !view.errors.length) {
      empty(state.query ? 'Nenhum resultado encontrado' : 'Ainda não há conteúdo nesta seleção', state.query ? 'Tente outro nome, texto ou formato.' : 'Comece ajustando uma peça ou montando um vídeo com as cenas da biblioteca.', state.query ? null : brandLinks[0]?.href, 'Ajustar peça');
    }
  }
  function renderProjects(items, active) {
    if (!projects) return;
    projects.replaceChildren();
    const entries = [{ id: 'all', name: 'Toda a biblioteca', note: 'Todos os ativos' }, ...items.map(item => ({ ...item, note: item.assets.length ? `${item.assets.length} ativo(s) vinculado(s)` : 'Sem ativos vinculados' })), { id: 'unassigned', name: 'Sem projeto', note: 'Ativos ainda não vinculados' }];
    entries.forEach(entry => {
      const button = node('button', 'studio-project-chip');
      button.type = 'button'; button.dataset.project = entry.id; button.setAttribute('aria-pressed', String(entry.id === active));
      button.append(node('strong', '', entry.name), node('span', '', entry.note));
      button.addEventListener('click', () => store.project(entry.id));
      button.addEventListener('dragover', event => { if(entry.id==='all')return;event.preventDefault(); button.classList.add('is-drop'); });
      button.addEventListener('dragleave', () => button.classList.remove('is-drop'));
      button.addEventListener('drop', event => { event.preventDefault(); button.classList.remove('is-drop'); moveSelection(entry.id); });
      projects.append(button);
    });
  }
  function skeleton() {
    for (let i = 0; i < 3; i++) { const item = node('li', 'studio-skeleton'); item.setAttribute('aria-hidden', 'true'); list.append(item); }
  }
  function empty(title, description, href, label) {
    const item = node('li', 'studio-empty');
    item.append(node('strong', '', title), node('p', '', description));
    if (href) { const link = node('a', 'studio-button', label); link.href = href; item.append(link); }
    list.append(item);
  }
  function safeImage(value) {
    if (!value) return '';
    try { const url = new URL(value, window.location.origin); return ['http:', 'https:'].includes(url.protocol) ? url.href : ''; } catch (_) { return ''; }
  }
  function card(item, clientId) {
    const li = node('li', 'studio-card');
    li.dataset.assetId=item.id; li.draggable=true; li.classList.toggle('is-selected',selected.has(item.id));
    const select=node('button','studio-card-select',selected.has(item.id)?'✓':'');select.type='button';select.setAttribute('aria-label',selected.has(item.id)?'Remover da seleção':'Selecionar ativo');select.setAttribute('aria-pressed',String(selected.has(item.id)));
    select.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();toggleSelection(item.id);});li.append(select);
    const link = node('a');
    const params = new URLSearchParams({ run: String(item.run_id || ''), client: clientId });
    if (item.media === 'video') params.set('clip', String(item.id || ''));
    link.href = `/studio/modelagem-criativos/${item.media === 'video' ? 'video' : 'trocar'}?${params}`;
    const thumb = node('div', `studio-thumb ${item.media === 'video' ? 'is-video' : 'is-still'}`);
    const ratio=String(item.aspect_ratio||'');const parts=ratio.split(':').map(Number);if(parts.length===2&&parts.every(Number.isFinite)&&parts[0]>0&&parts[1]>0)thumb.style.aspectRatio=`${parts[0]} / ${parts[1]}`;
    const src = safeImage(item.thumb_url || item.poster_url || item.image_url);
    const fallback = node('span', '', 'Prévia indisponível');
    thumb.append(fallback);
    if (src && !item.broken) {
      const image = node('img'); image.alt = ''; image.loading = 'lazy'; image.decoding = 'async'; image.width = 480; image.height = 300;
      fallback.hidden = true;
      image.addEventListener('error', () => { image.remove(); fallback.hidden = false; });
      image.src = src; thumb.append(image);
    }
    if (item.media === 'video') {
      const motion = node('span', 'studio-motion', '▶ Movimento');
      thumb.append(motion);
    }
    const preview = node('button', 'studio-card-preview', 'Visualizar');
    preview.type = 'button';
    preview.setAttribute('aria-label', `Visualizar ${String(item.headline || item.name || item.title || 'ativo')}`);
    preview.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); openQuickLook(item); });
    thumb.append(preview);
    const body = node('div', 'studio-card-body');
    const title = String(item.headline || item.name || item.title || (item.media === 'video' ? 'Clipe' : 'Peça'));
    const strong = node('strong', '', title); strong.title = title;
    const meta = node('div', 'studio-card-meta');
    const ratioLabel = /^\d{1,4}:\d{1,4}$/.test(String(item.aspect_ratio)) ? item.aspect_ratio : 'Formato não informado';
    meta.append(node('span', 'studio-kind', item.media === 'video' ? 'Vídeo' : 'Imagem'), node('span', '', item.media === 'video' && item.duration ? `${Math.round(Number(item.duration))} s` : ratioLabel));
    body.append(strong, meta);
    const linkedProjects = item.projects || [];
    if (linkedProjects.length) body.append(node('span', 'studio-card-project', linkedProjects[0].name));
    const rawDate = String(item.created_at || '');
    const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(rawDate) ? `${rawDate}T12:00:00` : rawDate);
    if (item.created_at && Number.isFinite(date.getTime())) {
      const time = node('time', '', date.toLocaleDateString('pt-BR')); time.dateTime = date.toISOString(); body.append(time);
    }
    link.append(thumb, body);li.append(link);
    link.addEventListener('click',event=>{if(event.metaKey||event.ctrlKey||event.shiftKey){event.preventDefault();toggleSelection(item.id);}});
    li.addEventListener('keydown',event=>{if(event.code==='Space'){event.preventDefault();openQuickLook(item);}});li.tabIndex=0;
    li.addEventListener('dragstart',event=>{draggedId=item.id;if(!selected.has(item.id)){selected.clear();selected.add(item.id);renderSelection();}li.classList.add('is-dragging');event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',item.id);});
    li.addEventListener('dragend',()=>{draggedId='';li.classList.remove('is-dragging');});
    const action = node('a', 'studio-card-action', item.media === 'video' ? 'Abrir montagem' : 'Editar peça');
    action.href = link.href; li.append(action); return li;
  }
  function toggleSelection(id){if(selected.has(id))selected.delete(id);else selected.add(id);render(store.state);}
  function renderSelection(){const bar=$('studioSelectionBar');if(!bar)return;bar.hidden=!selected.size;$('studioSelectionCount').textContent=selected.size;}
  function chosen(){return visibleItems.filter(item=>selected.has(item.id));}
  async function moveSelection(projectId){
    const rows=chosen();if(!rows.length&&draggedId){const row=visibleItems.find(item=>item.id===draggedId);if(row)rows.push(row);}if(!rows.length)return;
    status.textContent='Organizando ativos…';
    try{
      for(const item of rows){
        const assetUrl=item.video_url||item.image_url||item.thumb_url;
        if(projectId==='unassigned'){
          for(const project of item.projects||[])await mutate(`/parametros/api/format-lab/studio/projects/${encodeURIComponent(project.id)}/items`,{method:'DELETE',body:{client_id:store.state.clientId,asset_url:assetUrl}});
        }else if(projectId!=='all'){
          for(const project of item.projects||[]){if(String(project.id)!==String(projectId))await mutate(`/parametros/api/format-lab/studio/projects/${encodeURIComponent(project.id)}/items`,{method:'DELETE',body:{client_id:store.state.clientId,asset_url:assetUrl}});}
          await mutate(`/parametros/api/format-lab/studio/projects/${encodeURIComponent(projectId)}/items`,{method:'POST',body:{client_id:store.state.clientId,kind:item.media==='video'?'video':'image',title:item.headline||item.name||item.title||'Ativo do Studio',asset_url:assetUrl,metadata:{library_id:item.id,aspect_ratio:item.aspect_ratio||''}}});
        }
      }
      selected.clear();await store.retry();status.textContent=projectId==='unassigned'?'Ativos movidos para Sem projeto.':'Ativos vinculados ao projeto.';
    }catch(error){status.textContent=error.message||'Não foi possível organizar os ativos.';}
  }
  async function deleteSelection(){const rows=chosen();if(!rows.length||!window.confirm(`Enviar ${rows.length} ativo(s) para a lixeira?`))return;try{for(const item of rows){const assetUrl=item.video_url||item.image_url||item.thumb_url;for(const project of item.projects||[])await mutate(`/parametros/api/format-lab/studio/projects/${encodeURIComponent(project.id)}/items`,{method:'DELETE',body:{client_id:store.state.clientId,asset_url:assetUrl}});}const personal=rows.filter(item=>item.personal),shared=rows.filter(item=>!item.personal);if(personal.length)await mutate(`/parametros/api/format-lab/studio/personal-assets`,{method:'DELETE',body:{client_id:store.state.clientId,ids:personal.map(item=>item.id)}});if(shared.length)await mutate(`/parametros/api/format-lab/swap/library`,{method:'DELETE',body:{client_id:store.state.clientId,ids:shared.map(item=>item.id)}});selected.clear();await store.retry();status.textContent='Ativos enviados para a lixeira.';}catch(error){status.textContent=error.message||'Não foi possível apagar.';}}
  function openQuickLook(item){const dialog=$('studioQuickLook'),host=$('studioQuickLookMedia');if(!dialog||!host)return;host.replaceChildren();const src=safeImage(item.video_url||item.image_url||item.poster_url||item.thumb_url);if(!src){host.append(node('p','studio-quicklook-empty','Prévia indisponível para este ativo.'));}else if(item.media==='video'){const video=node('video');video.src=src;video.controls=true;video.autoplay=true;video.playsInline=true;host.append(video);}else{const image=node('img');image.src=src;image.alt=String(item.headline||item.name||'Imagem');host.append(image);}$('studioQuickLookTitle').textContent=item.headline||item.name||item.title||'Ativo';$('studioQuickLookMeta').textContent=`${item.media==='video'?'Vídeo':'Imagem'} · ${item.aspect_ratio||'formato original'}`;dialog.showModal();}
  $('studioClearSelection')?.addEventListener('click',()=>{selected.clear();render(store.state);});
  $('studioDeleteSelection')?.addEventListener('click',deleteSelection);
  $('studioMoveSelection')?.addEventListener('click',()=>{
    const dialog=node('dialog','studio-move-dialog');const form=node('form');form.method='dialog';form.append(node('h2','','Mover seleção'));
    const choices=node('div','studio-move-choices');[{id:'unassigned',name:'Sem projeto'},...store.state.projects.items].forEach(project=>{const button=node('button','',project.name);button.type='submit';button.value=project.id;choices.append(button);});
    const cancel=node('button','studio-move-cancel','Cancelar');cancel.type='submit';cancel.value='';form.append(choices,cancel);dialog.append(form);document.body.append(dialog);dialog.showModal();dialog.addEventListener('close',()=>{const target=dialog.returnValue;dialog.remove();if(target)moveSelection(target);},{once:true});
  });
  $('studioQuickLook')?.querySelector('[data-quicklook-close]')?.addEventListener('click',()=>$('studioQuickLook').close());
  $('studioQuickLook')?.addEventListener('click',event=>{if(event.target===$('studioQuickLook'))$('studioQuickLook').close();});
  async function get(url, options) {
    const response = await fetch(url, { ...options, credentials: 'same-origin', headers: { Accept: 'application/json' } });
    const payload = await response.json();
    if (!response.ok || payload.success === false) throw new Error('Falha na leitura');
    return payload.data !== undefined ? payload.data : payload;
  }
  async function mutate(url,{method='POST',body}={}){const token=document.querySelector('meta[name="studio-csrf-token"]')?.content||'';const response=await fetch(url,{method,credentials:'same-origin',headers:{Accept:'application/json','Content-Type':'application/json','X-Studio-CSRF-Token':token,'X-Trocr-CSRF-Token':token},body:JSON.stringify(body||{})});const payload=await response.json();if(!response.ok||payload.success===false)throw new Error(payload.error||'Falha ao salvar');return payload.data!==undefined?payload.data:payload;}
})();
