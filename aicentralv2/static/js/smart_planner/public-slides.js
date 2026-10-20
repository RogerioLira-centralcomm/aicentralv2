(function () {
  // Apresentação da proposta: um slide por vez no desktop (escalado para caber, sem rolagem),
  // grade com todas as miniaturas, tela cheia e, em telas estreitas, os slides empilhados.
  var body = document.body;
  var frames = Array.prototype.slice.call(document.querySelectorAll("[data-sx-frame]"));
  if (!frames.length) return;
  var stage = document.querySelector("[data-sx-stage]");
  var current = document.querySelector("[data-sx-current]");
  var progress = document.querySelector("[data-sx-progress]");
  var prev = document.querySelector("[data-sx-prev]");
  var next = document.querySelector("[data-sx-next]");
  var gridBtn = document.querySelector("[data-sx-grid]");
  var fullBtn = document.querySelector("[data-sx-full]");
  var index = 0;
  var STACK_WIDTH = 760;

  function fromHash() {
    var match = /^#s(\d+)$/.exec(window.location.hash || "");
    var value = match ? parseInt(match[1], 10) - 1 : 0;
    return Math.max(0, Math.min(frames.length - 1, value));
  }

  function viewportWidth() {
    // No celular a janela pode "alargar" com conteúdo largo; a tela física é o limite real.
    var widths = [window.innerWidth, document.documentElement.clientWidth];
    if (window.visualViewport) widths.push(Math.round(window.visualViewport.width * window.visualViewport.scale));
    if (window.screen && window.screen.width) widths.push(window.screen.width);
    return Math.min.apply(Math, widths.filter(function (value) { return value > 0; }));
  }

  function layout() {
    var width = viewportWidth();
    var stack = width < STACK_WIDTH || (window.innerHeight < 420 && width < 900);
    body.classList.toggle("is-stack", stack);
    var bar = document.querySelector(".sx-bar");
    var barH = bar ? bar.offsetHeight : 64;
    var k;
    if (stack) {
      k = (width - 24) / 1600;
    } else {
      // Espaço para as setas laterais e uma margem; o slide nunca passa da tela.
      var availW = width - 140;
      var availH = window.innerHeight - barH - 40;
      k = Math.min(availW / 1600, availH / 900);
    }
    document.documentElement.style.setProperty("--k", Math.max(0.12, k).toFixed(4));
    var cols = Math.max(2, Math.min(5, Math.floor((width - 48) / 340)));
    var thumb = Math.min(0.24, ((width - 48 - (cols - 1) * 22) / cols) / 1600);
    document.documentElement.style.setProperty("--thumb", Math.max(0.1, thumb).toFixed(4));
  }

  function show(target, opts) {
    index = Math.max(0, Math.min(frames.length - 1, target));
    frames.forEach(function (frame, i) {
      frame.classList.toggle("is-active", i === index);
      frame.setAttribute("aria-hidden", i === index || body.classList.contains("is-grid") || body.classList.contains("is-stack") ? "false" : "true");
    });
    if (current) current.textContent = String(index + 1);
    if (progress) progress.style.setProperty("--sx-progress", ((index + 1) / frames.length).toFixed(3));
    if (prev) prev.disabled = index === 0;
    if (next) next.disabled = index === frames.length - 1;
    if (!opts || opts.hash !== false) {
      var hash = "#s" + (index + 1);
      if (window.location.hash !== hash) history.replaceState(null, "", hash);
    }
    if (body.classList.contains("is-stack") && opts && opts.scroll) frames[index].scrollIntoView({ block: "start" });
  }

  function setGrid(on) {
    body.classList.toggle("is-grid", on);
    if (gridBtn) {
      gridBtn.setAttribute("aria-pressed", on ? "true" : "false");
      gridBtn.textContent = on ? "Voltar ao slide" : "Ver todos";
    }
    if (on) {
      frames[index].scrollIntoView({ block: "center" });
    } else {
      show(index);
    }
  }

  function step(delta) {
    if (body.classList.contains("is-grid")) return;
    show(index + delta);
  }

  if (prev) prev.addEventListener("click", function () { step(-1); });
  if (next) next.addEventListener("click", function () { step(1); });
  if (gridBtn) gridBtn.addEventListener("click", function () { setGrid(!body.classList.contains("is-grid")); });
  frames.forEach(function (frame, i) {
    frame.addEventListener("click", function () {
      if (!body.classList.contains("is-grid")) return;
      show(i);
      setGrid(false);
    });
  });
  if (fullBtn) {
    fullBtn.addEventListener("click", function () {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
    });
    document.addEventListener("fullscreenchange", function () {
      fullBtn.textContent = document.fullscreenElement ? "Sair da tela cheia" : "Tela cheia";
      layout();
    });
  }
  var copy = document.querySelector("[data-sx-copy]");
  if (copy) copy.addEventListener("click", function () {
    var url = (window.SMART_PLANNER_PUBLIC_URL || window.location.href.split("#")[0]);
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () {
      copy.textContent = "Link copiado";
      setTimeout(function () { copy.textContent = "Copiar link"; }, 1800);
    });
  });
  var print = document.querySelector("[data-sx-print]");
  if (print) print.addEventListener("click", function () { window.print(); });

  document.addEventListener("keydown", function (event) {
    if (event.target && /input|textarea|select/i.test(event.target.tagName)) return;
    var key = event.key;
    if (key === "ArrowRight" || key === "PageDown" || key === " ") { event.preventDefault(); step(1); }
    else if (key === "ArrowLeft" || key === "PageUp") { event.preventDefault(); step(-1); }
    else if (key === "Home") { event.preventDefault(); show(0); }
    else if (key === "End") { event.preventDefault(); show(frames.length - 1); }
    else if (key === "g" || key === "G") { setGrid(!body.classList.contains("is-grid")); }
    else if ((key === "f" || key === "F") && fullBtn) { fullBtn.click(); }
    else if (key === "Escape" && body.classList.contains("is-grid")) { setGrid(false); }
  });

  // Toque: arrastar para o lado troca de slide no modo apresentação.
  var touchX = null;
  if (stage) {
    stage.addEventListener("touchstart", function (event) { touchX = event.touches[0].clientX; }, { passive: true });
    stage.addEventListener("touchend", function (event) {
      if (touchX === null || body.classList.contains("is-stack") || body.classList.contains("is-grid")) return;
      var dx = event.changedTouches[0].clientX - touchX;
      if (Math.abs(dx) > 50) step(dx < 0 ? 1 : -1);
      touchX = null;
    });
  }

  // Celular: slide escalado fica ilegível; a versão documento é a leitura certa ali.
  var documentUrl = body.getAttribute("data-document-url");
  if (documentUrl && viewportWidth() < STACK_WIDTH && !/[?&]slides=1/.test(window.location.search)) {
    window.location.replace(documentUrl);
    return;
  }

  window.addEventListener("resize", layout);
  window.addEventListener("hashchange", function () { show(fromHash(), { hash: false, scroll: true }); });
  window.addEventListener("beforeprint", function () { document.documentElement.style.setProperty("--k", "1"); });
  window.addEventListener("afterprint", layout);
  layout();
  show(fromHash(), { scroll: true });
})();
