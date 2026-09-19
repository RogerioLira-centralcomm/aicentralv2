(function () {
  const bar = document.getElementById("mcCaduBar");
  const projectSelect = document.getElementById("mcCaduProject");
  const clientSelect = document.getElementById("mcCaduBarClient");
  // The legacy Studio shell keeps a compact text treatment, but reads the
  // same organisation-level token balance as every current Cadu product.
  const legacyCredits = document.getElementById("mcCaduCredits");
  if (!bar || !projectSelect) return;

  const apiRoot = String(bar.dataset.mcApiRoot || "/parametros/api").replace(/\/$/, "");
  const creditSummaryUrl = String(bar.dataset.creditSummaryUrl || "/workspace/api/creditos/resumo");
  const allowQuickCreate = bar.dataset.allowQuickCreate === "true";
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
    return { clientId: String(option?.dataset.clientId || ""), projectId: String(projectSelect.value || ""), brandName: String(option?.dataset.brandName || ""), quickMode: option?.dataset.quickMode === "true" };
  }
  async function paintLegacyCredits() {
    if (!legacyCredits) return;
    const requestId = ++creditsRequest;
    try {
      const data = await get(creditSummaryUrl);
      if (requestId !== creditsRequest || !data?.configured) return;
      const available = Number(data.available || 0);
      const total = Number(data.monthly || 0);
      const usage = total > 0 ? Math.max(0, Math.min(100, Math.round(((total - available) * 100) / total))) : 0;
      if (Number.isFinite(available)) {
        legacyCredits.hidden = false;
        legacyCredits.textContent = `${usage}% usado · ${available.toLocaleString("pt-BR")} disponíveis`;
      }
    } catch (_error) { /* Keep the balance hidden when the shared ledger is unavailable. */ }
  }
  function activate() {
    const context = activeContext();
    if (clientSelect) {
      clientSelect.innerHTML = `<option value="${escapeHtml(context.clientId)}">${escapeHtml(context.brandName)}</option>`;
      clientSelect.value = context.clientId;
    }
    try { if (!context.quickMode) localStorage.setItem("cadu-studio-project", context.projectId); } catch (_error) {}
    paintLegacyCredits();
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
      const quickOption = allowQuickCreate ? '<option value="" data-quick-mode="true" selected>Criação rápida · sem projeto</option>' : "";
      projectSelect.innerHTML = items.length ? quickOption + items.map((item) => {
        const suffix = Number(item.brand_count || 1) > 1 ? ` +${Number(item.brand_count) - 1}` : "";
        return `<option value="${escapeHtml(item.id)}" data-client-id="${escapeHtml(item.client_id)}" data-brand-name="${escapeHtml(item.brand_name)}" data-brand-context="${escapeHtml(JSON.stringify(item.brand_context || {}))}" data-project-brief="${escapeHtml(item.brief || "")}"${!allowQuickCreate && String(item.id) === selected ? " selected" : ""}>${escapeHtml(item.name)} · ${escapeHtml(item.brand_name)}${suffix}</option>`;
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
    if (String(event.detail?.clientId || context.clientId) === context.clientId) paintLegacyCredits();
  });
  loadProjects();
})();
