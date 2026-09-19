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
    var node = document.createElement("div");
    node.className = "sp-inline-toast" + (type ? " is-" + type : "");
    node.setAttribute("role", "status");
    node.textContent = message;
    document.body.appendChild(node);
    window.setTimeout(function () {
      node.classList.add("is-out");
      window.setTimeout(function () { node.remove(); }, 220);
    }, 3600);
  }

  function askConfirmation(message, title) {
    var dialog = document.getElementById("sp-confirm");
    if (!dialog || typeof dialog.showModal !== "function") return Promise.resolve(false);
    var messageEl = document.getElementById("sp-confirm-message");
    var titleEl = document.getElementById("sp-confirm-title");
    if (messageEl) messageEl.textContent = message || "Confirme esta ação.";
    if (titleEl) titleEl.textContent = title || "Confirmar ação";
    dialog.returnValue = "";
    return new Promise(function (resolve) {
      dialog.addEventListener("close", function handleClose() {
        resolve(dialog.returnValue === "confirm");
      }, { once: true });
      dialog.showModal();
      var accept = document.getElementById("sp-confirm-accept");
      if (accept) window.setTimeout(function () { accept.focus(); }, 20);
    });
  }

  function setLoading(button, loading) {
    if (!button) return;
    button.disabled = loading;
    button.classList.toggle("is-loading", loading);
  }

  function setStatus(el, message, type) {
    if (!el) return;
    el.hidden = !message;
    el.textContent = message || "";
    el.className = "sp-status" + (type ? " is-" + type : "");
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

  var BRIEF_STEPS = [
    { id: "read", title: "Leitura do briefing", copy: "Contexto, objetivo e restrições" },
    { id: "extract", title: "Campos e sinais", copy: "Dados confirmados e pontos de atenção" },
    { id: "narrative", title: "Síntese para revisão", copy: "Uma estrutura clara para a conversa comercial" },
    { id: "save", title: "Revisão pronta", copy: "Salvando o material para você conferir" },
  ];

  function generationWaitSteps(mode) {
    var node = document.getElementById("sp-wait-gen-steps");
    if (!node || !node.textContent) return [];
    try {
      var catalog = JSON.parse(node.textContent) || {};
      return catalog[mode] || catalog.one_page || [];
    } catch (error) {
      return [];
    }
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, function (ch) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch];
    });
  }

  function readJson(id, fallback) {
    var node = document.getElementById(id);
    if (!node || !node.textContent) return fallback;
    try {
      return JSON.parse(node.textContent) || fallback;
    } catch (error) {
      return fallback;
    }
  }

  function portalSelected(canais) {
    var portals = ((readJson("sp-mix-spec", {}).portalChannels) || ["g1", "uol", "r7", "cnn"]);
    return (canais || []).some(function (key) { return portals.indexOf(key) !== -1; });
  }

  function collectPlaces() {
    var channel = document.querySelector('#sp-mix-channels input[name="canais"][value="places"]');
    if (channel && !channel.checked) return [];
    var catalog = readJson("sp-places-catalog", []);
    var out = [];
    catalog.forEach(function (place) {
      var box = document.querySelector('input[name="places"][value="' + place.slug + '"]');
      if (!box || !box.checked) return;
      out.push({ slug: place.slug, title: place.title, point_ids: [], apps: [] });
    });
    return out;
  }

  function collectInterativos() {
    var channel = document.querySelector('#sp-mix-channels input[name="canais"][value="interativos"]');
    if (channel && !channel.checked) return { formats: [] };
    return {
      formats: Array.prototype.slice.call(document.querySelectorAll('input[name="interativos_formats"]:checked')).map(function (el) {
        return el.value;
      }),
    };
  }

  function setWaitMeta(eyebrow, title, copy) {
    var eye = document.getElementById("sp-wait-eyebrow");
    var heading = document.getElementById("sp-wait-title");
    var stepEl = document.getElementById("sp-compile-step");
    if (eye) eye.textContent = eyebrow;
    if (heading) heading.textContent = title;
    if (stepEl && copy) stepEl.textContent = copy;
  }

  function setWaitProgress(done, total) {
    var frac = document.getElementById("sp-wait-frac");
    var bar = document.getElementById("sp-compile-bar");
    var safeTotal = Math.max(1, Number(total) || 1);
    var safeDone = Math.max(0, Math.min(safeTotal, Number(done) || 0));
    if (frac) frac.textContent = safeDone + " de " + safeTotal;
    if (bar) bar.style.width = Math.max(8, Math.round((safeDone / safeTotal) * 100)) + "%";
  }

  function renderWaitSteps(steps, currentId) {
    var list = document.getElementById("sp-compile-skills");
    if (!list) return;
    if (!steps || !steps.length) {
      list.innerHTML = "";
      return;
    }
    var pivot = steps.findIndex(function (row) { return row.id && row.id === currentId; });
    var visibleIndexes = steps.map(function (_item, index) { return index; });
    if (steps.length > 6) {
      var runningIndex = pivot >= 0 ? pivot : 0;
      var doneIndexes = steps.map(function (item, index) { return item.state === "done" ? index : -1; }).filter(function (index) { return index >= 0; });
      visibleIndexes = doneIndexes.slice(-2).concat([runningIndex]).filter(function (index, position, values) {
        return index >= 0 && values.indexOf(index) === position;
      }).sort(function (a, b) { return a - b; });
    }
    list.innerHTML = visibleIndexes.map(function (index) {
      var item = steps[index];
      var state = item.state;
      if (!state) {
        if (pivot >= 0) state = index < pivot ? "done" : index === pivot ? "running" : "pending";
        else state = "pending";
      }
      var cls = state === "running" ? "is-run" : state === "done" ? "is-done" : state === "error" ? "is-error" : state === "skipped" ? "is-skip" : "";
      var title = item.title || item.label || item.skill || "";
      var copy = item.copy || "";
      if (copy && copy === title) copy = "";
      return "<li class=\"" + cls + "\">" +
        "<span class=\"sp-wait-dot\" aria-hidden=\"true\"></span>" +
        "<div><strong>" + escapeHtml(title) + "</strong>" +
        (copy ? "<span>" + escapeHtml(copy) + "</span>" : "") + "</div></li>";
    }).join("") + (steps.length > visibleIndexes.length
      ? "<li class=\"sp-wait-more\"><span aria-hidden=\"true\">·</span><div>" + (steps.length - visibleIndexes.length) + " etapas serão concluídas em seguida.</div></li>"
      : "");
    var done = steps.filter(function (item) { return item.state === "done"; }).length;
    var running = steps.some(function (item) { return item.state === "running"; });
    var current = pivot >= 0 ? pivot + 1 : (running ? done + 1 : Math.max(done, steps.length && done === steps.length ? steps.length : 1));
    if (done === steps.length) current = steps.length;
    setWaitProgress(current, steps.length);
  }

  function applyGenerationProgress(data) {
    var mode = (data.mode || root.getAttribute("data-mode") || "").toLowerCase();
    var steps = data.steps && data.steps.length ? data.steps : generationWaitSteps(mode);
    setWaitMeta(
      "Gerando",
      mode === "one_page" ? "Construindo a página única" : "Construindo o planejamento",
      data.title || "Redigindo a recomendação de mídia."
    );
    renderWaitSteps(steps, data.step);
    if (data.total) {
      var current = Number(data.index || 0) + (data.status === "done" ? 1 : 1);
      if (data.status === "done") current = Number(data.total);
      else current = Math.min(Number(data.total), Number(data.index || 0) + 1);
      setWaitProgress(current, data.total);
    }
    if (data.percent) {
      var bar = document.getElementById("sp-compile-bar");
      if (bar) bar.style.width = Math.max(8, Number(data.percent) || 8) + "%";
    }
  }

  function waitForGeneration(mode) {
    return new Promise(function (resolve, reject) {
      var started = Date.now();
      var misses = 0;
      var timer = window.setInterval(function () {
        fetch("/smart-planner/api/" + token + "/gerar/status?mode=" + encodeURIComponent(mode || ""), {
          credentials: "same-origin"
        }).then(function (response) { return response.json(); }).then(function (payload) {
          if (!payload || !payload.success) {
            misses += 1;
            if (misses >= 8) {
              window.clearInterval(timer);
              reject(new Error("Não foi possível acompanhar o progresso da geração."));
            }
            return;
          }
          misses = 0;
          var data = payload.data || {};
          applyGenerationProgress(data);
          if (data.status === "done") {
            window.clearInterval(timer);
            resolve(data);
          } else if (data.status === "error") {
            window.clearInterval(timer);
            reject(new Error(data.error || "Não foi possível gerar o planejamento."));
          } else if (Date.now() - started > 12 * 60 * 1000) {
            window.clearInterval(timer);
            reject(new Error("A geração está demorando demais. Tente de novo."));
          }
        }).catch(function () {
          misses += 1;
          if (misses >= 8) {
            window.clearInterval(timer);
            reject(new Error("A conexão caiu enquanto o plano era gerado."));
          }
        });
      }, 900);
    });
  }

  function waitForBriefing() {
    return new Promise(function (resolve, reject) {
      var started = Date.now();
      var misses = 0;
      var timer = window.setInterval(function () {
        fetch("/smart-planner/api/" + token + "/processar/status", { credentials: "same-origin" })
          .then(function (response) { return response.json(); })
          .then(function (payload) {
            if (!payload || !payload.success) {
              misses += 1;
              if (misses >= 8) { window.clearInterval(timer); reject(new Error("Não foi possível acompanhar o processamento do briefing.")); }
              return;
            }
            misses = 0;
            var data = payload.data || {};
            var index = Math.max(0, Number(data.index) || 0);
            var steps = BRIEF_STEPS.map(function (item, stepIndex) {
              return { id: item.id, title: item.title, copy: item.copy, state: stepIndex < index ? "done" : stepIndex === index ? "running" : "pending" };
            });
            if (data.status === "done") steps = steps.map(function (item) { return { id: item.id, title: item.title, copy: item.copy, state: "done" }; });
            setWaitMeta("Processando", data.status === "done" ? "Revisão pronta" : "Analisando o briefing", data.title || "Organizando contexto, dados e pontos de atenção.");
            renderWaitSteps(steps, data.step);
            setWaitProgress(data.status === "done" ? BRIEF_STEPS.length : index + 1, BRIEF_STEPS.length);
            if (data.status === "done") { window.clearInterval(timer); resolve(data); }
            else if (data.status === "error") { window.clearInterval(timer); reject(new Error(data.error || "Não foi possível processar o briefing.")); }
            else if (Date.now() - started > 12 * 60 * 1000) { window.clearInterval(timer); reject(new Error("O processamento está demorando demais. Tente novamente.")); }
          }).catch(function () {
            misses += 1;
            if (misses >= 8) { window.clearInterval(timer); reject(new Error("A conexão caiu enquanto o briefing era processado.")); }
          });
      }, 900);
    });
  }

  function showCompileOverlay(inputText, mode) {
    var overlay = document.getElementById("sp-compile-overlay");
    var dismiss = document.getElementById("sp-wait-dismiss");
    if (!overlay) return function () {};
    overlay.hidden = false;
    overlay.classList.add("is-open");
    overlay.classList.remove("is-error");
    if (dismiss) dismiss.hidden = true;
    document.body.classList.add("is-sp-wait");
    if (mode) {
      setWaitMeta(
        "Gerando",
        mode === "one_page" ? "Construindo a página única" : "Construindo o planejamento",
        "Preparando a recomendação de mídia."
      );
      var planned = generationWaitSteps(mode);
      renderWaitSteps(planned.map(function (item, index) {
        return { id: item.id, title: item.title, state: index === 0 ? "running" : "pending" };
      }), (planned[0] || {}).id);
      fetch("/smart-planner/api/" + token + "/gerar/status?mode=" + encodeURIComponent(mode), {
        credentials: "same-origin"
      }).then(function (response) { return response.json(); }).then(function (payload) {
        if (payload && payload.success) applyGenerationProgress(payload.data || {});
      }).catch(function () {});
      return function () {};
    }
    setWaitMeta("Processando", "Analisando o briefing", "Organizando contexto, dados e pontos de atenção.");
    renderWaitSteps(BRIEF_STEPS.map(function (item, index) {
      return { id: item.id, title: item.title, copy: item.copy, state: index === 0 ? "running" : "pending" };
    }), BRIEF_STEPS[0].id);
    return function () {
      return undefined;
    };
  }

  function closeCompileOverlay() {
    var overlay = document.getElementById("sp-compile-overlay");
    var dismiss = document.getElementById("sp-wait-dismiss");
    if (overlay) {
      overlay.hidden = true;
      overlay.classList.remove("is-open", "is-error");
    }
    if (dismiss) dismiss.hidden = true;
    document.body.classList.remove("is-sp-wait");
  }

  function hideCompileOverlay() {
    var bar = document.getElementById("sp-compile-bar");
    var stepEl = document.getElementById("sp-compile-step");
    if (bar) bar.style.width = "100%";
    if (stepEl) stepEl.textContent = "Pronto.";
    window.setTimeout(closeCompileOverlay, 280);
  }

  function failCompileOverlay(message) {
    var overlay = document.getElementById("sp-compile-overlay");
    var dismiss = document.getElementById("sp-wait-dismiss");
    var bar = document.getElementById("sp-compile-bar");
    if (!overlay) {
      toast(message, "error");
      return;
    }
    overlay.hidden = false;
    overlay.classList.add("is-open", "is-error");
    document.body.classList.add("is-sp-wait");
    setWaitMeta("Não gerou", "A geração parou", message || "Não foi possível terminar o documento.");
    if (bar) bar.style.width = "100%";
    if (dismiss) {
      dismiss.hidden = false;
      dismiss.focus();
    }
  }

  var waitDismiss = document.getElementById("sp-wait-dismiss");
  if (waitDismiss) {
    waitDismiss.addEventListener("click", closeCompileOverlay);
  }

  function setLive(message) {
    var live = document.getElementById("sp-save-live");
    if (live) live.textContent = message || "";
  }

  function setupStepper() {
    var current = document.querySelector(".sp-stepper-item.is-current");
    if (current && !current.getAttribute("aria-current")) {
      current.setAttribute("aria-current", "step");
    }
  }

  function openMediaModal() {
    var openBtn = document.getElementById("sp-media-open");
    if (openBtn && !((document.getElementById("sp-media") || {}).open)) {
      openBtn.click();
      return;
    }
    var dlg = document.getElementById("sp-media");
    if (dlg && typeof dlg.showModal === "function" && !dlg.open) dlg.showModal();
  }

  function focusField(id) {
    var el = typeof id === "string" ? document.getElementById(id) : id;
    if (!el) return;
    if (el.id === "sp-mix-channels" || el.closest("#sp-media")) openMediaModal();
    var acc = el.closest("details.sp-acc");
    if (acc) acc.open = true;
    if (el.scrollIntoView) {
      el.scrollIntoView({ block: "center", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    }
    if (typeof el.focus === "function") {
      window.setTimeout(function () { el.focus(); }, 50);
    }
  }

  function setupBriefing() {
    var form = document.getElementById("sp-briefing-form");
    var textarea = document.getElementById("sp-text");
    if (!form || !textarea) return;

    var importer = document.getElementById("sp-importer");
    var cards = document.getElementById("sp-brief-cards");
    var empty = document.getElementById("sp-refs-empty");
    var refsCount = document.getElementById("sp-refs-count");
    var count = document.getElementById("sp-brief-count");
    var autosave = document.getElementById("sp-autosave-hint");
    var status = document.getElementById("sp-status");
    var kbd = document.getElementById("sp-kbd-mod");
    var continueBtn = document.getElementById("sp-process-btn");
    var pending = null;
    var refs = [];
    var jobs = [];
    var draftKey = "sp_briefing_draft_" + token;
    var isMac = /Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent);
    if (kbd && !isMac) kbd.textContent = "Ctrl";

    function escapeHtml(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function kindLabel(kind) {
      return { url: "página", file: "arquivo", image: "imagem", search: "busca" }[kind] || "apoio";
    }

    function kindIcon(kind) {
      return { url: "fa-link", file: "fa-file-lines", image: "fa-image", search: "fa-magnifying-glass" }[kind] || "fa-paperclip";
    }

    function scopeLabel(scope) {
      return { briefing: "briefing", marca: "marca", cliente: "cliente", agencia: "agência", campanhas: "campanhas", mercado: "mercado" }[scope] || "";
    }

    function previewText(value) {
      var clean = String(value || "").replace(/\s+/g, " ").trim();
      return clean.length > 160 ? clean.slice(0, 160) + "…" : clean;
    }

    function growTextarea() {
      var narrow = window.matchMedia("(max-width: 640px)").matches;
      textarea.style.height = "auto";
      var next = Math.min(Math.max(textarea.scrollHeight, narrow ? 200 : 420), narrow ? 340 : 720);
      textarea.style.height = next + "px";
    }

    function updateCount() {
      if (!count) return;
      var n = textarea.value.length;
      count.textContent = n.toLocaleString("pt-BR") + " / 20.000 caracteres";
    }

    function updateContinue() {
      var ready = Boolean(textarea.value.trim() || refs.length);
      if (continueBtn) continueBtn.disabled = !ready;
    }

    function setDraftStatus(message, type) {
      if (autosave) autosave.textContent = message || "";
      setLive(message || "");
      if (autosave) {
        autosave.className = "sp-hi-save" + (type ? " is-" + type : "");
      }
    }

    function saveDraft() {
      setDraftStatus("Salvando…", "");
      try {
        localStorage.setItem(draftKey, JSON.stringify({ text: textarea.value, refs: refs, at: Date.now() }));
        setDraftStatus("Rascunho salvo agora", "ok");
      } catch (err) {
        setDraftStatus("Erro ao salvar rascunho", "error");
      }
    }

    function restoreDraft() {
      if (textarea.value.trim()) return;
      try {
        var saved = JSON.parse(localStorage.getItem(draftKey) || "null");
        if (!saved || Date.now() - (saved.at || 0) > 86400000) return;
        if (!saved.text && !(saved.refs && saved.refs.length)) return;
        if (saved.text) textarea.value = saved.text;
        refs = Array.isArray(saved.refs) ? saved.refs : [];
        renderCards();
        updateCount();
        growTextarea();
        updateContinue();
        setDraftStatus("Rascunho salvo agora", "ok");
      } catch (err) { /* ignore */ }
    }

    function renderCards() {
      var items = jobs.concat(refs.map(function (item) {
        return { status: "pronto", ref: item };
      }));
      var refsBlock = document.getElementById("sp-refs-card");
      if (refsBlock) refsBlock.hidden = items.length === 0;
      if (cards) {
        cards.hidden = items.length === 0;
        cards.innerHTML = items.map(function (item, index) {
          var job = item.status !== "pronto";
          var ref = item.ref || item;
          var notas = ref.notas || ref.digest || "";
          var statusLabel = item.status === "capturando" ? ((ref.kind || item.kind) === "search" ? "Pesquisando fontes" : "Analisando") : item.status === "erro" ? (item.error || "Erro na captura") : "Processado";
          return (
            '<li class="sp-brief-card' + (item.status === "erro" ? " is-error" : item.status === "capturando" ? " is-busy" : "") + '">' +
              '<i class="fa-solid ' + kindIcon(ref.kind || item.kind) + '" aria-hidden="true"></i>' +
              "<div>" +
                "<strong>" + escapeHtml(ref.label || ref.url || kindLabel(ref.kind || item.kind)) + "</strong>" +
                "<em>" + escapeHtml(kindLabel(ref.kind || item.kind)) + (ref.scope ? " · " + escapeHtml(scopeLabel(ref.scope)) : ref.papel ? " · " + escapeHtml(ref.papel) : "") + (ref.source_mode === "model" ? " · apoio do modelo" : ref.source_mode === "web" ? " · fontes públicas" : "") + "</em>" +
                '<p class="sp-brief-card-status">' + escapeHtml(statusLabel) + "</p>" +
                (notas ? '<p class="sp-brief-card-preview">' + escapeHtml(previewText(notas)) + "</p>" : "") +
                (notas ? '<p class="sp-brief-card-full" hidden>' + escapeHtml(notas) + "</p>" : "") +
              "</div>" +
              '<div class="sp-brief-card-actions">' +
                (notas ? '<button type="button" data-ref-expand="' + index + '">Ver</button>' : "") +
                (item.status === "erro" ? '<button type="button" data-ref-retry="' + item.id + '">Tentar de novo</button>' : "") +
                (!job ? '<button type="button" data-ref-remove="' + (index - jobs.length) + '" aria-label="Remover">Remover</button>' : "") +
              "</div>" +
            "</li>"
          );
        }).join("");
      }
      if (empty) empty.hidden = items.length > 0;
      if (refsCount) {
        refsCount.hidden = items.length === 0;
        refsCount.textContent = items.length ? "(" + items.length + ")" : "";
      }
      updateContinue();
    }

    function setupImporter() {
      if (!importer) return;
      var fileInput = document.getElementById("sp-ref-file");
      var imageInput = document.getElementById("sp-ref-file-image");
      var fileDrop = document.getElementById("sp-drop-file");
      var imageDrop = document.getElementById("sp-drop-image");
      function selectTab(kind) {
        var tab = kind || "text";
        importer.querySelectorAll("[data-ref-tab]").forEach(function (button) {
          var on = button.getAttribute("data-ref-tab") === tab;
          button.classList.toggle("is-on", on);
          button.setAttribute("aria-selected", on ? "true" : "false");
        });
        if (tab === "text") textarea.focus();
      }
      importer.querySelectorAll("[data-ref-tab]").forEach(function (button) {
        button.addEventListener("click", function () {
          selectTab(button.getAttribute("data-ref-tab"));
        });
      });
      function takeFiles(list) {
        if (!list) return;
        Array.prototype.forEach.call(list, function (file) {
          if (file) captureFile(file);
        });
      }
      function bindDrop(drop) {
        if (!drop) return;
        ["dragenter", "dragover"].forEach(function (name) {
          drop.addEventListener(name, function (event) {
            event.preventDefault();
            drop.classList.add("is-over");
          });
        });
        ["dragleave", "drop"].forEach(function (name) {
          drop.addEventListener(name, function (event) {
            event.preventDefault();
            drop.classList.remove("is-over");
          });
        });
        drop.addEventListener("drop", function (event) {
          takeFiles(event.dataTransfer && event.dataTransfer.files);
        });
      }
      bindDrop(fileDrop);
      bindDrop(imageDrop);
      [fileInput, imageInput].forEach(function (input) {
        if (!input) return;
        input.addEventListener("change", function (event) {
          takeFiles(event.target.files);
          event.target.value = "";
        });
      });
    }

    function nextJobId() {
      return "job-" + Date.now() + "-" + jobs.length;
    }

    async function runCapture(kind, extra, job) {
      var statusEl = document.getElementById("sp-ref-status");
      setStatus(statusEl, kind === "search" ? "Buscando fontes públicas e organizando os achados…" : "Capturando…", "");
      var captured;
      if (kind === "file" || kind === "image") {
        var data = new FormData();
        data.append("file", extra);
        var response = await fetch("/smart-planner/api/" + token + "/referencia", {
          method: "POST",
          credentials: "same-origin",
          body: data,
        });
        var payload = await response.json();
        if (!payload.success) throw new Error(payload.error || "Falha ao capturar");
        captured = payload.data;
      } else {
        captured = await postJson("/smart-planner/api/" + token + "/referencia", extra);
      }
      pending = captured;
      var digest = document.getElementById("sp-ref-digest");
      var result = document.getElementById("sp-ref-result");
      if (digest) digest.textContent = captured.notas || captured.digest || captured.bloco || "";
      if (result) result.hidden = true;
      setStatus(statusEl, "", "");
      if (job) {
        jobs = jobs.filter(function (item) { return item.id !== job.id; });
      }
      addRef(captured);
      return captured;
    }

    function addRef(captured) {
      if (!captured) return;
      refs.push({
        kind: captured.kind,
        label: captured.label,
        url: captured.url || "",
        name: captured.name || "",
        notas: captured.notas || captured.digest || "",
        fatos: captured.fatos || {},
        papel: captured.papel || "",
        scope: captured.scope || "",
        source_mode: captured.source_mode || "",
      });
      renderCards();
      saveDraft();
    }

    function startJob(kind, extra, label) {
      var job = { id: nextJobId(), status: "capturando", kind: kind, extra: extra, label: label };
      jobs.push(job);
      renderCards();
      runCapture(kind, extra, job).then(function () {
        renderCards();
      }).catch(function (error) {
        job.status = "erro";
        job.error = error.message;
        renderCards();
        setStatus(document.getElementById("sp-ref-status"), error.message, "error");
      });
    }

    function captureFile(file) {
      var kind = (file.type || "").indexOf("image/") === 0 ? "image" : "file";
      startJob(kind, file, file.name);
    }

    var urlGo = document.getElementById("sp-ref-url-go");
    if (urlGo) {
      urlGo.addEventListener("click", function () {
        var urlInput = document.getElementById("sp-ref-url");
        var url = urlInput ? urlInput.value.trim() : "";
        if (!url) {
          setStatus(document.getElementById("sp-ref-status"), "Informe uma URL para ler a fonte.", "error");
          if (urlInput) urlInput.focus();
          return;
        }
        startJob("url", { kind: "url", url: url }, url);
        closeCampaignModal();
      });
    }
    var campaignModal = document.getElementById("sp-campaign-modal");
    var sourcesOpen = document.getElementById("sp-sources-open");
    var campaignOpen = document.getElementById("sp-campaign-research-open");
    var campaignSearch = document.getElementById("sp-campaign-search");
    var campaignQuery = document.getElementById("sp-campaign-query");
    var campaignResults = document.getElementById("sp-campaign-results");
    var campaignStatus = document.getElementById("sp-campaign-status");
    function closeCampaignModal() { if (campaignModal && campaignModal.open) campaignModal.close(); }
    function setSourceMode(mode) {
      if (!campaignModal) return;
      campaignModal.querySelectorAll("[data-source-mode]").forEach(function (button) {
        var active = button.getAttribute("data-source-mode") === mode;
        button.classList.toggle("is-on", active);
        button.setAttribute("aria-selected", active ? "true" : "false");
      });
      campaignModal.querySelectorAll("[data-source-pane]").forEach(function (pane) {
        pane.hidden = pane.getAttribute("data-source-pane") !== mode;
      });
      var focusId = mode === "url" ? "sp-ref-url" : mode === "campaign" ? "sp-campaign-query" : "";
      var focus = focusId && document.getElementById(focusId);
      if (focus) window.setTimeout(function () { focus.focus(); }, 0);
    }
    function openSources(mode) {
      if (!campaignModal) return;
      setSourceMode(mode || "url");
      if (!campaignModal.open) campaignModal.showModal();
    }
    function renderCampaignResults(items) {
      if (!campaignResults) return;
      campaignResults.innerHTML = (items || []).map(function (item, index) {
        var image = item.image_url ? '<img src="' + escapeHtml(item.image_url) + '" alt="" loading="lazy">' : '<div class="sp-campaign-result-placeholder"><i class="fa-regular fa-image" aria-hidden="true"></i></div>';
        return '<article class="sp-campaign-result">' + image + '<div><strong>' + escapeHtml(item.title) + '</strong><p>' + escapeHtml(previewText(item.snippet)) + '</p><small>' + (item.source_mode === "web" ? "Fonte pública" : "Resumo de apoio") + '</small></div>' + (item.url ? '<button type="button" data-campaign-source="' + index + '">Usar fonte</button>' : '') + '</article>';
      }).join("") || '<p class="sp-empty">Nenhuma campanha encontrada. Tente uma marca ou categoria mais específica.</p>';
      campaignResults._items = items || [];
    }
    async function searchCampaigns() {
      var query = campaignQuery ? campaignQuery.value.trim() : "";
      if (!query) { if (campaignStatus) campaignStatus.textContent = "Informe a marca, campanha ou categoria."; return; }
      if (campaignStatus) campaignStatus.textContent = "Pesquisando fontes públicas e imagens de campanha…";
      if (campaignResults) campaignResults.innerHTML = '<div class="sp-campaign-loading"><i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Organizando referências</div>';
      try {
        var data = await postJson("/smart-planner/api/" + token + "/campanhas/pesquisa", { query: query, briefing: textarea.value });
        if (campaignStatus) campaignStatus.textContent = (data.items || []).length + " fontes encontradas.";
        renderCampaignResults(data.items);
      } catch (error) { if (campaignStatus) campaignStatus.textContent = error.message; if (campaignResults) campaignResults.innerHTML = ""; }
    }
    if (sourcesOpen) sourcesOpen.addEventListener("click", function () { openSources("url"); });
    if (campaignOpen) campaignOpen.addEventListener("click", function () { openSources("campaign"); });
    if (campaignSearch) campaignSearch.addEventListener("click", searchCampaigns);
    if (campaignQuery) campaignQuery.addEventListener("keydown", function (event) { if (event.key === "Enter") { event.preventDefault(); searchCampaigns(); } });
    if (campaignModal) {
      campaignModal.querySelectorAll("[data-source-mode]").forEach(function (button) { button.addEventListener("click", function () { setSourceMode(button.getAttribute("data-source-mode")); }); });
      campaignModal.querySelectorAll("[data-close-campaign-modal]").forEach(function (button) { button.addEventListener("click", closeCampaignModal); });
      campaignModal.addEventListener("click", function (event) { if (event.target === campaignModal) closeCampaignModal(); });
    }
    if (campaignResults) campaignResults.addEventListener("click", function (event) { var button = event.target.closest("[data-campaign-source]"); if (!button) return; var item = (campaignResults._items || [])[Number(button.getAttribute("data-campaign-source"))]; if (!item || !item.url) return; startJob("url", { kind: "url", url: item.url }, item.title || item.url); closeCampaignModal(); });
    document.getElementById("sp-ref-insert").addEventListener("click", function () {
      if (!pending) return;
      var already = refs.some(function (item) {
        return item.label === pending.label && (item.notas || "") === (pending.notas || pending.digest || "");
      });
      if (!already) addRef(pending);
      pending = null;
      document.getElementById("sp-ref-result").hidden = true;
    });
    if (cards) {
      cards.addEventListener("click", function (event) {
        var retry = event.target.closest("[data-ref-retry]");
        if (retry) {
          var job = jobs.filter(function (item) { return item.id === retry.getAttribute("data-ref-retry"); })[0];
          if (job) {
            job.status = "capturando";
            job.error = "";
            renderCards();
            runCapture(job.kind, job.extra, job).then(function () {
              renderCards();
            }).catch(function (error) {
              job.status = "erro";
              job.error = error.message;
              renderCards();
            });
          }
          return;
        }
        var remove = event.target.closest("[data-ref-remove]");
        if (remove) {
          refs.splice(Number(remove.getAttribute("data-ref-remove")), 1);
          renderCards();
          saveDraft();
          return;
        }
        var expand = event.target.closest("[data-ref-expand]");
        if (!expand) return;
        var card = expand.closest(".sp-brief-card");
        var full = card && card.querySelector(".sp-brief-card-full");
        var preview = card && card.querySelector(".sp-brief-card-preview");
        if (!full) return;
        var open = full.hidden;
        full.hidden = !open;
        if (preview) preview.hidden = open;
        expand.textContent = open ? "Ocultar" : "Ver";
      });
    }
    textarea.addEventListener("input", function () {
      if (textarea.value.length > 20000) textarea.value = textarea.value.slice(0, 20000);
      updateCount();
      growTextarea();
      updateContinue();
      window.clearTimeout(textarea._draft);
      textarea._draft = window.setTimeout(saveDraft, 800);
    });
    textarea.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        if (!continueBtn || continueBtn.disabled) return;
        form.requestSubmit();
      }
    });

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      var button = document.getElementById("sp-process-btn");
      var text = textarea.value.trim();
      if (!text && !refs.length) {
        setStatus(status, "Escreva o briefing ou adicione uma referência de apoio.", "error");
        textarea.focus();
        updateContinue();
        return;
      }
      setLoading(button, true);
      var stop = showCompileOverlay(text || (refs[0] && refs[0].notas) || "");
      try {
        var result = await postJson("/smart-planner/api/" + token + "/processar", {
          text: text,
          references: refs.map(function (item) {
            return {
              kind: item.kind,
              label: item.label,
              url: item.url || "",
              name: item.name || "",
              notas: item.notas || "",
              fatos: item.fatos || {},
              papel: item.papel || "",
              scope: item.scope || "",
              source_mode: item.source_mode || "",
            };
          }),
        });
        if (result.started) await waitForBriefing();
        stop();
        hideCompileOverlay();
        try { localStorage.removeItem(draftKey); } catch (err) { /* ignore */ }
        window.setTimeout(function () {
          window.location.href = result.redirect;
        }, 400);
      } catch (error) {
        stop();
        failCompileOverlay(error.message);
        setStatus(status, error.message, "error");
        setLoading(button, false);
      }
    });

    setupImporter();
    restoreDraft();
    updateCount();
    growTextarea();
    updateContinue();
    window.addEventListener("resize", growTextarea);
  }

  setupStepper();
  setupBriefing();

  function setupMixDesk() {
    var form = document.getElementById("sp-revisao-form");
    var specEl = document.getElementById("sp-mix-spec");
    if (!form || !specEl) return;
    var spec = {};
    try { spec = JSON.parse(specEl.textContent || "{}") || {}; } catch (err) { spec = {}; }
    var desk = document.getElementById("sp-wizard") || document.getElementById("sp-hi-plan") || root;
    var pace = {};
    try { pace = JSON.parse((document.getElementById("sp-pace-boot") || {}).textContent || "{}") || {}; } catch (err) { pace = {}; }
    var fixedMonths = {};
    var ritmoTimer = null;
    var objetivoEl = document.getElementById("sp-objetivo");
    var bars = document.getElementById("sp-mix-bars");
    var empty = document.getElementById("sp-mix-empty");
    var sumEl = document.getElementById("sp-mix-sum");
    var hint = document.getElementById("sp-mix-hint");
    var more = document.querySelector(".sp-mix-more");
    var picks = document.getElementById("sp-mix-picks");
    var morePicks = document.querySelector(".sp-mix-more .sp-mix-picks");
    var balanceContent = document.getElementById("sp-mix-balance-content");
    var singleState = document.getElementById("sp-mix-single");
    var mediaDlg = document.getElementById("sp-media");
    var mediaApply = document.getElementById("sp-media-apply");
    var mediaSnapshot = "";
    var mediaOpener = null;
    var mediaApplied = false;
    var restoringMedia = false;


    function selectedCanais() {
      return Array.prototype.slice.call(desk.querySelectorAll('input[name="canais"]:checked')).map(function (el) {
        return el.value;
      });
    }
    function selectedMethod() {
      var input = desk.querySelector('input[name="mix_method"]:checked');
      return input ? input.value : "funil";
    }
    function recommendedFor(objetivo) {
      return (spec.recommend && spec.recommend[objetivo]) || ["funil", "alcance"];
    }
    function groupOf(id) {
      return (spec.groups || {})[id] || "performance";
    }
    function normalizePcts(pairs) {
      var total = pairs.reduce(function (sum, item) { return sum + Math.max(item[1], 0); }, 0);
      if (total <= 0) {
        pairs = pairs.map(function (item) { return [item[0], 1]; });
        total = pairs.length;
      }
      var exact = pairs.map(function (item) { return [item[0], 100 * Math.max(item[1], 0) / total]; });
      var floors = exact.map(function (item) { return [item[0], Math.floor(item[1])]; });
      var rem = 100 - floors.reduce(function (sum, item) { return sum + item[1]; }, 0);
      var order = exact.slice().sort(function (a, b) {
        return (b[1] - Math.floor(b[1])) - (a[1] - Math.floor(a[1]));
      });
      var bump = {};
      for (var i = 0; i < rem; i += 1) bump[order[i][0]] = true;
      var out = {};
      floors.forEach(function (item) { out[item[0]] = item[1] + (bump[item[0]] ? 1 : 0); });
      return out;
    }
    function tableWeights(method, objetivo) {
      var table = (spec.tables || {})[method] || {};
      return table[objetivo] || table.default || {};
    }
    function frequenciaWeights(objetivo, groups) {
      var ranking = tableWeights("funil", objetivo);
      var ranked = groups.slice().sort(function (a, b) { return (ranking[b] || 0) - (ranking[a] || 0); });
      var weights = {};
      groups.forEach(function (group) { weights[group] = 0; });
      if (!ranked.length) return weights;
      if (ranked.length === 1) { weights[ranked[0]] = 100; return weights; }
      if (ranked.length === 2) { weights[ranked[0]] = 70; weights[ranked[1]] = 30; return weights; }
      weights[ranked[0]] = 40;
      weights[ranked[1]] = 30;
      var rest = ranked.slice(2);
      var share = 30 / rest.length;
      rest.forEach(function (group) { weights[group] = share; });
      return weights;
    }
    function groupWeights(method, objetivo, groups) {
      if (method === "alcance") {
        var even = {};
        groups.forEach(function (group) { even[group] = 1; });
        return even;
      }
      if (method === "frequencia") return frequenciaWeights(objetivo, groups);
      var table = tableWeights(method === "eficiencia" || method === "presenca" || method === "funil" ? method : "funil", objetivo);
      var fallback = spec.defaultGroupWeight || 4;
      var out = {};
      groups.forEach(function (group) { out[group] = table[group] != null ? table[group] : fallback; });
      return out;
    }
    function mediaKeys(canais) {
      var media = spec.media || [];
      return media.filter(function (key) { return canais.indexOf(key) !== -1; });
    }
    function allocateCore(keys, objetivo, method, weights) {
      if (!keys.length) return [];
      var raw;
      if (method === "manual") {
        var prev = {};
        (weights || []).forEach(function (item) {
          if (item && item.id) prev[item.id] = Number(item.pct) || 0;
        });
        raw = keys.map(function (key) { return [key, prev[key] != null ? prev[key] : 0]; });
      } else {
        var groups = [];
        keys.forEach(function (key) {
          var group = groupOf(key);
          if (groups.indexOf(group) === -1) groups.push(group);
        });
        var gw = groupWeights(method, objetivo, groups);
        var counts = {};
        keys.forEach(function (key) {
          var group = groupOf(key);
          counts[group] = (counts[group] || 0) + 1;
        });
        raw = keys.map(function (key) {
          var group = groupOf(key);
          return [key, (gw[group] != null ? gw[group] : 4) / (counts[group] || 1)];
        });
      }
      var pcts = normalizePcts(raw);
      return keys.map(function (key) {
        return { id: key, label: (spec.labels || {})[key] || key, group: groupOf(key), pct: pcts[key] || 0 };
      });
    }
    function allocate(canais, objetivo, method, weights) {
      var keys = mediaKeys(canais);
      if (!keys.length) return [];
      var specialIds = spec.specialMix || ["places", "interativos"];
      var specialPct = spec.specialPct || 8;
      var digital = keys.filter(function (key) { return specialIds.indexOf(key) === -1; });
      var special = keys.filter(function (key) { return specialIds.indexOf(key) !== -1; });
      if (method === "manual" || !special.length) return allocateCore(keys, objetivo, method, weights);
      var digitalRows = allocateCore(digital, objetivo, method, weights);
      var prev = {};
      (weights || []).forEach(function (item) {
        if (item && item.id) prev[item.id] = Number(item.pct) || 0;
      });
      var specialRaw = special.map(function (key) {
        return [key, prev[key] != null ? prev[key] : specialPct];
      });
      if (!digitalRows.length) return allocateCore(special, objetivo, "manual", specialRaw.map(function (item) {
        return { id: item[0], pct: item[1] };
      }));
      var specialShare = Math.min(specialRaw.reduce(function (sum, item) { return sum + Math.max(item[1], 0); }, 0), 40);
      if (specialShare <= 0) specialShare = specialPct * special.length;
      var remaining = Math.max(100 - specialShare, 0);
      var pairs = digitalRows.map(function (row) {
        return [row.id, row.pct * remaining / 100];
      });
      var specTotal = specialRaw.reduce(function (sum, item) { return sum + Math.max(item[1], 0); }, 0) || 1;
      specialRaw.forEach(function (item) {
        pairs.push([item[0], specialShare * Math.max(item[1], 0) / specTotal]);
      });
      var pcts = normalizePcts(pairs);
      return keys.map(function (key) {
        return { id: key, label: (spec.labels || {})[key] || key, group: groupOf(key), pct: pcts[key] || 0 };
      });
    }
    function currentWeights() {
      if (!bars) return [];
      return Array.prototype.slice.call(bars.querySelectorAll("li")).map(function (row) {
        var slider = row.querySelector("input[type=range]");
        return {
          id: row.getAttribute("data-canal"),
          pct: slider ? Number(slider.value) || 0 : 0,
        };
      });
    }
    function setMethod(method) {
      desk.querySelectorAll('input[name="mix_method"]').forEach(function (input) {
        input.checked = input.value === method;
        var label = input.closest(".sp-mix-pick");
        if (label) label.classList.toggle("is-on", input.checked);
      });
    }
    function paintPicks() {
      if (!picks || !morePicks) return;
      var rec = recommendedFor(objetivoEl ? objetivoEl.value : "");
      var current = selectedMethod();
      desk.querySelectorAll(".sp-mix-pick").forEach(function (label) {
        var input = label.querySelector("input");
        var id = input ? input.value : "";
        if (rec.indexOf(id) !== -1) picks.appendChild(label);
        else morePicks.appendChild(label);
        label.classList.toggle("is-on", id === current);
      });
      if (more) more.open = rec.indexOf(current) === -1;
      if (hint) {
        hint.textContent = (objetivoEl && objetivoEl.value)
          ? "Dois métodos indicados para este objetivo. Os outros quatro ficam em mais métodos."
          : "Escolha o objetivo na narrativa para indicar os dois métodos do funil.";
      }
    }
    function paintBalanceMode() {
      var count = selectedCanais().length;
      if (balanceContent) balanceContent.hidden = count <= 1;
      if (singleState) {
        singleState.hidden = count !== 1;
        var copy = singleState.querySelector("p");
        if (copy && count === 0) copy.textContent = "Selecione pelo menos um canal para visualizar o calendário de uso.";
      }
    }
    function paintBars(weights) {
      if (!bars) return;
      paintBalanceMode();
      var budget = budgetTotal();
      bars.innerHTML = weights.map(function (item) {
        var amount = budget > 0 ? Math.round(budget * (item.pct || 0) / 100) : 0;
        return '<li data-canal="' + item.id + '"><span>' + channelMark(item.id, item.label) + "<strong>"
          + escapeHtml(item.label) + "</strong><em>" + item.pct + "%</em>"
          + (budget > 0 ? "<small>" + formatBRL(amount) + "</small>" : "")
          + '</span><i><b data-pct="' + item.pct + '"></b></i>'
          + '<input type="range" min="0" max="100" value="' + item.pct + '" data-canal="' + item.id
          + '" aria-label="Percentual de ' + escapeHtml(item.label) + '"></li>';
      }).join("");
      bars.querySelectorAll("b[data-pct]").forEach(function (fill) {
        fill.style.setProperty("--pct", fill.getAttribute("data-pct") || "0");
      });
      if (empty) empty.hidden = weights.length > 0;
      paintMixValidity();
      paintMediaFacts();
      paintDirty();
    }
    function money(value) {
      return parseInt(String(value || "").replace(/\D/g, ""), 10) || 0;
    }
    function formatMoney(value) {
      return Math.max(0, value).toLocaleString("pt-BR");
    }
    function formatBRL(value) {
      try {
        return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(Math.max(0, value || 0));
      } catch (err) {
        return "R$ " + formatMoney(value);
      }
    }
    function channelMark(id, label) {
      var logo = (spec.logos || {})[id];
      var name = label || (spec.labels || {})[id] || id;
      if (logo) return '<img class="sp-mix-logo" src="' + escapeHtml(logo) + '" alt="" aria-hidden="true">';
      var initials = String(name).replace(/[^A-Za-z0-9ÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+/g, " ").trim().split(/\s+/).slice(0, 2).map(function (word) {
        return word.charAt(0);
      }).join("").toUpperCase() || "?";
      return '<span class="sp-mix-fallback" aria-hidden="true">' + escapeHtml(initials) + "</span>";
    }
    function mixTotal(weights) {
      return (weights || []).reduce(function (sum, item) { return sum + (Number(item.pct) || 0); }, 0);
    }
    function mixValid(weights) {
      return !!(weights && weights.length && mixTotal(weights) === 100);
    }
    function budgetTotal() {
      return parseInt(pace.total, 10) || money((document.getElementById("sp-field-verba") || {}).value);
    }
    function paintMixValidity() {
      var weights = currentWeights();
      var total = mixTotal(weights);
      var ok = mixValid(weights);
      if (sumEl) {
        sumEl.hidden = weights.length === 0;
        sumEl.textContent = weights.length ? "Soma " + total + "%" : "";
        sumEl.classList.toggle("is-bad", weights.length > 0 && !ok);
      }
      if (mediaApply) mediaApply.disabled = !ok;
      var status = document.getElementById("sp-media-status");
      if (status) {
        if (weights.length && !ok) status.textContent = "Ajuste os canais até somar 100%.";
        else if (status.textContent.indexOf("100%") !== -1) status.textContent = "";
      }
    }
    function paintMediaFacts() {
      var el = document.getElementById("sp-media-facts");
      if (!el) return;
      var parts = [];
      if (pace.helper) parts.push(pace.helper);
      else if (pace.inicio && pace.fim) parts.push(pace.inicio + " a " + pace.fim);
      if (pace.total > 0) parts.push(pace.como || formatBRL(pace.total));
      var n = selectedCanais().length;
      parts.push(n + (n === 1 ? " canal" : " canais"));
      el.textContent = parts.join(" · ");
    }
    function paintDirty() {
      var mark = document.getElementById("sp-media-dirty");
      if (!mark) return;
      mark.hidden = !mediaSnapshot || mediaSnapshot === snapshotMedia();
    }
    function snapshotMedia() {
      return JSON.stringify({
        canais: selectedCanais(),
        mix: currentWeights(),
        method: selectedMethod(),
        alocacao: monthValues(),
      });
    }
    function restoreMediaSnapshot(raw) {
      if (!raw) return;
      var snap;
      try { snap = JSON.parse(raw); } catch (err) { return; }
      restoringMedia = true;
      try {
        desk.querySelectorAll('input[name="canais"]').forEach(function (input) {
          input.checked = (snap.canais || []).indexOf(input.value) !== -1;
        });
        if (snap.method) setMethod(snap.method);
        paintBars(allocate(
          selectedCanais(),
          objetivoEl ? objetivoEl.value : "",
          selectedMethod(),
          snap.mix
        ));
        var cols = document.getElementById("sp-gantt-cols");
        if (cols && snap.alocacao) {
          Object.keys(snap.alocacao).forEach(function (key) {
            var field = cols.querySelector('[data-chave="' + key + '"]');
            if (field) field.value = formatMoney(snap.alocacao[key]);
          });
        }
        paintPicks();
        paintSummary();
        paintCalendar();
        paintDirty();
        desk.querySelectorAll('input[name="canais"]').forEach(function (input) {
          if (input.value === "places" || input.value === "interativos") {
            input.dispatchEvent(new Event("change", { bubbles: true }));
          }
        });
        var anyCanal = desk.querySelector('input[name="canais"]');
        if (anyCanal) anyCanal.dispatchEvent(new Event("change", { bubbles: true }));
      } finally {
        restoringMedia = false;
      }
    }
    function weekHints() {
      var start = pace.inicio;
      var end = pace.fim;
      if (!start || !end || (pace.meses || 0) > 1) return [];
      var a = new Date(start + "T00:00:00");
      var b = new Date(end + "T00:00:00");
      if (isNaN(a.getTime()) || isNaN(b.getTime()) || b < a) return [];
      var weeks = [];
      var cursor = new Date(a);
      var index = 1;
      while (cursor <= b && index <= 6) {
        var stop = new Date(cursor);
        stop.setDate(stop.getDate() + 6);
        if (stop > b) stop = b;
        weeks.push("Semana " + index + " · " + cursor.getDate() + "/" + (cursor.getMonth() + 1) + "–" + stop.getDate() + "/" + (stop.getMonth() + 1));
        cursor.setDate(cursor.getDate() + 7);
        index += 1;
      }
      return weeks;
    }
    function monthWeekLabels(key) {
      var parts = String(key || "").split("-");
      if (parts.length < 2) return [];
      var year = Number(parts[0]);
      var month = Number(parts[1]);
      if (!year || !month) return [];
      var start = new Date(year, month - 1, 1);
      var last = new Date(year, month, 0);
      if (pace.inicio) {
        var campaignStart = new Date(pace.inicio + "T00:00:00");
        if (!isNaN(campaignStart.getTime()) && campaignStart > start) start = campaignStart;
      }
      if (pace.fim) {
        var campaignEnd = new Date(pace.fim + "T00:00:00");
        if (!isNaN(campaignEnd.getTime()) && campaignEnd < last) last = campaignEnd;
      }
      var weeks = [];
      var cursor = new Date(start);
      var index = 1;
      while (cursor <= last && index <= 6) {
        var stop = new Date(cursor);
        stop.setDate(stop.getDate() + 6);
        if (stop > last) stop = last;
        weeks.push("Semana " + index + " · " + cursor.getDate() + "/" + (cursor.getMonth() + 1) + "–" + stop.getDate() + "/" + (stop.getMonth() + 1));
        cursor.setDate(cursor.getDate() + 7);
        index += 1;
      }
      return weeks;
    }
    function monthValues() {
      var cols = document.getElementById("sp-gantt-cols");
      var out = {};
      if (!cols) return Object.assign({}, pace.alocacao || {});
      cols.querySelectorAll("[data-chave]").forEach(function (input) {
        out[input.getAttribute("data-chave")] = money(input.value);
      });
      if (!Object.keys(out).length) return Object.assign({}, pace.alocacao || {});
      return out;
    }
    function monthMix() {
      var canais = selectedCanais();
      var method = selectedMethod();
      var objetivo = objetivoEl ? objetivoEl.value : "";
      return allocate(canais, objetivo, method, currentWeights());
    }
    function paintSummary() {
      var copy = document.getElementById("sp-mix-summary-copy");
      var snap = document.getElementById("sp-mix-snap");
      var weights = currentWeights();
      var labels = {};
      Object.keys(spec.labels || {}).forEach(function (key) { labels[key] = spec.labels[key]; });
      desk.querySelectorAll("#sp-mix-channels input[name='canais']:checked").forEach(function (input) {
        var name = input.closest("label") && input.closest("label").querySelector("span:last-child");
        if (name && name.textContent) labels[input.value] = name.textContent.trim();
      });
      if (copy) {
        var methodLabel = "";
        var pick = desk.querySelector(".sp-mix-pick.is-on strong");
        if (pick) methodLabel = pick.textContent;
        copy.textContent = weights.length
          ? weights.length + (weights.length === 1 ? " canal · " : " canais · ") + (methodLabel || "Mix")
          : "Abra o modal para marcar canais e fechar 100%.";
      }
      if (snap) {
        snap.hidden = weights.length === 0;
        snap.innerHTML = weights.map(function (item) {
          var name = labels[item.id] || item.label || item.id;
          return "<li data-canal=\"" + escapeHtml(item.id) + "\"><span>" + channelMark(item.id, name) + " "
            + escapeHtml(name) + "</span><i><b style=\"width:" + item.pct + "%\"></b></i><em>" + item.pct + "%</em></li>";
        }).join("");
      }
    }
    function paintMiniCal() {
      var mini = document.getElementById("sp-cal-mini");
      if (!mini) return;
      var keys = pace.chaves || [];
      var labels = pace.rotulos || [];
      var values = pace.editavel ? monthValues() : (pace.alocacao || {});
      var total = parseInt(pace.total, 10) || 0;
      mini.hidden = !(pace.visivel || pace.editavel) || !keys.length;
      if (mini.hidden) return;
      var unit = pace.granularidade === "semana" ? "semanas" : "meses";
      mini.innerHTML = "<p>" + keys.length + " " + unit + " · começa menor e solta no meio e no fim</p><ol>"
        + keys.map(function (key, index) {
          var valor = values[key] || 0;
          var pct = total > 0 ? Math.round((valor / total) * 100) : 0;
          return "<li title=\"" + (labels[index] || key) + "\"><b style=\"--pct:" + pct + "\"></b><span>"
            + (labels[index] || key) + "</span></li>";
        }).join("") + "</ol>";
    }
    function paintGantt() {
      var track = document.getElementById("sp-gantt-track");
      var cols = document.getElementById("sp-gantt-cols");
      var gantt = document.getElementById("sp-gantt");
      if (!gantt) return;
      var keys = pace.chaves || [];
      var labels = pace.rotulos || [];
      var values = pace.editavel ? monthValues() : (pace.alocacao || {});
      if (!Object.keys(values).length) values = pace.alocacao || {};
      var total = parseInt(pace.total, 10) || 0;
      var verbaEl = document.getElementById("sp-field-verba");
      var show = money(verbaEl && verbaEl.value) > 0 && (pace.parseou || keys.length);
      gantt.hidden = !show;
      gantt.style.setProperty("--months", String(Math.max(1, keys.length)));
      if (cols) cols.hidden = !pace.editavel;
      if (pace.editavel && cols && !cols.children.length) {
        cols.innerHTML = keys.map(function (key, index) {
          var valor = (pace.alocacao && pace.alocacao[key]) || 0;
          return "<label><span>" + (labels[index] || key) + "</span><input data-chave=\"" + key
            + "\" inputmode=\"numeric\" value=\"" + formatMoney(valor) + "\"></label>";
        }).join("");
      }
      if (!track) return;
      var peak = keys.reduce(function (max, key) { return Math.max(max, values[key] || 0); }, 0) || 1;
      track.innerHTML = keys.map(function (key, index) {
        var valor = values[key] || 0;
        var pct = Math.round((valor / peak) * 100);
        var tone = index === 0 ? "is-learn" : (index === keys.length - 1 ? "is-release" : "is-mid");
        return "<div class=\"sp-gantt-col " + tone + (valor <= 0 ? " is-hole" : "") + "\">"
          + "<span class=\"sp-gantt-stem\"><b style=\"height:" + pct + "%\"></b></span><strong>"
          + (labels[index] || key) + "</strong><small>R$ " + formatMoney(valor) + "</small></div>";
      }).join("");
    }
    function paintCalendar() {
      paintGantt();
      paintMiniCal();
      paintMediaFacts();
      var wrap = document.getElementById("sp-cal-wrap");
      var table = document.getElementById("sp-cal-table");
      var emptyCal = document.getElementById("sp-cal-empty");
      var weekHint = document.getElementById("sp-week-hint");
      var weekBox = document.getElementById("sp-month-weeks");
      var expanded = "";
      if (table) {
        var openTh = table.querySelector("th[aria-expanded='true']");
        if (openTh) expanded = openTh.getAttribute("data-month") || "";
      }
      var keys = pace.chaves || [];
      var canais = selectedCanais();
      if (emptyCal) emptyCal.hidden = !!(pace.parseou && canais.length);
      if (weekHint) {
        if (pace.granularidade === "semana") {
          weekHint.hidden = true;
          weekHint.textContent = "";
        } else {
          var weeks = weekHints();
          weekHint.hidden = weeks.length === 0;
          weekHint.textContent = weeks.length ? "Leitura das datas: " + weeks.join(" · ") : "";
        }
      }
      if (!wrap || !table) return;
      wrap.hidden = !((pace.visivel || pace.editavel) && keys.length >= 2 && canais.length);
      if (wrap.hidden) {
        if (weekBox) {
          weekBox.hidden = true;
          weekBox.textContent = "";
        }
        return;
      }
      var labels = pace.rotulos || [];
      var values = monthValues();
      var weightsByMonth = keys.map(function () { return monthMix(); });
      var channels = weightsByMonth[0] || currentWeights();
      table.innerHTML = "<thead><tr><th>Canal</th>" + keys.map(function (key, index) {
        return "<th data-month=\"" + escapeHtml(key) + "\" aria-expanded=\"" + (key === expanded ? "true" : "false") + "\"><button type=\"button\">"
          + escapeHtml(labels[index] || key) + "</button></th>";
      }).join("") + "</tr></thead><tbody>" + channels.map(function (item) {
        return "<tr><th>" + channelMark(item.id, item.label) + " " + escapeHtml(item.label) + "</th>"
          + weightsByMonth.map(function (month, index) {
            var cell = month.filter(function (row) { return row.id === item.id; })[0] || item;
            var monthTotal = values[keys[index]] || 0;
            var valor = Math.round(monthTotal * (cell.pct || 0) / 100);
            return "<td style=\"--pct:" + (cell.pct || 0) + "\"><strong>" + cell.pct
              + "%</strong><small>" + formatBRL(valor) + "</small></td>";
          }).join("") + "</tr>";
      }).join("") + "</tbody>";
      if (weekBox) {
        if (expanded && keys.indexOf(expanded) !== -1) {
          var monthWeeks = monthWeekLabels(expanded);
          var monthLabel = labels[keys.indexOf(expanded)] || expanded;
          weekBox.hidden = monthWeeks.length === 0;
          weekBox.textContent = monthWeeks.length ? monthLabel + ": " + monthWeeks.join(" · ") : "";
        } else {
          weekBox.hidden = true;
          weekBox.textContent = "";
        }
      }
    }
    function applyPace(next) {
      var same = (pace.chaves || []).join("|") === ((next && next.chaves) || []).join("|");
      pace = next || {};
      if (!same) {
        fixedMonths = {};
        var cols = document.getElementById("sp-gantt-cols");
        if (cols) cols.innerHTML = "";
      }
      var note = document.getElementById("sp-gantt-note");
      var totalEl = document.getElementById("sp-gantt-total");
      var ritmoEl = document.getElementById("sp-gantt-ritmo");
      var helper = document.querySelector(".sp-hi-budget .sp-flight-note");
      if (helper) helper.textContent = pace.helper || "";
      if (totalEl) totalEl.textContent = pace.total > 0 ? "R$ " + formatMoney(pace.total) : "—";
      if (ritmoEl) {
        if (pace.ritmo > 0 && pace.granularidade === "semana") ritmoEl.textContent = "~R$ " + formatMoney(pace.ritmo) + "/semana";
        else if (pace.ritmo > 0) ritmoEl.textContent = "~R$ " + formatMoney(pace.ritmo) + "/mês";
        else ritmoEl.textContent = "—";
      }
      if (note) {
        if (pace.granularidade === "semana") note.textContent = "Abertura semanal nos canais. Começa menor e solta no meio e no fim. Ajuste a semana.";
        else if (pace.editavel) note.textContent = "Começa menor para aprender. Solta mais verba no meio e no fim. Ajuste o mês.";
        else note.textContent = "Informe uma duração (30 dias, 1 mês ou set a nov) para ver o voo.";
      }
      paintCalendar();
    }
    async function refreshPace() {
      var verbaEl = document.getElementById("sp-field-verba");
      var baseEl = document.getElementById("sp-field-verba-base");
      var periodoEl = document.getElementById("sp-field-periodo");
      try {
        var next = await postJson("/smart-planner/api/" + token + "/ritmo", {
          verba: verbaEl ? verbaEl.value : "",
          verba_valor: money(verbaEl && verbaEl.value),
          verba_base: baseEl ? baseEl.value : "total",
          periodo: periodoEl ? periodoEl.value : "",
          verba_alocacao: monthValues(),
        });
        applyPace(next);
      } catch (err) { /* ignore live calc */ }
    }
    function schedulePace() {
      window.clearTimeout(ritmoTimer);
      ritmoTimer = window.setTimeout(refreshPace, 280);
    }
    function refresh(method) {
      method = method || selectedMethod();
      var weights = allocate(selectedCanais(), objetivoEl ? objetivoEl.value : "", method, currentWeights());
      paintBars(weights);
      paintSummary();
      paintCalendar();
    }
    desk.addEventListener("change", function (event) {
      if (restoringMedia) return;
      var target = event.target;
      if (!target) return;
      if (target.name === "objetivo") {
        paintPicks();
        if (selectedMethod() !== "manual") refresh();
        return;
      }
      if (target.name === "canais") {
        refresh();
        return;
      }
      if (target.name === "mix_method") {
        setMethod(target.value);
        refresh(target.value);
      }
    });
    function applyLocked(lockedId, lockedPct) {
      var keys = selectedCanais();
      var prev = {};
      currentWeights().forEach(function (item) { prev[item.id] = item.pct; });
      var others = keys.filter(function (key) { return key !== lockedId; });
      var rest = Math.max(0, 100 - lockedPct);
      var otherSum = others.reduce(function (sum, key) { return sum + (prev[key] || 0); }, 0);
      var rawOthers = others.map(function (key) { return [key, otherSum > 0 ? (prev[key] || 0) : 1]; });
      var otherPcts = rawOthers.length ? normalizePcts(rawOthers) : {};
      var scaled = others.map(function (key) { return [key, (otherPcts[key] || 0) * rest / 100]; });
      var floors = scaled.map(function (item) { return [item[0], Math.floor(item[1])]; });
      var used = floors.reduce(function (sum, item) { return sum + item[1]; }, 0);
      var rem = rest - used;
      var order = scaled.slice().sort(function (a, b) {
        return (b[1] - Math.floor(b[1])) - (a[1] - Math.floor(a[1]));
      });
      var bump = {};
      for (var i = 0; i < rem && order[i]; i += 1) bump[order[i][0]] = true;
      var pcts = {};
      pcts[lockedId] = lockedPct;
      floors.forEach(function (item) { pcts[item[0]] = item[1] + (bump[item[0]] ? 1 : 0); });
      keys.forEach(function (key) {
        var row = bars.querySelector('li[data-canal="' + key + '"]');
        if (!row) return;
        var value = pcts[key] || 0;
        var em = row.querySelector("em");
        var fill = row.querySelector("b");
        var slider = row.querySelector("input[type=range]");
        if (em) em.textContent = value + "%";
        if (fill) fill.style.setProperty("--pct", String(value));
        if (slider && key !== lockedId) slider.value = String(value);
        var moneyEl = row.querySelector("small");
        var budget = budgetTotal();
        if (moneyEl && budget > 0) moneyEl.textContent = formatBRL(Math.round(budget * value / 100));
      });
      paintMixValidity();
      paintDirty();
    }
    if (bars) {
      bars.addEventListener("input", function (event) {
        var slider = event.target.closest("input[type=range]");
        if (!slider) return;
        setMethod("manual");
        applyLocked(slider.getAttribute("data-canal"), Math.max(0, Math.min(100, Number(slider.value) || 0)));
      });
    }
    paintPicks();
    paintBalanceMode();
    if (bars) {
      bars.querySelectorAll("b[data-pct]").forEach(function (fill) {
        fill.style.setProperty("--pct", fill.getAttribute("data-pct") || "0");
      });
    }
    var mediaOpen = document.getElementById("sp-media-open");
    var mediaClose = document.getElementById("sp-media-close");
    var mediaCancel = document.getElementById("sp-media-cancel");
    var mediaAuto = document.getElementById("sp-mix-auto");
    var releaseFocusTrap = null;
    function isMediaDirty() {
      return !!(mediaSnapshot && mediaSnapshot !== snapshotMedia());
    }
    function confirmCloseMedia() {
      if (!isMediaDirty()) return Promise.resolve(true);
      return askConfirmation("Há alterações não aplicadas. Fechar sem salvar?", "Descartar alterações?");
    }
    function closeMedia() {
      if (mediaDlg && typeof mediaDlg.close === "function" && mediaDlg.open) mediaDlg.close();
    }
    function visibleMediaControls() {
      if (!mediaDlg) return [];
      var nodes = mediaDlg.querySelectorAll("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])");
      return Array.prototype.filter.call(nodes, function (el) {
        if (el.hidden || el.closest("[hidden]")) return false;
        return el.offsetParent !== null;
      });
    }
    function firstMediaControl() {
      var search = document.getElementById("sp-mix-search");
      var searchWrap = document.getElementById("sp-mix-search-wrap");
      if (search && searchWrap && !searchWrap.hidden && search.offsetParent !== null) return search;
      var channel = mediaDlg && mediaDlg.querySelector('#sp-mix-channels input[name="canais"]');
      if (channel && !channel.closest("[hidden]")) return channel;
      var list = visibleMediaControls().filter(function (el) {
        return el.id !== "sp-media-close" && el.id !== "sp-media-cancel";
      });
      return list[0] || (mediaDlg && mediaDlg.querySelector("#sp-media-close"));
    }
    function trapMediaFocus(event) {
      if (!mediaDlg || event.key !== "Tab") return;
      var list = visibleMediaControls();
      if (!list.length) return;
      var first = list[0];
      var last = list[list.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    function openDeskModal() {
      var wasOpen = !!(mediaDlg && mediaDlg.open);
      mediaOpener = document.activeElement;
      if (!wasOpen) document.dispatchEvent(new Event("sp-media-will-open"));
      if (mediaDlg && typeof mediaDlg.showModal === "function" && !mediaDlg.open) mediaDlg.showModal();
      document.documentElement.classList.add("is-sp-media");
      if (!wasOpen) {
        mediaApplied = false;
        mediaSnapshot = snapshotMedia();
      }
      var status = document.getElementById("sp-media-status");
      if (status) status.textContent = "";
      paintDirty();
      paintCalendar();
      paintMixValidity();
      if (mediaDlg && !wasOpen) {
        mediaDlg.addEventListener("keydown", trapMediaFocus);
        releaseFocusTrap = function () {
          mediaDlg.removeEventListener("keydown", trapMediaFocus);
        };
        var first = firstMediaControl();
        if (first && typeof first.focus === "function") window.setTimeout(function () { first.focus(); }, 30);
      }
    }
    if (mediaOpen) {
      mediaOpen.addEventListener("click", openDeskModal);
    }
    if (mediaDlg) {
      mediaDlg.addEventListener("cancel", function (event) {
        event.preventDefault();
        requestCloseMedia();
      });
      mediaDlg.addEventListener("close", function () {
        document.documentElement.classList.remove("is-sp-media");
        if (releaseFocusTrap) releaseFocusTrap();
        releaseFocusTrap = null;
        if (!mediaApplied && mediaSnapshot) restoreMediaSnapshot(mediaSnapshot);
        mediaApplied = false;
        mediaSnapshot = "";
        if (mediaOpener && typeof mediaOpener.focus === "function") mediaOpener.focus();
        mediaOpener = null;
      });
    }
    async function requestCloseMedia() {
      if (!await confirmCloseMedia()) return;
      closeMedia();
    }
    if (mediaClose) mediaClose.addEventListener("click", requestCloseMedia);
    if (mediaCancel) mediaCancel.addEventListener("click", requestCloseMedia);
    if (mediaAuto) {
      mediaAuto.addEventListener("click", function () {
        var method = selectedMethod() === "manual" ? recommendedFor(objetivoEl ? objetivoEl.value : "")[0] : selectedMethod();
        if (method === "manual") method = "funil";
        setMethod(method);
        refresh(method);
      });
    }
    var calTable = document.getElementById("sp-cal-table");
    if (calTable) {
      calTable.addEventListener("click", function (event) {
        var button = event.target.closest("thead th[data-month] button");
        if (!button) return;
        var th = button.closest("[data-month]");
        var box = document.getElementById("sp-month-weeks");
        if (!th || !box) return;
        var key = th.getAttribute("data-month");
        var open = th.getAttribute("aria-expanded") === "true";
        calTable.querySelectorAll("thead th[data-month]").forEach(function (item) {
          item.setAttribute("aria-expanded", "false");
        });
        if (open) {
          box.hidden = true;
          box.textContent = "";
          return;
        }
        th.setAttribute("aria-expanded", "true");
        var weeks = monthWeekLabels(key);
        box.hidden = weeks.length === 0;
        box.textContent = weeks.length ? (th.textContent || key) + ": " + weeks.join(" · ") : "";
      });
    }
    if (mediaApply) {
      mediaApply.addEventListener("click", async function () {
        if (!mixValid(currentWeights())) {
          paintMixValidity();
          return;
        }
        var status = document.getElementById("sp-media-status");
        setLoading(mediaApply, true);
        if (status) status.textContent = "Aplicando…";
        try {
          await postJson("/smart-planner/api/" + token + "/revisao", collectReview());
          paintSummary();
          paintMiniCal();
          mediaApplied = true;
          mediaSnapshot = snapshotMedia();
          paintDirty();
          if (status) status.textContent = "Aplicado no plano.";
          toast("Mix e calendário aplicados.", "success");
          closeMedia();
        } catch (error) {
          if (status) status.textContent = "";
          toast(error.message, "error");
        } finally {
          setLoading(mediaApply, false);
        }
      });
    }
    var verbaEl = document.getElementById("sp-field-verba");
    var baseEl = document.getElementById("sp-field-verba-base");
    var periodoEl = document.getElementById("sp-field-periodo");
    if (verbaEl) verbaEl.addEventListener("input", schedulePace);
    if (baseEl) baseEl.addEventListener("change", schedulePace);
    if (periodoEl) periodoEl.addEventListener("input", schedulePace);
    var cols = document.getElementById("sp-gantt-cols");
    if (cols) {
      cols.addEventListener("input", function (event) {
        var input = event.target.closest("[data-chave]");
        if (!input || !pace.editavel) return;
        input.value = formatMoney(money(input.value));
        fixedMonths[input.getAttribute("data-chave")] = true;
        var keys = pace.chaves || [];
        var total = parseInt(pace.total, 10) || 0;
        var current = monthValues();
        var locked = 0;
        var free = [];
        keys.forEach(function (key) {
          if (fixedMonths[key]) locked += current[key] || 0;
          else free.push(key);
        });
        var rest = Math.max(0, total - locked);
        var freeSum = free.reduce(function (sum, key) { return sum + (current[key] || 0); }, 0);
        free.forEach(function (key, index) {
          var field = cols.querySelector('[data-chave="' + key + '"]');
          if (!field) return;
          var next = freeSum > 0 ? Math.floor(((current[key] || 0) / freeSum) * rest) : Math.floor(rest / Math.max(free.length, 1));
          if (index === free.length - 1) {
            var used = free.slice(0, -1).reduce(function (sum, item) { return sum + money(cols.querySelector('[data-chave="' + item + '"]') && cols.querySelector('[data-chave="' + item + '"]').value); }, 0);
            next = Math.max(0, rest - used);
          }
          field.value = formatMoney(next);
        });
        paintCalendar();
      });
    }
    var bootWeights = currentWeights().map(function (item) {
      return {
        id: item.id,
        label: (spec.labels || {})[item.id] || item.id,
        group: groupOf(item.id),
        pct: item.pct,
      };
    });
    if (bootWeights.length) paintBars(bootWeights);
    paintSummary();
    paintCalendar();

    function collectReview() {
      var data = new FormData(form);
      return {
        briefing: data.get("briefing"),
        canais: selectedCanais(),
        mix: {
          method: selectedMethod(),
          weights: currentWeights(),
          locked: selectedMethod() === "manual",
          progress: false,
        },
        places: collectPlaces(),
        interativos: collectInterativos(),
        verba_alocacao: monthValues(),
        campos: {
          campanha: data.get("campanha"),
          cliente: data.get("cliente"),
          cliente_id: data.get("cliente_id") || null,
          agencia: data.get("agencia"),
          agencia_id: data.get("agencia_id") || null,
          cx_client_id: data.get("cx_client_id") || null,
          objetivo: data.get("objetivo"),
          objetivo_texto: data.get("objetivo_texto"),
          publico: data.get("publico"),
          verba: data.get("verba"),
          verba_base: data.get("verba_base"),
          periodo: data.get("periodo"),
          praca: data.get("praca"),
          praca_detalhe: data.get("praca_detalhe"),
          contexto: data.get("contexto"),
          observacoes: data.get("observacoes"),
          criativos: data.get("criativos"),
          conteudo_capturado: data.get("conteudo_capturado"),
          kpis: data.get("kpis"),
          places: collectPlaces(),
          interativos: collectInterativos(),
          anunciante_confidencial: data.get("anunciante_confidencial") === "1" || data.get("anunciante_confidencial") === "on",
        },
      };
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      try {
        await postJson("/smart-planner/api/" + token + "/revisao", collectReview());
        toast("Revisão salva.", "success");
      } catch (error) {
        toast(error.message, "error");
      }
    });

    setupChannelPicker(desk);
    setupKpiChips();
    setupPlacesDesk();
    setupGeoModal();
    setupInterativosDesk();
    setupReviewSections();
    setupCompleteness();
    setupReviewAutosave(collectReview);
    setupReviewActions(collectReview);
  }
  setupMixDesk();

  function setupReviewSections() {
    var accs = Array.prototype.slice.call(document.querySelectorAll(".sp-review .sp-acc"));
    if (!accs.length) return;
    var form = document.getElementById("sp-revisao-form");

    function fieldFilled(el) {
      if (!el) return false;
      if (el.type === "checkbox" || el.type === "radio") return el.checked;
      return String(el.value || "").trim().length > 0;
    }

    function gapIds() {
      return Array.prototype.slice.call(document.querySelectorAll(".sp-complete-gaps [data-gap]")).map(function (link) {
        return gapTarget(link.getAttribute("data-gap") || link.textContent);
      });
    }

    function sectionStats(acc) {
      var fields = acc.querySelectorAll("input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea");
      var filled = 0;
      var total = 0;
      fields.forEach(function (el) {
        total += 1;
        if (fieldFilled(el)) filled += 1;
      });
      var required = (acc.getAttribute("data-required") || "").split(",").filter(Boolean);
      var missing = required.filter(function (id) { return !fieldFilled(document.getElementById(id)); });
      var hits = gapIds();
      var hasGap = required.some(function (id) { return hits.indexOf(id) !== -1; })
        || Array.prototype.some.call(fields, function (el) { return hits.indexOf(el.id) !== -1; });
      return {
        filled: filled,
        total: total,
        incomplete: missing.length > 0 || hasGap,
      };
    }

    function paintMeta() {
      accs.forEach(function (acc) {
        var stats = sectionStats(acc);
        var meta = acc.querySelector("[data-acc-meta]");
        var summary = acc.querySelector("summary");
        if (meta) {
          if (!stats.total) meta.textContent = acc.getAttribute("data-acc") === "source" ? "fonte" : "";
          else meta.textContent = stats.total + (stats.total === 1 ? " campo" : " campos");
          meta.classList.toggle("is-gap", stats.incomplete);
        }
        acc.classList.toggle("is-gap", stats.incomplete);
        if (summary) summary.setAttribute("aria-expanded", acc.open ? "true" : "false");
      });
    }

    function paintChecks() {
      var rootChecks = document.getElementById("sp-complete-checks");
      if (!rootChecks) return;
      var hasCanal = document.querySelector('#sp-mix-channels input[name="canais"]:checked');
      var state = {
        campanha: fieldFilled(document.getElementById("sp-field-campanha")),
        objetivo: fieldFilled(document.getElementById("sp-objetivo")),
        publico: fieldFilled(document.getElementById("sp-field-publico")),
        verba: /\d/.test(String((document.getElementById("sp-field-verba") || {}).value || "")),
        periodo: fieldFilled(document.getElementById("sp-field-periodo")),
        praca: fieldFilled(document.getElementById("sp-field-praca")),
        kpis: !!document.querySelector("#sp-kpi-chips button.is-on"),
        canais: !!hasCanal,
      };
      var keys = Object.keys(state);
      var filled = keys.filter(function (key) { return state[key]; }).length;
      var score = Math.round((filled / keys.length) * 100);
      var missing = keys.filter(function (key) { return !state[key]; });
      rootChecks.querySelectorAll("[data-check]").forEach(function (item) {
        item.classList.toggle("is-on", !!state[item.getAttribute("data-check")]);
      });
      var num = document.getElementById("sp-score-num");
      var fill = document.getElementById("sp-score-fill");
      var title = document.getElementById("sp-complete-title");
      var copy = document.getElementById("sp-complete-copy");
      var bar = document.getElementById("sp-complete-bar");
      var card = document.querySelector(".sp-complete");
      if (num) num.innerHTML = score + "<small>/100</small>";
      if (fill) fill.setAttribute("stroke-dasharray", (score * 94.2 / 100).toFixed(1) + " 94.2");
      if (bar) bar.value = score;
      var tom = score >= 70 ? "alto" : score >= 35 ? "medio" : "baixo";
      if (card) card.setAttribute("data-tom", tom);
      if (title) title.textContent = score >= 70 ? "Dá para gerar" : score >= 35 ? "Dá para gerar" : "Incompleto";
      if (copy) {
        copy.textContent = missing.length
          ? "Dá para gerar. Falta só " + missing.join(", ") + "."
          : "Dá para gerar. Os oito campos da mesa estão preenchidos.";
      }
      document.querySelectorAll("#sp-complete-gaps [data-gap]").forEach(function (link) {
        var target = gapTarget(link.getAttribute("data-gap") || link.textContent);
        var map = {
          "sp-field-campanha": "campanha",
          "sp-objetivo": "objetivo",
          "sp-field-publico": "publico",
          "sp-field-verba": "verba",
          "sp-field-periodo": "periodo",
          "sp-field-praca": "praca",
          "sp-mix-channels": "canais",
        };
        var key = map[target];
        var li = link.closest("li");
        if (li) li.hidden = !!(key && state[key]);
      });
      var gaps = document.getElementById("sp-complete-gaps");
      if (gaps) {
        var visible = Array.prototype.slice.call(gaps.querySelectorAll("li")).filter(function (li) { return !li.hidden; });
        gaps.hidden = visible.length === 0;
      }
    }

    function autoOpen() {
      accs.forEach(function (acc) {
        var id = acc.getAttribute("data-acc");
        if (id === "narrative" || id === "source") {
          acc.open = false;
          return;
        }
        if (id === "extracted") {
          acc.open = sectionStats(acc).filled > 0;
          return;
        }
        acc.open = true;
      });
    }

    accs.forEach(function (acc) {
      var summary = acc.querySelector("summary");
      if (summary) summary.setAttribute("aria-expanded", acc.open ? "true" : "false");
      acc.addEventListener("toggle", function () {
        if (summary) summary.setAttribute("aria-expanded", acc.open ? "true" : "false");
      });
    });
    paintMeta();
    paintChecks();
    autoOpen();
    if (form) {
      form.addEventListener("input", function () { paintMeta(); paintChecks(); });
      form.addEventListener("change", function () { paintMeta(); paintChecks(); });
    }
    var desk = document.getElementById("sp-wizard") || document.getElementById("sp-hi-plan");
    if (desk) {
      desk.addEventListener("change", function (event) {
        if (event.target && event.target.name === "canais") paintChecks();
      });
    }
  }

  function gapTarget(text) {
    var t = String(text || "").toLowerCase();
    if (/objetivo/.test(t)) return "sp-objetivo";
    if (/p[uú]blic/.test(t)) return "sp-field-publico";
    if (/verba|or[cç]amento|budget/.test(t)) return "sp-field-verba";
    if (/per[ií]odo|prazo|dura[cç]/.test(t)) return "sp-field-periodo";
    if (/pra[cç]a|local|cidade/.test(t)) return "sp-field-praca";
    if (/campanha/.test(t) && !/objetivo/.test(t)) return "sp-field-campanha";
    if (/canais|canal/.test(t)) return "sp-mix-channels";
    if (/\bkpis?\b|indicador/.test(t)) return "sp-field-kpis";
    if (/anunciante|cliente/.test(t) && !/p[uú]blic/.test(t)) return "sp-field-cliente";
    return "sp-objetivo";
  }

  function setupCompleteness() {
    document.querySelectorAll(".sp-complete-gaps [data-gap]").forEach(function (link) {
      var id = gapTarget(link.getAttribute("data-gap") || link.textContent);
      link.setAttribute("href", "#" + id);
      link.setAttribute("data-focus", id);
      link.addEventListener("click", function (event) {
        event.preventDefault();
        focusField(id);
      });
    });
  }

  function setupChannelPicker(desk) {
    var rootDesk = desk || document.getElementById("sp-hi-plan") || root;
    var searchWrap = document.getElementById("sp-mix-search-wrap");
    var search = document.getElementById("sp-mix-search");
    var moreBtn = document.getElementById("sp-mix-more-btn");
    var chips = document.getElementById("sp-mix-chips");
    var labels = rootDesk.querySelectorAll(".sp-mix-checks label");
    if (!labels.length) return;
    if (labels.length > 8 && searchWrap) searchWrap.hidden = false;
    var extras = rootDesk.querySelectorAll(".sp-mix-checks label[data-extra]");
    if (moreBtn && extras.length) {
      moreBtn.hidden = false;
      moreBtn.addEventListener("click", function () {
        var open = moreBtn.getAttribute("aria-expanded") === "true";
        extras.forEach(function (label) { label.hidden = open; });
        moreBtn.setAttribute("aria-expanded", open ? "false" : "true");
        moreBtn.textContent = open ? "Ver mais canais" : "Ver menos canais";
      });
    }
    function paintChips() {
      var spec = readJson("sp-mix-spec", {});
      var selected = Array.prototype.slice.call(rootDesk.querySelectorAll('input[name="canais"]:checked'));
      var count = document.getElementById("sp-mix-count");
      if (count) count.textContent = selected.length ? selected.length + (selected.length === 1 ? " canal selecionado" : " canais selecionados") : "Nenhum canal selecionado";
      if (!chips) return;
      chips.hidden = selected.length === 0;
      chips.innerHTML = selected.map(function (input) {
        var name = (input.closest("label") && input.closest("label").querySelector("span:last-child"));
        var label = name ? name.textContent : input.value;
        var logo = (spec.logos || {})[input.value];
        var mark = logo
          ? '<img class="sp-mix-logo" src="' + escapeHtml(logo) + '" alt="" aria-hidden="true">'
          : '<span class="sp-mix-fallback" aria-hidden="true">' + escapeHtml(String(label).slice(0, 2)) + "</span>";
        return '<span class="sp-mix-chip">' + mark + escapeHtml(label) + '<button type="button" data-uncheck="' + escapeHtml(input.value) + '" aria-label="Remover ' + escapeHtml(label) + '">×</button></span>';
      }).join("");
    }
    if (chips) {
      chips.addEventListener("click", function (event) {
        var button = event.target.closest("[data-uncheck]");
        if (!button) return;
        var input = rootDesk.querySelector('input[name="canais"][value="' + button.getAttribute("data-uncheck") + '"]');
        if (input) {
          input.checked = false;
          input.dispatchEvent(new Event("change", { bubbles: true }));
        }
        paintChips();
      });
    }
    if (search) {
      search.addEventListener("input", function () {
        var q = search.value.trim().toLowerCase();
        labels.forEach(function (label) {
          var match = !q || (label.getAttribute("data-label") || "").indexOf(q) !== -1;
          if (q) label.hidden = !match;
          else label.hidden = label.hasAttribute("data-extra") && moreBtn && moreBtn.getAttribute("aria-expanded") !== "true";
        });
      });
    }
    rootDesk.addEventListener("change", function (event) {
      if (event.target && event.target.name === "canais") paintChips();
    });
    paintChips();
  }

  function setupKpiChips() {
    var box = document.getElementById("sp-kpi-chips");
    var field = document.getElementById("sp-field-kpis");
    var spec = readJson("sp-mix-spec", {});
    if (!box || !field) return;
    function selectedCanaisNow() {
      return Array.prototype.slice.call(document.querySelectorAll('#sp-mix-channels input[name="canais"]:checked')).map(function (el) {
        return el.value;
      });
    }
    function currentList() {
      return String(field.value || "").split(",").map(function (item) { return item.trim(); }).filter(Boolean);
    }
    function paint() {
      var canais = selectedCanaisNow();
      var groups = {};
      canais.forEach(function (key) {
        var group = (spec.groups || {})[key];
        (spec.kpis && spec.kpis[group] || []).forEach(function (label) { groups[label] = true; });
      });
      var suggestions = Object.keys(groups);
      var picked = currentList();
      box.innerHTML = suggestions.map(function (label) {
        return '<button type="button" data-kpi="' + escapeHtml(label) + '" class="' + (picked.indexOf(label) !== -1 ? "is-on" : "") + '">' + escapeHtml(label) + "</button>";
      }).join("");
    }
    box.addEventListener("click", function (event) {
      var button = event.target.closest("[data-kpi]");
      if (!button) return;
      var label = button.getAttribute("data-kpi");
      var picked = currentList();
      var next = picked.indexOf(label) === -1 ? picked.concat([label]) : picked.filter(function (item) { return item !== label; });
      field.value = next.join(", ");
      field.dispatchEvent(new Event("input", { bubbles: true }));
      paint();
    });
    document.addEventListener("change", function (event) {
      if (event.target && event.target.name === "canais") paint();
    });
    paint();
  }

  function setupPlacesDesk() {
    var desk = document.getElementById("sp-places-desk");
    var list = document.getElementById("sp-places-list");
    var catalog = readJson("sp-places-catalog", []);
    var boot = readJson("sp-places-boot", []);
    if (!desk || !list) return;
    var selected = {};
    boot.forEach(function (item) {
      if (item && item.slug) selected[item.slug] = item;
    });
    function placeChecked() {
      var box = document.querySelector('#sp-mix-channels input[name="canais"][value="places"]');
      return !!(box && box.checked);
    }
    function paint() {
      desk.hidden = !placeChecked();
      if (desk.hidden) return;
      list.innerHTML = catalog.map(function (place) {
        var current = selected[place.slug] || {};
        var on = !!current.slug || !!current.point_ids;
        var metrics = place.metrics || {};
        return '<article class="sp-place-card">'
          + '<label><input type="checkbox" name="places" value="' + place.slug + '"' + (on ? " checked" : "") + "> "
          + escapeHtml(place.title || place.slug) + (place.city_label ? " · " + escapeHtml(place.city_label) : "") + "</label>"
          + (place.type_label ? '<small class="sp-place-type">' + escapeHtml(place.type_label) + '</small>' : '')
          + ((metrics.addressable || metrics.four_weeks) ? '<div class="sp-place-audience">' + (metrics.addressable ? '<span><b>Audiência endereçável</b>' + escapeHtml(metrics.addressable) + '</span>' : '') + (metrics.four_weeks ? '<span><b>Média em 4 semanas</b>' + escapeHtml(metrics.four_weeks) + '</span>' : '') + '</div>' : '')
          + (place.investment_label ? '<p class="sp-place-investment">Mínimo: ' + escapeHtml(place.investment_label) + '</p>' : '<p class="sp-place-investment is-unknown">Mínimo comercial a confirmar</p>')
          + "</article>";
      }).join("");
    }
    list.addEventListener("change", function (event) {
      var target = event.target;
      if (!target) return;
      if (target.name === "places") {
        if (target.checked) selected[target.value] = selected[target.value] || { slug: target.value, point_ids: [], apps: [] };
        else delete selected[target.value];
        paint();
        return;
      }
    });
    document.addEventListener("change", function (event) {
      if (event.target && event.target.name === "canais" && event.target.value === "places") paint();
    });
    paint();
  }

  function setupGeoModal() {
    var dialog = document.getElementById("sp-geo-modal");
    var open = document.getElementById("sp-geo-open");
    var apply = document.getElementById("sp-geo-apply");
    var cancel = document.getElementById("sp-geo-cancel");
    var list = document.getElementById("sp-geo-list");
    var state = document.getElementById("sp-geo-state");
    var search = document.getElementById("sp-geo-search");
    var instruction = document.getElementById("sp-geo-instruction");
    var detail = document.getElementById("sp-field-praca-detalhe");
    var market = document.getElementById("sp-field-praca");
    var selectedNote = document.getElementById("sp-geo-selected");
    var selectedList = document.getElementById("sp-geo-selected-list");
    var interpretation = document.getElementById("sp-geo-interpretation");
    var interpret = document.getElementById("sp-geo-interpret");
    var catalogStatus = document.getElementById("sp-geo-catalog-status");
    if (!dialog || !open || !list || !detail) return;
    var cities = [];
    var states = [];
    var selected = {};
    var loaded = false;
    var rmbh = {"Belo Horizonte":1,"Betim":1,"Contagem":1,"Nova Lima":1,"Ribeirão das Neves":1,"Santa Luzia":1,"Sabará":1,"Caeté":1,"Vespasiano":1,"Lagoa Santa":1,"Pedro Leopoldo":1,"Confins":1,"Esmeraldas":1,"Ibirité":1,"Igarapé":1,"Juatuba":1,"Mário Campos":1,"Mateus Leme":1,"Raposos":1,"Rio Acima":1,"Rio Manso":1,"São Joaquim de Bicas":1,"Sarzedo":1,"Taquaraçu de Minas":1};
    function normalize(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
    function cityKey(item) { return String(item.id); }
    function stateOf(item) { return item && item.microrregiao && item.microrregiao.mesorregiao && item.microrregiao.mesorregiao.UF ? item.microrregiao.mesorregiao.UF.sigla : ""; }
    function paintSelected() {
      var picked = Object.keys(selected).map(function (key) { return cities.find(function (item) { return cityKey(item) === key; }); }).filter(Boolean);
      if (selectedNote) selectedNote.textContent = picked.length ? picked.length + " município" + (picked.length === 1 ? "" : "s") + " selecionado" + (picked.length === 1 ? "" : "s") : "Nenhuma área selecionada";
      if (selectedList) selectedList.innerHTML = picked.length ? picked.slice(0, 18).map(function (item) { return '<span>' + escapeHtml(item.nome) + ' · ' + escapeHtml(item.uf) + '</span>'; }).join("") + (picked.length > 18 ? '<small>+' + (picked.length - 18) + ' municípios</small>' : "") : "<span>Nenhum município selecionado.</span>";
    }
    function visibleCities() {
      var query = normalize(search && search.value);
      if (!query && !state.value) return [];
      return cities.filter(function (item) { return (!state.value || item.uf === state.value) && (!query || normalize(item.nome + " " + item.uf).indexOf(query) !== -1); }).slice(0, 240);
    }
    function paint() {
      paintSelected();
      if (!loaded) { list.innerHTML = "<p class=\"sp-geo-empty\">Carregando o catálogo oficial…</p>"; return; }
      var items = visibleCities();
      if (!items.length) { list.innerHTML = '<p class="sp-geo-empty">Escolha um estado ou digite ao menos parte do nome de uma cidade.</p>'; return; }
      list.innerHTML = items.map(function (item) {
        var key = cityKey(item);
        return '<label class="sp-geo-city"><input type="checkbox" data-geo-city="' + escapeHtml(key) + '"' + (selected[key] ? " checked" : "") + '><span><strong>' + escapeHtml(item.nome) + '</strong><small>' + escapeHtml(item.uf + " · Código IBGE " + item.id) + '</small></span><em><b>Total</b> A validar<br><b>Digital</b> A validar</em></label>';
      }).join("");
    }
    function choose(items) { selected = {}; items.forEach(function (item) { selected[cityKey(item)] = true; }); paint(); }
    function applyInstruction() {
      var raw = (instruction && instruction.value || "").trim();
      var normalized = normalize(raw);
      if (!raw) return;
      if (/brasil|todo o pais|todo pais/.test(normalized)) { choose(cities); if (interpretation) interpretation.textContent = "Brasil inteiro: todos os municípios do catálogo IBGE foram selecionados."; return; }
      var ufMatches = states.filter(function (item) { return normalized.indexOf(normalize(item.sigla)) !== -1 || normalized.indexOf(normalize(item.nome)) !== -1; });
      if (/regiao metropolitana.*bh|rmbh/.test(normalized)) { choose(cities.filter(function (item) { return item.uf === "MG" && rmbh[item.nome]; })); if (interpretation) interpretation.textContent = "Região Metropolitana de Belo Horizonte interpretada pelo conjunto de municípios definido para a cobertura."; return; }
      if (ufMatches.length) {
        var chosen = cities.filter(function (item) { return ufMatches.some(function (uf) { return uf.sigla === item.uf; }); });
        if (/interior/.test(normalized)) chosen = chosen.filter(function (item) { return !(item.uf === "MG" && rmbh[item.nome]); });
        choose(chosen); if (state && ufMatches.length === 1) state.value = ufMatches[0].sigla;
        if (interpretation) interpretation.textContent = (/(interior)/.test(normalized) ? "Interior interpretado; capitais e municípios metropolitanos foram excluídos quando mapeados." : "Estados identificados e municípios selecionados a partir do catálogo IBGE.");
        return;
      }
      if (interpretation) interpretation.textContent = "Não identifiquei uma UF. Use o estado, uma cidade ou escreva a cobertura com mais detalhes.";
    }
    function shortcut(name) {
      if (name === "brasil") { instruction.value = "Brasil inteiro."; applyInstruction(); return; }
      if (name === "state" && state.value) { instruction.value = state.options[state.selectedIndex].text + " inteiro."; applyInstruction(); return; }
      if (name === "interior" && state.value) { instruction.value = "Interior de " + state.options[state.selectedIndex].text + "."; applyInstruction(); return; }
      if (name === "rmbh") { instruction.value = "Região Metropolitana de Belo Horizonte."; applyInstruction(); }
    }
    function loadCatalog() {
      Promise.all([fetch("https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome"), fetch("https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome")]).then(function (responses) { return Promise.all(responses.map(function (response) { if (!response.ok) throw new Error("IBGE indisponível"); return response.json(); })); }).then(function (payload) {
        states = payload[0].map(function (item) { return { id: item.id, sigla: item.sigla, nome: item.nome }; });
        cities = payload[1].map(function (item) { return { id: item.id, nome: item.nome, uf: stateOf(item) }; }).filter(function (item) { return item.uf; });
        var current = normalize(detail.value); cities.forEach(function (item) { if (current.indexOf(normalize(item.nome)) !== -1) selected[cityKey(item)] = true; });
        states.forEach(function (item) { var option = document.createElement("option"); option.value = item.sigla; option.textContent = item.sigla + " · " + item.nome; state.appendChild(option); });
        loaded = true; if (catalogStatus) catalogStatus.textContent = cities.length.toLocaleString("pt-BR") + " municípios carregados do IBGE. Escolha um estado ou busque uma cidade."; paint();
      }).catch(function () { loaded = false; if (catalogStatus) catalogStatus.textContent = "Não foi possível carregar o IBGE agora. Digite uma instrução e tente novamente."; list.innerHTML = '<p class="sp-geo-empty">Catálogo indisponível. A instrução de cobertura será preservada para revisão.</p>'; });
    }
    open.addEventListener("click", function () { if (dialog.showModal) dialog.showModal(); else dialog.setAttribute("open", "open"); paint(); if (!loaded && !cities.length) loadCatalog(); });
    if (cancel) cancel.addEventListener("click", function () { dialog.close(); });
    if (interpret) interpret.addEventListener("click", applyInstruction);
    state.addEventListener("change", paint); if (search) search.addEventListener("input", paint);
    dialog.querySelectorAll("[data-geo-shortcut]").forEach(function (button) { button.addEventListener("click", function () { shortcut(button.getAttribute("data-geo-shortcut")); }); });
    list.addEventListener("change", function (event) { var key = event.target.getAttribute("data-geo-city"); if (!key) return; if (event.target.checked) selected[key] = true; else delete selected[key]; paint(); });
    apply.addEventListener("click", function () {
      var names = Object.keys(selected).map(function (key) { var item = cities.find(function (city) { return cityKey(city) === key; }); return item ? item.nome + " (" + item.uf + ")" : ""; }).filter(Boolean);
      var extra = (instruction && instruction.value || "").trim();
      var coverage = names.length > 80 ? extra || (names.length === cities.length ? "Brasil inteiro." : names.length + " municípios selecionados no IBGE.") : names.join(", ");
      detail.value = [coverage, extra && coverage !== extra ? extra : ""].filter(Boolean).join(". ");
      if (market && (names.length || extra)) market.value = "geolocalizada";
      detail.dispatchEvent(new Event("input", { bubbles: true }));
      dialog.close();
    });
    paint();
  }

  function setupInterativosDesk() {
    var desk = document.getElementById("sp-interativos-desk");
    var formats = document.getElementById("sp-interativos-formats");
    var note = document.getElementById("sp-interativos-note");
    var spec = readJson("sp-mix-spec", {});
    var boot = readJson("sp-interativos-boot", {});
    var box = document.querySelector('#sp-mix-channels input[name="canais"][value="interativos"]');
    var label = box && box.closest("label");
    if (!desk || !formats) return;
    function canaisNow() {
      return Array.prototype.slice.call(document.querySelectorAll('#sp-mix-channels input[name="canais"]:checked')).map(function (el) {
        return el.value;
      });
    }
    function paint() {
      var allowed = portalSelected(canaisNow());
      if (label) label.classList.toggle("is-off", !allowed);
      if (box && !allowed && box.checked) box.checked = false;
      desk.hidden = !(box && box.checked && allowed);
      if (note) note.textContent = allowed ? "Formatos só nestes portais." : "Interativos entram no portal.";
      var picked = (boot.formats || []);
      formats.innerHTML = (spec.interativosFormats || []).map(function (item) {
        return '<label><input type="checkbox" name="interativos_formats" value="' + item.id + '"'
          + (picked.indexOf(item.id) !== -1 ? " checked" : "") + "> " + escapeHtml(item.label) + "</label>";
      }).join("");
    }
    document.addEventListener("change", function (event) {
      if (!event.target) return;
      if (event.target.name === "canais") {
        if (event.target.value === "interativos" && event.target.checked && !portalSelected(canaisNow().concat(["interativos"]))) {
          event.target.checked = false;
          if (note) note.textContent = "Interativos entram no portal.";
        }
        paint();
      }
      if (event.target.name === "interativos_formats") {
        boot.formats = collectInterativos().formats;
      }
    });
    paint();
  }

  function setupReviewAutosave(collectReview) {
    var form = document.getElementById("sp-revisao-form");
    var saveBtn = document.getElementById("sp-save-draft");
    if (!form || typeof collectReview !== "function") return;
    var timer = null;
    function mediaOpen() {
      var dlg = document.getElementById("sp-media");
      return !!(dlg && dlg.open);
    }
    async function persist(manual) {
      if (!manual && mediaOpen()) return;
      setLive("Salvando…");
      try {
        await postJson("/smart-planner/api/" + token + "/revisao", collectReview());
        setLive("Rascunho salvo agora");
        if (manual) toast("Rascunho salvo.", "success");
      } catch (error) {
        setLive("Erro ao salvar rascunho");
        if (manual) toast(error.message, "error");
      }
    }
    function flushPendingReview() {
      if (!timer) return;
      window.clearTimeout(timer);
      timer = null;
      persist();
    }
    document.addEventListener("sp-media-will-open", flushPendingReview);
    form.addEventListener("input", function () {
      if (mediaOpen()) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(persist, 900);
    });
    form.addEventListener("change", function () {
      if (mediaOpen()) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(persist, 400);
    });
    var narrative = document.getElementById("sp-narrative");
    if (narrative) {
      narrative.addEventListener("input", function () { form.dispatchEvent(new Event("input", { bubbles: true })); });
      narrative.addEventListener("change", function () { form.dispatchEvent(new Event("change", { bubbles: true })); });
    }
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        window.clearTimeout(timer);
        persist(true);
      });
    }
  }

  function setupReviewActions(collectReview) {
    var original = document.getElementById("sp-original");
    var compiled = document.getElementById("sp-compiled");
    var compiledOpen = document.getElementById("sp-compiled-open");
    if (compiledOpen) {
      compiledOpen.addEventListener("click", function () {
        if (compiled && typeof compiled.showModal === "function") compiled.showModal();
      });
    }
    document.querySelectorAll("#sp-original-open").forEach(function (button) {
      button.addEventListener("click", function () {
        if (original && typeof original.showModal === "function") original.showModal();
      });
    });

    var rebrief = document.getElementById("sp-rebrief-btn");
    if (rebrief) {
      rebrief.addEventListener("click", async function () {
        setLoading(rebrief, true);
        try {
          var result = await postJson("/smart-planner/api/" + token + "/rebrief", collectReview());
          var narrative = document.getElementById("sp-narrative");
          if (narrative && result.briefing) narrative.value = result.briefing;
          toast("Briefing reescrito com o plano atual.", "success");
        } catch (error) {
          toast(error.message, "error");
        } finally {
          setLoading(rebrief, false);
        }
      });
    }

    var genDlg = document.getElementById("sp-gen");
    var genOpen = document.getElementById("sp-gen-open");
    if (genOpen) {
      genOpen.addEventListener("click", async function () {
        var objetivo = document.getElementById("sp-objetivo");
        var hasCanal = document.querySelector('#sp-mix-channels input[name="canais"]:checked');
        var hasKpi = document.querySelector("#sp-kpi-chips button.is-on");
        if (objetivo && !objetivo.value) {
          focusField("sp-objetivo");
        } else if (!hasKpi) {
          focusField("sp-kpi-chips");
          toast("Selecione pelo menos um KPI antes de gerar.", "error");
          return;
        } else if (!hasCanal) {
          focusField("sp-mix-channels");
        }
        setLoading(genOpen, true);
        try {
          await postJson("/smart-planner/api/" + token + "/revisao", collectReview());
          if (genDlg && typeof genDlg.showModal === "function") genDlg.showModal();
        } catch (error) {
          toast(error.message, "error");
        } finally {
          setLoading(genOpen, false);
        }
      });
    }

    document.querySelectorAll("[data-gen-mode]").forEach(function (button) {
      button.addEventListener("click", async function () {
        var mode = button.getAttribute("data-gen-mode");
        if (genDlg && typeof genDlg.close === "function") genDlg.close();
        var stop = showCompileOverlay("", mode);
        try {
          var result = await postJson("/smart-planner/api/" + token + "/gerar", { plan_mode: mode });
          if (result.started) await waitForGeneration(mode);
          stop();
          hideCompileOverlay();
          window.setTimeout(function () {
            window.location.href = result.redirect;
          }, 400);
        } catch (error) {
          stop();
          failCompileOverlay(error.message);
        }
      });
    });
  }

  function setupCanais() {
    var form = document.getElementById("sp-canais-form");
    if (!form) return;
    var bootEl = document.getElementById("sp-cb-boot");
    var boot = {};
    try { boot = JSON.parse(bootEl ? bootEl.textContent : "{}"); } catch (err) { boot = {}; }
    var catalog = boot.catalog || {};
    var pace = boot.pace || {};
    var verbaInput = document.getElementById("sp-cb-verba");
    var baseEl = document.getElementById("sp-cb-verba-base");
    var periodoEl = document.getElementById("sp-cb-periodo");
    var list = document.getElementById("sp-cb-list");
    var chips = document.getElementById("sp-cb-chips");
    var catalogBox = document.getElementById("sp-cb-catalog");
    var addBtn = document.getElementById("sp-cb-add");
    var track = document.getElementById("sp-gantt-track");
    var cols = document.getElementById("sp-gantt-cols");
    var gantt = document.getElementById("sp-gantt");
    var fixedMonths = {};
    var fixedChannels = {};
    var ritmoTimer = null;

    function money(value) {
      return parseInt(String(value || "").replace(/\D/g, ""), 10) || 0;
    }
    function format(value) {
      return Math.max(0, value).toLocaleString("pt-BR");
    }
    function verbaValor() {
      return money(verbaInput && verbaInput.value);
    }
    function verbaBase() {
      return baseEl && baseEl.value === "mensal" ? "mensal" : "total";
    }
    function rows() {
      return list ? Array.prototype.slice.call(list.querySelectorAll(".sp-cb-row")) : [];
    }
    function canais() {
      return rows().map(function (row) { return row.getAttribute("data-canal"); });
    }
    function channelValues() {
      var out = {};
      rows().forEach(function (row) {
        var input = row.querySelector(".sp-cb-channel-input");
        out[row.getAttribute("data-canal")] = input ? money(input.value) : 0;
      });
      return out;
    }
    function monthValues() {
      var out = {};
      if (!cols) return out;
      cols.querySelectorAll("[data-chave]").forEach(function (input) {
        out[input.getAttribute("data-chave")] = money(input.value);
      });
      return out;
    }
    function tone(index, total) {
      if (total <= 1) return "is-release";
      var t = index / (total - 1);
      if (t < 0.34) return "is-learn";
      if (t < 0.67) return "is-mid";
      return "is-release";
    }
    function redistributeMonths() {
      var keys = (pace.chaves || []).slice();
      var total = parseInt(pace.total, 10) || 0;
      if (!keys.length || total <= 0 || !pace.editavel) return;
      var locked = 0;
      var free = [];
      keys.forEach(function (key) {
        if (fixedMonths[key]) locked += monthValues()[key] || 0;
        else free.push(key);
      });
      var rest = Math.max(0, total - locked);
      var current = monthValues();
      var freeSum = free.reduce(function (sum, key) { return sum + (current[key] || 0); }, 0);
      free.forEach(function (key, index) {
        var input = cols.querySelector('[data-chave="' + key + '"]');
        if (!input) return;
        var next = freeSum > 0 ? Math.floor(((current[key] || 0) / freeSum) * rest) : Math.floor(rest / free.length);
        if (index === free.length - 1) {
          var used = free.slice(0, -1).reduce(function (sum, item) {
            var el = cols.querySelector('[data-chave="' + item + '"]');
            return sum + (el ? money(el.value) : 0);
          }, 0);
          next = Math.max(0, rest - used);
        }
        input.value = format(next);
      });
    }
    function ensureMonthInputs() {
      var keys = pace.chaves || [];
      var labels = pace.rotulos || [];
      if (!cols) return;
      cols.hidden = !pace.editavel;
      if (!pace.editavel || !keys.length) {
        cols.innerHTML = "";
        return;
      }
      var current = Array.prototype.map.call(cols.querySelectorAll("[data-chave]"), function (el) {
        return el.getAttribute("data-chave");
      }).join("|");
      if (current === keys.join("|")) return;
      cols.innerHTML = keys.map(function (key, index) {
        var valor = (pace.alocacao && pace.alocacao[key]) || 0;
        return '<label><span>' + (labels[index] || key) + '</span>'
          + '<input data-chave="' + key + '" inputmode="numeric" value="' + format(valor) + '"></label>';
      }).join("");
    }
    function paintGantt() {
      if (!track || !gantt) return;
      var keys = pace.chaves || [];
      var labels = pace.rotulos || [];
      ensureMonthInputs();
      var values = pace.editavel ? monthValues() : (pace.alocacao || {});
      if (!Object.keys(values).length) values = pace.alocacao || {};
      var total = parseInt(pace.total, 10) || 0;
      var peak = 0;
      keys.forEach(function (key) { peak = Math.max(peak, values[key] || 0); });
      var show = verbaValor() > 0 && (pace.parseou || keys.length);
      gantt.hidden = !show;
      track.hidden = !keys.length;
      gantt.style.setProperty("--months", String(Math.max(1, keys.length)));
      track.innerHTML = keys.map(function (key, index) {
        var valor = values[key] || 0;
        var pct = peak > 0 ? Math.max(10, (valor / peak) * 100) : 10;
        var label = labels[index] || key;
        return '<div class="sp-gantt-col ' + tone(index, keys.length) + (valor <= 0 ? ' is-hole' : '') + '">'
          + '<span class="sp-gantt-stem"><b style="height:' + pct + '%"></b></span><strong>' + label + '</strong><small>'
          + (valor > 0 ? 'R$ ' + format(valor) : 'Fora do ar') + '</small></div>';
      }).join("");
    }
    function paintChannels() {
      var selected = canais();
      var soma = 0;
      var values = channelValues();
      selected.forEach(function (key) { soma += values[key] || 0; });
      var base = verbaValor() || soma;
      rows().forEach(function (row) {
        var key = row.getAttribute("data-canal");
        var pct = base > 0 ? ((values[key] || 0) / base) * 100 : 0;
        var label = row.querySelector(".sp-cb-pct");
        if (label) {
          label.textContent = (pct >= 10 ? Math.round(pct) : Math.round(pct * 10) / 10).toLocaleString("pt-BR") + "%";
        }
      });
      var empty = document.getElementById("sp-cb-empty");
      var count = document.getElementById("sp-cb-count");
      var summaryCount = document.getElementById("sp-cb-summary-count");
      var rest = document.getElementById("sp-cb-rest");
      if (empty) empty.hidden = selected.length > 0;
      if (count) count.textContent = String(selected.length);
      if (summaryCount) summaryCount.textContent = String(selected.length);
      if (rest) {
        var diff = verbaValor() - soma;
        if (!verbaValor() || Math.abs(diff) < 1) rest.textContent = "";
        else if (diff > 0) rest.textContent = "Faltam R$ " + format(diff) + " para distribuir entre os canais";
        else rest.textContent = "Passou R$ " + format(Math.abs(diff)) + " da verba dos canais";
      }
      if (chips) {
        chips.querySelectorAll(".sp-cb-chip").forEach(function (chip) {
          chip.hidden = selected.indexOf(chip.getAttribute("data-canal")) !== -1;
        });
      }
    }
    function redistributeChannels() {
      var total = verbaValor();
      if (total <= 0) return;
      var selected = canais();
      var locked = 0;
      var free = [];
      selected.forEach(function (key) {
        if (fixedChannels[key]) locked += channelValues()[key] || 0;
        else free.push(key);
      });
      var rest = Math.max(0, total - locked);
      var current = channelValues();
      var freeSum = free.reduce(function (sum, key) { return sum + (current[key] || 0); }, 0);
      free.forEach(function (key, index) {
        var row = list.querySelector('[data-canal="' + key + '"]');
        var input = row && row.querySelector(".sp-cb-channel-input");
        if (!input) return;
        var next = freeSum > 0 ? Math.floor(((current[key] || 0) / freeSum) * rest) : Math.floor(rest / free.length);
        if (index === free.length - 1) {
          var used = free.slice(0, -1).reduce(function (sum, item) {
            return sum + (channelValues()[item] || 0);
          }, 0);
          next = Math.max(0, rest - used);
        }
        input.value = format(next);
      });
    }
    function applyPace(next) {
      var same = (pace.chaves || []).join("|") === (next.chaves || []).join("|");
      pace = next || {};
      if (!same) fixedMonths = {};
      var helper = document.getElementById("sp-cb-periodo-helper");
      var totalEl = document.getElementById("sp-gantt-total");
      var ritmoEl = document.getElementById("sp-gantt-ritmo");
      var note = document.getElementById("sp-gantt-note");
      var summaryRitmo = document.getElementById("sp-cb-summary-ritmo");
      var summaryPeriodo = document.getElementById("sp-cb-summary-periodo");
      var summaryVerba = document.getElementById("sp-cb-summary-verba");
      if (helper) helper.textContent = pace.helper || "";
      if (totalEl) totalEl.textContent = pace.total > 0 ? "R$ " + format(pace.total) : "—";
      if (ritmoEl) ritmoEl.textContent = pace.ritmo > 0 ? "~R$ " + format(pace.ritmo) + "/mês" : "—";
      if (summaryRitmo) summaryRitmo.textContent = pace.como || "A definir";
      if (summaryPeriodo) summaryPeriodo.textContent = pace.helper || "A definir";
      if (summaryVerba) summaryVerba.textContent = verbaValor() > 0 ? "R$ " + format(verbaValor()) : "A definir";
      if (note) {
        if (pace.editavel) note.textContent = "Começa menor para aprender. Solta mais verba no meio e no fim. Ajuste pela coluna.";
        else if (pace.granularidade === "semana") note.textContent = "Abertura semanal nos canais. Começa menor e solta no meio e no fim.";
        else note.textContent = "Informe uma duração (30 dias, 1 mês ou set a nov) para ver o voo.";
      }
      if (!same && cols) cols.innerHTML = "";
      paintGantt();
    }
    async function refreshPace() {
      try {
        var next = await postJson("/smart-planner/api/" + token + "/ritmo", {
          verba: verbaInput ? verbaInput.value : "",
          verba_valor: verbaValor(),
          verba_base: verbaBase(),
          periodo: periodoEl ? periodoEl.value : "",
          verba_alocacao: monthValues(),
        });
        applyPace(next);
      } catch (err) { /* ignore live calc */ }
    }
    function schedulePace() {
      window.clearTimeout(ritmoTimer);
      ritmoTimer = window.setTimeout(refreshPace, 280);
    }
    if (verbaInput) {
      verbaInput.addEventListener("input", function () {
        verbaInput.value = format(money(verbaInput.value));
        redistributeChannels();
        paintChannels();
        schedulePace();
      });
    }
    if (baseEl) baseEl.addEventListener("change", schedulePace);
    if (periodoEl) periodoEl.addEventListener("input", schedulePace);
    if (cols) {
      cols.addEventListener("input", function (event) {
        var input = event.target.closest("[data-chave]");
        if (!input || !pace.editavel) return;
        input.value = format(money(input.value));
        fixedMonths[input.getAttribute("data-chave")] = true;
        redistributeMonths();
        paintGantt();
      });
    }
    if (list) {
      list.addEventListener("input", function (event) {
        var input = event.target.closest(".sp-cb-channel-input");
        if (!input) return;
        var row = input.closest(".sp-cb-row");
        input.value = format(money(input.value));
        if (row) fixedChannels[row.getAttribute("data-canal")] = true;
        redistributeChannels();
        paintChannels();
      });
      list.addEventListener("click", function (event) {
        var button = event.target.closest(".sp-cb-remove");
        if (!button) return;
        var row = button.closest(".sp-cb-row");
        if (!row) return;
        delete fixedChannels[row.getAttribute("data-canal")];
        row.remove();
        redistributeChannels();
        paintChannels();
      });
    }
    if (addBtn && catalogBox) {
      addBtn.addEventListener("click", function () {
        var open = catalogBox.hidden;
        catalogBox.hidden = !open;
        addBtn.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }
    if (chips) {
      chips.addEventListener("click", function (event) {
        var chip = event.target.closest(".sp-cb-chip");
        if (!chip) return;
        var id = chip.getAttribute("data-canal");
        if (!id || canais().indexOf(id) !== -1) return;
        var meta = catalog[id] || { label: chip.textContent.trim(), desc: chip.getAttribute("data-desc") || "" };
        var li = document.createElement("li");
        li.className = "sp-cb-row";
        li.setAttribute("data-canal", id);
        li.innerHTML = '<span class="sp-cb-mark" aria-hidden="true"></span><span class="sp-cb-id"><strong></strong><small></small></span>'
          + '<span class="sp-cb-money"><span aria-hidden="true">R$</span><input class="sp-cb-channel-input" inputmode="numeric" value="0"><em class="sp-cb-pct">0%</em></span>'
          + '<button type="button" class="sp-cb-remove" aria-label="Remover">×</button>';
        li.querySelector(".sp-cb-mark").textContent = (meta.label || id).slice(0, 1);
        li.querySelector("strong").textContent = meta.label || id;
        li.querySelector("small").textContent = meta.desc || "";
        list.appendChild(li);
        redistributeChannels();
        paintChannels();
      });
    }
    form.querySelectorAll(".sp-praca-card").forEach(function (card) {
      var input = card.querySelector("input");
      if (input) {
        input.addEventListener("change", function () {
          form.querySelectorAll(".sp-praca-card").forEach(function (item) {
            item.classList.toggle("is-on", item.querySelector("input").checked);
          });
        });
      }
    });
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      var button = document.querySelector('button[form="sp-canais-form"]');
      setLoading(button, true);
      var data = new FormData(form);
      try {
        var result = await postJson("/smart-planner/api/" + token + "/canais", {
          verba: verbaInput ? verbaInput.value : "",
          verba_valor: verbaValor(),
          verba_base: verbaBase(),
          periodo: periodoEl ? periodoEl.value : "",
          praca: data.get("praca") || "",
          praca_detalhe: data.get("praca_detalhe") || "",
          canais: canais(),
          canais_verba: channelValues(),
          verba_alocacao: monthValues(),
        });
        window.location.href = result.redirect;
      } catch (error) {
        toast(error.message, "error");
        setLoading(button, false);
      }
    });
    paintGantt();
    paintChannels();
  }
  setupCanais();

})();
