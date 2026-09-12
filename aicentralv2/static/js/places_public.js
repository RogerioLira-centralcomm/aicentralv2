(function () {
  var dataNode = document.getElementById("cc-place-data");
  if (!dataNode) return;
  var place = JSON.parse(dataNode.textContent || "{}");
  var points = (place.points || []).filter(function (item) {
    return item && item.lat != null && item.lng != null;
  });
  var zones = place.zones || [];
  var nav = document.getElementById("cc-zone-nav");
  var map;
  var layers = {};

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
        audiences: point.audiences || [],
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
        audiences: zone.audiences || [],
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

  function fillList(id, values, className) {
    var node = document.getElementById(id);
    if (!node) return;
    node.innerHTML = (values || []).map(function (item) {
      return "<" + className + ">" + escapeHtml(item) + "</" + className + ">";
    }).join("");
  }

  function setPhoto(id, url, name) {
    var img = document.getElementById(id);
    var wrap = img && img.closest(".cc-point-photo");
    if (!img || !wrap) return;
    if (url) {
      wrap.hidden = false;
      img.src = url;
      img.alt = name || "";
    } else {
      wrap.hidden = true;
      img.removeAttribute("src");
    }
  }

  function toggleWrap(id, values) {
    var node = document.getElementById(id);
    if (node) node.hidden = !(values && values.length);
  }

  function setFlag(id, on) {
    var node = document.getElementById(id);
    if (node) node.hidden = !on;
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
        chip.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
      }
    });
    document.querySelectorAll(".cc-gallery-card").forEach(function (card) {
      card.classList.toggle("is-on", card.getAttribute("data-point") === item.id);
    });
    Object.keys(layers).forEach(function (key) {
      paintLayer(key, key === item.id);
    });
    setText("zoneName", item.name);
    setText("zoneCommercial", item.commercial);
    setText("zoneRadius", item.radius);
    setText("zoneReach", item.reach);
    setText("cc-map-label", item.name + " · " + item.radius);
    setFlag("zoneReachFlag", item.reach_status === "to_validate");
    fillList("zoneFormats", item.formats, "span");
    fillList("zoneAudiences", item.audiences, "div");
    toggleWrap("zoneFormatsWrap", item.formats);
    toggleWrap("zoneAudiencesWrap", item.audiences);
    setPhoto("zonePhoto", item.image, item.name);
    if (map && item.lat != null) {
      map.flyTo([item.lat, item.lng], zoomFor(item.radius_m), { duration: 0.55 });
    }
  }

  var catalog = items();
  if (nav && catalog.length) {
    nav.innerHTML = catalog.map(function (item, index) {
      return '<button type="button" class="cc-zone-chip" role="tab" data-zone="' +
        escapeHtml(item.id) + '" aria-selected="' + (index === 0 ? "true" : "false") + '">' +
        escapeHtml(item.name) + "<small>" + escapeHtml(item.radius) + "</small></button>";
    }).join("");
    nav.querySelectorAll(".cc-zone-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var item = catalog.find(function (entry) { return entry.id === chip.getAttribute("data-zone"); });
        applyItem(item);
      });
    });
  }

  document.querySelectorAll(".cc-gallery-card").forEach(function (card) {
    card.addEventListener("click", function () {
      var item = catalog.find(function (entry) { return entry.id === card.getAttribute("data-point"); });
      applyItem(item);
      var mapa = document.getElementById("mapa");
      if (mapa) mapa.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  var mapNode = document.getElementById("cc-map");
  if (mapNode && typeof L !== "undefined") {
    var geo = place.geo || {};
    var start = catalog[0] && catalog[0].lat != null
      ? [catalog[0].lat, catalog[0].lng]
      : [geo.lat || -15.8, geo.lng || -47.9];
    var startZoom = catalog[0] ? zoomFor(catalog[0].radius_m) : (geo.zoom || 15);
    map = L.map(mapNode, { scrollWheelZoom: false, attributionControl: true }).setView(start, startZoom);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
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
  }

  if (catalog[0]) applyItem(catalog[0]);
})();
