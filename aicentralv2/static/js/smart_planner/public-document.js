(function () {
  document.documentElement.classList.add("spv3-js");
  var tabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
  function activate(tab, focus) {
    tabs.forEach(function (item) {
      var on = item === tab;
      item.setAttribute("aria-selected", on ? "true" : "false");
      item.tabIndex = on ? 0 : -1;
      var panel = document.getElementById(item.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
    });
    if (focus) tab.focus();
    history.replaceState(null, "", "#" + tab.getAttribute("aria-controls"));
  }
  tabs.forEach(function (tab, index) {
    tab.addEventListener("click", function () { activate(tab, false); });
    tab.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      var next = event.key === "ArrowRight" ? index + 1 : index - 1;
      activate(tabs[(next + tabs.length) % tabs.length], true);
    });
  });
  var fromHash = tabs.find(function (tab) { return "#" + tab.getAttribute("aria-controls") === location.hash; });
  if (fromHash) activate(fromHash, false);
  var print = document.querySelector("[data-print]");
  if (print) print.addEventListener("click", function () { window.print(); });
  var copy = document.querySelector("[data-copy-link]");
  if (copy) copy.addEventListener("click", function () {
    navigator.clipboard.writeText(window.SMART_PLANNER_PUBLIC_URL || location.href).then(function () {
      copy.textContent = "Link copiado";
      setTimeout(function () { copy.textContent = "Copiar link"; }, 1800);
    });
  });

  var reveals = Array.prototype.slice.call(document.querySelectorAll("[data-scroll-reveal]"));
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reveals.length || reduced || !("IntersectionObserver" in window)) {
    reveals.forEach(function (item) { item.classList.add("is-revealed"); });
    return;
  }
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-revealed");
      observer.unobserve(entry.target);
    });
  }, { rootMargin: "0px 0px -10% 0px", threshold: 0.08 });
  reveals.forEach(function (item) { observer.observe(item); });
})();
