(function () {
  function toast(message, type) {
    if (typeof window.showToast === "function") {
      window.showToast(message, type || "info");
      return;
    }
    window.alert(message);
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
      .then(function (response) { return response.json(); })
      .then(function (payload) {
        if (!payload.success) throw new Error(payload.error || "Falha ao excluir");
        toast("Planejamento excluído.", "success");
        var row = button.closest("tr");
        if (row) row.remove();
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
          onConfirm: function () { excludePlan(button); },
        });
        return;
      }
      if (window.confirm("Excluir este planejamento?")) excludePlan(button);
    });
  });
})();
