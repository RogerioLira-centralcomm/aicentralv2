(function () {
  var root = document.body;
  var tabs = document.querySelectorAll("[data-cc-tab]");
  var panels = document.querySelectorAll("[data-cc-panel]");

  function known(id) {
    return id === "folha" || id === "plano" ? id : "";
  }

  function ready(id) {
    return Boolean(document.querySelector('[data-cc-panel="' + id + '"][data-ready="1"]'));
  }

  function fallback() {
    if (ready("folha")) return "folha";
    if (ready("plano")) return "plano";
    return "";
  }

  function show(id) {
    var wanted = known(id);
    var key = wanted && ready(wanted) ? wanted : fallback();
    if (!key) return;
    root.setAttribute("data-tab", key);
    tabs.forEach(function (tab) {
      var on = tab.getAttribute("data-cc-tab") === key;
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.classList.toggle("is-on", on);
    });
    panels.forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-cc-panel") !== key;
    });
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function (event) {
      event.preventDefault();
      var key = tab.getAttribute("data-cc-tab");
      if (history.replaceState) history.replaceState(null, "", "#" + key);
      show(key);
    });
    tab.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      var list = Array.prototype.slice.call(tabs);
      var index = list.indexOf(tab);
      var next = event.key === "ArrowRight" ? list[index + 1] || list[0] : list[index - 1] || list[list.length - 1];
      if (next) next.click();
    });
  });

  window.addEventListener("hashchange", function () {
    show(location.hash.replace("#", ""));
  });

  document.getElementById("cc-print")?.addEventListener("click", function () {
    window.print();
  });

  var pinned = "";

  function markCanal(id) {
    var current = id || pinned;
    var exec = document.querySelector(".cc-exec");
    if (exec) exec.classList.toggle("is-picking", Boolean(current));
    document.querySelectorAll("[data-canal]").forEach(function (node) {
      var on = Boolean(current && node.getAttribute("data-canal") === current);
      node.classList.toggle("is-on", on);
    });
    document.querySelectorAll("#cc-mix-legend button").forEach(function (button) {
      var li = button.closest("[data-canal]");
      var key = li && li.getAttribute("data-canal");
      button.setAttribute("aria-pressed", pinned && key === pinned ? "true" : "false");
    });
  }

  function pinCanal(id) {
    pinned = pinned === id ? "" : id;
    markCanal(pinned);
  }

  document.querySelectorAll("#cc-mix-legend button, .cc-gantt-row, .cc-exec-table tbody tr").forEach(function (node) {
    var canal = node.getAttribute("data-canal") || (node.closest("[data-canal]") && node.closest("[data-canal]").getAttribute("data-canal"));
    if (node.tagName === "BUTTON") {
      node.setAttribute("aria-pressed", "false");
      node.addEventListener("click", function () { pinCanal(canal); });
      node.addEventListener("mouseenter", function () { markCanal(canal); });
    } else {
      node.addEventListener("click", function () { pinCanal(canal); });
      node.addEventListener("mouseenter", function () { markCanal(canal); });
    }
  });
  document.querySelector(".cc-exec")?.addEventListener("mouseleave", function () { markCanal(pinned); });

  show(location.hash.replace("#", "") || root.getAttribute("data-tab"));
})();
