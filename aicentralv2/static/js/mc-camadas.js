(() => {
  const API = '/parametros/api/format-lab/layers/split';
  const EXAMPLE = '/parametros/api/format-lab/layers/example';
  const ROLE_NAME = { cast: 'Pessoa', product: 'Produto', ground: 'Tinta' };
  const ENGINE_NAME = {
    python: 'Python · recorte',
    custom: 'Python · recorte',
    image2: 'Image 2 · redesenha',
  };

  function boot() {
    const fileInput = document.getElementById('mcLayersFile');
    const drop = document.getElementById('mcLayersDrop');
    const frame = document.getElementById('mcLayersFrame');
    const preview = document.getElementById('mcLayersPreview');
    const overlay = document.getElementById('mcLayersOverlay');
    const run = document.getElementById('mcLayersRun');
    const imageBtn = document.getElementById('mcLayersImage');
    const both = document.getElementById('mcLayersBoth');
    const demo = document.getElementById('mcLayersDemo');
    const status = document.getElementById('mcLayersStatus');
    const field = document.getElementById('mcLayersField');
    const engine = document.getElementById('mcLayersEngine');
    const board = document.getElementById('mcLayersBoard');
    const grids = {
      python: document.getElementById('mcLayersGridPython'),
      image2: document.getElementById('mcLayersGridImage'),
    };
    if (!fileInput || !drop || !run) return;
    let imageUrl = '';

    function buttons() {
      return [run, imageBtn, both, demo].filter(Boolean);
    }

    function setBusy(busy) {
      buttons().forEach((node) => {
        if (node === demo) {
          node.disabled = busy;
          return;
        }
        node.disabled = busy || !imageUrl;
      });
    }

    function setStep(step) {
      document.querySelectorAll('[data-layers-step]').forEach((node) => {
        const value = Number(node.getAttribute('data-layers-step'));
        node.classList.toggle('is-current', value === step);
        node.classList.toggle('is-done', value < step);
      });
    }

    function showStill(url) {
      imageUrl = url;
      if (preview) preview.src = url;
      frame?.classList.remove('hidden');
      drop.classList.add('has-still');
      Object.values(grids).forEach((grid) => {
        if (grid) grid.innerHTML = '';
      });
      field?.classList.add('hidden');
      if (overlay) {
        overlay.innerHTML = '';
        overlay.hidden = true;
      }
      board?.classList.remove('is-compare');
      setStep(1);
      setBusy(false);
      if (status) status.textContent = 'Still na placa. Rode Python, Image 2 ou os dois.';
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

    function paintGrid(grid, layers) {
      if (!grid) return;
      grid.innerHTML = (layers || []).map((item, index) => {
        const box = item.box || {};
        const name = ROLE_NAME[item.role] || item.label || `camada-${index + 1}`;
        const file = `${item.role || 'layer'}-${index + 1}.png`;
        return `<li data-role="${item.role || ''}">
          <figure>
            <img src="${item.png_data_url || ''}" alt="${name}">
            <figcaption>
              <strong>${name}</strong>
              <span>${Math.round(box.w || 0)}×${Math.round(box.h || 0)}%</span>
            </figcaption>
          </figure>
          <a class="cx-btn cx-btn-secondary cx-btn-sm" href="${item.png_data_url || ''}" download="${file}">Baixar PNG</a>
        </li>`;
      }).join('') || '<li class="mc-layers-empty">Nenhum recorte.</li>';
    }

    function showPack(data) {
      const key = data.engine === 'image2' ? 'image2' : 'python';
      paintGrid(grids[key], data.layers || []);
      if (key === 'python') drawBoxes(data.layers || []);
      if (field && data.field) {
        field.textContent = data.field;
        field.style.setProperty('--layers-field', data.field);
        field.classList.remove('hidden');
      }
      const pythonFilled = Boolean(grids.python?.querySelector('img'));
      const imageFilled = Boolean(grids.image2?.querySelector('img'));
      board?.classList.toggle('is-compare', pythonFilled && imageFilled);
      if (engine) {
        if (pythonFilled && imageFilled) engine.textContent = 'Python e Image 2';
        else engine.textContent = ENGINE_NAME[data.engine] || 'Python · recorte';
      }
    }

    async function requestSplit(engineName) {
      const response = await fetch(API, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageUrl, engine: engineName }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || 'Não recortei o still.');
      }
      return payload.data || {};
    }

    async function split(engineName) {
      if (!imageUrl) return;
      setBusy(true);
      if (status) {
        status.textContent = engineName === 'image'
          ? 'Image 2 redesenhando elenco e fundo.'
          : 'Recortando no Python.';
      }
      try {
        const data = await requestSplit(engineName);
        showPack(data);
        setStep(3);
        if (status) {
          status.textContent = data.engine === 'image2'
            ? 'Image 2 redesenhou. Confira se inventou pixel.'
            : 'Python recortou. Tipo fica no HTML.';
        }
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        setBusy(false);
      }
    }

    async function splitBoth() {
      if (!imageUrl) return;
      setBusy(true);
      if (status) status.textContent = 'Python primeiro. Image 2 em seguida.';
      try {
        const python = await requestSplit('python');
        showPack(python);
        if (status) status.textContent = 'Python ok. Pedindo Image 2.';
        const image = await requestSplit('image');
        showPack(image);
        setStep(3);
        if (status) status.textContent = 'Os dois na mesa. Compare pessoa e tinta.';
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
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
    both?.addEventListener('click', () => splitBoth());
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
