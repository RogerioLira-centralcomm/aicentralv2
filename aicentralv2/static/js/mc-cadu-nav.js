(function () {
  const bar = document.getElementById("mcCaduBar");
  const projectSelect = document.getElementById("mcCaduProject");
  const clientSelect = document.getElementById("mcCaduBarClient");
  // The legacy Studio shell still exposes the image-credit balance as text.
  // The current shell renders the shared monthly credit meter server-side.
  const legacyCredits = document.getElementById("mcCaduCredits");
  if (!bar || !projectSelect) return;

  const apiRoot = String(bar.dataset.mcApiRoot || "/parametros/api").replace(/\/$/, "");
  let projectRequest = 0;
  let creditsRequest = 0;
  const escapeHtml = (value) => String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  async function get(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) throw new Error(payload.error || "Falha na leitura.");
    return payload.data !== undefined ? payload.data : payload;
  }
  function publish(type, detail) {
    window.McCaduContext = detail;
    document.dispatchEvent(new CustomEvent(type, { detail }));
  }
  function activeContext() {
    const option = projectSelect.selectedOptions[0];
    return { clientId: String(option?.dataset.clientId || ""), projectId: String(projectSelect.value || ""), brandName: String(option?.dataset.brandName || "") };
  }
  async function paintLegacyCredits(clientId) {
    if (!legacyCredits || !clientId) return;
    const requestId = ++creditsRequest;
    try {
      const data = await get(`${apiRoot}/image-credits?client_id=${encodeURIComponent(clientId)}`);
      if (requestId !== creditsRequest || activeContext().clientId !== clientId) return;
      const remaining = Number(data?.remaining ?? Math.max(0, Number(data?.monthly || 0) - Number(data?.used || 0)));
      if (Number.isFinite(remaining)) {
        legacyCredits.hidden = false;
        legacyCredits.textContent = `${remaining.toLocaleString("pt-BR")} créditos disponíveis`;
      }
    } catch (_error) { /* Keep the legacy balance hidden when the API is unavailable. */ }
  }
  function activate() {
    const context = activeContext();
    if (clientSelect) {
      clientSelect.innerHTML = `<option value="${escapeHtml(context.clientId)}">${escapeHtml(context.brandName)}</option>`;
      clientSelect.value = context.clientId;
    }
    try { localStorage.setItem("cadu-studio-project", context.projectId); } catch (_error) {}
    paintLegacyCredits(context.clientId);
    publish("cadu:brand-ready", context);
    publish("cadu:brand-change", context);
    publish("cadu:project-ready", context);
    publish("cadu:project-change", context);
  }
  async function loadProjects() {
    const requestId = ++projectRequest;
    projectSelect.disabled = true;
    projectSelect.innerHTML = '<option value="">Carregando projetos…</option>';
    try {
      const payload = await get(`${apiRoot}/format-lab/studio/project-contexts`);
      if (requestId !== projectRequest) return;
      const items = Array.isArray(payload?.items) ? payload.items : [];
      const saved = (() => { try { return localStorage.getItem("cadu-studio-project") || ""; } catch (_error) { return ""; } })();
      const selected = items.some((item) => String(item.id) === saved) ? saved : String(items[0]?.id || "");
      projectSelect.innerHTML = items.length ? items.map((item) => {
        const suffix = Number(item.brand_count || 1) > 1 ? ` +${Number(item.brand_count) - 1}` : "";
        return `<option value="${escapeHtml(item.id)}" data-client-id="${escapeHtml(item.client_id)}" data-brand-name="${escapeHtml(item.brand_name)}"${String(item.id) === selected ? " selected" : ""}>${escapeHtml(item.name)} · ${escapeHtml(item.brand_name)}${suffix}</option>`;
      }).join("") : '<option value="">Nenhum projeto com marca vinculada</option>';
      projectSelect.disabled = !items.length;
      if (items.length) activate(); else publish("cadu:project-ready", { clientId: "", projectId: "", items: [] });
    } catch (_error) {
      projectSelect.innerHTML = '<option value="">Não foi possível carregar projetos</option>';
      publish("cadu:project-ready", { clientId: "", projectId: "", error: true, items: [] });
    }
  }
  projectSelect.addEventListener("change", activate);
  document.addEventListener("cadu:context-retry", loadProjects);
  document.addEventListener("cadu:credits-refresh", (event) => {
    const context = activeContext();
    if (String(event.detail?.clientId || context.clientId) === context.clientId) paintLegacyCredits(context.clientId);
  });
  loadProjects();
})();
