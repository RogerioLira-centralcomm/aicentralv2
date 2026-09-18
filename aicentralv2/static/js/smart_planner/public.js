(function () {
  function live(message) {
    var node = document.getElementById("cc-live");
    if (node) node.textContent = message || "";
  }

  function navData() {
    var node = document.getElementById("cc-nav-data");
    if (!node) return { folha: [], plano: [] };
    try {
      return JSON.parse(node.textContent || "{}");
    } catch (err) {
      return { folha: [], plano: [] };
    }
  }

  function closeMenus() {
    document.querySelectorAll("[data-cc-menu]").forEach(function (menu) {
      var list = menu.querySelector(".cc-menu-list");
      var button = menu.querySelector("[aria-expanded]");
      if (list) list.hidden = true;
      if (button) button.setAttribute("aria-expanded", "false");
    });
  }

  function initActionMenus() {
    document.querySelectorAll("[data-cc-menu]").forEach(function (menu) {
      var button = menu.querySelector("[aria-expanded]");
      var list = menu.querySelector(".cc-menu-list");
      if (!button || !list) return;
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        var open = list.hidden;
        closeMenus();
        list.hidden = !open;
        button.setAttribute("aria-expanded", open ? "true" : "false");
      });
    });
    document.addEventListener("click", closeMenus);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeMenus();
    });
  }

  function copyLink() {
    var url = document.body.getAttribute("data-share") || location.href;
    var done = function () { live("Link copiado"); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(done).catch(function () {
        window.prompt("Copie o link", url);
      });
      return;
    }
    window.prompt("Copie o link", url);
  }

  function initShareButton() {
    var share = document.getElementById("cc-share");
    if (!share) return;
    share.addEventListener("click", function () {
      var url = document.body.getAttribute("data-share") || location.href;
      var title = document.title;
      if (navigator.share) {
        navigator.share({ title: title, url: url }).catch(function () {});
        return;
      }
      copyLink();
    });
  }

  function initPrintButton() {
    function printPage() { window.print(); }
    var printBtn = document.getElementById("cc-print");
    if (printBtn) printBtn.addEventListener("click", printPage);
    document.querySelectorAll("[data-cc-print]").forEach(function (button) {
      button.addEventListener("click", printPage);
    });
    var copy = document.getElementById("cc-copy");
    if (copy) copy.addEventListener("click", copyLink);
  }

  function bindSectionLinks(root) {
    (root || document).querySelectorAll("[data-cc-section]").forEach(function (link) {
      link.addEventListener("click", function (event) {
        var id = link.getAttribute("href");
        var target = id && document.querySelector(id);
        if (!target || target.closest("[hidden]")) return;
        event.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        if (history.replaceState) history.replaceState(null, "", id);
      });
    });
  }

  function renderNav(view) {
    var data = navData();
    var items = data[view] || [];
    var nav = document.getElementById("cc-nav");
    var tabs = document.getElementById("cc-nav-tabs");
    var select = document.getElementById("cc-nav-select");
    if (!nav || !tabs || !select) return;
    nav.hidden = !items.length;
    tabs.innerHTML = "";
    select.innerHTML = "";
    items.forEach(function (item) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#" + item.id;
      a.setAttribute("data-cc-section", item.id);
      a.textContent = item.label;
      li.appendChild(a);
      tabs.appendChild(li);
      var option = document.createElement("option");
      option.value = "#" + item.id;
      option.textContent = item.label;
      select.appendChild(option);
    });
    bindSectionLinks(tabs);
    if (items[0]) markSection(items[0].id);
  }

  function markSection(id) {
    document.querySelectorAll("[data-cc-section]").forEach(function (link) {
      var on = link.getAttribute("data-cc-section") === id;
      if (on) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    });
    var select = document.getElementById("cc-nav-select");
    if (select && id) select.value = "#" + id;
  }

  function initScrollSpy() {
    if (!window.IntersectionObserver) return;
    var observer = new IntersectionObserver(function (entries) {
      var visible = entries
        .filter(function (entry) {
          return entry.isIntersecting && !entry.target.closest("[hidden]");
        })
        .sort(function (a, b) { return b.intersectionRatio - a.intersectionRatio; });
      if (visible[0]) markSection(visible[0].target.id);
    }, { rootMargin: "-35% 0px -50% 0px", threshold: [0.15, 0.35, 0.6] });
    document.querySelectorAll(".cc-section[id], .cc-plan-chapter[id], .cc-plan-board > section[id]").forEach(function (section) {
      observer.observe(section);
    });
  }

  function initSectionNavigation() {
    var select = document.getElementById("cc-nav-select");
    if (!select) return;
    select.addEventListener("change", function () {
      var target = document.querySelector(select.value);
      if (target && !target.closest("[hidden]")) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }

  function setView(view, options) {
    var opts = options || {};
    var hasFolha = document.body.getAttribute("data-has-folha") === "1";
    var hasPlano = document.body.getAttribute("data-has-plano") === "1";
    if (view === "folha" && !hasFolha && hasPlano) view = "plano";
    if (view === "plano" && !hasPlano && hasFolha) view = "folha";
    document.body.setAttribute("data-view", view);
    document.body.setAttribute("data-tab", view);
    document.querySelectorAll("[data-view-panel]").forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-view-panel") !== view;
    });
    document.querySelectorAll("[data-cc-view]").forEach(function (button) {
      var on = button.getAttribute("data-cc-view") === view;
      button.setAttribute("aria-selected", on ? "true" : "false");
    });
    renderNav(view);
    live(view === "plano" ? "Visualização: plano completo" : "Visualização: página única");
    if (!opts.silent && history.replaceState) {
      history.replaceState(null, "", "#" + view);
    }
    if (!opts.keepScroll) {
      var shell = document.getElementById("conteudo");
      if (shell) shell.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function initViewSwitch() {
    document.querySelectorAll("[data-cc-view]").forEach(function (button) {
      button.addEventListener("click", function () {
        setView(button.getAttribute("data-cc-view"));
      });
    });
    var hash = (location.hash || "").replace(/^#/, "");
    var data = navData();
    var initial = document.body.getAttribute("data-view") || "folha";
    if (hash === "folha" || hash === "plano") {
      initial = hash;
    } else if (hash) {
      if ((data.plano || []).some(function (item) { return item.id === hash; })) initial = "plano";
      else if ((data.folha || []).some(function (item) { return item.id === hash; })) initial = "folha";
    }
    setView(initial, { silent: hash !== "folha" && hash !== "plano", keepScroll: Boolean(hash && hash !== "folha" && hash !== "plano") });
    if (hash && hash !== "folha" && hash !== "plano") {
      window.setTimeout(function () {
        var target = document.getElementById(hash);
        if (target && !target.closest("[hidden]")) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
          markSection(hash);
        }
      }, 40);
    }
    window.addEventListener("hashchange", function () {
      var next = (location.hash || "").replace(/^#/, "");
      if (next === "folha" || next === "plano") setView(next, { silent: true, keepScroll: true });
    });
  }

  function initTimelineToggle() {
    var month = document.querySelector(".cc-gantt.is-month");
    var week = document.querySelector(".cc-gantt.is-week");
    if (!month || !week) return;
    document.querySelectorAll("[data-cc-scale]").forEach(function (button) {
      button.addEventListener("click", function () {
        var scale = button.getAttribute("data-cc-scale");
        document.querySelectorAll("[data-cc-scale]").forEach(function (item) {
          item.setAttribute("aria-pressed", item === button ? "true" : "false");
        });
        month.hidden = scale !== "mes";
        week.hidden = scale !== "semana";
        live(scale === "semana" ? "Visão semanal de intensidade" : "Visão mensal do voo");
      });
    });
  }

  function initPortalFilters() {
    var list = document.getElementById("cc-inventory");
    if (!list) return;
    var query = document.getElementById("cc-inventory-q");
    var count = document.getElementById("cc-inventory-count");
    var current = "todos";
    function apply() {
      var term = ((query && query.value) || "").toLowerCase();
      var visible = 0;
      list.querySelectorAll("li").forEach(function (item) {
        var tags = item.getAttribute("data-tags") || "";
        var text = item.textContent.toLowerCase();
        var tagOk = current === "todos" || tags.indexOf(current) !== -1;
        var qOk = !term || text.indexOf(term) !== -1;
        var on = tagOk && qOk;
        item.classList.toggle("is-off", !on);
        if (on) visible += 1;
      });
      if (count) {
        count.textContent = visible === 1
          ? "1 ambiente potencial"
          : visible + " ambientes potenciais";
      }
    }
    document.querySelectorAll("[data-cc-filter]").forEach(function (button) {
      button.addEventListener("click", function () {
        current = button.getAttribute("data-cc-filter");
        document.querySelectorAll("[data-cc-filter]").forEach(function (item) {
          item.setAttribute("aria-pressed", item === button ? "true" : "false");
        });
        apply();
      });
    });
    if (query) query.addEventListener("input", apply);
  }

  function initChannelPick() {
    var pinned = "";
    function mark(id) {
      var current = id || pinned;
      document.querySelectorAll("[data-canal]").forEach(function (node) {
        node.classList.toggle("is-on", Boolean(current && node.getAttribute("data-canal") === current));
      });
    }
    document.querySelectorAll(".cc-legend button, .cc-gantt-row, .cc-table tbody tr").forEach(function (node) {
      var canal = node.getAttribute("data-canal") || (node.closest("[data-canal]") && node.closest("[data-canal]").getAttribute("data-canal"));
      if (!canal) return;
      node.addEventListener("mouseenter", function () { mark(canal); });
      node.addEventListener("click", function () {
        pinned = pinned === canal ? "" : canal;
        mark(pinned);
      });
    });
  }

  function initReducedMotion() {
    if (!window.matchMedia || !window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    document.documentElement.style.scrollBehavior = "auto";
  }

  initReducedMotion();
  initActionMenus();
  initShareButton();
  initPrintButton();
  initSectionNavigation();
  initScrollSpy();
  initTimelineToggle();
  initPortalFilters();
  initChannelPick();
  initViewSwitch();
})();
