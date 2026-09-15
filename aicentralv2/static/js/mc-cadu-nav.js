(function () {
  const bar = document.getElementById("mcCaduBar");
  if (!bar) return;

  const Desk = window.McDeskBrand || {
    read() { return ""; },
    write() {},
    forSelect(list) { return Array.isArray(list) ? list : []; },
    pick(_list, fallback) { return String(fallback || ""); },
    label(client) { return client?.name || ""; },
  };

  const menus = Array.from(bar.querySelectorAll("details.mc-cadu-menu"));
  const select = document.getElementById("mcCaduBarClient");
  const credits = document.getElementById("mcCaduCredits");

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

  function publishContext(type, detail) {
    window.McCaduContext = detail;
    document.dispatchEvent(new CustomEvent(type, { detail }));
  }

  if (select) {
    select.addEventListener("change", () => {
      Desk.write(select.value);
      paintCredits(select.value);
      publishContext("cadu:brand-change", { clientId: select.value });
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
      // O Studio contratado opera exclusivamente sobre o perfil 174.
      const payload = await get("/parametros/api/clients?client_id=174");
      clients = Array.isArray(payload) ? payload : (payload?.items || payload?.clients || []);
    } catch (_error) {
      if (requestId !== contextRequest) return;
      select.disabled = false;
      select.innerHTML = '<option value="">Não deu para carregar as marcas</option>';
      if (credits) credits.hidden = true;
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
  }

  async function paintCredits(clientId) {
    if (!credits) return;
    const requestId = ++creditsRequest;
    credits.hidden = true;
    credits.textContent = "";
    if (!clientId) return;
    const query = `?client_id=${encodeURIComponent(clientId)}`;
    try {
      const data = await get(`/parametros/api/image-credits${query}`);
      if (requestId !== creditsRequest || select.value !== clientId) return;
      const hasBalance = data?.remaining != null;
      const hasUsage = data?.monthly != null && data?.used != null;
      if (!hasBalance && !hasUsage) return;
      const remaining = hasBalance ? Number(data.remaining) : Math.max(0, Number(data.monthly) - Number(data.used));
      if (!Number.isFinite(remaining)) return;
      const monthly = Number(data?.monthly || 0);
      credits.hidden = false;
      credits.textContent = `${formatCount(remaining)} créditos`;
      credits.title = monthly ? `${formatCount(data?.used || 0)} usados de ${formatCount(monthly)}` : "";
    } catch (_error) {
      if (requestId === creditsRequest) credits.hidden = true;
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
