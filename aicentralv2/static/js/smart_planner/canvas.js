(function () {
  var root = document.getElementById("sp-canvas");
  if (!root) return;
  var token = root.getAttribute("data-token");
  var mode = root.getAttribute("data-mode");
  var readonly = root.getAttribute("data-readonly") === "1";
  var isPublic = root.getAttribute("data-public") === "1";
  var board = document.getElementById("sp-canvas-board");
  var stage = document.getElementById("sp-stage");
  var presenterSelect = document.getElementById("sp-presenter");
  var plan = { sections: [], branding: {}, meta: {}, theme: {}, share: {} };

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

  var LEGACY_SLOTS = [
    { type: "summary", label: "Objetivo" },
    { type: "audience", label: "Público" },
    { type: "channel-mix", label: "Mix", wide: true },
    { type: "allocation", label: "Verba" },
    { type: "kpi-group", label: "Indicadores" },
  ];

  function toast(message, type) {
    if (typeof window.showToast === "function") {
      window.showToast(message, type || "info");
      return;
    }
    window.alert(message);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function logoBox(party, kind) {
    if (!party || !(party.name || party.logo_url)) return "";
    var img = party.logo_url
      ? '<img src="' + escapeHtml(party.logo_url) + '" alt="' + escapeHtml(party.name) + '" onerror="this.remove()">'
      : '<span class="sp-logo-fallback">' + escapeHtml((party.name || "?").slice(0, 2)) + "</span>";
    return (
      '<div class="sp-logo is-' +
      kind +
      '">' +
      img +
      "<span>" +
      escapeHtml(party.name || "") +
      "</span></div>"
    );
  }

  function findCard(cards, type) {
    return cards.findIndex(function (card) {
      return card.type === type;
    });
  }

  function fieldBlock(card, sectionIndex, cardIndex, label, extraFields) {
    var extras = (extraFields || [])
      .map(function (field) {
        return (
          '<input type="hidden" data-extra="' +
          field +
          '" value="' +
          escapeHtml(card[field] || "") +
          '">'
        );
      })
      .join("");
    var body = readonly
      ? "<p>" + escapeHtml(card.body || "") + "</p>"
      : '<textarea data-field="body">' + escapeHtml(card.body || "") + "</textarea>";
    var title = readonly
      ? "<strong>" + escapeHtml(card.title || label) + "</strong>"
      : '<input value="' + escapeHtml(card.title || "") + '" data-field="title">';
    return (
      '<article class="sp-card" data-section="' +
      sectionIndex +
      '" data-card="' +
      cardIndex +
      '" data-type="' +
      escapeHtml(card.type) +
      '">' +
      '<span class="sp-card-type">' +
      escapeHtml(label) +
      "</span>" +
      title +
      body +
      extras +
      "</article>"
    );
  }

  function brandChip(party) {
    if (!party || !(party.name || party.logo_url)) return "";
    var mark = party.logo_url
      ? '<img src="' + escapeHtml(party.logo_url) + '" alt="">'
      : '<span>' + escapeHtml((party.name || "?").slice(0, 2)) + "</span>";
    return (
      '<div class="sp-ad-mark is-' +
      escapeHtml(party.source || "client") +
      '">' +
      mark +
      "<em>" +
      escapeHtml(party.name || "") +
      "</em></div>"
    );
  }

  function mockup(card, party) {
    var surface = card.surface || "display";
    var image = card.image_url
      ? '<img src="' + escapeHtml(card.image_url) + '" alt="">'
      : "<p>" + escapeHtml(card.body || "Criativo no canal") + "</p>";
    return (
      '<div class="sp-mockup is-' +
      escapeHtml(surface) +
      '">' +
      '<div class="sp-mockup-chrome" aria-hidden="true"></div>' +
      '<div class="sp-mockup-screen">' +
      image +
      "</div>" +
      brandChip(party) +
      (surface === "ctv" ? '<span class="sp-mockup-qr" aria-hidden="true"></span>' : "") +
      "</div>"
    );
  }

  function densityChart(theme) {
    var bars = (theme.density || [])
      .map(function (item) {
        var value = Math.max(0, Math.min(100, Number(item.value) || 0));
        return (
          '<div class="sp-density-row"><span>' +
          escapeHtml(item.label || "") +
          "</span><i><b style=\"width:" +
          value +
          '%"></b></i><em>' +
          value +
          "</em></div>"
        );
      })
      .join("");
    if (!bars) return "";
    return (
      '<div class="sp-density"><p>' +
      escapeHtml(theme.density_caption || "Peso do mix") +
      "</p>" +
      bars +
      "</div>"
    );
  }

  function shareBlock(share) {
    var url = share.url || share.path || "";
    if (!url) return "";
    var qrSrc = share.public_token
      ? "/smart-planner/api/p/" + encodeURIComponent(share.public_token) + "/qr.svg"
      : "";
    var qr = qrSrc
      ? '<img class="sp-qr" src="' +
        qrSrc +
        '" alt="QR do quadro completo" width="96" height="96">'
      : "";
    return (
      '<div class="sp-share">' +
      qr +
      '<div><a href="' +
      escapeHtml(url) +
      '" target="_blank" rel="noopener">' +
      escapeHtml(share.label || "Quadro completo") +
      "</a><button type=\"button\" class=\"sp-pdf\" data-print=\"1\">" +
      escapeHtml(share.pdf_label || "Salvar PDF") +
      "</button><small>" +
      escapeHtml(url) +
      "</small></div></div>"
    );
  }

  function applyTheme(theme) {
    var host = stage || root;
    if (!theme || !host) return;
    host.setAttribute("data-market", theme.id || "");
    ["ink", "paper", "accent", "fog", "rule"].forEach(function (key) {
      if (theme[key]) host.style.setProperty("--sp-" + key, theme[key]);
    });
    if (theme.bg_url) {
      host.style.setProperty("--sp-bg", "url('" + theme.bg_url + "')");
    }
  }

  function renderPitchSheet(section, sectionIndex) {
    var cards = section.cards || [];
    var branding = plan.branding || {};
    var meta = plan.meta || {};
    var theme = plan.theme || {};
    var share = plan.share || {};
    var presenter = branding.presenter || {};
    var hero = branding.hero || {};
    var strategyIdx = findCard(cards, "strategy");
    var creativeIdx = findCard(cards, "creative");
    var marketIdx = findCard(cards, "market");
    var defenseIdx = findCard(cards, "defense");
    var strategy = cards[strategyIdx] || {};
    var creative = cards[creativeIdx] || {};
    var market = cards[marketIdx] || {};
    var defense = cards[defenseIdx] || {};
    var partners = (branding.partners || [])
      .map(function (partner) {
        if (partner.logo_url) {
          return (
            '<img src="' +
            escapeHtml(partner.logo_url) +
            '" alt="' +
            escapeHtml(partner.label || "") +
            '" title="' +
            escapeHtml(partner.label || "") +
            '">'
          );
        }
        return partner.label ? "<span>" + escapeHtml(partner.label) + "</span>" : "";
      })
      .join("");
    var footer =
      presenter.role === "support" && presenter.logo_url
        ? '<footer class="sp-sheet-support">' +
          '<img src="' +
          escapeHtml(presenter.logo_url) +
          '" alt="' +
          escapeHtml(presenter.name || "") +
          '"><span>com ' +
          escapeHtml(presenter.name || "CentralComm") +
          "</span></footer>"
        : presenter.role === "principal"
          ? '<footer class="sp-sheet-support is-principal"><span>' +
            escapeHtml(presenter.name || "") +
            "</span></footer>"
          : "";
    applyTheme(theme);
    return (
      '<article class="sp-sheet is-pitch" data-market="' +
      escapeHtml(theme.id || "") +
      '">' +
      '<div class="sp-sheet-band" aria-hidden="true"></div>' +
      '<header class="sp-sheet-brands">' +
      logoBox(branding.client, "client") +
      logoBox(branding.agency, "agency") +
      (presenter.role === "principal" ? logoBox(presenter, "presenter") : "") +
      "</header>" +
      '<div class="sp-sheet-lead">' +
      "<h2>" +
      escapeHtml(meta.client || hero.name || meta.title || "Página única") +
      "</h2>" +
      (meta.agency ? "<p>" + escapeHtml(meta.agency) + "</p>" : "") +
      "</div>" +
      (strategyIdx >= 0 ? fieldBlock(strategy, sectionIndex, strategyIdx, "Estratégia") : "") +
      '<div class="sp-sheet-main">' +
      (creativeIdx >= 0
        ? '<div class="sp-hero">' +
          mockup(creative, hero) +
          fieldBlock(creative, sectionIndex, creativeIdx, "Criativo no canal", [
            "channel",
            "surface",
            "image_url",
            "image_prompt",
          ]) +
          "</div>"
        : "") +
      '<aside class="sp-aside">' +
      (marketIdx >= 0
        ? '<div class="sp-market"><p class="sp-stat">' +
          escapeHtml(market.stat || "") +
          '</p><p class="sp-stat-label">' +
          escapeHtml(market.stat_label || "") +
          "</p>" +
          fieldBlock(market, sectionIndex, marketIdx, "Mercado", ["stat", "stat_label"]) +
          "</div>"
        : "") +
      densityChart(theme) +
      (defenseIdx >= 0 ? fieldBlock(defense, sectionIndex, defenseIdx, "Defesa") : "") +
      "</aside></div>" +
      shareBlock(share) +
      (partners ? '<div class="sp-partners">' + partners + "</div>" : "") +
      footer +
      "</article>"
    );
  }

  function cardMarkup(card, sectionIndex, cardIndex, extraClass, labelOverride) {
    var type = card.type || "summary";
    var label = labelOverride || TYPE_LABELS[type] || card.title || "Bloco";
    return (
      '<article class="sp-card' +
      (extraClass ? " " + extraClass : "") +
      '" data-section="' +
      sectionIndex +
      '" data-card="' +
      cardIndex +
      '" data-type="' +
      escapeHtml(type) +
      '">' +
      '<span class="sp-card-type">' +
      escapeHtml(label) +
      "</span>" +
      '<input value="' +
      escapeHtml(card.title) +
      '" data-field="title">' +
      '<textarea data-field="body">' +
      escapeHtml(card.body) +
      "</textarea></article>"
    );
  }

  function renderLegacySheet(section, sectionIndex) {
    var cards = section.cards || [];
    var used = {};
    var slots = LEGACY_SLOTS.map(function (slot) {
      var index = cards.findIndex(function (card, i) {
        return card.type === slot.type && !used[i];
      });
      if (index < 0) return "";
      used[index] = true;
      return cardMarkup(cards[index], sectionIndex, index, slot.wide ? "is-wide" : "", slot.label);
    }).join("");
    var meta = plan.meta || {};
    return (
      '<article class="sp-sheet">' +
      '<div class="sp-sheet-band" aria-hidden="true"></div>' +
      '<header class="sp-sheet-head"><strong>Página única</strong><h2>' +
      escapeHtml(meta.title || meta.campaign || "Página única") +
      "</h2></header>" +
      '<div class="sp-sheet-grid">' +
      slots +
      "</div></article>"
    );
  }

  function renderBoard() {
    return (plan.sections || [])
      .map(function (section, sectionIndex) {
        var cards = (section.cards || [])
          .map(function (card, cardIndex) {
            return cardMarkup(card, sectionIndex, cardIndex, "");
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
  }

  function isPitchSheet(section) {
    return (section.cards || []).some(function (card) {
      return card.type === "strategy" || card.type === "defense" || card.type === "creative";
    });
  }

  function render() {
    if (!board) return;
    var sections = plan.sections || [];
    if (!sections.length || !sections.some(function (section) { return (section.cards || []).length; })) {
      board.innerHTML = '<div class="sp-empty-board"><p>A folha ainda está vazia. Clique em Gerar de novo.</p></div>';
      return;
    }
    if (mode === "one_page") {
      board.innerHTML = isPitchSheet(sections[0] || {})
        ? renderPitchSheet(sections[0] || {}, 0)
        : renderLegacySheet(sections[0] || {}, 0);
      return;
    }
    board.innerHTML = renderBoard();
  }

  function collect() {
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
      node.querySelectorAll("[data-extra]").forEach(function (hidden) {
        card[hidden.getAttribute("data-extra")] = hidden.value;
      });
    });
    return plan;
  }

  async function load() {
    var endpoint = isPublic
      ? "/smart-planner/api/p/" + token
      : "/smart-planner/api/" + token + "/canvas";
    var response = await fetch(endpoint, {
      credentials: "same-origin",
    });
    var payload = await response.json();
    if (!payload.success) throw new Error(payload.error || "Falha ao carregar");
    plan = payload.data.plan || { sections: [] };
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
    render();
  }

  document.getElementById("sp-canvas-save")?.addEventListener("click", async function () {
    try {
      var response = await fetch("/smart-planner/api/" + token + "/canvas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ plan: collect() }),
      });
      var payload = await response.json();
      if (!payload.success) throw new Error(payload.error || "Falha ao salvar");
      toast("Quadro salvo.", "success");
    } catch (error) {
      toast(error.message, "error");
    }
  });

  document.getElementById("sp-canvas-regen")?.addEventListener("click", async function () {
    try {
      await regenerate();
      toast(
        mode === "one_page"
          ? "Página única e arte geradas no GPT Image 2."
          : "Quadro gerado de novo.",
        "success"
      );
    } catch (error) {
      toast(error.message, "error");
    }
  });

  presenterSelect?.addEventListener("change", async function () {
    try {
      await regenerate(presenterSelect.value);
      toast(
        presenterSelect.value === "centralcomm"
          ? "CentralComm voltou como apoio."
          : "Marca principal trocada. CentralComm saiu da folha.",
        "success"
      );
    } catch (error) {
      toast(error.message, "error");
    }
  });

  board?.addEventListener("click", function (event) {
    if (event.target && event.target.getAttribute("data-print") === "1") {
      window.print();
    }
  });

  load().catch(function (error) {
    toast(error.message, "error");
  });
})();
