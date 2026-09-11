(function () {
  function toast(message, type) {
    if (typeof window.showToast === "function") {
      window.showToast(message, type || "info");
      return;
    }
    window.alert(message);
  }

  function showEmpty() {
    var list = document.getElementById("sp-history");
    if (!list || list.querySelector("li")) return;
    list.insertAdjacentHTML(
      "afterend",
      '<div class="sp-empty" id="sp-empty"><h2>Nenhuma campanha neste usuário</h2>' +
        "<p>Comece pelo briefing. O CentralX monta a página única ou o plano completo no quadro.</p>" +
        '<a class="cx-btn cx-btn-primary" href="/smart-planner/novo">Nova campanha</a></div>'
    );
    list.remove();
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
        var row = button.closest("li") || button.closest("tr");
        if (row) row.remove();
        showEmpty();
      })
      .catch(function (error) {
        toast(error.message, "error");
        button.disabled = false;
      });
  }

  document.querySelectorAll(".js-sp-delete").forEach(function (button) {
    button.addEventListener("click", function () {
      if (typeof window.showConfirm === "function") {
        window.showConfirm({
          title: "Excluir planejamento",
          message: "Este planejamento será removido.",
          theme: "danger",
          confirmText: "Excluir",
          onConfirm: function () {
            excludePlan(button);
          },
        });
        return;
      }
      if (window.confirm("Excluir este planejamento?")) excludePlan(button);
    });
  });
})();
