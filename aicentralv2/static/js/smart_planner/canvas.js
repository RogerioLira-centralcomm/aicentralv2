(function () {
  var root = document.getElementById("sp-canvas");
  if (!root) return;
  var token = root.getAttribute("data-token");
  var mode = root.getAttribute("data-mode");
  var isEditor = root.getAttribute("data-editor") === "1";
  var readonly = root.getAttribute("data-readonly") === "1";
  var isPublic = root.getAttribute("data-public") === "1";
  var board = document.getElementById("sp-canvas-board");
  var presenterSelect = document.getElementById("sp-presenter");
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
    window.alert(message);
  }

  function setLive(message) {
    var live = document.getElementById("sp-save-live");
    if (live) live.textContent = message || "";
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
    return plan;
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
          '"><img src="' +
          escapeHtml(item.url) +
          '" alt="' +
          escapeHtml(item.label || "") +
          '" loading="lazy"><figcaption>' +
          escapeHtml(item.label || "") +
          "</figcaption></figure>"
        );
      })
      .join("");
  }

  function applyCreativeUrl(url) {
    var hidden = document.getElementById("sp-field-image-url");
    if (hidden) hidden.value = url || "";
    document.querySelectorAll(".sp-gallery-item").forEach(function (node) {
      node.classList.toggle("is-active", node.getAttribute("data-url") === url && node.getAttribute("data-kind") === "creative");
    });
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
  }

  async function regenerate(presenter) {
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
    await save();
    var response = await fetch("/smart-planner/api/" + token + "/canvas/imagem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({}),
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
      toast("Nova peça gerada.", "success");
    } catch (error) {
      setLive("");
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
    var figure = event.target.closest(".sp-gallery-item");
    if (!figure || figure.getAttribute("data-kind") !== "creative") return;
    applyCreativeUrl(figure.getAttribute("data-url"));
  });

  document.querySelectorAll(".sp-editor-checks a[href^='#']").forEach(function (link) {
    link.addEventListener("click", function (event) {
      var id = link.getAttribute("href").slice(1);
      var target = document.getElementById(id);
      if (!target) return;
      event.preventDefault();
      if (target.tagName === "DETAILS") target.open = true;
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  load().catch(function (error) {
    toast(error.message, "error");
  });
})();
