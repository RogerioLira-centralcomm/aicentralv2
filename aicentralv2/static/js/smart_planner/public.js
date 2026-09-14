(function () {
  function live(message) {
    var node = document.getElementById("cc-live");
    if (node) node.textContent = message || "";
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

  function initSmoothScroll() {
    document.querySelectorAll("[data-cc-section]").forEach(function (link) {
      link.addEventListener("click", function (event) {
        var id = link.getAttribute("href");
        var target = id && document.querySelector(id);
        if (!target) return;
        event.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        if (history.replaceState) history.replaceState(null, "", id);
      });
    });
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
    var sections = Array.prototype.slice.call(document.querySelectorAll(".cc-section[id]"));
    if (!sections.length || !window.IntersectionObserver) return;
    var observer = new IntersectionObserver(function (entries) {
      var visible = entries.filter(function (entry) { return entry.isIntersecting; })
        .sort(function (a, b) { return b.intersectionRatio - a.intersectionRatio; });
      if (visible[0]) markSection(visible[0].target.id);
    }, { rootMargin: "-35% 0px -50% 0px", threshold: [0.15, 0.35, 0.6] });
    sections.forEach(function (section) { observer.observe(section); });
  }

  function initSectionNavigation() {
    var select = document.getElementById("cc-nav-select");
    if (!select) return;
    select.addEventListener("change", function () {
      var target = document.querySelector(select.value);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function initTimelineToggle() {
    var month = document.querySelector(".cc-gantt.is-month");
    var week = document.querySelector(".cc-gantt.is-week");
    document.querySelectorAll("[data-cc-scale]").forEach(function (button) {
      button.addEventListener("click", function () {
        var scale = button.getAttribute("data-cc-scale");
        document.querySelectorAll("[data-cc-scale]").forEach(function (item) {
          item.setAttribute("aria-pressed", item === button ? "true" : "false");
        });
        if (month) month.hidden = scale !== "mes";
        if (week) week.hidden = scale !== "semana";
      });
    });
  }

  function initPortalFilters() {
    var list = document.getElementById("cc-inventory");
    if (!list) return;
    var query = document.getElementById("cc-inventory-q");
    var current = "todos";
    function apply() {
      var term = ((query && query.value) || "").toLowerCase();
      list.querySelectorAll("li").forEach(function (item) {
        var tags = item.getAttribute("data-tags") || "";
        var text = item.textContent.toLowerCase();
        var tagOk = current === "todos" || tags.indexOf(current) !== -1;
        var qOk = !term || text.indexOf(term) !== -1;
        item.classList.toggle("is-off", !(tagOk && qOk));
      });
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
  initSmoothScroll();
  initSectionNavigation();
  initScrollSpy();
  initTimelineToggle();
  initPortalFilters();
  initChannelPick();
  markSection((document.querySelector(".cc-section[id]") || {}).id);
})();
