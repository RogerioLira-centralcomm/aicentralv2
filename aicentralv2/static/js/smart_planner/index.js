(function () {
  var table = document.getElementById("sp-history");
  var wrap = document.getElementById("sp-history-wrap");
  var bar = document.getElementById("sp-book-bar");
  var empty = document.getElementById("sp-empty");
  var filterEmpty = document.getElementById("sp-filter-empty");
  var summary = document.getElementById("sp-history-summary");
  var search = document.getElementById("sp-filter-q");
  var clientFilter = document.getElementById("sp-filter-cliente");
  var agencyFilter = document.getElementById("sp-filter-agencia");
  var responsibleFilter = document.getElementById("sp-filter-responsavel");
  var statusFilter = document.getElementById("sp-filter-status");
  var modeButtons = document.querySelectorAll(".sp-mode-switch button");
  var activeMode = "";
  var originalSummary = summary ? summary.textContent.trim() : "";

  function toast(message, type) {
    if (typeof window.showToast === "function") {
      window.showToast(message, type || "info");
      return;
    }
    var node = document.querySelector(".sp-inline-toast");
    if (!node) {
      node = document.createElement("div");
      node.className = "sp-inline-toast";
      node.setAttribute("role", "status");
      document.body.appendChild(node);
    }
    node.textContent = message;
    node.dataset.type = type || "info";
    node.classList.add("is-visible");
    window.clearTimeout(node._hideTimer);
    node._hideTimer = window.setTimeout(function () { node.classList.remove("is-visible"); }, 4200);
  }

  function confirmDelete(onConfirm) {
    if (typeof window.showConfirm === "function") {
      window.showConfirm({
        title: "Excluir planejamento",
        message: "Este planejamento será removido.",
        theme: "danger",
        confirmText: "Excluir",
        onConfirm: onConfirm,
      });
      return;
    }
    var dialog = document.createElement("dialog");
    dialog.className = "sp-inline-confirm";
    dialog.innerHTML = '<form method="dialog"><h2>Excluir planejamento?</h2><p>Este planejamento será removido.</p><div><button value="cancel" class="cx-btn cx-btn-secondary cx-btn-sm">Cancelar</button><button value="confirm" class="cx-btn cx-btn-danger cx-btn-sm">Excluir</button></div></form>';
    document.body.appendChild(dialog);
    dialog.addEventListener("close", function () {
      if (dialog.returnValue === "confirm") onConfirm();
      dialog.remove();
    }, { once: true });
    dialog.showModal();
  }

  function rows() {
    return table ? Array.prototype.slice.call(table.querySelectorAll("[data-sp-history-row]")) : [];
  }

  function fillSelect(select, values, allLabel, emptyValue, emptyLabel) {
    if (!select) return;
    var current = select.value;
    select.innerHTML = "";
    var all = document.createElement("option");
    all.value = "";
    all.textContent = allLabel;
    select.appendChild(all);
    if (values.some(function (value) { return !value; })) {
      var none = document.createElement("option");
      none.value = emptyValue;
      none.textContent = emptyLabel;
      select.appendChild(none);
    }
    values
      .filter(Boolean)
      .sort(function (a, b) { return a.localeCompare(b, "pt-BR"); })
      .forEach(function (value) {
        var option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      });
    if (Array.prototype.some.call(select.options, function (option) { return option.value === current; })) {
      select.value = current;
    }
  }

  function uniqueAttr(name) {
    var seen = {};
    return rows().map(function (row) {
      return (row.getAttribute(name) || "").trim();
    }).filter(function (value) {
      if (seen[value]) return false;
      seen[value] = true;
      return true;
    });
  }

  function hydrateFilters() {
    fillSelect(clientFilter, uniqueAttr("data-cliente"), "Todos os clientes", "__none__", "Sem cliente");
    fillSelect(agencyFilter, uniqueAttr("data-agencia"), "Todas as agências", "__none__", "Sem agência");
    fillSelect(responsibleFilter, uniqueAttr("data-responsavel"), "Todos os responsáveis", "__none__", "Não atribuído");
    fillSelect(statusFilter, uniqueAttr("data-status"), "Todos os status", "__none__", "Sem status");
  }

  function matches(row) {
    var query = ((search && search.value) || "").trim().toLowerCase();
    var hay = (row.getAttribute("data-search") || "").toLowerCase();
    if (query && hay.indexOf(query) === -1) return false;
    if (activeMode && (row.getAttribute("data-documents") || "").split(/\s+/).indexOf(activeMode) === -1) return false;
    var cliente = (row.getAttribute("data-cliente") || "").trim();
    var agencia = (row.getAttribute("data-agencia") || "").trim();
    var responsavel = (row.getAttribute("data-responsavel") || "").trim();
    var status = (row.getAttribute("data-status") || "").trim();
    if (clientFilter && clientFilter.value === "__none__" && cliente) return false;
    if (clientFilter && clientFilter.value && clientFilter.value !== "__none__" && cliente !== clientFilter.value) return false;
    if (agencyFilter && agencyFilter.value === "__none__" && agencia) return false;
    if (agencyFilter && agencyFilter.value && agencyFilter.value !== "__none__" && agencia !== agencyFilter.value) return false;
    if (responsibleFilter && responsibleFilter.value === "__none__" && responsavel) return false;
    if (responsibleFilter && responsibleFilter.value && responsibleFilter.value !== "__none__" && responsavel !== responsibleFilter.value) return false;
    if (statusFilter && statusFilter.value === "__none__" && status) return false;
    if (statusFilter && statusFilter.value && statusFilter.value !== "__none__" && status !== statusFilter.value) return false;
    return true;
  }

  function updateSummary(visible, total) {
    if (!summary || !total) return;
    var label = visible === 1 ? "campanha" : "campanhas";
    if (visible === total) {
      summary.textContent = originalSummary || (total + " " + label + " neste usuário.");
      return;
    }
    summary.textContent = visible + " de " + total + " " + (total === 1 ? "campanha" : "campanhas") + " neste recorte.";
  }

  function applyFilters() {
    var all = rows();
    var visible = 0;
    all.forEach(function (row) {
      var show = matches(row);
      row.hidden = !show;
      if (show) visible += 1;
    });
    var hasRows = all.length > 0;
    if (wrap) wrap.hidden = !hasRows || visible === 0;
    if (bar) bar.hidden = !hasRows;
    if (empty) empty.hidden = hasRows;
    if (filterEmpty) filterEmpty.hidden = !hasRows || visible > 0;
    updateSummary(visible, all.length);
  }

  function clearFilters() {
    activeMode = "";
    if (search) search.value = "";
    if (clientFilter) clientFilter.value = "";
    if (agencyFilter) agencyFilter.value = "";
    if (responsibleFilter) responsibleFilter.value = "";
    if (statusFilter) statusFilter.value = "";
    modeButtons.forEach(function (button) {
      var on = !button.getAttribute("data-mode");
      button.classList.toggle("is-on", on);
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
    applyFilters();
    if (search) search.focus();
  }

  function excludePlan(button) {
    var id = button.getAttribute("data-id");
    if (!id) return;
    button.disabled = true;
    fetch("/smart-planner/api/" + id + "/excluir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (payload) {
        if (!payload.success) throw new Error(payload.error || "Falha ao excluir");
        toast("Planejamento excluído.", "success");
        var row = button.closest("[data-sp-history-row]");
        if (row) row.remove();
        hydrateFilters();
        applyFilters();
      })
      .catch(function (error) {
        toast(error.message, "error");
        button.disabled = false;
      });
  }

  if (search) search.addEventListener("input", applyFilters);
  if (clientFilter) clientFilter.addEventListener("change", applyFilters);
  if (agencyFilter) agencyFilter.addEventListener("change", applyFilters);
  if (responsibleFilter) responsibleFilter.addEventListener("change", applyFilters);
  if (statusFilter) statusFilter.addEventListener("change", applyFilters);
  modeButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      activeMode = button.getAttribute("data-mode") || "";
      modeButtons.forEach(function (item) {
        var on = item === button;
        item.classList.toggle("is-on", on);
        item.setAttribute("aria-pressed", on ? "true" : "false");
      });
      applyFilters();
    });
  });
  var clear = document.getElementById("sp-clear-filters");
  if (clear) clear.addEventListener("click", clearFilters);

  document.querySelectorAll(".js-sp-delete").forEach(function (button) {
    button.addEventListener("click", function () {
      confirmDelete(function () { excludePlan(button); });
    });
  });

  hydrateFilters();
})();
