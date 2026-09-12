(function () {
  var dataNode = document.getElementById("cc-place-data");
  if (!dataNode) return;
  var place = JSON.parse(dataNode.textContent || "{}");
  var points = (place.points || []).filter(function (item) {
    return item && item.lat != null && item.lng != null;
  });
  var zones = place.zones || [];
  var nav = document.getElementById("cc-zone-nav");
  var sheet = document.getElementById("cc-sheet");
  var overlay = document.getElementById("cc-overlay");
  var closeBtn = document.getElementById("cc-close");
  var mqSheet = window.matchMedia("(max-width: 1100px)");
  var lastFocus = null;
  var map;
  var markers = {};

  function items() {
    if (points.length) return points.map(function (point) {
      return {
        id: point.id || point.name,
        name: point.name,
        description: point.note || ((point.kind_label || point.kind || "Ponto") + " no recorte de " + (place.title || "este place") + "."),
        radius: (point.kind_label || point.kind || "ponto"),
        reach: Number(point.lat).toFixed(5) + ", " + Number(point.lng).toFixed(5),
        commercial: point.source || "Ponto da bacia — presença que a campanha compra neste recorte.",
        formats: point.formats || [],
        audiences: point.audiences || [],
        image: point.image_url || "",
        lat: point.lat,
        lng: point.lng
      };
    });
    return zones.map(function (zone) {
      return Object.assign({}, zone, { image: zone.image_url || "" });
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
      wrap.classList.remove("is-in");
      window.requestAnimationFrame(function () {
        wrap.classList.add("is-in");
      });
    } else {
      wrap.hidden = true;
      img.removeAttribute("src");
    }
  }

  function toggleWrap(id, values) {
    var node = document.getElementById(id);
    if (node) node.hidden = !(values && values.length);
  }

  function usesSheet() {
    return mqSheet.matches;
  }

  function show(node, on) {
    if (!node) return;
    node.hidden = !on;
    if (on) node.removeAttribute("inert");
    else node.setAttribute("inert", "");
  }

  function openSheet() {
    if (!sheet || !overlay) return;
    lastFocus = document.activeElement;
    show(sheet, true);
    show(overlay, true);
    document.body.classList.add("is-sheet-open");
    if (closeBtn) closeBtn.focus();
  }

  function closeSheet() {
    show(sheet, false);
    show(overlay, false);
    document.body.classList.remove("is-sheet-open");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function applyItem(item, openMobile) {
    if (!item) return;
    document.querySelectorAll(".cc-zone-chip").forEach(function (chip) {
      var on = chip.getAttribute("data-zone") === item.id;
      chip.classList.toggle("is-on", on);
      chip.setAttribute("aria-selected", on ? "true" : "false");
    });
    document.querySelectorAll(".cc-gallery-card").forEach(function (card) {
      card.classList.toggle("is-on", card.getAttribute("data-point") === item.id);
    });
    Object.keys(markers).forEach(function (key) {
      var marker = markers[key];
      if (marker && marker.setOpacity) marker.setOpacity(key === item.id ? 1 : 0.55);
    });
    setText("zoneId", item.id);
    setText("zoneName", item.name);
    setText("zoneDescription", item.description);
    setText("zoneRadius", item.radius);
    setText("zoneReach", item.reach);
    setText("zoneCommercial", item.commercial);
    fillList("zoneFormats", item.formats, "span");
    fillList("zoneAudiences", item.audiences, "div");
    toggleWrap("zoneFormatsWrap", item.formats);
    toggleWrap("zoneAudiencesWrap", item.audiences);
    setPhoto("zonePhoto", item.image, item.name);
    setText("mZoneId", item.id);
    setText("mZoneName", item.name);
    setText("mZoneDescription", item.description);
    setText("mZoneRadius", item.radius);
    setText("mZoneReach", item.reach);
    setText("mZoneCommercial", item.commercial);
    fillList("mZoneFormats", item.formats, "span");
    fillList("mZoneAudiences", item.audiences, "div");
    toggleWrap("mZoneFormatsWrap", item.formats);
    toggleWrap("mZoneAudiencesWrap", item.audiences);
    setPhoto("mZonePhoto", item.image, item.name);
    if (map && item.lat != null) map.flyTo([item.lat, item.lng], Math.max(map.getZoom(), 15), { duration: 0.7 });
    if (openMobile && usesSheet()) openSheet();
  }

  var catalog = items();
  if (nav && catalog.length) {
    nav.innerHTML = catalog.map(function (item, index) {
      return '<button type="button" class="cc-zone-chip" role="tab" data-zone="' +
        escapeHtml(item.id) + '" aria-selected="' + (index === 0 ? "true" : "false") + '">' +
        escapeHtml(item.name) + "</button>";
    }).join("");
    nav.querySelectorAll(".cc-zone-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var item = catalog.find(function (entry) { return entry.id === chip.getAttribute("data-zone"); });
        applyItem(item, true);
      });
    });
  }

  document.querySelectorAll(".cc-gallery-card").forEach(function (card) {
    card.addEventListener("click", function () {
      var item = catalog.find(function (entry) { return entry.id === card.getAttribute("data-point"); });
      applyItem(item, true);
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
    map = L.map(mapNode, { scrollWheelZoom: false }).setView(start, geo.zoom || 14);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Tiles © Esri"
    }).addTo(map);
    catalog.forEach(function (item) {
      if (item.lat == null) return;
      var marker = L.circleMarker([item.lat, item.lng], {
        radius: 9,
        color: "#f3b71b",
        weight: 2,
        fillColor: "#9ccf31",
        fillOpacity: 0.85
      }).addTo(map);
      marker.bindTooltip(item.name);
      marker.on("click", function () { applyItem(item, true); });
      markers[item.id] = marker;
    });
  }

  if (catalog[0]) applyItem(catalog[0], false);
  if (overlay) overlay.addEventListener("click", closeSheet);
  if (closeBtn) closeBtn.addEventListener("click", closeSheet);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeSheet();
  });

  var cta = document.getElementById("proposta");
  if (cta && "IntersectionObserver" in window) {
    var observer = new IntersectionObserver(function (entries) {
      document.body.classList.toggle("is-cta-visible", entries.some(function (entry) { return entry.isIntersecting; }));
    }, { threshold: 0.35 });
    observer.observe(cta);
  }

  var form = document.getElementById("cc-inquiry");
  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var note = document.getElementById("cc-form-note") || form.querySelector(".cc-form-note");
      var button = form.querySelector("button[type='submit']");
      var body = {
        name: form.elements.name.value,
        company: form.elements.company.value,
        email: form.elements.email.value,
        phone: form.elements.phone.value,
        message: form.elements.message.value
      };
      function fail(message) {
        if (!note) return;
        note.hidden = false;
        note.classList.add("is-error");
        note.textContent = message;
      }
      if (!body.email && !body.phone) {
        fail("Informe e-mail ou WhatsApp.");
        (form.elements.email || form.elements.phone).focus();
        return;
      }
      if (button) {
        button.disabled = true;
        button.textContent = "Enviando…";
      }
      fetch("/places/api/p/" + form.getAttribute("data-slug") + "/inquiry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }).then(function (response) {
        return response.json().then(function (payload) {
          return { ok: response.ok, payload: payload };
        });
      }).then(function (result) {
        if (!result.ok || !result.payload.success) {
          throw new Error((result.payload && result.payload.error) || "Não foi possível enviar.");
        }
        form.reset();
        if (note) {
          note.hidden = false;
          note.classList.remove("is-error");
          note.textContent = "Pedido enviado. O comercial entra em contato.";
        }
      }).catch(function (error) {
        fail(error.message);
      }).finally(function () {
        if (button) {
          button.disabled = false;
          button.textContent = "Pedir proposta";
        }
      });
    });
  }
})();
