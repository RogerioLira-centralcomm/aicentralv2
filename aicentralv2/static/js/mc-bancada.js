(() => {
  const API = {
    campaigns: '/parametros/api/campaigns',
    formats: '/parametros/api/formats',
    credits: '/parametros/api/image-credits',
    agents: '/parametros/api/agents',
    productions: '/parametros/api/productions',
    clients: '/parametros/api/clients',
    composeLibrary: '/parametros/api/compose-library',
  };
  const LAYER_META = {
    fundo: { label: 'Fundo', group: 'Fundo' },
    imagem: { label: 'Imagem principal', group: 'Imagem' },
    video: { label: 'Vídeo', group: 'Imagem' },
    texto: { label: 'Texto e logo', group: 'Texto e logo' },
    logo: { label: 'Logo', group: 'Texto e logo' },
    forma: { label: 'Forma', group: 'Elementos' },
    icone: { label: 'Ícone', group: 'Elementos' },
    overlay: { label: 'Overlay', group: 'Overlay' },
    cta: { label: 'CTA', group: 'CTA' },
    anotacao: { label: 'Anotação', group: 'Overlay' },
  };
  const AGENT_COPY = {
    dna: 'Direção de Arte lê paleta, fonte e logo.',
    producer: 'Copywriter preenche as camadas de texto.',
    scriptwriter: 'Roteirista organiza as batidas.',
    extractor: 'Editor de imagens lê o mapa da peça.',
    reviewer: 'Brand Checker confere safe area, contraste e marca.',
    motion: 'Motion aplica entrada nas camadas encaixadas.',
  };

  const state = {
    campaigns: [],
    campaign: null,
    production: null,
    formats: [],
    credits: { used: 0, monthly: 500 },
    layers: [],
    selectedId: null,
    tool: 'select',
    exploded: true,
    zoom: 100,
    tab: 'mesa',
    dock: 'variacoes',
    sceneId: null,
    undo: [],
    redo: [],
    saving: false,
    savedAt: null,
    pan: { x: 0, y: 0 },
    drag: null,
    benchScenes: [],
    benchSceneId: null,
    playIndex: 0,
    playing: false,
    playTimer: null,
    brandAssets: [],
  };

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function api(url, options) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
      const error = new Error(payload.error || 'Não concluí a solicitação.');
      error.status = response.status;
      throw error;
    }
    return payload.data;
  }

  function uid(prefix) {
    return `${prefix}-${Math.random().toString(36).slice(2, 8)}`;
  }

  function brief() {
    return state.campaign?.creative_brief || {};
  }

  function pack() {
    return brief().campaign_pack?.extracted || {};
  }

  function client() {
    return state.campaign?.client || {};
  }

  function brandProfile() {
    return client().brand_profile || {};
  }

  function brandFonts() {
    const fonts = brandProfile().fonts || [];
    const display = fonts.find((item) => /display|head/i.test(item.role || '')) || fonts[0];
    const body = fonts.find((item) => item !== display) || display;
    return {
      display: display?.family || 'Georgia',
      body: body?.family || 'Inter',
    };
  }

  function brandColors() {
    const line = brandProfile().creative_line || {};
    const palette = line.color_palette || brandProfile().color_palette || [];
    const colors = palette.map((item) => (typeof item === 'string' ? item : item?.hex)).filter(Boolean);
    if (client().primary_color) colors.unshift(client().primary_color);
    if (client().secondary_color) colors.push(client().secondary_color);
    return [...new Set(colors)].slice(0, 6);
  }

  function brandAssets(role) {
    const list = state.brandAssets.length
      ? state.brandAssets
      : (client().brand_assets || []);
    if (!role) return list;
    return list.filter((item) => item.role === role);
  }

  function assetSrc(item) {
    return item?.public_url || item?.asset_url || item?.url || item?.asset_path || '';
  }

  function production() {
    return state.production
      || state.campaign?.production
      || state.campaign?.productions?.[0]
      || null;
  }

  function scenes() {
    return Array.isArray(production()?.scenes) ? production().scenes : [];
  }

  function activeScene() {
    return scenes().find((scene) => String(scene.id) === String(state.sceneId)) || scenes()[0] || null;
  }

  function sceneAsset(scene) {
    const assets = scene?.assets || [];
    return assets.find((item) => item.status === 'approved')
      || assets.find((item) => String(item.id) === String(scene?.preview_asset_id || scene?.approved_asset_id))
      || assets[0]
      || null;
  }

  function assetUrl(asset) {
    return asset?.public_url || asset?.asset_url || asset?.url || '';
  }

  function formatRow() {
    const prod = production() || {};
    return state.formats.find((item) => (
      String(item.id) === String(prod.format_template_id)
      || item.slug === prod.format_slug
    )) || prod;
  }

  function formatHasCta() {
    const elements = formatRow().direction?.elements || [];
    const cta = elements.find((item) => item.key === 'cta');
    if (cta) return Boolean(cta.present);
    const beats = formatRow().direction?.beats || [];
    if (beats.length) return beats.some((beat) => (beat.on_screen || []).includes('cta'));
    return true;
  }

  function formatSize() {
    const format = production() || {};
    const raw = format.default_size || format.format_default_size || '1080x1920';
    const match = String(raw).match(/(\d+)\s*[xX×]\s*(\d+)/);
    if (match) return { w: Number(match[1]), h: Number(match[2]), label: `${match[1]}×${match[2]}` };
    if (format.width && format.height) {
      return { w: Number(format.width), h: Number(format.height), label: `${format.width}×${format.height}` };
    }
    return { w: 1080, h: 1920, label: '1080×1920' };
  }

  function cloneLayers(layers) {
    return JSON.parse(JSON.stringify(layers || []));
  }

  function snapshot() {
    state.undo.push(cloneLayers(state.layers));
    if (state.undo.length > 40) state.undo.shift();
    state.redo = [];
  }

  function defaultLayers() {
    const mapped = brief().compose_library?.params?.regions;
    const saved = brief().bancada?.layers;
    if (Array.isArray(saved) && saved.length) {
      return saved.map((item, index) => normalizeLayer(item, index));
    }
    if (Array.isArray(mapped) && mapped.length) {
      return mapped.map((item, index) => normalizeLayer({
        ...item,
        tipo: layerTipo(item.tipo),
      }, index));
    }
    const photo = assetUrl(sceneAsset(activeScene()));
    const logo = client().logo_upload_path || client().logo_url || '';
    const colors = brandColors();
    const fonts = brandFonts();
    const extracted = pack();
    const fundoSrc = assetSrc(brandAssets('background')[0]);
    const iconSrc = assetSrc(brandAssets('icon')[0]);
    const supports = brandAssets('support').slice(0, 2);
    const layers = [
      normalizeLayer({
        id: 'fundo', tipo: 'fundo', x: 0, y: 0, w: 100, h: 100, z: 0,
        content: { src: fundoSrc, fill: colors[0] || '#183436' },
      }, 0),
      normalizeLayer({
        id: 'imagem', tipo: 'imagem', x: 8, y: 16, w: 84, h: 52, z: 1,
        content: { src: photo },
      }, 1),
      normalizeLayer({
        id: 'texto', tipo: 'texto', x: 8, y: 6, w: 70, h: 16, z: 2,
        content: {
          text: extracted.headline || state.campaign?.name || 'Headline',
          font: fonts.display,
          color: '#ffffff',
        },
      }, 2),
      normalizeLayer({
        id: 'logo', tipo: 'logo', x: 72, y: 6, w: 20, h: 8, z: 3,
        content: { src: logo },
      }, 3),
    ];
    if (formatHasCta()) {
      layers.push(normalizeLayer({
        id: 'cta', tipo: 'cta', x: 8, y: 78, w: 84, h: 12, z: 5,
        content: {
          text: extracted.cta || state.campaign?.cta_text || 'Saiba mais',
          font: fonts.body,
          color: '#ffffff',
          fill: colors[0] || '#1E4D4F',
        },
      }, layers.length));
    }
    supports.forEach((asset, index) => {
      layers.push(normalizeLayer({
        id: `apoio-${index + 1}`,
        tipo: 'imagem',
        x: 8 + index * 46,
        y: 70,
        w: 20,
        h: 10,
        z: 4 + index,
        content: { src: assetSrc(asset) },
      }, layers.length));
    });
    if (iconSrc) {
      layers.push(normalizeLayer({
        id: 'icone', tipo: 'icone', x: 8, y: 88, w: 10, h: 8, z: 8,
        content: { src: iconSrc },
      }, layers.length));
    }
    return layers;
  }

  function layerTipo(tipo) {
    const raw = String(tipo || '').toLowerCase();
    if (raw === 'headline' || raw === 'texto') return 'texto';
    if (raw === 'cta' || raw === 'overlay') return 'cta';
    if (['foto_produto', 'foto_pessoa', 'visual', 'foto'].includes(raw)) return 'imagem';
    return LAYER_META[raw] ? raw : 'forma';
  }

  function defaultBenchScenes() {
    const saved = brief().bancada?.scenes || brief().bancada?.cards;
    if (Array.isArray(saved) && saved.length) {
      return saved.map((item, index) => ({
        id: String(item.id || `cena-${index + 1}`),
        label: item.label || `Cena ${index + 1}`,
        duration: Number(item.duration) || 2,
        scene_id: item.scene_id || null,
        layers: Array.isArray(item.layers) && item.layers.length
          ? item.layers.map((layer, layerIndex) => normalizeLayer(layer, layerIndex))
          : [],
      }));
    }
    const list = scenes();
    if (!list.length) {
      return [{ id: 'cena-1', label: 'Cena 1', duration: 2, scene_id: null, layers: defaultLayers() }];
    }
    return list.map((scene, index) => ({
      id: `cena-${scene.id}`,
      scene_id: scene.id,
      label: `Cena ${index + 1}`,
      duration: 2,
      layers: [],
    }));
  }

  function benchScene() {
    return state.benchScenes.find((item) => String(item.id) === String(state.benchSceneId))
      || state.benchScenes[0]
      || null;
  }

  function syncActiveScene() {
    const current = benchScene();
    if (current) current.layers = cloneLayers(state.layers);
  }

  function openBenchScene(id) {
    syncActiveScene();
    state.benchSceneId = id;
    const item = benchScene();
    if (item?.scene_id) state.sceneId = item.scene_id;
    const layers = item?.layers?.length ? item.layers : defaultLayers();
    state.layers = layers.map((layer, index) => normalizeLayer(layer, index));
    if (item) item.layers = cloneLayers(state.layers);
    state.selectedId = state.layers[1]?.id || state.layers[0]?.id || null;
    state.undo = [];
    state.redo = [];
  }

  function addBenchScene() {
    syncActiveScene();
    const next = {
      id: uid('cena'),
      label: `Cena ${state.benchScenes.length + 1}`,
      duration: 2,
      scene_id: null,
      layers: defaultLayers(),
    };
    state.benchScenes.push(next);
    openBenchScene(next.id);
    persist();
    renderAll();
  }

  function normalizeLayer(item, index) {
    const tipo = layerTipo(item.tipo);
    return {
      id: String(item.id || uid(tipo)),
      tipo,
      x: clamp(item.x, 0, 100),
      y: clamp(item.y, 0, 100),
      w: Math.max(4, clamp(item.w, 1, 100)),
      h: Math.max(4, clamp(item.h, 1, 100)),
      z: Number.isFinite(Number(item.z)) ? Number(item.z) : index,
      visible: item.visible !== false,
      locked: Boolean(item.locked),
      content: item.content && typeof item.content === 'object' ? { ...item.content } : {},
      motion: item.motion && typeof item.motion === 'object' ? { ...item.motion } : { preset: 'none' },
    };
  }

  function clamp(value, min, max) {
    const number = Number(value);
    if (!Number.isFinite(number)) return min;
    return Math.min(max, Math.max(min, number));
  }

  function selectedLayer() {
    return state.layers.find((item) => item.id === state.selectedId) || null;
  }

  function setTab(tab) {
    state.tab = tab;
    document.querySelectorAll('[data-bench-tab]').forEach((node) => {
      node.classList.toggle('is-current', node.getAttribute('data-bench-tab') === tab);
    });
    document.querySelectorAll('[data-bench-panel]').forEach((node) => {
      const name = node.getAttribute('data-bench-panel');
      node.hidden = name !== tab;
    });
    if (tab === 'camadas') renderLayerList();
    if (tab === 'elementos') renderElements();
    if (tab === 'variacoes') renderVariationsPanel();
    if (tab === 'roteiro') renderScript();
    if (tab === 'aprovacao') renderReview();
  }

  function renderCampaignOptions() {
    const select = $('mcBenchCampaign');
    if (!select) return;
    const current = state.campaign?.id || '';
    select.innerHTML = '<option value="">Escolha uma campanha</option>'
      + state.campaigns.map((item) => (
        `<option value="${item.id}"${String(item.id) === String(current) ? ' selected' : ''}>${escapeHtml(item.name)}</option>`
      )).join('');
  }

  function renderCampaignCard() {
    const card = $('mcBenchCampaignCard');
    if (!card) return;
    if (!state.campaign) {
      card.innerHTML = '<p>Abra uma campanha para montar as camadas no retângulo.</p>';
      return;
    }
    const size = formatSize();
    const thumb = assetUrl(sceneAsset(activeScene()));
    card.innerHTML = `
      <strong>${escapeHtml(client().name || 'Marca')}</strong>
      ${thumb ? `<img src="${escapeHtml(thumb)}" alt="">` : ''}
      <small>${escapeHtml(size.label)}</small>
      <p>${escapeHtml(state.campaign.objective || state.campaign.campaign_text || 'Sem briefing na ficha.')}</p>
    `;
  }

  function renderCredits() {
    const value = $('mcBenchCreditsValue');
    const bar = $('mcBenchCreditsBar');
    const used = Number(state.credits.used || 0);
    const monthly = Number(state.credits.monthly || 500) || 500;
    if (value) value.textContent = `${used}/${monthly}`;
    if (bar) bar.style.setProperty('--used', String(Math.round((used / monthly) * 100)));
  }

  function renderHead() {
    const title = $('mcBenchTitle');
    const tags = $('mcBenchTags');
    const saved = $('mcBenchSaved');
    if (title) title.value = brief().bancada?.title || state.campaign?.name || '';
    const list = brief().bancada?.tags || [client().name, pack().offer].filter(Boolean);
    if (tags) {
      tags.innerHTML = list.map((item) => `<span>${escapeHtml(item)}</span>`).join('')
        + '<button type="button" data-bench-act="add-tag">Adicionar tag</button>';
    }
    if (saved) {
      saved.textContent = state.savedAt
        ? `Salvo há ${Math.max(1, Math.round((Date.now() - state.savedAt) / 60000))} min`
        : 'Ainda não gravou';
    }
  }

  function renderWell() {
    const canvas = $('mcBenchCanvas');
    const well = $('mcBenchWell');
    if (!canvas || !well) return;
    const size = formatSize();
    well.style.width = `${size.w}px`;
    well.style.height = `${size.h}px`;
    canvas.style.setProperty('--bench-zoom', String(state.zoom / 100));
    canvas.classList.toggle('is-exploded', state.exploded);
    canvas.classList.toggle('is-playing', state.playing);
    const toggle = $('mcBench3dToggle');
    if (toggle) toggle.classList.toggle('is-on', state.exploded);
    const zoomLabel = $('mcBenchZoomLabel');
    if (zoomLabel) zoomLabel.textContent = `${state.zoom}%`;
    const label = $('mcBenchWellLabel');
    if (label) label.textContent = `Poço ${size.label}`;
    const meta = $('mcBenchWellMeta');
    if (meta) {
      meta.textContent = state.playing
        ? 'Play no tamanho real. Texto, CTA e ícone ficam em HTML.'
        : 'O retângulo é o tamanho real. Fundo, texto, CTA e ícone entram em HTML.';
    }
    const visible = state.layers.filter((item) => item.visible !== false);
    well.innerHTML = visible.map((layer, index) => layerMarkup(layer, index, visible.length)).join('');
  }

  function layerMarkup(layer, index, total) {
    const meta = LAYER_META[layer.tipo] || LAYER_META.forma;
    const depth = state.exploded ? (index + 1) * 28 : 0;
    const motion = layer.motion?.preset && layer.motion.preset !== 'none'
      ? ` is-motion-${escapeHtml(layer.motion.preset)}`
      : '';
    const selected = layer.id === state.selectedId ? ' is-selected' : '';
    return `
      <div class="mc-bench-layer${selected}${motion}${layer.visible === false ? ' is-hidden' : ''}"
           data-layer-id="${escapeHtml(layer.id)}"
           data-tipo="${escapeHtml(layer.tipo)}"
           style="left:${layer.x}%;top:${layer.y}%;width:${layer.w}%;height:${layer.h}%;z-index:${layer.z + 1};--spread-z:${depth}px;background:${escapeHtml(layer.content.fill || '')};color:${escapeHtml(layer.content.color || '#183436')};font-family:${escapeHtml(layer.content.font || 'inherit')};opacity:${layer.content.opacity != null ? layer.content.opacity / 100 : 1};border-radius:${layer.content.radius || 0}px;">
        ${layerInner(layer)}
        <small class="mc-bench-layer-label">${escapeHtml(meta.group)} · Camada ${index + 1}</small>
        ${layer.id === state.selectedId && !layer.locked ? '<i class="mc-bench-handle" data-resize="1"></i>' : ''}
      </div>
    `;
  }

  function layerInner(layer) {
    const src = layer.content.src || '';
    if (layer.tipo === 'video' && src) {
      return `<video src="${escapeHtml(src)}" muted loop playsinline autoplay></video>`;
    }
    if ((layer.tipo === 'imagem' || layer.tipo === 'fundo' || layer.tipo === 'logo') && src) {
      return `<img src="${escapeHtml(src)}" alt="">`;
    }
    if (layer.tipo === 'icone') {
      if (src) return `<img src="${escapeHtml(src)}" alt="">`;
      return '<i class="fa-solid fa-star" aria-hidden="true"></i>';
    }
    if (layer.tipo === 'overlay' || layer.tipo === 'cta') {
      const text = layer.content.text || 'Saiba mais';
      return `<span class="mc-bench-cta" contenteditable="${layer.id === state.selectedId && state.tool === 'select' ? 'true' : 'false'}" data-edit-text="1">${escapeHtml(text)}</span>`;
    }
    if (layer.tipo === 'forma') return '';
    const text = layer.content.text || (layer.tipo === 'anotacao' ? 'Nota de direção' : '');
    if (!text) return '';
    return `<span contenteditable="${layer.id === state.selectedId && state.tool === 'select' ? 'true' : 'false'}" data-edit-text="1">${escapeHtml(text)}</span>`;
  }

  function renderThumbs() {
    const root = $('mcBenchThumbs');
    if (!root) return;
    root.innerHTML = state.benchScenes.map((item) => {
      const photo = (item.layers || []).find((layer) => layer.tipo === 'imagem')?.content?.src
        || assetUrl(sceneAsset(scenes().find((scene) => String(scene.id) === String(item.scene_id))));
      return `<button type="button" data-bench-scene="${escapeHtml(item.id)}" class="${String(item.id) === String(state.benchSceneId) ? 'is-current' : ''}">${photo ? `<img src="${escapeHtml(photo)}" alt="">` : escapeHtml(item.label || '+')}</button>`;
    }).join('') + '<button type="button" data-bench-act="add-scene" title="Nova cena">+</button>';
  }

  function renderLayerList() {
    const list = $('mcBenchLayerList');
    if (!list) return;
    const rows = [...state.layers].sort((a, b) => b.z - a.z);
    list.innerHTML = rows.map((layer) => {
      const meta = LAYER_META[layer.tipo] || LAYER_META.forma;
      return `<li data-layer-id="${escapeHtml(layer.id)}" class="${layer.id === state.selectedId ? 'is-current' : ''}">
        <button type="button" data-layer-act="select">${escapeHtml(meta.label)}</button>
        <small>${Math.round(layer.w)}×${Math.round(layer.h)}%</small>
        <button type="button" data-layer-act="visible">${layer.visible === false ? 'Mostrar' : 'Ocultar'}</button>
        <button type="button" data-layer-act="lock">${layer.locked ? 'Destravar' : 'Travar'}</button>
      </li>`;
    }).join('');
  }

  function renderElements() {
    const root = $('mcBenchElements');
    if (!root) return;
    const logo = client().logo_upload_path || client().logo_url || '';
    const colors = brandColors();
    const assets = brandProfile().brand_assets || brandProfile().assets || [];
    root.innerHTML = `
      ${logo ? `<article draggable="true" data-element="logo" data-src="${escapeHtml(logo)}"><img src="${escapeHtml(logo)}" alt="Logo"><span>Logo</span></article>` : ''}
      ${colors.map((hex) => `<article draggable="true" data-element="forma" data-fill="${escapeHtml(hex)}"><i style="background:${escapeHtml(hex)}"></i><span>${escapeHtml(hex)}</span></article>`).join('')}
      <article draggable="true" data-element="texto"><span>Texto</span></article>
      <article draggable="true" data-element="icone"><span>Ícone</span></article>
      ${(Array.isArray(assets) ? assets : []).slice(0, 8).map((item) => {
        const src = item.asset_url || item.url || item.public_url || '';
        return src ? `<article draggable="true" data-element="imagem" data-src="${escapeHtml(src)}"><img src="${escapeHtml(src)}" alt=""><span>Referência</span></article>` : '';
      }).join('')}
    `;
  }

  function variationCards() {
    const size = formatSize();
    const fromScenes = scenes().map((scene, index) => {
      const asset = sceneAsset(scene);
      return {
        id: `scene-${scene.id}`,
        sceneId: scene.id,
        title: `Versão ${index + 1}`,
        size: size.label,
        src: assetUrl(asset),
      };
    });
    const extras = (state.campaign?.variations || []).map((item, index) => ({
      id: `var-${item.id}`,
      title: item.label ? `Variação ${item.label}` : `Versão ${fromScenes.length + index + 1}`,
      size: size.label,
      src: item.steps?.[0]?.asset_url || '',
    }));
    return fromScenes.concat(extras);
  }

  function renderDock() {
    const body = $('mcBenchDockBody');
    const varCount = $('mcDockVarCount');
    const fmtCount = $('mcDockFmtCount');
    const sceneCount = $('mcDockSceneCount');
    const cards = variationCards();
    if (varCount) varCount.textContent = String(cards.length);
    if (fmtCount) fmtCount.textContent = String(state.formats.length);
    if (sceneCount) sceneCount.textContent = String(scenes().length);
    document.querySelectorAll('[data-dock]').forEach((node) => {
      node.classList.toggle('is-current', node.getAttribute('data-dock') === state.dock);
    });
    if (!body) return;
    if (state.dock === 'formatos') {
      body.innerHTML = state.formats.slice(0, 16).map((item) => (
        `<button class="mc-bench-card" type="button" data-format-id="${item.id}">
          <figure></figure>
          <strong>${escapeHtml(item.name_pt || item.slug)}</strong>
          <small>${escapeHtml(item.default_size || '')}</small>
        </button>`
      )).join('');
      return;
    }
    if (state.dock === 'cenas') {
      body.innerHTML = scenes().map((scene, index) => {
        const url = assetUrl(sceneAsset(scene));
        return `<button class="mc-bench-card${String(scene.id) === String(state.sceneId) ? ' is-current' : ''}" type="button" data-scene-id="${scene.id}">
          <figure>${url ? `<img src="${escapeHtml(url)}" alt="">` : ''}</figure>
          <strong>Cena ${index + 1}</strong>
          <small>${escapeHtml((scene.description || '').slice(0, 42))}</small>
        </button>`;
      }).join('');
      return;
    }
    if (state.dock === 'roteiro') {
      body.innerHTML = scenes().map((scene, index) => (
        `<article class="mc-bench-card"><strong>Batida ${index + 1}</strong><small>${escapeHtml(scene.description || scene.prompt || 'Sem texto')}</small></article>`
      )).join('') || '<p>O roteiro aparece quando a campanha tem cenas.</p>';
      return;
    }
    if (state.dock === 'moodboard') {
      const logo = client().logo_upload_path || client().logo_url || '';
      const colors = brandColors();
      body.innerHTML = (logo ? `<article class="mc-bench-card"><figure><img src="${escapeHtml(logo)}" alt=""></figure><strong>Logo</strong></article>` : '')
        + colors.map((hex) => `<article class="mc-bench-card"><figure style="background:${escapeHtml(hex)}"></figure><small>${escapeHtml(hex)}</small></article>`).join('');
      return;
    }
    body.innerHTML = cards.map((item) => (
      `<button class="mc-bench-card${String(item.sceneId || '') === String(state.sceneId) ? ' is-current' : ''}" type="button" data-scene-id="${item.sceneId || ''}">
        <figure>${item.src ? `<img src="${escapeHtml(item.src)}" alt="">` : ''}</figure>
        <strong>${escapeHtml(item.title)}</strong>
        <small>${escapeHtml(item.size)}</small>
      </button>`
    )).join('') + '<button class="mc-bench-card" type="button" data-bench-act="new-variation"><figure></figure><strong>Nova variação</strong></button>';
  }

  function renderVariationsPanel() {
    const root = $('mcBenchVariationsPanel');
    if (!root) return;
    root.innerHTML = $('mcBenchDockBody')?.innerHTML || '';
    if (state.dock !== 'variacoes') {
      state.dock = 'variacoes';
      renderDock();
      root.innerHTML = $('mcBenchDockBody')?.innerHTML || '';
    }
  }

  function renderScript() {
    const root = $('mcBenchScript');
    if (!root) return;
    const items = scenes();
    root.innerHTML = items.length
      ? items.map((scene, index) => (
        `<li><strong>Batida ${index + 1}</strong><p>${escapeHtml(scene.description || scene.prompt || 'Sem texto nesta batida.')}</p></li>`
      )).join('')
      : '<li>Peça um roteiro ao agente para preencher as batidas.</li>';
  }

  function renderReview() {
    const root = $('mcBenchReview');
    if (!root) return;
    const fitted = !state.exploded;
    root.innerHTML = `
      <p>${fitted ? 'A peça está encaixada no retângulo. O Brand Checker lê este fechamento.' : 'Encaixe a peça no 3D para o canal entrar.'}</p>
      <button class="cx-btn cx-btn-primary" type="button" data-bench-act="review">Rodar Brand Checker</button>
      ${fitted ? '<div class="mc-bench-channel" id="mcBenchChannel">Canal vestido só no fechamento. Sem YouTube ou Instagram no miolo da Mesa.</div>' : ''}
    `;
  }

  function renderBrand() {
    const root = $('mcBenchBrandBody');
    if (!root) return;
    const logo = client().logo_upload_path || client().logo_url || '';
    const colors = brandColors();
    const fonts = brandFonts();
    const size = formatSize();
    const fundo = brandAssets('background')[0];
    const supports = brandAssets('support').slice(0, 2);
    const icon = brandAssets('icon')[0];
    root.className = 'mc-bench-brand-body';
    root.innerHTML = `
      ${logo ? `<img src="${escapeHtml(logo)}" alt="Logo da marca">` : '<span>Sem logo</span>'}
      <div class="mc-bench-swatches">${colors.map((hex) => `<i style="background:${escapeHtml(hex)}" title="${escapeHtml(hex)}"></i>`).join('')}</div>
      <small>${escapeHtml(fonts.display)} / ${escapeHtml(fonts.body)}</small>
      <p class="mc-bench-crop-note">No ${escapeHtml(size.label)} o fundo cobre o poço. Foto 2 e 3 só entram se couberem no slot.</p>
      <div class="mc-bench-brand-slots">
        ${slotThumb('Fundo', fundo)}
        ${supports.map((item, index) => slotThumb(`Foto ${index + 2}`, item)).join('')}
        ${slotThumb('Ícone', icon)}
      </div>
    `;
  }

  function slotThumb(label, asset) {
    const src = assetSrc(asset);
    return `<figure><span>${escapeHtml(label)}</span>${src ? `<img src="${escapeHtml(src)}" alt="">` : '<i></i>'}</figure>`;
  }

  function renderAll() {
    const has = Boolean(state.campaign);
    if ($('mcBenchWorkspace')) $('mcBenchWorkspace').hidden = !has;
    if ($('mcBenchEmpty')) $('mcBenchEmpty').hidden = has;
    renderCampaignOptions();
    renderCampaignCard();
    renderCredits();
    if (!has) return;
    renderHead();
    renderWell();
    renderThumbs();
    renderDock();
    renderBrand();
    if (state.tab !== 'mesa') setTab(state.tab);
  }

  function pushChat(text, who) {
    const chat = $('mcBenchChat');
    if (!chat) return;
    const p = document.createElement('p');
    p.className = who === 'user' ? 'is-user' : 'is-agent';
    p.textContent = text;
    chat.appendChild(p);
    chat.scrollTop = chat.scrollHeight;
  }

  function agentSummary(name, data) {
    if (name === 'motion') return 'Apliquei o movimento na camada selecionada.';
    if (!data || typeof data !== 'object') return AGENT_COPY[name] || 'Pronto.';
    if (data.summary) return String(data.summary);
    if (data.message) return String(data.message);
    if (Array.isArray(data.regions) && data.regions.length) {
      return `Li ${data.regions.length} regiões no mapa.`;
    }
    if (data.instance_data) {
      const copy = data.instance_data;
      return `Copy: ${copy.headline || copy.cta || 'camadas de texto atualizadas.'}`;
    }
    if (data.tokens) return 'Atualizei paleta e fontes da marca na mesa.';
    if (data.passed === true) return 'Brand Checker: passou.';
    if (data.passed === false) return `Brand Checker: ${data.notes || data.reason || 'voltou com apontamentos.'}`;
    return AGENT_COPY[name] || 'O assistente respondeu.';
  }

  function applyAgentResult(name, data) {
    if (!data || typeof data !== 'object') return;
    if (name === 'motion') {
      const layer = selectedLayer() || state.layers.find((item) => item.tipo === 'imagem') || state.layers[0];
      if (!layer) return;
      snapshot();
      layer.motion = { preset: data.preset || 'fade', duration: 1.2 };
      return;
    }
    if (Array.isArray(data.regions) && data.regions.length) {
      snapshot();
      state.layers = data.regions.map((item, index) => normalizeLayer({
        ...item,
        content: item.content || state.layers[index]?.content || {},
      }, index));
    }
    const copy = data.instance_data || data.copy || {};
    if (copy.headline) {
      const layer = state.layers.find((item) => item.tipo === 'texto');
      if (layer) layer.content.text = copy.headline;
    }
    if (copy.cta) {
      const layer = state.layers.find((item) => item.tipo === 'cta' || item.tipo === 'overlay');
      if (layer) layer.content.text = copy.cta;
    }
    const palette = data.tokens?.palette || data.palette;
    if (Array.isArray(palette) && palette[0]) {
      const text = state.layers.find((item) => item.tipo === 'texto');
      if (text) text.content.color = palette[0];
    }
  }

  async function runAgent(name, prompt) {
    pushChat(prompt || AGENT_COPY[name] || name, 'user');
    if (name === 'motion') {
      applyAgentResult('motion', { preset: selectedLayer()?.tipo === 'imagem' ? 'kenburns' : 'fade' });
      renderWell();
      persist();
      pushChat(agentSummary('motion'), 'agent');
      return;
    }
    const mapped = name === 'copywriter' ? 'producer' : name;
    try {
      const data = await api(`${API.agents}/${mapped}`, {
        method: 'POST',
        body: JSON.stringify({
          prompt: prompt || '',
          campaign_id: state.campaign?.id,
          contract: {
            regions: state.layers,
            params: { regions: state.layers },
            tokens: { palette: brandColors(), fonts: brandFonts() },
            instance_data: {
              headline: state.layers.find((item) => item.tipo === 'texto')?.content.text,
              cta: state.layers.find((item) => item.tipo === 'cta' || item.tipo === 'overlay')?.content.text,
            },
          },
        }),
      });
      applyAgentResult(mapped, data);
      renderAll();
      persist();
      pushChat(agentSummary(mapped, data), 'agent');
    } catch (error) {
      pushChat(error.message, 'agent');
    }
  }

  async function persist() {
    if (!state.campaign?.id || state.saving) return;
    syncActiveScene();
    state.saving = true;
    try {
      await api(`${API.campaigns}/${state.campaign.id}/bancada`, {
        method: 'PATCH',
        body: JSON.stringify({
          layers: state.layers,
          tags: brief().bancada?.tags || [],
          title: $('mcBenchTitle')?.value || state.campaign.name,
          exploded: state.exploded,
          zoom: state.zoom,
          active_layer_id: state.selectedId,
          active_scene_id: state.sceneId,
          scenes: state.benchScenes,
          cards: state.benchScenes,
        }),
      });
      state.savedAt = Date.now();
      if (state.campaign.creative_brief) {
        state.campaign.creative_brief.bancada = {
          ...(state.campaign.creative_brief.bancada || {}),
          layers: cloneLayers(state.layers),
          scenes: cloneLayers(state.benchScenes),
        };
      }
      renderHead();
    } catch (error) {
      const saved = $('mcBenchSaved');
      if (saved) saved.textContent = error.message;
    } finally {
      state.saving = false;
    }
  }

  function addLayer(tipo, extras) {
    snapshot();
    const layer = normalizeLayer({
      id: uid(tipo),
      tipo,
      x: 18,
      y: 22,
      w: tipo === 'fundo' ? 100 : 36,
      h: tipo === 'fundo' ? 100 : 18,
      z: state.layers.length,
      content: extras || {},
    }, state.layers.length);
    if (tipo === 'fundo') {
      layer.x = 0;
      layer.y = 0;
    }
    state.layers.push(layer);
    state.selectedId = layer.id;
    renderWell();
    persist();
  }

  function layerFromPoint(event) {
    const node = event.target.closest('[data-layer-id]');
    return node ? state.layers.find((item) => item.id === node.getAttribute('data-layer-id')) : null;
  }

  function wellRect() {
    return $('mcBenchWell')?.getBoundingClientRect();
  }

  function startDrag(event) {
    if (event.button !== 0) return;
    const well = wellRect();
    if (!well) return;
    const resize = event.target.closest('[data-resize]');
    const layer = layerFromPoint(event);
    if (state.tool === 'select' || state.tool === 'move') {
      if (layer && !layer.locked) {
        state.selectedId = layer.id;
        state.drag = {
          kind: resize ? 'resize' : 'move',
          id: layer.id,
          startX: event.clientX,
          startY: event.clientY,
          x: layer.x,
          y: layer.y,
          w: layer.w,
          h: layer.h,
        };
        snapshot();
        renderWell();
        return;
      }
    }
    if (['texto', 'imagem', 'forma', 'icone', 'video', 'fundo', 'anotacao'].includes(state.tool)) {
      return;
    }
    state.drag = {
      kind: 'pan',
      startX: event.clientX,
      startY: event.clientY,
      x: state.pan.x,
      y: state.pan.y,
    };
    $('mcBenchCanvas')?.classList.add('is-dragging');
  }

  function moveDrag(event) {
    if (!state.drag) return;
    const well = wellRect();
    if (!well) return;
    const dx = ((event.clientX - state.drag.startX) / well.width) * 100;
    const dy = ((event.clientY - state.drag.startY) / well.height) * 100;
    if (state.drag.kind === 'pan') {
      state.pan.x = state.drag.x + (event.clientX - state.drag.startX);
      state.pan.y = state.drag.y + (event.clientY - state.drag.startY);
      const wellNode = $('mcBenchWell');
      if (wellNode) wellNode.style.margin = `${state.pan.y}px 0 0 ${state.pan.x}px`;
      return;
    }
    const layer = state.layers.find((item) => item.id === state.drag.id);
    if (!layer) return;
    if (state.drag.kind === 'move') {
      layer.x = clamp(state.drag.x + dx, 0, 100 - layer.w);
      layer.y = clamp(state.drag.y + dy, 0, 100 - layer.h);
    } else {
      layer.w = Math.max(6, clamp(state.drag.w + dx, 6, 100 - layer.x));
      layer.h = Math.max(6, clamp(state.drag.h + dy, 6, 100 - layer.y));
    }
    renderWell();
  }

  function endDrag() {
    if (!state.drag) return;
    const kind = state.drag.kind;
    state.drag = null;
    $('mcBenchCanvas')?.classList.remove('is-dragging');
    if (kind !== 'pan') persist();
  }

  function pickFile(accept, done) {
    const input = $('mcBenchFile');
    if (!input) return;
    input.accept = accept;
    input.onchange = () => {
      const file = input.files?.[0];
      input.value = '';
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => done(reader.result, file);
      reader.readAsDataURL(file);
    };
    input.click();
  }

  async function selectCampaign(id) {
    if (!id) {
      state.campaign = null;
      state.production = null;
      state.layers = [];
      renderAll();
      return;
    }
    const campaign = await api(`${API.campaigns}/${id}`);
    state.campaign = campaign;
    state.production = campaign.production || campaign.productions?.[0] || null;
    if (state.production?.id) {
      try {
        state.production = await api(`${API.productions}/${state.production.id}`);
      } catch (error) {
        if (error.status !== 404) pushChat(error.message, 'agent');
      }
    }
    state.sceneId = brief().bancada?.active_scene_id || scenes()[0]?.id || null;
    state.exploded = brief().bancada?.exploded !== false;
    state.zoom = brief().bancada?.zoom || 100;
    state.benchScenes = defaultBenchScenes();
    state.benchSceneId = brief().bancada?.active_layer_id
      ? state.benchScenes.find((item) => item.layers?.some((layer) => layer.id === brief().bancada.active_layer_id))?.id
      : (state.benchScenes[0]?.id || null);
    openBenchScene(state.benchSceneId || state.benchScenes[0]?.id);
    const download = $('mcDownloadAssets');
    if (download) download.href = `${API.campaigns}/${id}/assets/download`;
    const html5 = $('mcDownloadHtml5');
    if (html5) html5.href = `${API.campaigns}/${id}/html5`;
    const clientId = campaign.client?.id || campaign.client_id;
    if (clientId) {
      try {
        const detail = await api(`${API.clients}/${clientId}`);
        state.brandAssets = detail.brand_assets || [];
        state.campaign.client = { ...client(), ...detail };
      } catch (_) { /* marca sem assets extras */ }
    }
    if (!state.benchScenes.length) state.benchScenes = defaultBenchScenes();
    renderAll();
  }

  function stopPlay() {
    state.playing = false;
    if (state.playTimer) {
      window.clearTimeout(state.playTimer);
      state.playTimer = null;
    }
    const play = $('mcBenchPlay');
    if (play) play.textContent = 'Play';
    $('mcBenchCanvas')?.classList.remove('is-playing');
  }

  function playNext() {
    if (!state.playing || !state.benchScenes.length) return;
    const nextIndex = (state.playIndex + 1) % state.benchScenes.length;
    state.playIndex = nextIndex;
    const card = state.benchScenes[nextIndex];
    openBenchScene(card.id);
    renderWell();
    renderThumbs();
    state.playTimer = window.setTimeout(playNext, Number(card?.duration || 2) * 1000);
  }

  function togglePlay() {
    if (state.playing) {
      stopPlay();
      renderWell();
      return;
    }
    if (!state.benchScenes.length) state.benchScenes = defaultBenchScenes();
    state.playing = true;
    state.exploded = false;
    state.playIndex = Math.max(0, state.benchScenes.findIndex((item) => item.id === state.benchSceneId));
    const play = $('mcBenchPlay');
    if (play) play.textContent = 'Pausar';
    renderWell();
    const first = state.benchScenes[state.playIndex] || state.benchScenes[0];
    state.playTimer = window.setTimeout(playNext, Number(first?.duration || 2) * 1000);
  }

  async function boot() {
    if (!$('mcBench')) return;
    try {
      const [campaigns, formats, credits] = await Promise.all([
        api(API.campaigns),
        api(API.formats),
        api(API.credits).catch(() => ({ used: 0, monthly: 500 })),
      ]);
      state.campaigns = campaigns || [];
      state.formats = formats || [];
      state.credits = credits || state.credits;
      renderCampaignOptions();
      renderCredits();
      const params = new URLSearchParams(location.search);
      const requested = params.get('campaign');
      const variationId = params.get('variation');
      if (requested) await selectCampaign(requested);
      if (variationId) {
        try {
          const library = await api(API.composeLibrary);
          const found = (library.variations || library || []).find?.((item) => String(item.id) === String(variationId))
            || (Array.isArray(library) ? library.find((item) => String(item.id) === String(variationId)) : null);
          const regions = found?.params?.regions || found?.regions;
          if (Array.isArray(regions) && regions.length) {
            snapshot();
            state.layers = regions.map((item, index) => normalizeLayer(item, index));
            syncActiveScene();
            persist();
            renderWell();
          }
        } catch (_) { /* molde extraído opcional */ }
      }
      $('mcBenchPlay')?.addEventListener('click', togglePlay);
    } catch (error) {
      pushChat(error.message, 'agent');
    }

    $('mcBenchCampaign')?.addEventListener('change', (event) => {
      selectCampaign(event.target.value).catch((error) => pushChat(error.message, 'agent'));
    });
    $('mcBenchTitle')?.addEventListener('change', persist);
    $('mcBenchTabs')?.addEventListener('click', (event) => {
      const tab = event.target.closest('[data-bench-tab]')?.getAttribute('data-bench-tab');
      if (tab) setTab(tab);
    });
    document.querySelector('.mc-bench-toolbar')?.addEventListener('click', (event) => {
      const act = event.target.closest('[data-bench-act]')?.getAttribute('data-bench-act');
      if (act === 'undo' && state.undo.length) {
        state.redo.push(cloneLayers(state.layers));
        state.layers = state.undo.pop();
        renderWell();
        persist();
      }
      if (act === 'redo' && state.redo.length) {
        state.undo.push(cloneLayers(state.layers));
        state.layers = state.redo.pop();
        renderWell();
        persist();
      }
      if (act === 'zoom-in') state.zoom = Math.min(220, state.zoom + 10);
      if (act === 'zoom-out') state.zoom = Math.max(40, state.zoom - 10);
      if (act === 'explode') state.exploded = !state.exploded;
      if (act === 'zoom-in' || act === 'zoom-out' || act === 'explode') {
        renderWell();
        persist();
      }
    });
    $('mcBenchTools')?.addEventListener('click', (event) => {
      const tool = event.target.closest('[data-bench-tool]')?.getAttribute('data-bench-tool');
      if (!tool) return;
      state.tool = tool;
      document.querySelectorAll('[data-bench-tool]').forEach((node) => {
        node.classList.toggle('is-current', node.getAttribute('data-bench-tool') === tool);
      });
      if (tool === 'texto') addLayer('texto', { text: 'Novo texto', font: brandFonts().display });
      if (tool === 'forma') addLayer('forma', { fill: brandColors()[0] || '#1E4D4F' });
      if (tool === 'icone') addLayer('icone', {});
      if (tool === 'anotacao') addLayer('anotacao', { text: 'Nota de direção', fill: '#fff8d6' });
      if (tool === 'fundo') {
        const fundo = state.layers.find((item) => item.tipo === 'fundo');
        if (fundo) {
          state.selectedId = fundo.id;
          renderWell();
        } else {
          addLayer('fundo', { fill: '#111111' });
        }
      }
      if (tool === 'imagem') {
        pickFile('image/*', (src) => addLayer('imagem', { src }));
      }
      if (tool === 'video') {
        pickFile('video/*', (src) => addLayer('video', { src }));
      }
    });
    const canvas = $('mcBenchCanvas');
    canvas?.addEventListener('pointerdown', startDrag);
    window.addEventListener('pointermove', moveDrag);
    window.addEventListener('pointerup', endDrag);
    canvas?.addEventListener('wheel', (event) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      state.zoom = clamp(state.zoom + (event.deltaY > 0 ? -8 : 8), 40, 220);
      renderWell();
    }, { passive: false });
    canvas?.addEventListener('dblclick', (event) => {
      const layer = layerFromPoint(event);
      if (layer && (layer.tipo === 'texto' || layer.tipo === 'cta' || layer.tipo === 'overlay' || layer.tipo === 'anotacao')) {
        state.selectedId = layer.id;
        state.exploded = false;
        renderWell();
        const editor = canvas.querySelector('[data-edit-text]');
        editor?.focus();
      }
    });
    canvas?.addEventListener('focusout', (event) => {
      if (!event.target.matches('[data-edit-text]')) return;
      const layer = layerFromPoint(event);
      if (!layer) return;
      snapshot();
      layer.content.text = event.target.textContent.trim();
      persist();
    });
    $('mcBenchThumbs')?.addEventListener('click', (event) => {
      if (event.target.closest('[data-bench-act="add-scene"]')) {
        addBenchScene();
        return;
      }
      const id = event.target.closest('[data-bench-scene]')?.getAttribute('data-bench-scene');
      if (!id) return;
      openBenchScene(id);
      persist();
      renderAll();
    });
    $('mcBenchDock')?.addEventListener('click', (event) => {
      const dock = event.target.closest('[data-dock]')?.getAttribute('data-dock');
      if (dock) {
        state.dock = dock;
        renderDock();
        return;
      }
      if (event.target.closest('[data-bench-act="new-variation"]')) {
        runAgent('scriptwriter', 'Gere outra variação desta peça no mesmo retângulo.');
        return;
      }
      const sceneId = event.target.closest('[data-scene-id]')?.getAttribute('data-scene-id');
      if (sceneId) {
        state.sceneId = sceneId;
        renderAll();
      }
    });
    $('mcBenchLayerList')?.addEventListener('click', (event) => {
      const row = event.target.closest('[data-layer-id]');
      const layer = state.layers.find((item) => item.id === row?.getAttribute('data-layer-id'));
      if (!layer) return;
      const act = event.target.closest('[data-layer-act]')?.getAttribute('data-layer-act');
      if (act === 'visible') layer.visible = layer.visible === false;
      if (act === 'lock') layer.locked = !layer.locked;
      state.selectedId = layer.id;
      renderLayerList();
      renderWell();
      persist();
    });
    $('mcBenchElements')?.addEventListener('dragstart', (event) => {
      const node = event.target.closest('[data-element]');
      if (!node) return;
      event.dataTransfer.setData('text/plain', JSON.stringify({
        tipo: node.getAttribute('data-element'),
        src: node.getAttribute('data-src') || '',
        fill: node.getAttribute('data-fill') || '',
      }));
    });
    canvas?.addEventListener('dragover', (event) => event.preventDefault());
    canvas?.addEventListener('drop', (event) => {
      event.preventDefault();
      try {
        const payload = JSON.parse(event.dataTransfer.getData('text/plain') || '{}');
        addLayer(payload.tipo || 'forma', { src: payload.src, fill: payload.fill, text: payload.tipo === 'texto' ? 'Novo texto' : '' });
      } catch (error) {
        addLayer('forma', { fill: brandColors()[0] || '#1E4D4F' });
      }
    });
    $('mcBenchPromptForm')?.addEventListener('submit', (event) => {
      event.preventDefault();
      const field = $('mcBenchPrompt');
      const text = field?.value.trim();
      if (!text) return;
      field.value = '';
      const guess = /layout|região|camada/i.test(text) ? 'extractor'
        : /marca|contraste|brand/i.test(text) ? 'reviewer'
          : /foto|imagem/i.test(text) ? 'extractor'
            : /motion|anima/i.test(text) ? 'motion'
              : /roteiro|batida/i.test(text) ? 'scriptwriter'
                : 'producer';
      runAgent(guess, text);
    });
    $('mcBenchAssistants')?.addEventListener('click', (event) => {
      const name = event.target.closest('[data-bench-agent]')?.getAttribute('data-bench-agent');
      if (name) runAgent(name, AGENT_COPY[name]);
    });
    document.querySelector('.mc-bench-shortcuts')?.addEventListener('click', (event) => {
      const kind = event.target.closest('[data-bench-shortcut]')?.getAttribute('data-bench-shortcut');
      if (kind === 'variacoes') runAgent('scriptwriter', 'Gere variações desta peça.');
      if (kind === 'texto') runAgent('producer', 'Ajuste headline e CTA nas camadas de texto.');
      if (kind === 'imagem') runAgent('extractor', 'Sugira um recorte melhor para a imagem principal.');
      if (kind === 'layout') runAgent('dna', 'Sugira layout com a paleta e as fontes da marca.');
    });
    $('mcBenchTags')?.addEventListener('click', (event) => {
      if (!event.target.closest('[data-bench-act="add-tag"]')) return;
      const label = window.prompt('Tag da campanha');
      if (!label) return;
      const current = brief().bancada || {};
      current.tags = [...(current.tags || []), label].slice(0, 8);
      if (state.campaign.creative_brief) state.campaign.creative_brief.bancada = current;
      renderHead();
      persist();
    });
    $('mcCreatePublicLink')?.addEventListener('click', async () => {
      if (!state.campaign?.id) return;
      try {
        await api(`${API.campaigns}/${state.campaign.id}/public-collections`, {
          method: 'POST',
          body: JSON.stringify({}),
        });
        pushChat('Link público criado.', 'agent');
      } catch (error) {
        pushChat(error.message, 'agent');
      }
    });
    document.addEventListener('click', (event) => {
      if (event.target.closest('[data-bench-act="review"]')) {
        state.exploded = false;
        renderWell();
        renderReview();
        runAgent('reviewer', 'Revise a peça encaixada.');
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
