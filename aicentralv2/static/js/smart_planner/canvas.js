(function () {
  var root = document.getElementById("sp-canvas");
  if (!root) return;
  var token = root.getAttribute("data-token");
  var mode = root.getAttribute("data-mode");
  var isEditor = root.getAttribute("data-editor") === "1";
  var readonly = root.getAttribute("data-readonly") === "1";
  var isPublic = root.getAttribute("data-public") === "1";
  var ready = false;
  var board = document.getElementById("sp-canvas-board");
  var presenterSelect = document.getElementById("sp-presenter-legacy") || document.getElementById("sp-presenter");
  var plan = { sections: [], branding: {}, meta: {}, theme: {}, share: {}, media: {} };

  var TYPE_LABELS = {
    strategy: "Estratégia",
    creative: "Criativo",
    market: "Mercado",
    defense: "Defesa",
    summary: "Resumo",
    audience: "Público",
    "channel-mix": "Mix",
    allocation: "Verba",
    "kpi-group": "Indicadores",
    recommendation: "Recomendação",
    "next-steps": "Próximos passos",
    table: "Tabela",
  };

  var WIDE_TYPES = {
    summary: 1,
    strategy: 1,
    recommendation: 1,
    "channel-mix": 1,
    allocation: 1,
    table: 1,
  };

  var LEAD_TYPES = {
    summary: 1,
    strategy: 1,
    recommendation: 1,
  };

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

  function setLive(message) {
    var live = document.getElementById("sp-save-live");
    if (live) live.textContent = message || "";
  }

  function setImageStatus(message, kind) {
    var node = document.getElementById("sp-image-status");
    if (node) {
      node.textContent = message || "";
      node.dataset.state = kind || "";
    }
  }

  // Contract: POST /canvas/imagem { logo?: dataUrl, reference?: dataUrl }
  // Response: { success, data: { plan, editor: { gallery } } }

  function reviewedImagePrompt() {
    var body = val("sp-field-creative") || "o principal produto ou serviço da campanha";
    var channel = val("sp-field-channel") || "display ou CTV";
    return "Crie uma arte publicitária horizontal 16:9 para " + channel + ", com fotografia realista e acabamento comercial. " +
      "Mostre como herói o principal produto ou serviço da campanha: " + body + ". " +
      "A logo enviada é a fonte exata da identidade: preserve desenho, proporções e cores, sem redesenhar nem inventar texto. " +
      "Aplique a logo sempre no canto superior esquerdo, dentro de uma área segura, com contraste suficiente e espaço de respiro. " +
      "Use a imagem de referência apenas para orientar produto, cena, luz ou linguagem visual; não copie marcas de terceiros. " +
      "Use pessoas e contexto quando ajudarem a explicar a oferta. Harmonize as cores com a logo, priorizando contraste e legibilidade. " +
      "Não criar mockup de site, interface, colagem, outra logo, marca d’água, agência, QR code, preço ou texto ilegível. Uma única cena, foco claro, sem corte vertical.";
  }

  function reviewImagePrompt() {
    var field = document.getElementById("sp-field-image-prompt");
    if (!field) return;
    field.value = reviewedImagePrompt();
      setImageStatus("Prompt revisado: cores e tipografia da logo, posição, referência, contraste e formato conferidos. A primeira versão não terá texto.", "ready");
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function val(id) {
    var node = document.getElementById(id);
    return node ? node.value : "";
  }

  function autosizeTextarea(field) {
    if (!field) return;
    field.style.height = "auto";
    field.style.height = Math.max(field.scrollHeight, 96) + "px";
    field.style.overflowY = "hidden";
  }

  function setupAutosizeTextareas() {
    if (!isEditor) return;
    var fields = Array.prototype.slice.call(document.querySelectorAll("#sp-folha-form textarea"));
    fields.forEach(function (field) {
      field.classList.add("is-autosized");
      autosizeTextarea(field);
      field.addEventListener("input", function () {
        autosizeTextarea(field);
      });
    });
    window.requestAnimationFrame(function () {
      fields.forEach(autosizeTextarea);
    });
    window.addEventListener("resize", function () {
      fields.forEach(autosizeTextarea);
    });
  }

  function ensureSection() {
    if (!plan.sections || !plan.sections.length) {
      plan.sections = [{ id: "one_page", type: "one_page", title: "Página única", order: 1, cards: [] }];
    }
    return plan.sections[0];
  }

  function upsertCard(type, fields) {
    var section = ensureSection();
    section.cards = section.cards || [];
    var index = section.cards.findIndex(function (card) {
      return card.type === type;
    });
    var card = index >= 0 ? Object.assign({}, section.cards[index], fields) : Object.assign({ id: type, type: type }, fields);
    if (index >= 0) section.cards[index] = card;
    else section.cards.push(card);
    return card;
  }

  function collectEditor() {
    upsertCard("strategy", {
      title: val("sp-field-strategy-title") || "Tese e briefing",
      body: val("sp-field-strategy"),
    });
    upsertCard("creative", {
      title: val("sp-field-creative-title") || "Criativo",
      body: val("sp-field-creative"),
      channel: val("sp-field-channel"),
      surface: val("sp-field-surface") || "display",
      image_url: val("sp-field-image-url"),
      image_prompt: val("sp-field-image-prompt"),
    });
    upsertCard("market", {
      title: "Mercado",
      body: val("sp-field-market"),
      stat: val("sp-field-stat"),
      stat_label: val("sp-field-stat-label"),
    });
    upsertCard("defense", {
      title: val("sp-field-defense-title") || "Por que aprovar",
      body: val("sp-field-defense"),
    });
    plan.planMode = "one_page";
    plan.meta = plan.meta || {};
    if (presenterSelect) {
      plan.meta.presenter = presenterSelect.value;
    }
    var presenterField = document.getElementById("sp-presenter");
    if (presenterField && presenterSelect) presenterField.value = presenterSelect.value;
    plan.public_design = plan.public_design || {};
    plan.public_design.hero = plan.public_design.hero || {};
    plan.public_design.hero.use_as_background = Boolean(document.getElementById("sp-public-hero-background")?.checked);
    return plan;
  }

  function readImage(file) {
    return new Promise(function (resolve, reject) {
      if (!file) return resolve("");
      var reader = new FileReader();
      reader.onload = function () { resolve(reader.result); };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function refreshGallery(items) {
    var host = document.getElementById("sp-gallery");
    if (!host || !items || !items.length) return;
    host.innerHTML = items
      .map(function (item) {
        return (
          '<figure class="sp-gallery-item' +
          (item.active ? " is-active" : "") +
          '" data-url="' +
          escapeHtml(item.url) +
          '" data-kind="' +
          escapeHtml(item.kind || "") +
          '" data-status="' +
          escapeHtml(item.status || "draft") +
          '"><img src="' +
          escapeHtml(item.url) +
          '" alt="' +
          escapeHtml(item.label || "") +
          '" loading="lazy"><figcaption><span>' +
          escapeHtml(item.label || "") +
          ' <small>' + escapeHtml(item.status || "draft") +
          '</small></span><div class="sp-gallery-actions"><button type="button" data-gallery-action="hero">Usar no hero</button><button type="button" data-gallery-action="remove">Apagar</button></div></figcaption></figure>'
        );
      })
      .join("");
  }

  function applyCreativeUrl(url) {
    var hidden = document.getElementById("sp-field-image-url");
    if (hidden) hidden.value = url || "";
    plan.public_design = plan.public_design || {};
    plan.public_design.hero = plan.public_design.hero || {};
    plan.public_design.hero.asset_url = url || "";
    document.querySelectorAll(".sp-gallery-item").forEach(function (node) {
      node.classList.toggle("is-active", node.getAttribute("data-url") === url);
    });
  }

  function removeGalleryAsset(url) {
    if (!url) return;
    plan.asset_manifest = (plan.asset_manifest || []).filter(function (asset) {
      return (asset.asset_url || asset.image_url) !== url;
    });
    plan.supporting_visuals = (plan.supporting_visuals || []).filter(function (asset) {
      return (asset.asset_url || asset.image_url) !== url;
    });
    var creative = (((plan.sections || [])[0] || {}).cards || []).find(function (card) { return card.type === "creative"; });
    if (creative && creative.image_url === url) creative.image_url = "";
    plan.public_design = plan.public_design || {};
    plan.public_design.hero = plan.public_design.hero || {};
    if (plan.public_design.hero.asset_url === url) plan.public_design.hero.asset_url = "";
    var hidden = document.getElementById("sp-field-image-url");
    if (hidden && hidden.value === url) hidden.value = "";
    var host = document.getElementById("sp-gallery");
    var node = host && host.querySelector('.sp-gallery-item[data-url="' + CSS.escape(url) + '"]');
    if (node) node.remove();
    if (host && !host.querySelector(".sp-gallery-item")) host.innerHTML = '<p class="sp-gallery-empty">Nenhuma imagem selecionada. Gere uma nova versão quando precisar.</p>';
  }

  function setupUploadPreviews() {
    [
      { id: "sp-logo-upload", preview: "sp-logo-upload-preview", copy: "logo", label: "Logo selecionada. Ela será usada na arte e no link público." },
      { id: "sp-reference-upload", preview: "sp-reference-upload-preview", copy: "reference", label: "Referência selecionada. Ela orientará a direção visual." },
    ].forEach(function (item) {
      var field = document.getElementById(item.id);
      if (!field) return;
      field.addEventListener("change", function () {
        var file = field.files && field.files[0];
        if (!file) return;
        var preview = document.getElementById(item.preview);
        var copy = document.querySelector('[data-upload-copy="' + item.copy + '"]');
        var reader = new FileReader();
        reader.onload = function () {
          if (preview) { preview.src = reader.result; preview.hidden = false; }
          if (copy) copy.textContent = item.label;
          setImageStatus(item.label, "ready");
          persistVisualInput(item.copy, reader.result).catch(function (error) {
            setImageStatus(error.message || "A imagem foi selecionada, mas não foi possível salvá-la.", "error");
          });
        };
        reader.readAsDataURL(file);
      });
    });
  }

  async function persistVisualInput(kind, data) {
    var response = await fetch("/smart-planner/api/" + token + "/canvas/asset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ kind: kind, data: data }),
    });
    var payload = await response.json();
    if (!payload.success) throw new Error(payload.error || "Não foi possível salvar a imagem.");
    plan.visual_inputs = plan.visual_inputs || {};
    plan.visual_inputs[kind + "_url"] = payload.data.url;
    if (kind === "logo") {
      plan.branding = plan.branding || {};
      plan.branding.client = plan.branding.client || plan.branding.hero || {};
      plan.branding.client.logo_url = payload.data.url;
      plan.branding.hero = plan.branding.hero || {};
      plan.branding.hero.logo_url = payload.data.url;
    }
    setLive(kind === "logo" ? "Logo salva para a página pública." : "Referência salva para a próxima geração.");
  }

  /* ——— Board mode (plano completo) ——— */

  function cardItems(card) {
    var items = card.items || [];
    if (!items.length) return "";
    return (
      '<ul class="sp-card-items">' +
      items
        .map(function (item) {
          return "<li>" + escapeHtml(item) + "</li>";
        })
        .join("") +
      "</ul>"
    );
  }

  function cardMarkup(card, sectionIndex, cardIndex, extraClass, labelOverride) {
    var type = card.type || "summary";
    var label = labelOverride || TYPE_LABELS[type] || card.title || "Bloco";
    var title = readonly
      ? "<strong>" + escapeHtml(card.title || label) + "</strong>"
      : '<input value="' + escapeHtml(card.title) + '" data-field="title">';
    var body = "";
    if (readonly) {
      body = String(card.body || "")
        .split(/\n\n+/)
        .map(function (para) {
          return para.trim();
        })
        .filter(Boolean)
        .map(function (para, index) {
          return '<p class="' + (index ? "" : "is-lead") + '">' + escapeHtml(para) + "</p>";
        })
        .join("");
    } else {
      body = '<textarea data-field="body">' + escapeHtml(card.body || "") + "</textarea>";
    }
    return (
      '<article class="sp-card is-' +
      escapeHtml(type) +
      (extraClass ? " " + extraClass : "") +
      '" data-section="' +
      sectionIndex +
      '" data-card="' +
      cardIndex +
      '" data-type="' +
      escapeHtml(type) +
      '">' +
      title +
      body +
      cardItems(card) +
      "</article>"
    );
  }

  function factsStrip(meta) {
    var canais = meta.canais || "";
    if (meta.mix_method && canais.indexOf(" · ") !== -1) {
      canais = canais.split(" · ")[0];
    }
    var items = [
      ["Objetivo", meta.objective],
      ["Público", meta.publico],
      ["Verba", meta.budget],
      ["Período", meta.period],
      ["Praça", meta.market],
      ["Canais", canais],
    ].filter(function (item) {
      return item[1];
    });
    if (!items.length) return "";
    return (
      '<dl class="sp-exec-facts">' +
      items
        .map(function (item) {
          return "<div><dt>" + escapeHtml(item[0]) + "</dt><dd>" + escapeHtml(item[1]) + "</dd></div>";
        })
        .join("") +
      "</dl>"
    );
  }

  function renderBoard() {
    var meta = plan.meta || {};
    var sections = (plan.sections || [])
      .map(function (section, sectionIndex) {
        var cards = (section.cards || [])
          .map(function (card, cardIndex) {
            var extras = [];
            if (WIDE_TYPES[card.type] || (cardIndex === 0 && LEAD_TYPES[card.type])) {
              extras.push("is-wide");
            }
            if (LEAD_TYPES[card.type] || cardIndex === 0) extras.push("is-lead");
            return cardMarkup(card, sectionIndex, cardIndex, extras.join(" "));
          })
          .join("");
        return (
          '<section class="sp-board-section"><h2>' +
          escapeHtml(section.title || section.id) +
          "</h2>" +
          cards +
          "</section>"
        );
      })
      .join("");
    return (
      '<article class="sp-sheet is-exec is-full">' +
      '<div class="sp-sheet-lead"><h2>' +
      escapeHtml(meta.client || meta.title || "Plano de mídia") +
      "</h2>" +
      (meta.campaign && meta.campaign !== meta.client ? "<p>" + escapeHtml(meta.campaign) + "</p>" : "") +
      factsStrip(meta) +
      "</div>" +
      '<div class="sp-board is-exec">' +
      sections +
      "</div></article>"
    );
  }

  function render() {
    if (!board) return;
    var sections = plan.sections || [];
    if (!sections.length || !sections.some(function (section) {
      return (section.cards || []).length;
    })) {
      board.innerHTML = '<div class="sp-empty-board"><p>O quadro ainda está vazio. Clique em Gerar de novo.</p></div>';
      return;
    }
    board.innerHTML = renderBoard();
  }

  function collectBoard() {
    if (!board) return plan;
    board.querySelectorAll(".sp-card").forEach(function (node) {
      var sectionIndex = Number(node.getAttribute("data-section"));
      var cardIndex = Number(node.getAttribute("data-card"));
      var card = (((plan.sections || [])[sectionIndex] || {}).cards || [])[cardIndex];
      if (!card) return;
      var title = node.querySelector('[data-field="title"]');
      var body = node.querySelector('[data-field="body"]');
      card.title = title ? title.value : card.title;
      card.body = body ? body.value : card.body;
    });
    return plan;
  }

  async function load() {
    root.classList.add("is-loading");
    setLive("Carregando planejamento…");
    if (isEditor) {
      var response = await fetch("/smart-planner/api/" + token + "/canvas?folha=1", {
        credentials: "same-origin",
      });
      var payload = await response.json();
      if (!payload.success) throw new Error(payload.error || "Falha ao carregar");
      plan = payload.data.plan || plan;
      if (payload.data.editor && payload.data.editor.gallery) {
        refreshGallery(payload.data.editor.gallery);
      }
      ready = true;
      root.classList.remove("is-loading");
      setLive("");
      setupAutosizeTextareas();
      return;
    }
    var endpoint = isPublic
      ? "/smart-planner/api/p/" + token
      : "/smart-planner/api/" + token + "/canvas";
    var boardResponse = await fetch(endpoint, { credentials: "same-origin" });
    var boardPayload = await boardResponse.json();
    if (!boardPayload.success) throw new Error(boardPayload.error || "Falha ao carregar");
    plan = boardPayload.data.plan || { sections: [] };
    render();
    ready = true;
    root.classList.remove("is-loading");
    setLive("");
  }

  async function regenerate(presenter) {
    if (!ready) throw new Error("O planejamento ainda está carregando.");
    var response = await fetch("/smart-planner/api/" + token + "/canvas/gerar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ presenter: presenter || (presenterSelect && presenterSelect.value) || "" }),
    });
    var payload = await response.json();
    if (!payload.success) throw new Error(payload.error || "Falha ao gerar");
    plan = payload.data.plan || { sections: [] };
    if (isEditor) {
      window.location.reload();
      return;
    }
    render();
  }

  async function save() {
    if (!ready) throw new Error("O planejamento ainda está carregando.");
    var body = isEditor
      ? { plan: collectEditor(), folha: true }
      : { plan: collectBoard() };
    var response = await fetch("/smart-planner/api/" + token + "/canvas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(body),
    });
    var payload = await response.json();
    if (!payload.success) throw new Error(payload.error || "Falha ao salvar");
  }

  async function generateImage() {
    setLive("Gerando imagem…");
    setImageStatus("Gerando arte 16:9 com a logo aplicada…", "loading");
    await save();
    var logo = await readImage(document.getElementById("sp-logo-upload")?.files?.[0]);
    var reference = await readImage(document.getElementById("sp-reference-upload")?.files?.[0]);
    var response = await fetch("/smart-planner/api/" + token + "/canvas/imagem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ logo, reference }),
    });
    var payload = await response.json();
    if (!payload.success) throw new Error(payload.error || "Falha ao gerar imagem");
    plan = payload.data.plan || plan;
    var creative = ((plan.sections || [])[0] || {}).cards || [];
    var card = creative.find(function (item) {
      return item.type === "creative";
    });
    if (card && card.image_url) applyCreativeUrl(card.image_url);
    if (payload.data.editor && payload.data.editor.gallery) {
      refreshGallery(payload.data.editor.gallery);
      applyCreativeUrl(card && card.image_url);
    }
    setLive("Imagem atualizada.");
    setImageStatus("Imagem gerada e aplicada ao plano.", "success");
  }

  document.getElementById("sp-canvas-save")?.addEventListener("click", async function () {
    try {
      setLive("Salvando…");
      await save();
      setLive("Salvo.");
      toast(isEditor ? "Página única salva." : "Quadro salvo.", "success");
    } catch (error) {
      setLive("");
      toast(error.message, "error");
    }
  });

  document.getElementById("sp-canvas-regen")?.addEventListener("click", async function () {
    try {
      setLive("Gerando…");
      await regenerate();
      toast(isEditor ? "Página única regenerada." : "Quadro gerado de novo.", "success");
      setLive("");
    } catch (error) {
      setLive("");
      toast(error.message, "error");
    }
  });

  document.getElementById("sp-canvas-image")?.addEventListener("click", async function () {
    try {
      await generateImage();
    } catch (error) {
      setLive("");
      setImageStatus(error.message || "Não foi possível gerar a imagem.", "error");
    }
  });

  document.getElementById("sp-review-image-prompt")?.addEventListener("click", reviewImagePrompt);
  if (!val("sp-field-image-prompt")) reviewImagePrompt();
  setupUploadPreviews();

  document.getElementById("sp-upgrade-completo")?.addEventListener("click", async function (event) {
    if (!isEditor) return;
    var button = event.currentTarget;
    var status = document.getElementById("sp-upgrade-status");
    try {
      button.disabled = true;
      button.textContent = "Preparando plano completo…";
      if (status) status.textContent = "Salvando a página única antes de iniciar.";
      await save();
      var response = await fetch("/smart-planner/api/" + token + "/gerar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ plan_mode: "completo" }),
      });
      var payload = await response.json();
      if (!payload.success) throw new Error(payload.error || "Não foi possível iniciar o plano completo.");
      if (status) status.textContent = "Plano completo em processamento. Abrindo acompanhamento…";
      window.location.href = payload.data && payload.data.redirect
        ? payload.data.redirect
        : "/smart-planner/" + token + "/conclusao";
    } catch (error) {
      button.disabled = false;
      button.textContent = "Transformar em plano completo";
      if (status) status.textContent = "Não foi possível iniciar. Revise e tente novamente.";
      toast(error.message, "error");
    }
  });

  presenterSelect?.addEventListener("change", async function () {
    if (!isEditor) return;
    try {
      setLive("Atualizando marca…");
      await regenerate(presenterSelect.value);
    } catch (error) {
      setLive("");
      toast(error.message, "error");
    }
  });

  document.getElementById("sp-gallery")?.addEventListener("click", function (event) {
    var action = event.target.closest("[data-gallery-action]");
    var figure = event.target.closest(".sp-gallery-item");
    if (!figure) return;
    var url = figure.getAttribute("data-url");
    if (action && action.getAttribute("data-gallery-action") === "remove") {
      event.preventDefault();
      removeGalleryAsset(url);
      save().then(function () {
        setLive("Imagem removida da página pública.");
        toast("Imagem removida.", "success");
      }).catch(function (error) { toast(error.message, "error"); });
      return;
    }
    if (action || figure.getAttribute("data-kind") === "creative") {
      event.preventDefault();
      applyCreativeUrl(url);
      save().then(function () {
        setLive("Imagem principal atualizada.");
        toast("Imagem definida como principal.", "success");
      }).catch(function (error) { toast(error.message, "error"); });
    }
  });

  load().catch(function (error) {
    root.classList.remove("is-loading");
    root.classList.add("is-load-error");
    setLive("Falha ao carregar");
    toast(error.message, "error");
  });
})();
