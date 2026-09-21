(function () {
  document.documentElement.classList.add("spv3-js");
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
