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
    chip.hidden = false;
    chip.innerHTML =
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
    var list = suggestList(kind);
    if (!list) return;
    if (query.trim().length < 2) {
      hideSuggest(kind);
      return;
    }
    var response = await fetch(
      "/smart-planner/api/partes?kind=" + encodeURIComponent(kind) + "&q=" + encodeURIComponent(query),
      { credentials: "same-origin" }
    );
    var payload = await response.json();
    var rows = ((payload.data || {}).rows) || [];
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
          escapeHtml(row.name) +
          "</button></li>"
        );
      })
      .join("");
    list.hidden = false;
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
    input.addEventListener("input", function () {
      state[kind] = input.value.trim();
      state[kind + "_id"] = null;
      if (kind === "cliente" && !state.cliente_id) renderBrand(null);
      clearTimeout(timers[kind]);
      timers[kind] = window.setTimeout(function () {
        searchParties(kind, input.value).catch(function () {
          hideSuggest(kind);
        });
      }, 250);
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
