(() => {
  const select = document.getElementById('mcReviewCampaign');
  const empty = document.getElementById('mcReviewEmpty');
  const image = document.getElementById('mcReviewImage');
  const run = document.getElementById('mcReviewRun');
  const verdict = document.getElementById('mcReviewVerdict');
  const checks = document.getElementById('mcReviewChecks');
  let contract = { instance_data: {}, family: 'sequence_16x9', params: {}, scenes: [] };

  async function loadCampaigns() {
    const response = await fetch('/parametros/api/campaigns', { credentials: 'same-origin' });
    const payload = await response.json();
    const rows = payload.data || [];
    select.innerHTML = '<option value="">Escolha a campanha</option>' + rows.map((item) => (
      `<option value="${item.id}">${item.name || ('Campanha ' + item.id)}</option>`
    )).join('');
  }

  select?.addEventListener('change', async () => {
    const id = select.value;
    run.disabled = !id;
    if (!id) return;
    const response = await fetch(`/parametros/api/campaigns/${id}`, { credentials: 'same-origin' });
    const payload = await response.json();
    const campaign = payload.data || {};
    const brief = campaign.creative_brief || {};
    contract = {
      campaign_id: String(campaign.id || ''),
      family: brief.compose_library?.family || 'sequence_16x9',
      template_variation: brief.compose_library?.variation_id || '',
      params: brief.compose_library?.params || {},
      instance_data: {
        headline: brief.locks?.headline || campaign.name || '',
        cta: brief.locks?.cta || campaign.cta_text || '',
      },
      scenes: brief.context_design?.scenes || [],
    };
    const asset = (campaign.assets || []).find((item) => item.status === 'approved')
      || (campaign.assets || [])[0];
    if (asset?.asset_url) {
      image.src = asset.asset_url;
      image.classList.remove('hidden');
      empty.classList.add('hidden');
    } else {
      image.classList.add('hidden');
      empty.classList.remove('hidden');
      empty.textContent = 'Esta campanha ainda não tem peça montada.';
    }
  });

  run?.addEventListener('click', async () => {
    run.disabled = true;
    verdict.textContent = 'Conferindo.';
    try {
      const response = await fetch('/parametros/api/agents/reviewer', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contract,
          expected_headline: contract.instance_data.headline || '',
          image_url: image.src || '',
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || 'Não conferi a peça.');
      }
      const qa = payload.data?.qa || {};
      verdict.textContent = qa.passed ? 'Passou. Pode aprovar no Montar.' : 'Volta. Tem item vermelho.';
      const notes = qa.notes || [];
      const ok = qa.checks || [];
      checks.innerHTML = [
        ...ok.map((item) => `<li>${item}</li>`),
        ...notes.map((item) => `<li class="is-fail">${item}</li>`),
      ].join('') || '<li>Sem checagens.</li>';
    } catch (error) {
      verdict.textContent = error.message;
    } finally {
      run.disabled = false;
    }
  });

  loadCampaigns().catch(() => {
    verdict.textContent = 'Não carreguei as campanhas.';
  });
})();
