(function () {
  var root = document.getElementById("sp-start");
  if (!root) return;

  var state = {
    cliente: "",
    cliente_id: null,
    agencia: "",
    agencia_id: null,
  };
  var timers = {};

  function toast(message, type) {
    if (typeof window.showToast === "function") {
      window.showToast(message, type || "info");
      return;
    }
    window.alert(message);
  }

  function partyInput(kind) {
    return root.querySelector('.sp-party[data-kind="' + kind + '"] .js-sp-party');
  }

  function suggestList(kind) {
    return root.querySelector('.sp-party[data-kind="' + kind + '"] .sp-suggest');
  }

  function hideSuggest(kind) {
    var list = suggestList(kind);
    if (!list) return;
    list.hidden = true;
    list.innerHTML = "";
  }

  function renderBrand(brand) {
    var chip = document.getElementById("sp-brand-chip");
    if (!chip) return;
    if (!brand || !brand.name) {
      chip.hidden = true;
      chip.innerHTML = "";
      return;
    }
    var note = brand.has_identity
      ? "Identidade na Modelagem — público, produto e tom entram no quadro."
      : "Marca na Modelagem, ainda sem identidade completa.";
    var logo = brand.logo_url
      ? '<img class="sp-brand-logo" src="' +
        escapeHtml(brand.logo_url) +
        '" alt="" width="28" height="28">'
      : "";
    chip.hidden = false;
    chip.innerHTML =
      logo +
      "<strong>" +
      escapeHtml(brand.name) +
      "</strong><span>" +
      escapeHtml(note) +
      "</span>";
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function initials(name) {
    var parts = String(name || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }

  function suggestMark(row) {
    if (row.logo_url) {
      return (
        '<span class="sp-suggest-mark">' +
        '<img src="' +
        escapeHtml(row.logo_url) +
        '" alt="" width="28" height="28" onerror="this.hidden=true; if(this.nextElementSibling) this.nextElementSibling.hidden=false">' +
        '<span hidden>' +
        escapeHtml(initials(row.name)) +
        "</span>" +
        "</span>"
      );
    }
    return '<span class="sp-suggest-mark"><span>' + escapeHtml(initials(row.name)) + "</span></span>";
  }

  function renderSuggest(kind, rows) {
    var list = suggestList(kind);
    if (!list) return;
    if (!rows.length) {
      hideSuggest(kind);
      return;
    }
    list.innerHTML = rows
      .map(function (row) {
        return (
          '<li><button type="button" data-id="' +
          escapeHtml(row.id) +
          '" data-name="' +
          escapeHtml(row.name) +
          '">' +
          suggestMark(row) +
          "<span>" +
          escapeHtml(row.name) +
          "</span></button></li>"
        );
      })
      .join("");
    list.hidden = false;
  }

  async function loadMarca(clienteId) {
    if (!clienteId) {
      renderBrand(null);
      return;
    }
    var response = await fetch("/smart-planner/api/marca?cliente_id=" + encodeURIComponent(clienteId), {
      credentials: "same-origin",
    });
    var payload = await response.json();
    if (!payload.success) return;
    var data = payload.data || {};
    renderBrand(data.brand);
    var agency = data.agency || {};
    if (agency.name && !state.agencia_id) {
      state.agencia = agency.name;
      state.agencia_id = agency.id || null;
      var input = partyInput("agencia");
      if (input) input.value = agency.name;
    }
  }

  async function searchParties(kind, query) {
    var response = await fetch(
      "/smart-planner/api/partes?kind=" +
        encodeURIComponent(kind) +
        "&q=" +
        encodeURIComponent(query || ""),
      { credentials: "same-origin" }
    );
    var payload = await response.json();
    renderSuggest(kind, ((payload.data || {}).rows) || []);
  }

  function selectParty(kind, id, name) {
    state[kind] = name;
    state[kind + "_id"] = id || null;
    var input = partyInput(kind);
    if (input) input.value = name;
    hideSuggest(kind);
    if (kind === "cliente") {
      loadMarca(id).catch(function () {
        renderBrand(null);
      });
    }
  }

  root.querySelectorAll(".js-sp-party").forEach(function (input) {
    var kind = input.closest(".sp-party").getAttribute("data-kind");
    input.addEventListener("focus", function () {
      searchParties(kind, input.value).catch(function () {
        hideSuggest(kind);
      });
    });
    input.addEventListener("input", function () {
      state[kind] = input.value.trim();
      state[kind + "_id"] = null;
      if (kind === "cliente" && !state.cliente_id) renderBrand(null);
      clearTimeout(timers[kind]);
      timers[kind] = window.setTimeout(function () {
        searchParties(kind, input.value).catch(function () {
          hideSuggest(kind);
        });
      }, 180);
    });
    input.addEventListener("blur", function () {
      window.setTimeout(function () {
        hideSuggest(kind);
      }, 180);
    });
  });

  root.querySelectorAll(".sp-suggest").forEach(function (list) {
    list.addEventListener("mousedown", function (event) {
      var button = event.target.closest("button");
      if (!button) return;
      event.preventDefault();
      var kind = list.closest(".sp-party").getAttribute("data-kind");
      selectParty(kind, button.getAttribute("data-id"), button.getAttribute("data-name"));
    });
  });

  // A marca pode iniciar o Planner pelo Workspace. Nesse caso o anunciante
  // já chega identificado, mas a pessoa ainda escolhe livremente o formato
  // e revisa o briefing antes de qualquer geração.
  var workspaceClientId = root.dataset.seedClientId || "";
  var workspaceClientName = root.dataset.seedClientName || "";
  var workspaceProjectId = root.dataset.seedProjectId || "";
  if (workspaceClientId && workspaceClientName) {
    selectParty("cliente", workspaceClientId, workspaceClientName);
  }

  document.querySelectorAll(".js-sp-start").forEach(function (button) {
    button.addEventListener("click", async function () {
      var cliente = (partyInput("cliente") && partyInput("cliente").value.trim()) || state.cliente;
      var agencia = (partyInput("agencia") && partyInput("agencia").value.trim()) || state.agencia;
      if (!cliente && !state.cliente_id) {
        toast("Informe o anunciante.", "error");
        var focus = partyInput("cliente");
        if (focus) focus.focus();
        return;
      }
      var mode = button.getAttribute("data-mode");
      button.disabled = true;
      try {
        var response = await fetch("/smart-planner/api/criar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            plan_mode: mode,
            cliente: cliente,
            cliente_id: state.cliente_id,
            agencia: agencia,
            agencia_id: state.agencia_id,
            workspace_project_id: workspaceProjectId || null,
            anunciante_confidencial: Boolean(document.getElementById("sp-start-confidential") && document.getElementById("sp-start-confidential").checked),
          }),
        });
        var payload = await response.json();
        if (!payload.success) throw new Error(payload.error || "Não foi possível criar o plano");
        window.location.href = payload.data.redirect;
      } catch (error) {
        toast(error.message, "error");
        button.disabled = false;
      }
    });
  });
})();
