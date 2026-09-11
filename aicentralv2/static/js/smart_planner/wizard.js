(function () {
  var root = document.getElementById("sp-wizard");
  if (!root) return;
  var token = root.getAttribute("data-token");
  var step = root.getAttribute("data-step");

  function toast(message, type) {
    if (typeof window.showToast === "function") {
      window.showToast(message, type || "info");
      return;
    }
    window.alert(message);
  }

  function setLoading(button, loading) {
    if (!button) return;
    button.disabled = loading;
    button.classList.toggle("is-loading", loading);
  }

  async function postJson(url, body) {
    var response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(body || {}),
    });
    var payload = await response.json();
    if (!payload.success) throw new Error(payload.error || "Falha na requisição");
    return payload.data || {};
  }

  var briefingForm = document.getElementById("sp-briefing-form");
  if (briefingForm) {
    briefingForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      var button = document.getElementById("sp-process-btn");
      setLoading(button, true);
      try {
        var form = new FormData(briefingForm);
        var file = form.get("file");
        var hasFile = file && file.size;
        var response;
        if (hasFile) {
          response = await fetch("/smart-planner/api/" + token + "/processar", {
            method: "POST",
            credentials: "same-origin",
            body: form,
          });
        } else {
          response = await fetch("/smart-planner/api/" + token + "/processar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({
              text: form.get("text") || "",
              url: form.get("url") || "",
            }),
          });
        }
        var payload = await response.json();
        if (!payload.success) throw new Error(payload.error || "Falha ao processar");
        window.location.href = payload.data.redirect;
      } catch (error) {
        toast(error.message, "error");
        setLoading(button, false);
      }
    });
  }

  var revisaoForm = document.getElementById("sp-revisao-form");
  if (revisaoForm) {
    revisaoForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      var button = revisaoForm.querySelector("button[type=submit]");
      setLoading(button, true);
      var data = new FormData(revisaoForm);
      try {
        var result = await postJson("/smart-planner/api/" + token + "/revisao", {
          briefing: data.get("briefing"),
          campos: {
            campanha: data.get("campanha"),
            cliente: data.get("cliente"),
            agencia: data.get("agencia"),
            objetivo: data.get("objetivo"),
            objetivo_texto: data.get("objetivo_texto"),
            publico: data.get("publico"),
            verba: data.get("verba"),
            periodo: data.get("periodo"),
            contexto: data.get("contexto"),
            observacoes: data.get("observacoes"),
          },
        });
        window.location.href = result.redirect;
      } catch (error) {
        toast(error.message, "error");
        setLoading(button, false);
      }
    });
  }

  var canaisForm = document.getElementById("sp-canais-form");
  if (canaisForm) {
    canaisForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      var button = canaisForm.querySelector("button[type=submit]");
      setLoading(button, true);
      var data = new FormData(canaisForm);
      try {
        var result = await postJson("/smart-planner/api/" + token + "/canais", {
          verba: data.get("verba"),
          periodo: data.get("periodo"),
          praca: data.get("praca"),
          praca_detalhe: data.get("praca_detalhe"),
          canais: data.getAll("canais"),
          dispositivos: data.getAll("dispositivos"),
        });
        window.location.href = result.redirect;
      } catch (error) {
        toast(error.message, "error");
        setLoading(button, false);
      }
    });
  }

  var generateBtn = document.getElementById("sp-generate-btn");
  if (generateBtn && step === "gerar") {
    async function runGenerate() {
      if (generateBtn.disabled) return;
      setLoading(generateBtn, true);
      var items = document.querySelectorAll("#sp-generate-status li");
      items.forEach(function (item, index) {
        window.setTimeout(function () {
          item.classList.add("is-on");
        }, 400 * index);
      });
      try {
        var result = await postJson("/smart-planner/api/" + token + "/gerar", {});
        window.location.href = result.redirect;
      } catch (error) {
        toast(error.message, "error");
        setLoading(generateBtn, false);
      }
    }
    generateBtn.addEventListener("click", runGenerate);
    runGenerate();
  }
})();
