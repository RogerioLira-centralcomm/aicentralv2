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

  buildRail();

  function buildRail() {
    var rail = document.querySelector("[data-rail]");
    var list = rail && rail.querySelector("[data-rail-list]");
    var sections = Array.prototype.slice.call(document.querySelectorAll("main [data-nav][id]"));
    if (!rail || !list || sections.length < 3) return;
    var links = {};
    sections.forEach(function (section) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = "#" + section.id;
      link.textContent = section.getAttribute("data-nav");
      item.appendChild(link);
      list.appendChild(item);
      links[section.id] = link;
    });
    rail.hidden = false;
    var current = "";
    function activate(id) {
      if (id === current || !links[id]) return;
      if (links[current]) links[current].classList.remove("is-active");
      links[id].classList.add("is-active");
      links[id].setAttribute("aria-current", "true");
      if (links[current]) links[current].removeAttribute("aria-current");
      current = id;
      // Na faixa horizontal do celular, mantém o item ativo à vista.
      if (rail.scrollWidth > rail.clientWidth) {
        links[id].scrollIntoView({ block: "nearest", inline: "center" });
      }
    }
    function spy() {
      var line = window.innerHeight * 0.3;
      var active = sections[0].id;
      sections.forEach(function (section) {
        if (section.getBoundingClientRect().top <= line) active = section.id;
      });
      activate(active);
      var max = document.documentElement.scrollHeight - window.innerHeight;
      rail.style.setProperty("--rail-progress", max > 0 ? Math.min(1, window.scrollY / max).toFixed(3) : "0");
    }
    var ticking = false;
    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(function () { ticking = false; spy(); });
    }, { passive: true });
    window.addEventListener("resize", spy);
    spy();
  }

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
