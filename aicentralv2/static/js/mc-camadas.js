(() => {
  const API = '/parametros/api/format-lab/layers/split';
  const EXAMPLE = '/parametros/api/format-lab/layers/example';
  const ROLE_NAME = { cast: 'Pessoa', product: 'Produto', ground: 'Tinta' };
  const COPY_LABEL = {
    headline: 'Headline',
    support: 'Apoio',
    price: 'Preço',
    cta: 'CTA',
    logo_text: 'Logo',
  };

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function boot() {
    const fileInput = document.getElementById('mcLayersFile');
    const drop = document.getElementById('mcLayersDrop');
    const frame = document.getElementById('mcLayersFrame');
    const preview = document.getElementById('mcLayersPreview');
    const overlay = document.getElementById('mcLayersOverlay');
    const run = document.getElementById('mcLayersRun');
    const imageBtn = document.getElementById('mcLayersImage');
    const demo = document.getElementById('mcLayersDemo');
    const status = document.getElementById('mcLayersStatus');
    const field = document.getElementById('mcLayersField');
    const engine = document.getElementById('mcLayersEngine');
    const grid = document.getElementById('mcLayersGrid');
    const castNote = document.getElementById('mcLayersCastNote');
    const copyBox = document.getElementById('mcLayersCopy');
    const copyList = document.getElementById('mcLayersCopyList');
    if (!fileInput || !drop || !run) return;
    let imageUrl = '';
    let lastKind = '';
    let operationId = 0;
    let lastRead = null;
    let lastNonGround = [];
    let lastCastOk = false;

    function setBusy(busy) {
      run.disabled = busy || !imageUrl;
      if (demo) demo.disabled = busy;
      if (imageBtn) {
        const allowWell = lastKind === 'image' && Boolean(imageUrl);
        imageBtn.classList.toggle('hidden', !allowWell);
        imageBtn.disabled = busy || !allowWell;
      }
    }

    function setStep(step) {
      document.querySelectorAll('[data-layers-step]').forEach((node) => {
        const value = Number(node.getAttribute('data-layers-step'));
        node.classList.toggle('is-current', value === step);
        node.classList.toggle('is-done', value < step);
      });
    }

    function showStill(url) {
      operationId += 1;
      imageUrl = url;
      lastKind = '';
      lastRead = null;
      lastNonGround = [];
      lastCastOk = false;
      if (preview) preview.src = url;
      frame?.classList.remove('hidden');
      drop.classList.add('has-still');
      if (grid) grid.innerHTML = '';
      field?.classList.add('hidden');
      castNote?.classList.add('hidden');
      copyBox?.classList.add('hidden');
      if (copyList) copyList.innerHTML = '';
      if (overlay) {
        overlay.innerHTML = '';
        overlay.hidden = true;
      }
      setStep(1);
      setBusy(false);
      if (status) status.textContent = 'Still na placa. Separe pessoa, tinta e copy.';
    }

    function drawBoxes(layers) {
      if (!overlay) return;
      overlay.innerHTML = (layers || [])
        .filter((item) => item.role !== 'ground' && item.box)
        .map((item) => {
          const box = item.box;
          return `<i class="mc-layers-box" style="left:${box.x}%;top:${box.y}%;width:${box.w}%;height:${box.h}%;"></i>`;
        })
        .join('');
      overlay.hidden = !overlay.innerHTML;
    }

    function paintCopy(read) {
      const items = Object.entries(COPY_LABEL)
        .map(([key, label]) => {
          const value = String((read || {})[key] || '').trim();
          return value ? `<li><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></li>` : '';
        })
        .filter(Boolean);
      if (copyList) copyList.innerHTML = items.join('');
      copyBox?.classList.toggle('hidden', !items.length);
    }

    function isGroundOnly(data) {
      return data.replace === 'ground' || data.engine === 'image2';
    }

    function mergeLayers(data) {
      const incoming = data.layers || [];
      if (isGroundOnly(data)) {
        const ground = incoming.filter((item) => item.role === 'ground');
        return lastNonGround.concat(ground);
      }
      lastNonGround = incoming.filter((item) => item.role !== 'ground');
      lastCastOk = Boolean(data.cast_ok);
      return incoming;
    }

    function cardHtml(item, index) {
      const box = item.box || {};
      const name = ROLE_NAME[item.role] || item.label || `camada-${index + 1}`;
      const file = `${item.role || 'layer'}-${index + 1}.png`;
      const safeName = escapeHtml(name);
      return `<li data-role="${escapeHtml(item.role || '')}">
            <figure>
              <img src="${item.png_data_url || ''}" alt="${safeName}">
              <figcaption>
                <strong>${safeName}</strong>
                <span>${Math.round(box.w || 0)}×${Math.round(box.h || 0)}%</span>
              </figcaption>
            </figure>
            <a class="cx-btn cx-btn-secondary cx-btn-sm" href="${item.png_data_url || ''}" download="${file}">Baixar PNG</a>
          </li>`;
    }

    function showPack(data) {
      lastKind = data.ground_kind || lastKind;
      const layers = mergeLayers(data);
      const castOk = isGroundOnly(data) ? lastCastOk : Boolean(data.cast_ok);
      if (grid) {
        const cards = layers.map((item, index) => cardHtml(item, index));
        if (!castOk) {
          cards.unshift(`<li class="mc-layers-empty" data-role="cast">Sem pessoa confiável. Tipo fica no HTML.</li>`);
        }
        grid.innerHTML = cards.join('') || '<li class="mc-layers-empty">Nenhum recorte veio do still.</li>';
      }
      drawBoxes(layers.filter((item) => item.role === 'cast'));
      if (field && (data.field || !isGroundOnly(data))) {
        field.textContent = data.field || field.textContent || '';
        field.style.setProperty('--layers-field', data.field || '#0033FF');
        field.classList.toggle('hidden', !(data.field || field.textContent));
      }
      if (castNote) {
        castNote.textContent = castOk ? 'Pessoa no acetato.' : 'Sem pessoa confiável.';
        castNote.classList.toggle('is-ok', castOk);
        castNote.classList.remove('hidden');
      }
      if (data.read && Object.keys(data.read).length) {
        lastRead = data.read;
      }
      paintCopy(data.read && Object.keys(data.read).length ? data.read : lastRead);
      if (engine) {
        engine.textContent = data.engine === 'image2'
          ? 'Image 2 · poço'
          : castOk
            ? `${data.engine || 'Python'} · recorte`
            : `${data.engine || 'Python'} · tinta`;
      }
      setBusy(false);
    }

    async function requestSplit(engineName, token) {
      const response = await fetch(API, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageUrl, engine: engineName, operation_id: String(token) }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || 'Não recortei o still.');
      }
      return payload.data || {};
    }

    async function split(engineName) {
      if (!imageUrl) return;
      const token = operationId + 1;
      operationId = token;
      const requested = imageUrl;
      setBusy(true);
      if (status) {
        status.textContent = engineName === 'image'
          ? 'Limpando o poço da foto.'
          : 'Recortando no Python.';
      }
      try {
        const data = await requestSplit(engineName, token);
        if (token !== operationId || requested !== imageUrl) return;
        if (data.operation_id && String(data.operation_id) !== String(token)) return;
        showPack(data);
        setStep(3);
        if (status) {
          status.textContent = data.engine === 'image2'
            ? 'Poço vazio. Tipo fica no HTML.'
            : (isGroundOnly(data) ? lastCastOk : data.cast_ok)
              ? 'Pessoa no acetato. Tinta no campo. Tipo fica no HTML.'
              : 'Tinta no campo. Sem pessoa confiável. Tipo fica no HTML.';
        }
      } catch (error) {
        if (token !== operationId) return;
        if (status) status.textContent = error.message;
        setBusy(false);
      }
    }

    function readFile(file) {
      if (!file || !file.type.startsWith('image/')) return;
      const reader = new FileReader();
      reader.onload = () => showStill(reader.result);
      reader.readAsDataURL(file);
    }

    drop.addEventListener('dragover', (event) => {
      event.preventDefault();
      drop.classList.add('is-dragging');
    });
    drop.addEventListener('dragleave', () => drop.classList.remove('is-dragging'));
    drop.addEventListener('drop', (event) => {
      event.preventDefault();
      drop.classList.remove('is-dragging');
      readFile(event.dataTransfer?.files?.[0]);
    });
    fileInput.addEventListener('change', () => readFile(fileInput.files?.[0]));
    run.addEventListener('click', () => split('python'));
    imageBtn?.addEventListener('click', () => split('image'));
    demo?.addEventListener('click', async () => {
      demo.disabled = true;
      if (status) status.textContent = 'Abrindo o still de teste.';
      try {
        const response = await fetch(EXAMPLE, { credentials: 'same-origin' });
        const payload = await response.json();
        if (!response.ok || payload.success === false) {
          throw new Error(payload.error || 'Não abri o still de teste.');
        }
        showStill((payload.data || {}).image || '');
        await split('python');
      } catch (error) {
        if (status) status.textContent = error.message;
        demo.disabled = false;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
