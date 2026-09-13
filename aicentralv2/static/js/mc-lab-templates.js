(function () {
  const API = {
    list: '/parametros/api/viewer-templates',
    item: (slug) => `/parametros/api/viewer-templates/${encodeURIComponent(slug)}`,
    formats: (slug) => `/parametros/api/viewer-templates/${encodeURIComponent(slug)}/formats`,
  };
  const KIND = { tv: 'CTV', portal: 'Portais', social: 'Redes' };

  document.addEventListener('DOMContentLoaded', boot);

  function $(id) {
    return document.getElementById(id);
  }

  async function boot() {
    if ($('mcLabTemplateEdit')) {
      await bootEdit();
      return;
    }
    if ($('mcLabTemplates')) await bootList();
  }

  async function bootList() {
    const status = $('mcLabTemplateStatus');
    const root = $('mcLabTemplateGroups');
    try {
      const profiles = await request(API.list);
      const groups = { tv: [], portal: [], social: [] };
      profiles.forEach((item) => {
        (groups[item.viewer_kind] || groups.portal).push(item);
      });
      root.innerHTML = Object.entries(groups).map(([kind, items]) => `
        <section class="mc-lab-template-group">
          <h2>${KIND[kind] || kind}</h2>
          <ul>${items.map((item) => {
            const formats = item.formats || [];
            return `
            <li>
              <a href="/lab/templates/${encodeURIComponent(item.slug)}">
                ${item.logo_asset_ref ? `<img src="${escapeHtml(item.logo_asset_ref)}" alt="">` : ''}
                <strong>${escapeHtml(item.name)}</strong>
                <small>${escapeHtml(item.slug)}</small>
                <em>${formats.length
                  ? formats.map((row) => escapeHtml(row.name || row.slug)).join(' · ')
                  : 'Nenhum formato ligado'}</em>
              </a>
            </li>`;
          }).join('')}</ul>
        </section>`).join('');
      const linked = profiles.reduce((sum, item) => sum + (item.formats || []).length, 0);
      if (status) status.textContent = `${profiles.length} ambientes · ${linked} formatos ligados.`;
    } catch (error) {
      if (status) status.textContent = error.message || 'Não deu para ler os modelos.';
    }
  }

  async function bootEdit() {
    const root = $('mcLabTemplateEdit');
    const slug = root?.dataset?.slug;
    const status = $('mcLabTemplateStatus');
    if (!slug) return;
    try {
      const profile = await request(API.item(slug));
      fillForm(profile);
      paintPreview(profile);
      paintFormats(profile);
      $('mcLabTemplateForm').hidden = false;
      if ($('mcLabTemplateTitle')) $('mcLabTemplateTitle').textContent = profile.name;
      if (status) status.textContent = `${profile.viewer_kind} · ${profile.slug}`;
      $('mcLabTemplateForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        await save(slug);
      });
      ['mcLabPrimary', 'mcLabSecondary', 'mcLabSurface', 'mcLabCanvas', 'mcLabText', 'mcLabShell', 'mcLabName', 'mcLabDisclaimer']
        .forEach((id) => $(id)?.addEventListener('input', () => paintPreview(readForm(profile))));
    } catch (error) {
      if (status) status.textContent = error.message || 'Modelo não encontrado.';
    }
  }

  function fillForm(profile) {
    const palette = profile.palette || {};
    $('mcLabName').value = profile.name || '';
    $('mcLabDisclaimer').value = profile.disclaimer || '';
    $('mcLabLogo').value = profile.logo_asset_ref || '';
    $('mcLabPrimary').value = palette.primary || '#111111';
    $('mcLabSecondary').value = palette.secondary || '#222222';
    $('mcLabSurface').value = palette.surface || '#ffffff';
    $('mcLabCanvas').value = palette.canvas || '#111111';
    $('mcLabText').value = palette.text || '#ffffff';
    $('mcLabShell').value = JSON.stringify(profile.shell_spec || {}, null, 2);
  }

  function readForm(base) {
    let shell = base.shell_spec || {};
    try {
      shell = JSON.parse($('mcLabShell').value || '{}');
    } catch (_error) {
      shell = base.shell_spec || {};
    }
    return {
      ...base,
      name: $('mcLabName').value,
      disclaimer: $('mcLabDisclaimer').value,
      logo_asset_ref: $('mcLabLogo').value,
      palette: {
        primary: $('mcLabPrimary').value,
        secondary: $('mcLabSecondary').value,
        surface: $('mcLabSurface').value,
        canvas: $('mcLabCanvas').value,
        text: $('mcLabText').value,
      },
      shell_spec: shell,
    };
  }

  function paintPreview(profile) {
    const frame = $('mcLabPreviewFrame');
    const shell = $('mcLabPreviewShell');
    if (!frame || !shell || !window.McViewerShell) return;
    window.McViewerShell.applyPalette(frame, profile);
    shell.innerHTML = window.McViewerShell.shellHtml(profile);
    if ($('mcLabPreviewDisclaimer')) {
      $('mcLabPreviewDisclaimer').textContent = profile.disclaimer || 'Simulação de ambiente';
    }
  }

  function paintFormats(profile) {
    const root = $('mcLabFormatList');
    const box = $('mcLabFormats');
    if (!root || !box) return;
    const linked = new Set((profile.formats || []).map((item) => String(item.id)));
    const rows = profile.compatible_formats || [];
    box.hidden = !rows.length;
    root.innerHTML = rows.map((item) => `
      <label>
        <input type="checkbox" value="${escapeHtml(item.id)}" ${linked.has(String(item.id)) ? 'checked' : ''}>
        <span>
          <strong>${escapeHtml(item.name || item.slug)}</strong>
          <small>${escapeHtml([item.slug, item.aspect_ratio, item.channel_name || item.channel].filter(Boolean).join(' · '))}</small>
        </span>
      </label>`).join('');
  }

  function selectedFormatIds() {
    return [...document.querySelectorAll('#mcLabFormatList input:checked')]
      .map((node) => Number(node.value))
      .filter((value) => Number.isInteger(value) && value > 0);
  }

  async function save(slug) {
    const status = $('mcLabTemplateStatus');
    let shell = {};
    try {
      shell = JSON.parse($('mcLabShell').value || '{}');
    } catch (_error) {
      if (status) status.textContent = 'O JSON do shell está inválido.';
      return;
    }
    try {
      const saved = await request(API.item(slug), {
        name: $('mcLabName').value,
        disclaimer: $('mcLabDisclaimer').value,
        logo_asset_ref: $('mcLabLogo').value,
        palette: {
          primary: $('mcLabPrimary').value,
          secondary: $('mcLabSecondary').value,
          surface: $('mcLabSurface').value,
          canvas: $('mcLabCanvas').value,
          text: $('mcLabText').value,
        },
        shell_spec: shell,
      }, 'PUT');
      const linked = await request(API.formats(slug), {
        format_ids: selectedFormatIds(),
      }, 'PUT');
      paintPreview(linked);
      paintFormats(linked);
      if ($('mcLabTemplateTitle')) $('mcLabTemplateTitle').textContent = saved.name;
      if (status) status.textContent = 'Modelo e formatos salvos.';
    } catch (error) {
      if (status) status.textContent = error.message || 'Não salvou o modelo.';
    }
  }

  async function request(url, body, method) {
    const response = await fetch(url, {
      method: method || (body ? 'POST' : 'GET'),
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
      throw new Error(payload.message || payload.error || 'Falha na API de templates.');
    }
    return payload.data || payload;
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
})();
