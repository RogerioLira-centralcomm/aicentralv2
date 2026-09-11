(function () {
  const API = {
    swap: '/parametros/api/format-lab/swap',
    quote: '/parametros/api/format-lab/quote',
    clients: '/parametros/api/clients',
  };
  const state = { reference: '', clientId: '', clients: [] };

  document.addEventListener('DOMContentLoaded', boot);

  function $(id) {
    return document.getElementById(id);
  }

  async function boot() {
    bind();
    try {
      const [clients, quote] = await Promise.all([
        fetch(API.clients, { credentials: 'same-origin' }).then(readJson),
        fetch(API.quote, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: 'swap' }),
        }).then(readJson),
      ]);
      state.clients = Array.isArray(clients) ? clients : (clients?.items || clients?.clients || []);
      renderClients();
      if (quote?.spent_brl != null) {
        $('mcSwapCost').textContent = `R$ ${Number(quote.spent_brl).toFixed(2)}`;
      }
    } catch (_error) {
      setStatus('Não deu para carregar as marcas. Você ainda pode escrever o nome no pedido.');
    }
  }

  function bind() {
    const drop = $('mcSwapDrop');
    const input = $('mcSwapFile');
    drop?.addEventListener('click', () => input?.click());
    drop?.addEventListener('dragover', (event) => {
      event.preventDefault();
      drop.classList.add('is-dragging');
    });
    drop?.addEventListener('dragleave', () => drop.classList.remove('is-dragging'));
    drop?.addEventListener('drop', (event) => {
      event.preventDefault();
      drop.classList.remove('is-dragging');
      takeFile(event.dataTransfer?.files?.[0]);
    });
    input?.addEventListener('change', () => takeFile(input.files?.[0]));
    $('mcSwapClient')?.addEventListener('change', (event) => {
      state.clientId = event.target.value;
    });
    $('mcSwapRun')?.addEventListener('click', runSwap);
  }

  function renderClients() {
    const select = $('mcSwapClient');
    if (!select) return;
    select.innerHTML = '<option value="">Marca da mesa</option>' + state.clients.map((item) => (
      `<option value="${item.id}">${escapeHtml(item.name || '')}</option>`
    )).join('');
  }

  function takeFile(file) {
    if (!file || !file.type.startsWith('image/')) {
      setStatus('Solte uma imagem. PNG ou JPG.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      state.reference = String(reader.result || '');
      $('mcSwapPreview').hidden = false;
      $('mcSwapDrop').hidden = true;
      $('mcSwapImage').src = state.reference;
      $('mcSwapRun').disabled = false;
      setStatus('Referência na mesa. Escreva o que entra no lugar.');
    };
    reader.readAsDataURL(file);
  }

  async function runSwap() {
    if (!state.reference) return;
    $('mcSwapRun').disabled = true;
    setStatus('Trocando o anúncio no GPT Image 2…');
    try {
      const client = state.clients.find((item) => String(item.id) === String(state.clientId));
      const data = await fetch(API.swap, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reference: state.reference,
          client_id: state.clientId || undefined,
          brand_name: client?.name || '',
          headline: $('mcSwapHeadline')?.value || '',
          support: $('mcSwapSupport')?.value || '',
          cta: $('mcSwapCta')?.value || '',
          note: $('mcSwapNote')?.value || '',
        }),
      }).then(readJson);
      if (data.png_data_url) {
        $('mcSwapImage').src = data.png_data_url;
        $('mcSwapPreview').hidden = false;
        $('mcSwapDrop').hidden = true;
      }
      if (data.quote?.spent_brl != null) {
        $('mcSwapCost').textContent = `R$ ${Number(data.quote.spent_brl).toFixed(2)}`;
      }
      setStatus('Still trocado. O quadro ficou; a marca mudou.');
    } catch (error) {
      setStatus(error.message);
    }
    $('mcSwapRun').disabled = !state.reference;
  }

  async function readJson(response) {
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      throw new Error(payload.message || payload.error || 'Não deu para trocar o anúncio.');
    }
    return payload.data || payload;
  }

  function setStatus(text) {
    const node = $('mcSwapStatus');
    if (node) node.textContent = text;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
})();
