(function () {
  // Apresentação da proposta. Padrão de modo apresentação (Canva, Google Slides, Keynote):
  // um slide por vez escalado para caber, dock que some em tela cheia, clique nas laterais,
  // grade de miniaturas, atalhos, e modo apresentador numa segunda janela sincronizada.
  var body = document.body;
  var frames = Array.prototype.slice.call(document.querySelectorAll("[data-sx-frame]"));
  if (!frames.length) return;
  var $ = function (selector) { return document.querySelector(selector); };
  var $$ = function (selector) { return Array.prototype.slice.call(document.querySelectorAll(selector)); };
  var stage = $("[data-sx-stage]");
  var dock = $("[data-sx-dock]");
  var live = $("[data-sx-live]");
  var help = $("[data-sx-help-panel]");
  var presenterPanel = $("[data-sx-presenter-panel]");
  var params = new URLSearchParams(window.location.search);
  var isPresenter = params.get("apresentador") === "1";
  var index = 0;
  var STACK_WIDTH = 760;
  var IDLE_MS = 2500;
  var idleTimer = null;
  var channel = null;

  // ---------------------------------------------------------------- medidas
  function viewportWidth() {
    // No celular a janela pode "alargar" com conteúdo largo; a tela física é o limite real.
    var widths = [window.innerWidth, document.documentElement.clientWidth];
    if (window.visualViewport) widths.push(Math.round(window.visualViewport.width * window.visualViewport.scale));
    if (window.screen && window.screen.width) widths.push(window.screen.width);
    return Math.min.apply(Math, widths.filter(function (value) { return value > 0; }));
  }

  function px(name, fallback) {
    var value = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
    return isNaN(value) ? fallback : value;
  }

  function layout() {
    var width = viewportWidth();
    var height = window.innerHeight;
    var stack = !isPresenter && (width < STACK_WIDTH || (height < 420 && width < 900));
    body.classList.toggle("is-stack", stack);
    var k;
    if (stack) {
      k = (width - 24) / 1600;
    } else if (body.classList.contains("is-fullscreen")) {
      k = Math.min(width / 1600, height / 900);
    } else if (isPresenter) {
      k = Math.min((width - 420 - 48) / 1600, (height - px("--sx-dock", 56) - 72) / 900);
    } else {
      // Navbar em cima, dock embaixo e 24px de respiro em volta: margem igual dos lados.
      var bar = px("--sx-bar", 60);
      var dockH = px("--sx-dock", 56);
      k = Math.min((width - 48) / 1600, (height - bar - dockH - 24 - 48) / 900);
    }
    document.documentElement.style.setProperty("--k", Math.max(0.12, k).toFixed(4));
    var cols = Math.max(2, Math.min(5, Math.floor((width - 48) / 320)));
    var thumb = Math.min(0.22, ((Math.min(width, 1680) - 48 - (cols - 1) * 24) / cols) / 1600);
    document.documentElement.style.setProperty("--thumb", Math.max(0.1, thumb).toFixed(4));
    body.classList.remove("is-booting");
  }

  // ---------------------------------------------------------------- navegação
  function fromHash() {
    var match = /^#s(\d+)$/.exec(window.location.hash || "");
    var value = match ? parseInt(match[1], 10) - 1 : 0;
    return Math.max(0, Math.min(frames.length - 1, value));
  }

  function show(target, opts) {
    opts = opts || {};
    var previous = index;
    index = Math.max(0, Math.min(frames.length - 1, target));
    var grid = body.classList.contains("is-grid");
    frames.forEach(function (frame, i) {
      var active = i === index;
      frame.classList.toggle("is-active", active);
      frame.classList.toggle("is-back", active && index < previous);
      frame.setAttribute("aria-hidden", active || grid || body.classList.contains("is-stack") ? "false" : "true");
      if (grid) frame.setAttribute("tabindex", active ? "0" : "-1");
    });
    var title = frames[index].getAttribute("data-title") || "";
    $$("[data-sx-current]").forEach(function (el) { el.textContent = String(index + 1); });
    $$("[data-sx-title]").forEach(function (el) { el.textContent = title; });
    var progress = $("[data-sx-progress]");
    if (progress) progress.style.setProperty("--sx-progress", ((index + 1) / frames.length).toFixed(3));
    $$("[data-sx-prev]").forEach(function (el) { el.disabled = index === 0; });
    $$("[data-sx-next]").forEach(function (el) { el.disabled = index === frames.length - 1; });
    if (live && previous !== index) live.textContent = "Slide " + (index + 1) + " de " + frames.length + ": " + title;
    if (opts.hash !== false) {
      var hash = "#s" + (index + 1);
      if (window.location.hash !== hash) history.replaceState(null, "", hash);
    }
    if (grid) frames[index].focus({ preventScroll: false });
    if (body.classList.contains("is-stack") && opts.scroll) frames[index].scrollIntoView({ block: "start" });
    if (isPresenter) paintPresenter();
    if (!opts.remote && channel) channel.postMessage({ type: "goto", index: index });
  }

  function step(delta) {
    if (body.classList.contains("is-grid")) return;
    show(index + delta);
  }

  // ---------------------------------------------------------------- grade
  function gridColumns() {
    var first = frames[0].getBoundingClientRect();
    var count = 0;
    for (var i = 0; i < frames.length; i++) {
      if (Math.abs(frames[i].getBoundingClientRect().top - first.top) < 4) count++;
      else break;
    }
    return Math.max(1, count);
  }

  function setGrid(on) {
    body.classList.toggle("is-grid", on);
    var button = $("[data-sx-grid]");
    if (button) button.setAttribute("aria-pressed", on ? "true" : "false");
    show(index, { hash: false });
    if (on) frames[index].scrollIntoView({ block: "center" });
    else frames[index].removeAttribute("tabindex");
  }

  frames.forEach(function (frame, i) {
    frame.addEventListener("click", function (event) {
      if (!body.classList.contains("is-grid")) return;
      event.stopPropagation();
      show(i);
      setGrid(false);
    });
  });

  // ---------------------------------------------------------------- tela cheia e chrome
  function canFullscreen() { return !!(document.documentElement.requestFullscreen && document.fullscreenEnabled !== false); }

  function setFullscreen(on) {
    if (canFullscreen()) {
      if (on && !document.fullscreenElement) document.documentElement.requestFullscreen().catch(function () { pseudoFullscreen(true); });
      else if (!on && document.fullscreenElement) document.exitFullscreen();
      else if (!on) pseudoFullscreen(false);
      return;
    }
    pseudoFullscreen(on);
  }

  // Sem a API (iOS, iframe, navegador que recusa): o mesmo modo, só sem a barra do navegador.
  function pseudoFullscreen(on) {
    body.classList.toggle("is-fullscreen", on);
    layout();
    wake();
  }

  document.addEventListener("fullscreenchange", function () {
    var on = !!document.fullscreenElement;
    body.classList.toggle("is-fullscreen", on);
    var button = $("[data-sx-full]");
    if (button) {
      button.setAttribute("aria-label", on ? "Sair da tela cheia" : "Tela cheia");
      button.setAttribute("title", on ? "Sair da tela cheia (F)" : "Tela cheia (F)");
    }
    layout();
    wake();
  });

  function wake() {
    body.classList.remove("is-idle");
    window.clearTimeout(idleTimer);
    if (!body.classList.contains("is-fullscreen")) return;
    idleTimer = window.setTimeout(function () {
      // O dock não some enquanto o mouse está em cima dele.
      if (dock && dock.matches(":hover")) { wake(); return; }
      body.classList.add("is-idle");
    }, IDLE_MS);
  }
  ["mousemove", "pointerdown", "keydown", "touchstart"].forEach(function (name) {
    document.addEventListener(name, wake, { passive: true });
  });

  // ---------------------------------------------------------------- clique nas laterais
  function zoneFor(event) {
    var rect = frames[index].getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) return 0;
    return event.clientX < rect.left + rect.width / 3 ? -1 : 1;
  }
  if (stage) {
    stage.addEventListener("click", function (event) {
      if (body.classList.contains("is-grid") || body.classList.contains("is-stack")) return;
      if (event.target.closest("a,button,input,select,textarea,summary")) return;
      var zone = zoneFor(event);
      if (zone) step(zone);
    });
    stage.addEventListener("mousemove", function (event) {
      var interactive = event.target.closest("a,button");
      var zone = body.classList.contains("is-grid") || interactive ? 0 : zoneFor(event);
      stage.classList.toggle("is-hover-next", zone === 1 && index < frames.length - 1);
      stage.classList.toggle("is-hover-prev", zone === -1 && index > 0);
    });
  }

  // ---------------------------------------------------------------- modo apresentador
  function presenterUrl() {
    var base = window.location.href.split("#")[0].split("?")[0];
    return base + "?apresentador=1#s" + (index + 1);
  }

  function openPresenter() {
    var name = "sx-presenter-" + (body.getAttribute("data-channel") || "plano");
    var win = window.open(presenterUrl(), name, "width=1280,height=800");
    if (win) win.focus();
  }

  var startedAt = Date.now();
  function two(n) { return (n < 10 ? "0" : "") + n; }
  function tick() {
    var timer = $("[data-sx-timer]");
    var clock = $("[data-sx-clock]");
    var elapsed = Math.floor((Date.now() - startedAt) / 1000);
    if (timer) timer.textContent = two(Math.floor(elapsed / 60)) + ":" + two(elapsed % 60);
    if (clock) clock.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  }

  function paintPresenter() {
    var slot = $("[data-sx-next-slot]");
    var list = $("[data-sx-notes-list]");
    if (slot) {
      slot.innerHTML = "";
      var next = frames[index + 1];
      slot.classList.toggle("is-end", !next);
      if (next) slot.appendChild(next.querySelector(".sx-slide").cloneNode(true));
    }
    if (list) {
      var template = frames[index].querySelector("template[data-sx-notes]");
      list.innerHTML = template ? template.innerHTML : "";
    }
  }

  if (isPresenter) {
    body.classList.add("is-presenter");
    if (presenterPanel) presenterPanel.hidden = false;
    document.title = "Apresentador · " + document.title;
    tick();
    window.setInterval(tick, 1000);
    var reset = $("[data-sx-timer-reset]");
    if (reset) reset.addEventListener("click", function () { startedAt = Date.now(); tick(); });
  }

  if ("BroadcastChannel" in window) {
    channel = new BroadcastChannel("sx-" + (body.getAttribute("data-channel") || "plano"));
    channel.onmessage = function (event) {
      var data = event.data || {};
      if (data.type === "goto" && typeof data.index === "number" && data.index !== index) show(data.index, { remote: true });
      if (data.type === "hello" && !isPresenter) channel.postMessage({ type: "goto", index: index });
    };
    if (isPresenter) channel.postMessage({ type: "hello" });
  }

  // ---------------------------------------------------------------- menu, ajuda, compartilhar
  var menu = $("[data-sx-menu]");
  var menuToggle = $("[data-sx-menu-toggle]");
  function setMenu(open) {
    if (!menu || !menuToggle) return;
    menu.querySelector(".sx-menu-list").hidden = !open;
    menuToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) menu.querySelector(".sx-menu-list [role=menuitem]").focus();
  }
  if (menuToggle) menuToggle.addEventListener("click", function (event) {
    event.stopPropagation();
    setMenu(menuToggle.getAttribute("aria-expanded") !== "true");
  });
  document.addEventListener("click", function (event) {
    if (menu && !menu.contains(event.target)) setMenu(false);
  });

  var lastFocus = null;
  function setHelp(open) {
    if (!help) return;
    help.hidden = !open;
    if (open) {
      lastFocus = document.activeElement;
      help.querySelector("[data-sx-help-close]").focus();
    } else if (lastFocus) {
      lastFocus.focus();
    }
  }
  $$("[data-sx-help]").forEach(function (el) { el.addEventListener("click", function () { setHelp(true); }); });
  var helpClose = $("[data-sx-help-close]");
  if (helpClose) helpClose.addEventListener("click", function () { setHelp(false); });
  if (help) help.addEventListener("click", function (event) { if (event.target === help) setHelp(false); });

  $$("[data-sx-prev]").forEach(function (el) { el.addEventListener("click", function () { step(-1); }); });
  $$("[data-sx-next]").forEach(function (el) { el.addEventListener("click", function () { step(1); }); });
  $$("[data-sx-grid]").forEach(function (el) { el.addEventListener("click", function () { setGrid(!body.classList.contains("is-grid")); }); });
  $$("[data-sx-full]").forEach(function (el) { el.addEventListener("click", function () { setFullscreen(!body.classList.contains("is-fullscreen")); }); });
  $$("[data-sx-present]").forEach(function (el) { el.addEventListener("click", function () { setGrid(false); setFullscreen(true); }); });
  $$("[data-sx-presenter]").forEach(function (el) { el.addEventListener("click", function () { setMenu(false); openPresenter(); }); });
  $$("[data-sx-copy]").forEach(function (el) {
    el.addEventListener("click", function () {
      var url = window.SMART_PLANNER_PUBLIC_URL || window.location.href.split("#")[0];
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(url).then(function () {
        var label = el.textContent;
        el.textContent = "Link copiado";
        if (live) live.textContent = "Link copiado";
        setTimeout(function () { el.textContent = label; setMenu(false); }, 1400);
      });
    });
  });
  $$("[data-sx-print]").forEach(function (el) { el.addEventListener("click", function () { setMenu(false); window.print(); }); });

  // ---------------------------------------------------------------- teclado
  document.addEventListener("keydown", function (event) {
    if (event.target && /input|textarea|select/i.test(event.target.tagName)) return;
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    var key = event.key;
    if (help && !help.hidden) {
      if (key === "Escape" || key === "?") { event.preventDefault(); setHelp(false); }
      return;
    }
    if (body.classList.contains("is-grid")) {
      var cols = gridColumns();
      var moves = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: cols, ArrowUp: -cols };
      if (moves[key] !== undefined) { event.preventDefault(); show(index + moves[key], { hash: false }); return; }
      if (key === "Enter" || key === " ") { event.preventDefault(); setGrid(false); return; }
      if (key === "Escape" || key === "g" || key === "G") { event.preventDefault(); setGrid(false); return; }
      return;
    }
    if (key === "ArrowRight" || key === "PageDown" || key === " ") { event.preventDefault(); step(1); }
    else if (key === "ArrowLeft" || key === "PageUp") { event.preventDefault(); step(-1); }
    else if (key === "Home") { event.preventDefault(); show(0); }
    else if (key === "End") { event.preventDefault(); show(frames.length - 1); }
    else if (/^[1-9]$/.test(key)) { show(parseInt(key, 10) - 1); }
    else if (key === "g" || key === "G") { setGrid(true); }
    else if (key === "f" || key === "F") { setFullscreen(!body.classList.contains("is-fullscreen")); }
    else if (key === "p" || key === "P") { if (!isPresenter) openPresenter(); }
    else if (key === "?") { setHelp(true); }
    else if (key === "Escape") { setMenu(false); if (body.classList.contains("is-fullscreen") && !document.fullscreenElement) setFullscreen(false); }
  });

  // Toque: arrastar para o lado troca de slide.
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
  if (documentUrl && !isPresenter && viewportWidth() < STACK_WIDTH && params.get("slides") !== "1") {
    window.location.replace(documentUrl);
    return;
  }

  window.addEventListener("resize", layout);
  window.addEventListener("hashchange", function () { show(fromHash(), { hash: false, scroll: true }); });
  window.addEventListener("beforeprint", function () { document.documentElement.style.setProperty("--k", "1"); });
  window.addEventListener("afterprint", layout);
  layout();
  show(fromHash(), { scroll: true, remote: isPresenter });
})();
