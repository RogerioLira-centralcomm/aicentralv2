(function () {
  const API = {
    swap: '/parametros/api/format-lab/swap',
    read: '/parametros/api/format-lab/swap/read',
    quote: '/parametros/api/format-lab/quote',
    clients: '/parametros/api/clients',
  };
  const ROLE_LABEL = {
    logo: 'Logo',
    headline: 'Headline',
    support: 'Apoio',
    cta: 'CTA',
    product: 'Produto',
    price: 'Preço',
    person: 'Pessoa',
    background: 'Fundo',
  };
  const state = {
    reference: '',
    clientId: '',
    clients: [],
    aspectRatio: '16:9',
    userPickedFormat: false,
  };

  document.addEventListener('DOMContentLoaded', boot);

  function $(id) {
    return document.getElementById(id);
  }

  async function boot() {
    bind();
    applyRatio(state.aspectRatio);
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
    document.querySelectorAll('input[name="mcSwapOut"]').forEach((input) => {
      input.addEventListener('change', () => {
        if (!input.checked) return;
        state.userPickedFormat = true;
        state.aspectRatio = input.value;
        applyRatio(input.value);
      });
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
      setStatus('Lendo headline, logo e CTA da referência…');
      readReference();
    };
    reader.readAsDataURL(file);
  }

  async function readReference() {
    if (!state.reference) return;
    try {
      const data = await fetch(API.read, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reference: state.reference }),
      }).then(readJson);
      fillFields(data);
      renderElements(data.elements || [], data.style || '');
      if (data.aspect_hint && !state.userPickedFormat) {
        selectFormat(data.aspect_hint);
      }
      setStatus('Elementos lidos. Edite o texto, escolha a saída e troque a marca.');
    } catch (_error) {
      renderElements([], '');
      setStatus('Não deu para ler os textos. Você ainda pode escrever na mão.');
    }
  }

  function fillFields(data) {
    const headline = $('mcSwapHeadline');
    const support = $('mcSwapSupport');
    const cta = $('mcSwapCta');
    if (headline && data.headline) headline.value = data.headline;
    if (support && data.support) support.value = data.support;
    if (cta && data.cta) cta.value = data.cta;
  }

  function renderElements(items, style) {
    const box = $('mcSwapRead');
    const list = $('mcSwapElements');
    if (!box || !list) return;
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length && !style) {
      box.hidden = true;
      list.innerHTML = '';
      return;
    }
    box.hidden = false;
    list.innerHTML = rows.map((item) => {
      const label = ROLE_LABEL[item.role] || item.role || 'Elemento';
      const text = item.text || item.note || '';
      return `<li><strong>${escapeHtml(label)}</strong>${text ? ` ${escapeHtml(text)}` : ''}</li>`;
    }).join('');
    if (style) {
      list.innerHTML += `<li class="is-style">${escapeHtml(style)}</li>`;
    }
  }

  function selectFormat(ratio) {
    const input = document.querySelector(`input[name="mcSwapOut"][value="${ratio}"]`);
    if (!input) return;
    input.checked = true;
    state.aspectRatio = ratio;
    applyRatio(ratio);
  }

  function applyRatio(ratio) {
    const [width, height] = String(ratio || '16:9').split(':').map(Number);
    const stage = $('mcSwapStage');
    if (!stage || !width || !height) return;
    stage.style.setProperty('--mc-swap-ratio', `${width} / ${height}`);
    stage.classList.toggle('is-vertical', height > width);
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
          aspect_ratio: state.aspectRatio,
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
      if (data.logo_used) {
        setStatus('Still trocado. A logo oficial entrou no quadro. O efeito da referência ficou.');
      } else if (state.clientId) {
        setStatus('Still trocado. Cadastre a logo em Marcas para ela entrar no quadro.');
      } else {
        setStatus('Still trocado. O quadro ficou; a marca mudou.');
      }
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
