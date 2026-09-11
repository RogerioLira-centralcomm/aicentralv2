(function () {
  function toast(message, type) {
    if (typeof window.showToast === "function") {
      window.showToast(message, type || "info");
      return;
    }
    window.alert(message);
  }

  document.querySelectorAll(".js-sp-start").forEach(function (button) {
    button.addEventListener("click", async function () {
      var mode = button.getAttribute("data-mode");
      button.disabled = true;
      try {
        var response = await fetch("/smart-planner/api/criar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ plan_mode: mode }),
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
