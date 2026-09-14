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

  if (select) {
    select.addEventListener("change", () => {
      Desk.write(select.value);
      paintCredits(select.value);
      document.dispatchEvent(new CustomEvent("cadu:brand-change", {
        detail: { clientId: select.value },
      }));
    });
    document.addEventListener("cadu:credits-refresh", (event) => {
      const id = String(event.detail?.clientId || select.value || "");
      if (id && select.value !== id) select.value = id;
      paintCredits(id);
    });
    loadContext();
  }

  async function loadContext() {
    let clients = [];
    try {
      const payload = await get("/parametros/api/clients");
      clients = Array.isArray(payload) ? payload : (payload?.items || payload?.clients || []);
    } catch (_error) {
      select.innerHTML = '<option value="">Não deu para carregar as marcas</option>';
      document.dispatchEvent(new CustomEvent("cadu:brand-ready", {
        detail: { clientId: Desk.read() || "" },
      }));
      return;
    }
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
    await paintCredits(select.value);
    document.dispatchEvent(new CustomEvent("cadu:brand-ready", {
      detail: { clientId: select.value || Desk.read() || "" },
    }));
  }

  async function paintCredits(clientId) {
    if (!credits) return;
    const query = clientId ? `?client_id=${encodeURIComponent(clientId)}` : "";
    try {
      const data = await get(`/parametros/api/image-credits${query}`);
      const remaining = Number(data?.remaining ?? Math.max(0, Number(data?.monthly || 0) - Number(data?.used || 0)));
      const monthly = Number(data?.monthly || 0);
      credits.hidden = false;
      credits.textContent = `${formatCount(remaining)} créditos`;
      credits.title = monthly ? `${formatCount(data?.used || 0)} usados de ${formatCount(monthly)}` : "";
    } catch (_error) {
      credits.hidden = true;
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
