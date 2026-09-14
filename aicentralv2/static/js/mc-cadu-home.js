(function () {
  const Desk = window.McDeskBrand || {
    read() { return ""; },
    write() {},
    forSelect(list) { return Array.isArray(list) ? list : []; },
    pick(_list, fallback) { return String(fallback || ""); },
    label(client) { return client?.name || ""; },
  };

  const takes = document.getElementById("mcCaduTakes");
  const empty = document.getElementById("mcCaduEmpty");
  if (!takes) return;

  const barSelect = document.getElementById("mcCaduBarClient");
  const homeSelect = document.getElementById("mcCaduHomeClient");

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  function boot() {
    document.addEventListener("cadu:brand-change", (event) => {
      const id = event.detail?.clientId || Desk.read();
      if (homeSelect && id) homeSelect.value = id;
      loadWall(id);
    });
    if (homeSelect && !barSelect) {
      loadHomeSelect();
    } else {
      const chosen = Desk.read();
      if (chosen) loadWall(chosen);
    }
  }

  async function loadHomeSelect() {
    let clients = [];
    try {
      const payload = await get("/parametros/api/clients");
      clients = Array.isArray(payload) ? payload : (payload?.items || payload?.clients || []);
    } catch (_error) {
      homeSelect.innerHTML = '<option value="">Não deu para carregar as marcas</option>';
      return;
    }
    const options = Desk.forSelect(clients, Desk.read());
    const chosen = Desk.pick(options, Desk.read());
    homeSelect.innerHTML = options.length
      ? options.map((item) => {
        const id = String(item.profile_id || item.id || "");
        return `<option value="${escapeHtml(id)}"${id === chosen ? " selected" : ""}>${escapeHtml(Desk.label(item))}</option>`;
      }).join("")
      : '<option value="">Nenhuma marca</option>';
    if (chosen) Desk.write(chosen);
    homeSelect.addEventListener("change", () => {
      Desk.write(homeSelect.value);
      loadWall(homeSelect.value);
    });
    await loadWall(homeSelect.value);
  }

  async function loadWall(clientId) {
    takes.querySelectorAll("[data-run]").forEach((node) => node.remove());
    if (empty) {
      empty.hidden = false;
      empty.innerHTML = "<p>Ainda não há peça nesta marca.</p><p>Abra Ajustar e solte o criativo. O histórico aparece aqui.</p>";
    }
    if (!clientId) return;
    try {
      const query = `?client_id=${encodeURIComponent(clientId)}`;
      const data = await get(`/parametros/api/format-lab/swap/history${query}`);
      const runs = (data?.runs || []).filter((item) => item?.run_id && item.version_count);
      if (!runs.length && !(data?.versions || []).length) return;
      const cards = (runs.length ? runs : [{
        run_id: data.run_id,
        title: data.title || "Peça",
        thumb_url: (data.versions || [])[0]?.thumb_url,
        version_count: (data.versions || []).length,
        aspect_ratio: data.aspect_ratio,
        updated_at: data.updated_at,
        active: true,
      }]).slice().sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
      if (empty) empty.hidden = true;
      cards.slice(0, 12).forEach((run) => {
        const href = `/parametros/modelagem-criativos/trocar?run=${encodeURIComponent(run.run_id || "")}&client=${encodeURIComponent(clientId)}`;
        const ratio = String(run.aspect_ratio || "4:5").replace(":", "/");
        const li = document.createElement("li");
        li.setAttribute("data-run", run.run_id || "");
        li.setAttribute("data-ratio", ratio);
        li.style.setProperty("--take-ratio", ratio);
        li.innerHTML = `
          <a href="${href}">
            ${run.thumb_url ? `<img src="${escapeHtml(run.thumb_url)}" alt="">` : "<span></span>"}
            <strong>${escapeHtml(run.title || "Peça")}</strong>
            <small>${run.version_count || 0} versões${run.aspect_ratio ? ` ${escapeHtml(run.aspect_ratio)}` : ""}</small>
          </a>`;
        li.querySelector("img")?.addEventListener("error", (event) => {
          event.target.replaceWith(document.createElement("span"));
        });
        takes.appendChild(li);
      });
    } catch (_error) {
      if (empty) {
        empty.hidden = false;
        empty.innerHTML = "<p>Não deu para abrir o histórico desta marca.</p><p>Tente de novo ou abra Ajustar.</p>";
      }
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

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
