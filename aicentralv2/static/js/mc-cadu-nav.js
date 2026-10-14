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
      // Links from Workspace and Reports name the project (Workspace UUID or Studio id) or only the brand;
      // honour them so the brand references travel with the request instead of falling back to quick creation.
      const query = new URLSearchParams(window.location.search);
      const wantedProject = String(query.get("project_id") || "").trim();
      const wantedBrand = String(query.get("creative_client_id") || "").trim();
      const brandQuery = /^\d+$/.test(wantedBrand) && !wantedProject ? `?brand_id=${encodeURIComponent(wantedBrand)}` : "";
      const payload = await get(`${apiRoot}/format-lab/studio/project-contexts${brandQuery}`);
      if (requestId !== projectRequest) return;
      const items = Array.isArray(payload?.items) ? payload.items : [];
      const saved = (() => { try { return localStorage.getItem("cadu-studio-project") || ""; } catch (_error) { return ""; } })();
      const requested = (wantedProject && items.find((item) => String(item.id) === wantedProject || String(item.external_project_id || "") === wantedProject))
        || (() => { const ofBrand = wantedBrand && !wantedProject ? items.filter((item) => String(item.client_id) === wantedBrand) : []; return ofBrand.length === 1 ? ofBrand[0] : null; })();
      const selected = requested ? String(requested.id) : items.some((item) => String(item.id) === saved) ? saved : String(items[0]?.id || "");
      // A brand without a single matching project opens as a quick creation that still carries that brand's identity.
      const brand = !requested && allowQuickCreate && payload?.requested_brand ? payload.requested_brand : null;
      const brandOption = brand ? `<option value="" data-quick-mode="true" data-client-id="${escapeHtml(brand.client_id)}" data-brand-name="${escapeHtml(brand.brand_name)}" data-brand-context="${escapeHtml(JSON.stringify(brand.brand_context || {}))}" selected>Criação rápida · ${escapeHtml(brand.brand_name)}</option>` : "";
      const quickOption = allowQuickCreate ? `<option value="" data-quick-mode="true"${requested || brand ? "" : " selected"}>Criação rápida · sem projeto</option>` : "";
      projectSelect.innerHTML = items.length || brand ? brandOption + quickOption + items.map((item) => {
        const suffix = Number(item.brand_count || 1) > 1 ? ` +${Number(item.brand_count) - 1}` : "";
        return `<option value="${escapeHtml(item.id)}" data-client-id="${escapeHtml(item.client_id)}" data-brand-name="${escapeHtml(item.brand_name)}" data-brand-context="${escapeHtml(JSON.stringify(item.brand_context || {}))}" data-project-brief="${escapeHtml(item.brief || "")}"${(!allowQuickCreate || requested) && String(item.id) === selected ? " selected" : ""}>${escapeHtml(item.name)} · ${escapeHtml(item.brand_name)}${suffix}</option>`;
      }).join("") : '<option value="">Nenhum projeto com marca vinculada</option>';
      projectSelect.disabled = !items.length && !brand;
      if (items.length || brand) activate(); else publish("cadu:project-ready", { clientId: "", projectId: "", items: [] });
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
