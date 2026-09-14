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
  const clips = document.getElementById("mcCaduClips");
  const clipsEmpty = document.getElementById("mcCaduClipsEmpty");
  if (!takes) return;

  const barSelect = document.getElementById("mcCaduBarClient");
  const homeSelect = document.getElementById("mcCaduHomeClient");

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  function boot() {
    const syncBrand = (event) => {
      const id = event.detail?.clientId || Desk.read();
      if (homeSelect && id) homeSelect.value = id;
      if (id) {
        loadWall(id);
        loadClips(id);
      }
    };
    document.addEventListener("cadu:brand-ready", syncBrand);
    document.addEventListener("cadu:brand-change", syncBrand);
    if (homeSelect && !barSelect) {
      loadHomeSelect();
    } else {
      const chosen = Desk.read();
      if (chosen) {
        loadWall(chosen);
        loadClips(chosen);
      }
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
      loadClips(homeSelect.value);
    });
    await loadWall(homeSelect.value);
    await loadClips(homeSelect.value);
  }

  async function loadWall(clientId) {
    paintLibrary(takes, empty, [], {
      empty: "<p>Ainda não há peça nesta marca.</p><p>Abra Ajustar e solte o criativo. O histórico aparece aqui.</p>",
      href: (item) => `/parametros/modelagem-criativos/trocar?run=${encodeURIComponent(item.run_id || "")}&client=${encodeURIComponent(clientId)}`,
      error: "<p>Não deu para abrir o histórico desta marca.</p><p>Tente de novo ou abra Ajustar.</p>",
    });
    if (!clientId) return;
    try {
      const data = await get(`/parametros/api/format-lab/swap/library?client_id=${encodeURIComponent(clientId)}&media=still`);
      paintLibrary(takes, empty, data.items || [], {
        empty: "<p>Ainda não há peça nesta marca.</p><p>Abra Ajustar e solte o criativo. O histórico aparece aqui.</p>",
        href: (item) => `/parametros/modelagem-criativos/trocar?run=${encodeURIComponent(item.run_id || "")}&client=${encodeURIComponent(clientId)}`,
        error: "",
      });
    } catch (_error) {
      if (empty) {
        empty.hidden = false;
        empty.innerHTML = "<p>Não deu para abrir o histórico desta marca.</p><p>Tente de novo ou abra Ajustar.</p>";
      }
    }
  }

  async function loadClips(clientId) {
    if (!clips) return;
    paintLibrary(clips, clipsEmpty, [], {
      empty: "<p>Ainda não há clipe nesta marca.</p><p>Abra Vídeo, escolha pelo menos duas cenas e gere.</p>",
      href: () => "/parametros/modelagem-criativos/video",
    });
    if (!clientId) return;
    try {
      const data = await get(`/parametros/api/format-lab/swap/library?client_id=${encodeURIComponent(clientId)}&media=video`);
      paintLibrary(clips, clipsEmpty, data.items || [], {
        empty: "<p>Ainda não há clipe nesta marca.</p><p>Abra Vídeo, escolha pelo menos duas cenas e gere.</p>",
        href: (item) => `/parametros/modelagem-criativos/video?run=${encodeURIComponent(item.run_id || "")}&clip=${encodeURIComponent(item.id || "")}&client=${encodeURIComponent(clientId)}`,
      });
    } catch (_error) {
      if (clipsEmpty) {
        clipsEmpty.hidden = false;
        clipsEmpty.innerHTML = "<p>Não deu para abrir os clipes desta marca.</p><p>Tente de novo ou abra Vídeo.</p>";
      }
    }
  }

  function paintLibrary(list, emptyNode, items, copy) {
    if (!list) return;
    list.querySelectorAll("[data-run]").forEach((node) => node.remove());
    if (emptyNode) {
      emptyNode.hidden = false;
      emptyNode.innerHTML = copy.empty;
    }
    if (!items.length) return;
    if (emptyNode) emptyNode.hidden = true;
    items.slice(0, 12).forEach((item) => {
      const href = copy.href(item);
      const ratio = String(item.aspect_ratio || "4:5").replace(":", "/");
      const li = document.createElement("li");
      li.setAttribute("data-run", item.run_id || item.id || "");
      li.setAttribute("data-ratio", ratio);
      li.style.setProperty("--take-ratio", ratio);
      const thumb = item.thumb_url || item.poster_url || item.image_url;
      li.innerHTML = `
        <a href="${href}">
          ${thumb ? `<img src="${escapeHtml(thumb)}" alt="">` : "<span></span>"}
          <strong>${escapeHtml(item.name || item.title || "Peça")}</strong>
          <small>${escapeHtml(item.aspect_ratio || "")}</small>
        </a>`;
      li.querySelector("img")?.addEventListener("error", (event) => {
        event.target.replaceWith(document.createElement("span"));
      });
      list.appendChild(li);
    });
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
