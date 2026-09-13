(function (root) {
  const KEY = 'cx-mc-desk-client';

  function read() {
    try {
      const raw = JSON.parse(root.localStorage.getItem(KEY) || 'null');
      return String(raw?.clientId || '').trim();
    } catch (_error) {
      return '';
    }
  }

  function write(clientId) {
    try {
      const id = String(clientId || '').trim();
      if (!id) {
        root.localStorage.removeItem(KEY);
        return;
      }
      root.localStorage.setItem(KEY, JSON.stringify({ clientId: id, at: Date.now() }));
    } catch (_error) {
      /* ignore quota / private mode */
    }
  }

  function hasInfo(client) {
    if (!client || typeof client !== 'object') return false;
    const profile = client.brand_profile;
    const line = profile && typeof profile === 'object' ? profile.creative_line : null;
    const filled = (value) => Array.isArray(value) && value.length > 0;
    const object = (value) => Boolean(value && typeof value === 'object' && Object.keys(value).length);
    return Boolean(
      client.logo_url
      || client.logo_upload_path
      || client.tone_of_voice
      || client.primary_color
      || (profile && typeof profile === 'object' && (
        profile.brand_summary
        || filled(profile.color_palette)
        || filled(profile.products_services)
        || object(line)
        || object(profile.trocr)
      ))
    );
  }

  function branded(list) {
    const seen = new Set();
    const items = [];
    (Array.isArray(list) ? list : []).forEach((item) => {
      const id = String(item?.profile_id || item?.id || '').trim();
      if (!id || seen.has(id) || !hasInfo(item)) return;
      seen.add(id);
      items.push(Object.assign({}, item, { id }));
    });
    items.sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'pt-BR'));
    return items;
  }

  function forSelect(list, preferred) {
    const items = branded(list);
    const wanted = String(preferred || read() || '').trim();
    if (wanted && !items.some((item) => String(item.id) === wanted)) {
      const extra = (Array.isArray(list) ? list : []).find((item) => (
        String(item?.profile_id || item?.id || '') === wanted
      ));
      if (extra) items.unshift(Object.assign({}, extra, { id: wanted }));
    }
    return items.length ? items : (Array.isArray(list) ? list.slice() : []);
  }

  function pick(list, fallback) {
    const items = forSelect(list, fallback);
    const preferred = String(read() || fallback || '').trim();
    if (preferred && items.some((item) => String(item.id) === preferred)) return preferred;
    return items[0] ? String(items[0].id) : '';
  }

  function label(client) {
    const name = String(client?.name || client?.id || 'Marca');
    if (client?.brand_profile?.creative_line) return `${name} — DNA`;
    if (hasInfo(client)) return `${name} — perfil`;
    return name;
  }

  root.McDeskBrand = { KEY, read, write, hasInfo, branded, forSelect, pick, label };
})(window);
