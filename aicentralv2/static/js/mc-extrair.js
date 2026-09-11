(() => {
  function boot() {
    const fileInput = document.getElementById('mcExtractFile');
    const drop = document.getElementById('mcExtractDrop');
    const frame = document.getElementById('mcExtractFrame');
    const preview = document.getElementById('mcExtractPreview');
    const overlay = document.getElementById('mcExtractOverlay');
    const run = document.getElementById('mcExtractRun');
    const status = document.getElementById('mcExtractStatus');
    const list = document.getElementById('mcExtractRegions');
    const openPrepare = document.getElementById('mcExtractOpenPrepare');
    const openBancada = document.getElementById('mcExtractOpenBancada');
    const family = document.getElementById('mcExtractFamily');
    if (!fileInput || !drop || !run) return;
    let imageUrl = '';

    function setStep(step) {
      document.querySelectorAll('[data-extract-step]').forEach((node) => {
        node.classList.toggle('is-current', Number(node.getAttribute('data-extract-step')) === step);
        node.classList.toggle('is-done', Number(node.getAttribute('data-extract-step')) < step);
      });
    }

    function drawRegions(regions) {
      if (!overlay) return;
      overlay.innerHTML = (regions || []).map((item) => (
        `<i class="mc-extract-box" style="left:${item.x}%;top:${item.y}%;width:${item.w}%;height:${item.h}%;" title="${item.tipo}"></i>`
      )).join('');
      overlay.hidden = !regions?.length;
    }

    function readFile(file) {
      if (!file || !file.type.startsWith('image/')) return;
      const reader = new FileReader();
      reader.onload = () => {
        imageUrl = reader.result;
        if (preview) preview.src = imageUrl;
        frame?.classList.remove('hidden');
        run.disabled = false;
        openPrepare?.classList.add('hidden');
        openBancada?.classList.add('hidden');
        drawRegions([]);
        setStep(2);
        if (status) status.textContent = 'Passo 2: leia as regiões para gravar o rascunho HTML.';
      };
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
    run.addEventListener('click', async () => {
      if (!imageUrl) return;
      run.disabled = true;
      if (status) status.textContent = 'Lendo o mapa do template.';
      try {
        const response = await fetch('/parametros/api/agents/extractor', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
            image_url: imageUrl,
            family: family?.value || 'square_1x1',
            decompose: true,
          }),
        });
        const payload = await response.json();
        if (!response.ok || payload.success === false) {
          throw new Error(payload.error || 'Não li as regiões.');
        }
        const regions = payload.data?.regions || [];
        if (list) {
          list.innerHTML = regions.map((item) => (
            `<li>${item.tipo} · ${Math.round(item.w)}×${Math.round(item.h)}%</li>`
          )).join('') || '<li>Nenhuma região veio no mapa.</li>';
        }
        drawRegions(regions);
        const saved = payload.data?.saved_variation;
        const query = saved?.id ? `?variation=${encodeURIComponent(saved.id)}` : '';
        if (openBancada) {
          openBancada.href = `/parametros/modelagem-criativos/bancada${query}`;
          openBancada.classList.remove('hidden');
        }
        if (saved?.id && openPrepare) {
          openPrepare.href = `/parametros/modelagem-criativos/preparar?variation=${encodeURIComponent(saved.id)}`;
          openPrepare.classList.remove('hidden');
          setStep(3);
          const parts = payload.data?.params || {};
          if (status) {
            status.textContent = parts.cast_url
              ? `Molde ${saved.id} gravado. Elenco recortado e fundo separados — abra na Bancada para desdobrar.`
              : `Molde ${saved.id} gravado. Fundo, foto e textos estão prontos para a Bancada 2.0.`;
          }
        } else {
          openPrepare?.classList.add('hidden');
          if (status) status.textContent = 'Mapa lido. Abra na Bancada 2.0 para montar as camadas.';
          if (regions.length) setStep(3);
        }
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        run.disabled = false;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
