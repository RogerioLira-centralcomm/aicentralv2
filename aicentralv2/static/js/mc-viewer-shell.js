(function (global) {
  const KIND_LABEL = { tv: 'CTV', portal: 'Portal', social: 'Social' };

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function safeColor(value, fallback) {
    return /^#[0-9a-f]{6}$/i.test(String(value || '')) ? value : fallback;
  }

  function logoHtml(profile) {
    return profile?.logo_asset_ref
      ? `<img src="${escapeHtml(profile.logo_asset_ref)}" alt="">`
      : `<strong>${escapeHtml(profile?.name || 'Mídia')}</strong>`;
  }

  function tvHtml(profile) {
    const hero = profile?.shell_spec?.hero || {};
    const slug = profile?.slug || 'tv';
    const scene = hero.image || profile?.shell_spec?.sections?.[0]?.items?.[0]?.image || '';
    return `
      <div class="mc-tv-playback is-${escapeHtml(slug)}">
        <div class="mc-tv-scene" aria-hidden="true">
          ${scene ? `<img src="${escapeHtml(scene)}" alt="">` : ''}
          <div class="mc-tv-scene-grade"></div>
          <div class="mc-tv-now">
            <small>${escapeHtml(hero.eyebrow || 'Em reprodução')}</small>
            <strong>${escapeHtml(hero.title || 'Uma história para continuar assistindo')}</strong>
          </div>
        </div>
        <div class="mc-tv-player">
          <header>${logoHtml(profile)}<span>Pausado</span></header>
          <footer>
            <i class="fa-solid fa-play"></i>
            <time>12:04</time>
            <b class="mc-tv-progress"><i></i></b>
            <time>48:22</time>
          </footer>
        </div>
      </div>`;
  }

  function portalHtml(profile) {
    const shell = profile?.shell_spec || {};
    const hero = shell.hero || {};
    const items = [];
    (shell.sections || []).forEach((section) => {
      (section.items || []).forEach((item) => items.push(item));
    });
    const highlights = items.slice(0, 2);
    const nav = (shell.nav || []).map((item) => `<span>${escapeHtml(item)}</span>`).join('');
    const network = (shell.network_links || []).map((item) => `<span>${escapeHtml(item)}</span>`).join('');
    return `
      <div class="mc-portal-page">
        <div class="mc-portal-network">${network}</div>
        <header class="mc-portal-masthead">
          <span>${logoHtml(profile)}</span>
          <b>${escapeHtml(shell.edition_label || profile?.name || 'Notícias')}</b>
        </header>
        <nav class="mc-portal-nav">${nav}</nav>
        <div class="mc-ad-zone is-leaderboard is-active" data-ad-zone="leaderboard"><small>Publicidade</small></div>
        <div class="mc-portal-body">
          <div class="mc-portal-main">
            <article class="mc-portal-lead">
              <small>${escapeHtml(hero.eyebrow || 'Destaque')}</small>
              <strong>${escapeHtml(hero.title || 'Manchete demonstrativa')}</strong>
              <span>${escapeHtml(hero.description || '')}</span>
            </article>
            <div class="mc-portal-highlights">${highlights.map((item) => `
              <article>
                ${item.image ? `<img src="${escapeHtml(item.image)}" alt="">` : ''}
                <small>${escapeHtml(item.category || '')}</small>
                <strong>${escapeHtml(item.title || '')}</strong>
              </article>`).join('')}</div>
            <div class="mc-ad-zone is-in-feed" data-ad-zone="in_feed"><small>Publicidade</small></div>
          </div>
        </div>
      </div>`;
  }

  function socialHtml(profile, aspect) {
    const slug = profile?.slug || 'instagram';
    const vertical = aspect === '9:16' || slug === 'tiktok';
    if (slug === 'tiktok' || (slug === 'youtube' && vertical)) {
      return `
        <div class="mc-social is-${escapeHtml(slug === 'youtube' ? 'youtube is-shorts' : 'tiktok')}">
          <div class="mc-ad-well" data-ad-well></div>
          <footer class="mc-tt-caption">
            ${logoHtml(profile)}
            <strong>Patrocinado</strong>
          </footer>
        </div>`;
    }
    if (vertical) {
      return `
        <div class="mc-social is-instagram is-story">
          <div class="mc-ad-well" data-ad-well></div>
          <div class="mc-ig-story-chrome" aria-hidden="true">
            <header><strong>marca.oficial</strong><small>Patrocinado</small></header>
          </div>
        </div>`;
    }
    return `
      <div class="mc-social is-${escapeHtml(slug)} is-feed">
        <header class="mc-social-status">${logoHtml(profile)}<span>Feed</span></header>
        <article class="mc-ig-post">
          <div class="mc-ig-head">
            <i class="mc-ig-avatar"></i>
            <div>
              <strong>marca.oficial</strong>
              <small>Patrocinado</small>
            </div>
          </div>
          <div class="mc-ad-well" data-ad-well></div>
        </article>
      </div>`;
  }

  function shellHtml(profile, aspect) {
    const kind = profile?.viewer_kind || 'portal';
    if (kind === 'tv') return tvHtml(profile);
    if (kind === 'social') return socialHtml(profile, aspect);
    return portalHtml(profile);
  }

  function applyPalette(node, profile) {
    if (!node) return;
    const palette = profile?.palette || {};
    node.dataset.viewer = profile?.slug || '';
    node.dataset.layout = profile?.shell_spec?.layout || 'standard';
    node.classList.toggle('is-tv', profile?.viewer_kind === 'tv');
    node.classList.toggle('is-portal', profile?.viewer_kind === 'portal');
    node.classList.toggle('is-page', profile?.viewer_kind === 'portal');
    node.classList.toggle('is-pause', profile?.viewer_kind === 'tv');
    node.style.setProperty('--viewer-primary', safeColor(palette.primary, '#1e4d4f'));
    node.style.setProperty('--viewer-secondary', safeColor(palette.secondary, '#173436'));
    node.style.setProperty('--viewer-surface', safeColor(palette.surface, '#ffffff'));
    node.style.setProperty('--viewer-canvas', safeColor(palette.canvas, '#edf2f1'));
    node.style.setProperty('--viewer-text', safeColor(palette.text, '#1f2937'));
  }

  function mountCreative(root, node, kind) {
    if (!root || !node) return;
    const host = kind === 'portal'
      ? root.querySelector('[data-ad-zone].is-active, [data-ad-zone]')
      : root.querySelector('[data-ad-well]');
    if (host) {
      host.appendChild(node);
      node.classList.add('is-in-zone');
      return;
    }
    node.classList.remove('is-in-zone');
    if (node.parentElement !== root) root.appendChild(node);
  }

  function profilesFor(profiles, kind) {
    const list = Array.isArray(profiles) ? profiles : [];
    if (kind === 'ctv' || kind === 'tv') {
      return list.filter((item) => item.viewer_kind === 'tv');
    }
    if (kind === 'mobile' || kind === 'social') {
      return list.filter((item) => item.viewer_kind === 'social');
    }
    if (kind === 'portal') {
      return list.filter((item) => item.viewer_kind === 'portal');
    }
    return list;
  }

  global.McViewerShell = {
    KIND_LABEL,
    escapeHtml,
    logoHtml,
    shellHtml,
    applyPalette,
    mountCreative,
    profilesFor,
  };
})(window);
