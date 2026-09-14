(function () {
  var btn = document.querySelector(".cc-menu-btn");
  var mega = document.getElementById("cc-mega");
  var scrim = document.getElementById("cc-scrim");
  var canHover = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  var closeTimer;
  var ignoreDoc = false;
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function setMega(open) {
    if (!btn || !mega) return;
    window.clearTimeout(closeTimer);
    mega.hidden = !open;
    if (scrim) scrim.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    document.documentElement.classList.toggle("is-mega", open);
  }
  function openMega() { setMega(true); }
  function closeMega() { setMega(false); }
  function requestClose() {
    window.clearTimeout(closeTimer);
    closeTimer = window.setTimeout(closeMega, 140);
  }

  if (scrim && scrim.parentNode !== document.body) {
    document.body.appendChild(scrim);
  }

  if (btn && mega) {
    btn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var willOpen = mega.hidden;
      if (canHover) {
        if (willOpen) openMega();
      } else if (willOpen) {
        openMega();
      } else {
        closeMega();
      }
      ignoreDoc = true;
      window.setTimeout(function () { ignoreDoc = false; }, 0);
      if (willOpen && event.detail === 0) {
        var first = mega.querySelector(".cc-mega-item");
        if (first) first.focus();
      }
    });
    if (canHover) {
      btn.addEventListener("mouseenter", openMega);
      btn.addEventListener("mouseleave", requestClose);
      mega.addEventListener("mouseenter", function () { window.clearTimeout(closeTimer); });
      mega.addEventListener("mouseleave", requestClose);
    }
    if (scrim) scrim.addEventListener("click", closeMega);
    mega.addEventListener("keydown", function (event) {
      var items = Array.prototype.slice.call(mega.querySelectorAll(".cc-mega-item"));
      if (!items.length) return;
      var index = items.indexOf(document.activeElement);
      if (index < 0) index = 0;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        items[(index + 1) % items.length].focus();
        event.preventDefault();
      } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        items[(index - 1 + items.length) % items.length].focus();
        event.preventDefault();
      } else if (event.key === "Home") {
        items[0].focus();
        event.preventDefault();
      } else if (event.key === "End") {
        items[items.length - 1].focus();
        event.preventDefault();
      }
    });
    document.addEventListener("click", function (event) {
      if (ignoreDoc || mega.hidden) return;
      if (mega.contains(event.target) || btn.contains(event.target)) return;
      closeMega();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeMega();
        btn.focus();
      }
    });
  }

  var dataNode = document.getElementById("cc-place-data");
  if (!dataNode) return;
  var place = {};
  try {
    place = JSON.parse(dataNode.textContent || "{}") || {};
  } catch (error) {
    return;
  }
  var points = (place.points || []).filter(function (item) {
    return item && item.lat != null && item.lng != null;
  });
  var zones = place.zones || [];
  var nav = document.getElementById("cc-zone-nav");
  var map;
  var layers = {};
  var primed = false;

  function items() {
    if (points.length) return points.map(function (point) {
      return {
        id: point.id || point.name,
        name: point.name,
        radius: point.radius_label || ((point.radius_m || "") + " m"),
        radius_m: Number(point.radius_m) || 300,
        reach: point.reach || "A calibrar",
        reach_status: point.reach_status || "estimate",
        commercial: point.commercial || point.note || "",
        formats: point.formats || [],
        image: point.image_url || "",
        color: point.color || "#167A3A",
        lat: point.lat,
        lng: point.lng
      };
    });
    return zones.map(function (zone) {
      return {
        id: zone.id || zone.name,
        name: zone.name,
        radius: zone.radius,
        radius_m: 400,
        reach: zone.reach,
        reach_status: zone.reach_status || "estimate",
        commercial: zone.commercial || zone.description || "",
        formats: zone.formats || [],
        image: zone.image_url || "",
        color: zone.color || "#167A3A"
      };
    });
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setText(id, value) {
    var node = document.getElementById(id);
    if (node) node.textContent = value || "";
  }

  function setPhoto(id, url, name) {
    var img = document.getElementById(id);
    var wrap = img && img.closest(".cc-point-photo");
    if (!img || !wrap) return;
    if (url) {
      wrap.hidden = false;
      img.src = url;
      img.alt = name || "";
      wrap.classList.add("is-in");
    } else {
      wrap.hidden = true;
      wrap.classList.remove("is-in");
      img.removeAttribute("src");
    }
  }

  function setFlag(id, on) {
    var node = document.getElementById(id);
    if (node) node.hidden = !on;
  }

  function hashId() {
    try {
      return decodeURIComponent((location.hash || "").replace(/^#/, ""));
    } catch (error) {
      return (location.hash || "").replace(/^#/, "");
    }
  }

  function persist(item) {
    if (!item || !item.id || !history.replaceState) return;
    var next = "#" + encodeURIComponent(item.id);
    if (location.hash === next) return;
    history.replaceState(null, "", next);
  }

  function zoomFor(radius) {
    if (radius >= 1100) return 13;
    if (radius >= 700) return 14;
    if (radius >= 350) return 15;
    return 16;
  }

  function tipOptions(on) {
    return {
      permanent: !!on,
      direction: "center",
      className: "cc-map-tip",
      opacity: 1
    };
  }

  function paintLayer(id, on) {
    var entry = layers[id];
    var layer = entry && entry.circle;
    if (!layer || !layer.setStyle) return;
    layer.setStyle({
      weight: on ? 3 : 1.5,
      fillOpacity: on ? 0.28 : 0.12,
      opacity: on ? 1 : 0.55
    });
    if (layer.bringToFront && on) layer.bringToFront();
    if (layer.bindTooltip) {
      layer.unbindTooltip();
      layer.bindTooltip(entry.item.name + " · " + entry.item.radius, tipOptions(on));
      if (on) layer.openTooltip();
    }
  }

  function applyItem(item) {
    if (!item) return;
    document.querySelectorAll(".cc-zone-chip").forEach(function (chip) {
      var on = chip.getAttribute("data-zone") === item.id;
      chip.classList.toggle("is-on", on);
      chip.setAttribute("aria-selected", on ? "true" : "false");
      if (on && chip.scrollIntoView) {
        chip.scrollIntoView({ inline: "center", block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
      }
    });
    Object.keys(layers).forEach(function (key) {
      paintLayer(key, key === item.id);
    });
    setText("zoneName", item.name);
    setText("zoneCommercial", item.commercial);
    setText("zoneRadius", item.radius);
    setText("zoneReach", item.reach);
    setFlag("zoneReachFlag", item.reach_status === "to_validate");
    var formats = document.getElementById("zoneFormats");
    if (formats) {
      formats.textContent = (item.formats || []).join(", ");
      formats.hidden = !(item.formats && item.formats.length);
    }
    setPhoto("zonePhoto", item.image, item.name);
    var sheet = document.getElementById("cc-detail");
    if (sheet && primed) {
      sheet.classList.remove("is-swap");
      void sheet.offsetWidth;
      sheet.classList.add("is-swap");
      var title = document.getElementById("zoneName") || sheet;
      var box = title.getBoundingClientRect();
      if (box.top > window.innerHeight - 160) {
        sheet.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" });
      }
    }
    persist(item);
    if (map && item.lat != null) {
      var zoom = zoomFor(item.radius_m);
      if (!primed || reduceMotion) {
        map.setView([item.lat, item.lng], zoom);
        primed = true;
      } else {
        map.flyTo([item.lat, item.lng], zoom, { duration: 0.55 });
      }
    }
  }

  var catalog = items();
  if (nav && catalog.length) {
    nav.innerHTML = catalog.map(function (item, index) {
      return '<button type="button" class="cc-zone-chip" role="tab" data-zone="' +
        escapeHtml(item.id) + '" aria-selected="' + (index === 0 ? "true" : "false") + '">' +
        escapeHtml(item.name) + " <small>" + escapeHtml(item.radius) + "</small></button>";
    }).join("");
    nav.querySelectorAll(".cc-zone-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var item = catalog.find(function (entry) { return entry.id === chip.getAttribute("data-zone"); });
        applyItem(item);
      });
    });
    nav.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      var chips = Array.prototype.slice.call(nav.querySelectorAll(".cc-zone-chip"));
      var index = chips.findIndex(function (chip) { return chip.classList.contains("is-on"); });
      if (index < 0) index = 0;
      index += event.key === "ArrowRight" ? 1 : -1;
      if (index < 0) index = chips.length - 1;
      if (index >= chips.length) index = 0;
      chips[index].focus();
      var item = catalog.find(function (entry) { return entry.id === chips[index].getAttribute("data-zone"); });
      applyItem(item);
      event.preventDefault();
    });
  }

  var mapNode = document.getElementById("cc-map");
  if (mapNode && typeof L !== "undefined") {
    var geo = place.geo || {};
    var start = catalog[0] && catalog[0].lat != null
      ? [catalog[0].lat, catalog[0].lng]
      : [geo.lat || -15.8, geo.lng || -47.9];
    var startZoom = catalog[0] ? zoomFor(catalog[0].radius_m) : (geo.zoom || 15);
    map = L.map(mapNode, { scrollWheelZoom: false, attributionControl: true }).setView(start, startZoom);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Tiles &copy; Esri",
      maxZoom: 19
    }).addTo(map);
    catalog.forEach(function (item) {
      if (item.lat == null) return;
      var circle = L.circle([item.lat, item.lng], {
        radius: item.radius_m,
        color: item.color,
        weight: 1.5,
        fillColor: item.color,
        fillOpacity: 0.12,
        opacity: 0.55
      }).addTo(map);
      circle.bindTooltip(item.name + " · " + item.radius, tipOptions(false));
      circle.on("click", function () { applyItem(item); });
      layers[item.id] = { circle: circle, item: item };
    });
    window.setTimeout(function () { map.invalidateSize(); }, 200);
    window.addEventListener("resize", function () {
      if (map) map.invalidateSize();
    });
  }

  var wanted = hashId();
  var opening = catalog.find(function (item) { return item.id === wanted; }) || catalog[0];
  if (opening) applyItem(opening);
  if (wanted && opening && document.getElementById("mapa")) {
    document.getElementById("mapa").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  }
  window.addEventListener("hashchange", function () {
    var next = catalog.find(function (item) { return item.id === hashId(); });
    if (next) applyItem(next);
  });
})();
