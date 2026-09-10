(() => {
  const fileInput = document.getElementById('mcExtractFile');
  const drop = document.getElementById('mcExtractDrop');
  const frame = document.getElementById('mcExtractFrame');
  const preview = document.getElementById('mcExtractPreview');
  const run = document.getElementById('mcExtractRun');
  const status = document.getElementById('mcExtractStatus');
  const list = document.getElementById('mcExtractRegions');
  let imageUrl = '';

  function readFile(file) {
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = () => {
      imageUrl = reader.result;
      preview.src = imageUrl;
      frame.classList.remove('hidden');
      run.disabled = false;
      status.textContent = 'Referência pronta. Leia as regiões para gravar o rascunho.';
    };
    reader.readAsDataURL(file);
  }

  drop?.addEventListener('dragover', (event) => {
    event.preventDefault();
  });
  drop?.addEventListener('drop', (event) => {
    event.preventDefault();
    readFile(event.dataTransfer?.files?.[0]);
  });
  fileInput?.addEventListener('change', () => readFile(fileInput.files?.[0]));
  run?.addEventListener('click', async () => {
    if (!imageUrl) return;
    run.disabled = true;
    status.textContent = 'Lendo o mapa do template.';
    try {
      const response = await fetch('/parametros/api/agents/extractor', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_url: imageUrl, family: 'square_1x1' }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || 'Não li as regiões.');
      }
      const regions = payload.data?.regions || [];
      list.innerHTML = regions.map((item) => (
        `<li>${item.tipo} · ${Math.round(item.w)}×${Math.round(item.h)}%</li>`
      )).join('') || '<li>Nenhuma região veio no mapa.</li>';
      status.textContent = 'Rascunho do template. Confira antes de usar no roteiro.';
    } catch (error) {
      status.textContent = error.message;
    } finally {
      run.disabled = false;
    }
  });
})();
