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

  var COMPILE_STEPS = [
    { text: "Lendo o material enviado…", progress: 10 },
    { text: "Identificando informações-chave…", progress: 25 },
    { text: "Estruturando o briefing…", progress: 45 },
    { text: "Validando dados da campanha…", progress: 65 },
    { text: "Organizando para análise…", progress: 85 },
    { text: "Finalizando…", progress: 95 },
  ];

  function showCompileOverlay(inputText) {
    var overlay = document.getElementById("sp-compile-overlay");
    var bar = document.getElementById("sp-compile-bar");
    var stepEl = document.getElementById("sp-compile-step");
    var excerpt = document.getElementById("sp-compile-excerpt");
    if (!overlay) return function () {};
    overlay.hidden = false;
    if (bar) bar.style.width = "0%";
    if (stepEl) stepEl.textContent = COMPILE_STEPS[0].text;
    if (excerpt && inputText) {
      excerpt.textContent = inputText.slice(0, 300).trim() + (inputText.length > 300 ? "…" : "");
    }
    var index = 0;
    var timer = window.setInterval(function () {
      index += 1;
      if (index >= COMPILE_STEPS.length) {
        window.clearInterval(timer);
        return;
      }
      if (stepEl) stepEl.textContent = COMPILE_STEPS[index].text;
      if (bar) bar.style.width = COMPILE_STEPS[index].progress + "%";
    }, 600);
    return function () {
      window.clearInterval(timer);
    };
  }

  function hideCompileOverlay() {
    var overlay = document.getElementById("sp-compile-overlay");
    var bar = document.getElementById("sp-compile-bar");
    var stepEl = document.getElementById("sp-compile-step");
    if (bar) bar.style.width = "100%";
    if (stepEl) stepEl.textContent = "Pronto!";
    window.setTimeout(function () {
      if (overlay) overlay.hidden = true;
    }, 400);
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

  function focusField(id) {
    var el = typeof id === "string" ? document.getElementById(id) : id;
    if (!el) return;
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
    var tipsToggle = document.getElementById("sp-brief-tips-toggle");
    var tips = document.getElementById("sp-brief-tips");
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
      if (cards) {
        cards.hidden = items.length === 0;
        cards.innerHTML = items.map(function (item, index) {
          var job = item.status !== "pronto";
          var ref = item.ref || item;
          var notas = ref.notas || ref.digest || "";
          var statusLabel = item.status === "capturando" ? "Analisando" : item.status === "erro" ? (item.error || "Erro na captura") : "Processado";
          return (
            '<li class="sp-brief-card' + (item.status === "erro" ? " is-error" : item.status === "capturando" ? " is-busy" : "") + '">' +
              '<i class="fa-solid ' + kindIcon(ref.kind || item.kind) + '" aria-hidden="true"></i>' +
              "<div>" +
                "<strong>" + escapeHtml(ref.label || ref.url || kindLabel(ref.kind || item.kind)) + "</strong>" +
                "<em>" + escapeHtml(kindLabel(ref.kind || item.kind)) + (ref.papel ? " · " + escapeHtml(ref.papel) : "") + "</em>" +
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
      var drop = document.getElementById("sp-drop-file");
      function selectTab(kind) {
        var tab = kind || "text";
        importer.querySelectorAll("[data-ref-tab]").forEach(function (button) {
          var on = button.getAttribute("data-ref-tab") === tab;
          button.classList.toggle("is-on", on);
          button.setAttribute("aria-selected", on ? "true" : "false");
        });
        importer.querySelectorAll("[data-ref-pane]").forEach(function (pane) {
          var on = pane.getAttribute("data-ref-pane") === tab;
          pane.hidden = !on;
          pane.classList.toggle("is-on", on);
        });
        if (drop) drop.setAttribute("for", tab === "image" ? "sp-ref-file-image" : "sp-ref-file");
        if (tab === "url") {
          var url = document.getElementById("sp-ref-url");
          if (url) url.focus();
        }
        if (tab === "search") {
          var query = document.getElementById("sp-ref-query");
          if (query) query.focus();
        }
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
      if (drop) {
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
      setStatus(statusEl, "Capturando…", "");
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
        var url = document.getElementById("sp-ref-url").value;
        startJob("url", { kind: "url", url: url }, url);
      });
    }
    var queryGo = document.getElementById("sp-ref-query-go");
    if (queryGo) {
      queryGo.addEventListener("click", function () {
        var query = document.getElementById("sp-ref-query").value;
        startJob("search", { kind: "search", query: query, briefing: textarea.value }, query);
      });
    }
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
    if (tipsToggle && tips && tipsToggle.tagName !== "SUMMARY") {
      tipsToggle.addEventListener("click", function () {
        var open = tips.hidden;
        tips.hidden = !open;
        tipsToggle.setAttribute("aria-expanded", open ? "true" : "false");
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
            };
          }),
        });
        stop();
        hideCompileOverlay();
        try { localStorage.removeItem(draftKey); } catch (err) { /* ignore */ }
        window.setTimeout(function () {
          window.location.href = result.redirect;
        }, 400);
      } catch (error) {
        stop();
        hideCompileOverlay();
        toast(error.message, "error");
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
    var desk = document.getElementById("sp-hi-plan") || root;
    var objetivoEl = document.getElementById("sp-objetivo");
    var bars = document.getElementById("sp-mix-bars");
    var empty = document.getElementById("sp-mix-empty");
    var sumEl = document.getElementById("sp-mix-sum");
    var hint = document.getElementById("sp-mix-hint");
    var more = document.querySelector(".sp-mix-more");
    var picks = document.getElementById("sp-mix-picks");
    var morePicks = document.querySelector(".sp-mix-more .sp-mix-picks");

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
    function allocate(canais, objetivo, method, weights) {
      var keys = mediaKeys(canais);
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
    function paintBars(weights) {
      if (!bars) return;
      bars.innerHTML = weights.map(function (item) {
        return '<li data-canal="' + item.id + '"><span><strong>' + item.label + "</strong><em>" + item.pct
          + '%</em></span><i><b data-pct="' + item.pct + '"></b></i>'
          + '<input type="range" min="0" max="100" value="' + item.pct + '" data-canal="' + item.id
          + '" aria-label="Percentual de ' + item.label + '"></li>';
      }).join("");
      bars.querySelectorAll("b[data-pct]").forEach(function (fill) {
        fill.style.setProperty("--pct", fill.getAttribute("data-pct") || "0");
      });
      if (empty) empty.hidden = weights.length > 0;
      if (sumEl) {
        var total = weights.reduce(function (sum, item) { return sum + item.pct; }, 0);
        sumEl.hidden = weights.length === 0;
        sumEl.textContent = "Soma " + total + "%";
      }
    }
    function refresh(method) {
      method = method || selectedMethod();
      var weights = allocate(selectedCanais(), objetivoEl ? objetivoEl.value : "", method, currentWeights());
      paintBars(weights);
    }
    desk.addEventListener("change", function (event) {
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
      });
      if (sumEl) {
        var total = keys.reduce(function (sum, key) { return sum + (pcts[key] || 0); }, 0);
        sumEl.hidden = keys.length === 0;
        sumEl.textContent = "Soma " + total + "%";
      }
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
    if (bars) {
      bars.querySelectorAll("b[data-pct]").forEach(function (fill) {
        fill.style.setProperty("--pct", fill.getAttribute("data-pct") || "0");
      });
    }

    function collectReview() {
      var data = new FormData(form);
      return {
        briefing: data.get("briefing"),
        canais: selectedCanais(),
        mix: {
          method: selectedMethod(),
          weights: currentWeights(),
          locked: selectedMethod() === "manual",
        },
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
          kpis: data.get("kpis"),
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
    setupReviewSections();
    setupCompleteness();
    setupReviewAutosave(collectReview);
    setupReviewActions(collectReview);
  }
  setupMixDesk();

  function setupReviewSections() {
    document.querySelectorAll(".sp-acc").forEach(function (acc) {
      var summary = acc.querySelector("summary");
      if (summary && !summary.getAttribute("aria-expanded")) {
        summary.setAttribute("aria-expanded", acc.open ? "true" : "false");
      }
      acc.addEventListener("toggle", function () {
        if (summary) summary.setAttribute("aria-expanded", acc.open ? "true" : "false");
      });
    });
  }

  function gapTarget(text) {
    var t = String(text || "").toLowerCase();
    if (/objetivo/.test(t)) return "sp-objetivo";
    if (/p[uú]blic/.test(t)) return "sp-field-publico";
    if (/verba|or[cç]amento|budget/.test(t)) return "sp-field-verba";
    if (/per[ií]odo|prazo|dura[cç]/.test(t)) return "sp-field-periodo";
    if (/pra[cç]a|local|cidade/.test(t)) return "sp-field-praca";
    if (/canal/.test(t)) return "sp-mix-channels";
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
      if (!chips) return;
      var selected = Array.prototype.slice.call(rootDesk.querySelectorAll('input[name="canais"]:checked'));
      chips.hidden = selected.length === 0;
      chips.innerHTML = selected.map(function (input) {
        var name = (input.closest("label") && input.closest("label").querySelector("span"));
        var label = name ? name.textContent : input.value;
        return '<span class="sp-mix-chip">' + label + '<button type="button" data-uncheck="' + input.value + '" aria-label="Remover ' + label + '">×</button></span>';
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

  function setupReviewAutosave(collectReview) {
    var form = document.getElementById("sp-revisao-form");
    var saveBtn = document.getElementById("sp-save-draft");
    if (!form || typeof collectReview !== "function") return;
    var timer = null;
    async function persist(manual) {
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
    form.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(persist, 900);
    });
    form.addEventListener("change", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(persist, 400);
    });
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        window.clearTimeout(timer);
        persist(true);
      });
    }
  }

  function setupReviewActions(collectReview) {
    var original = document.getElementById("sp-original");
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
        var hasCanal = document.querySelector('#sp-hi-plan input[name="canais"]:checked');
        if (objetivo && !objetivo.value) {
          focusField("sp-objetivo");
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
        var title = mode === "one_page" ? "Gerando a página única" : "Gerando o planejamento completo";
        var heading = document.querySelector("#sp-compile-overlay h2");
        if (heading) heading.textContent = title;
        var stop = showCompileOverlay("", title);
        var stepEl = document.getElementById("sp-compile-step");
        if (stepEl) {
          stepEl.textContent = mode === "completo"
            ? "Escrevendo a tese da página única…"
            : "Montando a folha…";
        }
        try {
          var result = await postJson("/smart-planner/api/" + token + "/gerar", { plan_mode: mode });
          stop();
          hideCompileOverlay();
          window.setTimeout(function () {
            window.location.href = result.redirect;
          }, 400);
        } catch (error) {
          stop();
          hideCompileOverlay();
          toast(error.message, "error");
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
        else if (pace.meses === 1) note.textContent = "Campanha de um mês: a verba entra inteira. O Gantt por coluna aparece quando o período passa de 30 dias.";
        else note.textContent = "Informe uma duração (90 dias, 3 meses ou set a nov) para ver o voo.";
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
