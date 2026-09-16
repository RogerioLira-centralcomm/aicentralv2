(function () {
  const bar = document.getElementById("mcCaduBar");
  if (!bar) return;
  const apiRoot = String(bar.dataset.mcApiRoot || "/parametros/api").replace(/\/$/, "");

  const Desk = window.McDeskBrand || {
    read() { return ""; },
    write() {},
    forSelect(list) { return Array.isArray(list) ? list : []; },
    pick(_list, fallback) { return String(fallback || ""); },
    label(client) { return client?.name || ""; },
  };

  const menus = Array.from(bar.querySelectorAll("details.mc-cadu-menu"));
  const select = document.getElementById("mcCaduBarClient");
  const projectSelect = document.getElementById("mcCaduProject");
  const credits = document.getElementById("mcCaduCredits");
  const accountCredit = String(credits?.dataset.accountCredit || "");

  function paintAccountCredit() {
    if (!credits || !accountCredit) return;
    const value = accountCredit.replace(/\s*créditos?$/i, "");
    const label = document.createElement("small");
    const balance = document.createElement("strong");
    label.textContent = "Créditos";
    balance.textContent = value;
    credits.replaceChildren(label, balance);
    credits.dataset.creditState = "account";
    credits.hidden = false;
  }

  function closeAll(except) {
    menus.forEach((item) => {
      if (item !== except) item.removeAttribute("open");
    });
  }

  menus.forEach((item) => {
    item.addEventListener("toggle", () => {
      if (item.open) closeAll(item);
    });
  });

  document.addEventListener("pointerdown", (event) => {
    if (!bar.contains(event.target)) closeAll();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeAll();
  });

  let contextRequest = 0;
  let creditsRequest = 0;
  let projectsRequest = 0;

  function publishContext(type, detail) {
    window.McCaduContext = detail;
    document.dispatchEvent(new CustomEvent(type, { detail }));
  }

  if (select) {
    select.addEventListener("change", () => {
      Desk.write(select.value);
      paintCredits(select.value);
      publishContext("cadu:brand-change", { clientId: select.value });
      loadProjects(select.value);
    });
    document.addEventListener("cadu:credits-refresh", (event) => {
      const id = String(event.detail?.clientId || select.value || "");
      // A completed generation from an old brand must not switch the active brand.
      if (id !== select.value) return;
      paintCredits(id);
    });
    document.addEventListener("cadu:context-retry", loadContext);
    loadContext();
  }

  async function loadContext() {
    const requestId = ++contextRequest;
    select.disabled = true;
    let clients = [];
    try {
      const payload = await get(`${apiRoot}/clients`);
      clients = Array.isArray(payload) ? payload : (payload?.items || payload?.clients || []);
    } catch (_error) {
      if (requestId !== contextRequest) return;
      select.disabled = false;
      select.innerHTML = '<option value="">Não deu para carregar as marcas</option>';
      paintAccountCredit();
      creditsRequest++;
      publishContext("cadu:brand-ready", { clientId: "", error: true });
      return;
    }
    if (requestId !== contextRequest) return;
    select.disabled = false;
    const options = Desk.forSelect(clients, Desk.read());
    const chosen = Desk.pick(options, Desk.read());
    select.innerHTML = options.length
      ? options.map((item) => {
        const id = String(item.profile_id || item.id || "");
        return `<option value="${escapeHtml(id)}"${id === chosen ? " selected" : ""}>${escapeHtml(Desk.label(item))}</option>`;
      }).join("")
      : '<option value="">Nenhuma marca</option>';
    if (chosen) {
      Desk.write(chosen);
      select.value = chosen;
    }
    if (!chosen) Desk.write("");
    publishContext("cadu:brand-ready", { clientId: select.value || "" });
    paintCredits(select.value);
    loadProjects(select.value);
  }

  if (projectSelect) {
    projectSelect.addEventListener("change", () => {
      const clientId = String(select?.value || "");
      const projectId = String(projectSelect.value || "");
      try { localStorage.setItem(`cadu-studio-project:${clientId}`, projectId); } catch (_error) {}
      publishContext("cadu:project-change", { clientId, projectId });
    });
  }

  async function loadProjects(clientId) {
    if (!projectSelect) return;
    const requestId = ++projectsRequest;
    projectSelect.disabled = true;
    projectSelect.innerHTML = '<option value="">Carregando projetos…</option>';
    if (!clientId) {
      projectSelect.innerHTML = '<option value="">Sem projeto disponível</option>';
      return;
    }
    try {
      const payload = await get(`${apiRoot}/format-lab/studio/projects?client_id=${encodeURIComponent(clientId)}`);
      if (requestId !== projectsRequest) return;
      const items = Array.isArray(payload?.items) ? payload.items : [];
      const saved = (() => { try { return localStorage.getItem(`cadu-studio-project:${clientId}`) || ""; } catch (_error) { return ""; } })();
      const chosen = items.some((item) => String(item.id) === saved) ? saved : String(items[0]?.id || "");
      projectSelect.innerHTML = items.length
        ? items.map((item) => `<option value="${escapeHtml(item.id)}"${String(item.id) === chosen ? " selected" : ""}>${escapeHtml(item.name || "Projeto sem nome")}</option>`).join("")
        : '<option value="">Nenhum projeto</option>';
      projectSelect.disabled = !items.length;
      publishContext("cadu:project-ready", { clientId: String(clientId), projectId: chosen, items });
    } catch (_error) {
      if (requestId !== projectsRequest) return;
      projectSelect.innerHTML = '<option value="">Não foi possível carregar</option>';
      projectSelect.disabled = true;
      publishContext("cadu:project-ready", { clientId: String(clientId), projectId: "", error: true, items: [] });
    }
  }

  async function paintCredits(clientId) {
    if (!credits) return;
    const requestId = ++creditsRequest;
    if (!clientId) {
      paintAccountCredit();
      return;
    }
    const query = `?client_id=${encodeURIComponent(clientId)}`;
    try {
      const data = await get(`${apiRoot}/image-credits${query}`);
      if (requestId !== creditsRequest || select.value !== clientId) return;
      const hasBalance = data?.remaining != null;
      const hasUsage = data?.monthly != null && data?.used != null;
      if (!hasBalance && !hasUsage) return;
      const remaining = hasBalance ? Number(data.remaining) : Math.max(0, Number(data.monthly) - Number(data.used));
      if (!Number.isFinite(remaining)) return;
      const monthly = Number(data?.monthly || 0);
      credits.hidden = false;
      const state = String(data?.status || (remaining ? "ok" : "empty"));
      credits.dataset.creditState = state;
      credits.textContent = state === "empty"
        ? "Sem saldo · ver créditos"
        : state === "low"
          ? `${formatCount(remaining)} tokens · saldo baixo`
          : `${formatCount(remaining)} tokens`;
      credits.title = monthly ? `${formatCount(data?.used || 0)} usados de ${formatCount(monthly)}` : "";
    } catch (_error) {
      if (requestId === creditsRequest) paintAccountCredit();
    }
  }

  async function get(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
      throw new Error(payload.error || "Falha na leitura.");
    }
    return payload.data !== undefined ? payload.data : payload;
  }

  function formatCount(value) {
    return Number(value || 0).toLocaleString("pt-BR");
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
