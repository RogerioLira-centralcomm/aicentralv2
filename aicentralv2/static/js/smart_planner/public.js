(function () {
  var root = document.body;
  var tabs = document.querySelectorAll("[data-cc-tab]");
  var panels = document.querySelectorAll("[data-cc-panel]");
  if (!tabs.length) return;

  function known(id) {
    return id === "folha" || id === "plano" ? id : "";
  }

  function fallback() {
    var ready = document.querySelector('[data-cc-panel="folha"][data-ready="1"]');
    return ready ? "folha" : "plano";
  }

  function show(id) {
    var key = known(id) || fallback();
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
  });

  window.addEventListener("hashchange", function () {
    show(location.hash.replace("#", ""));
  });

  document.getElementById("cc-print")?.addEventListener("click", function () {
    window.print();
  });

  show(location.hash.replace("#", "") || root.getAttribute("data-tab"));
})();
