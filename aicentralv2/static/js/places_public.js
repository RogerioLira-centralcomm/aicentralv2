(function () {
  var btn = document.querySelector(".cc-menu-btn");
  var mega = document.getElementById("cc-mega");
  var scrim = document.getElementById("cc-scrim");
  var canHover = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  var closeTimer;
  var ignoreDoc = false;
  var hoverOpened = false;
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
      if (mega.hidden) {
        openMega();
      } else if (!canHover || !hoverOpened) {
        closeMega();
      }
      hoverOpened = false;
      ignoreDoc = true;
      window.setTimeout(function () { ignoreDoc = false; }, 0);
      if (willOpen && event.detail === 0) {
        var first = mega.querySelector(".cc-mega-item");
        if (first) first.focus();
      }
    });
    if (canHover) {
      btn.addEventListener("mouseenter", function () {
        hoverOpened = true;
        openMega();
      });
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
      if (event.key !== "Escape" || mega.hidden) return;
      closeMega();
      btn.focus();
      event.preventDefault();
    });
  }

  function bootIndex() {
    var node = document.getElementById("cc-index-data");
    if (!node) return;
    var payload = {};
    try {
      payload = JSON.parse(node.textContent || "{}") || {};
    } catch (error) {
      return;
    }
    var places = (payload.places || []).filter(function (item) { return item && item.slug; });
    var featuredSlug = payload.featured || (places[0] && places[0].slug) || "";
    var input = document.getElementById("cc-q");
    var openBtn = document.getElementById("cc-open");
    var empty = document.getElementById("cc-empty");
    var form = document.querySelector(".cc-find");
    var chips = Array.prototype.slice.call(document.querySelectorAll(".cc-filter [data-tipo]"));
    var typeLinks = Array.prototype.slice.call(document.querySelectorAll(".cc-types [data-tipo]"));
    var picks = Array.prototype.slice.call(document.querySelectorAll(".cc-pick[data-slug]"));
    var cols = Array.prototype.slice.call(document.querySelectorAll(".cc-col[data-col]"));
    var state = { q: "", tipo: "" };
    var atlas;
    var markers = {};
    var fitTimer;

    function bySlug(slug) {
      return places.find(function (item) { return item.slug === slug; });
    }

    function match(item) {
      if (state.tipo && item.place_type !== state.tipo) return false;
      var needle = state.q.trim().toLowerCase();
      if (!needle) return true;
      return [item.title, item.code, item.city_label, item.type_label, item.slug, item.subtitle]
        .join(" ")
        .toLowerCase()
        .indexOf(needle) >= 0;
    }

    function visible() {
      return places.filter(match);
    }

    function readQuery() {
      var params = new URLSearchParams(location.search);
      return { q: params.get("q") || "", tipo: params.get("tipo") || "" };
    }

    function writeQuery() {
      var params = new URLSearchParams();
      if (state.q) params.set("q", state.q);
      if (state.tipo) params.set("tipo", state.tipo);
      var next = location.pathname + (params.toString() ? "?" + params.toString() : "");
      if (history.replaceState) history.replaceState(null, "", next);
    }

    function paintHero(item) {
      var img = document.getElementById("cc-index-hero-img");
      var passengers = document.getElementById("cc-index-passengers");
      var reach = document.getElementById("cc-index-reach");
      var traffic = document.getElementById("cc-index-traffic");
      if (!item) return;
      if (img && item.hero_url) {
        var current = img.getAttribute("src") || "";
        var next = item.hero_url;
        if (current !== next && current.indexOf(next) < 0) {
          img.alt = item.title || "";
          if (reduceMotion) {
            img.src = next;
          } else {
            img.classList.add("is-swap");
            window.setTimeout(function () {
              img.src = next;
              img.onload = function () {
                img.classList.remove("is-swap");
              };
            }, 90);
          }
        }
      }
      if (traffic && item.traffic_label) traffic.textContent = item.traffic_label;
      if (passengers && item.passengers) passengers.textContent = item.passengers;
      if (reach && item.reach) reach.textContent = item.reach;
    }

    function paintCard(item) {
      var card = document.getElementById("cc-atlas-card");
      if (!card) return;
      if (!item) {
        card.hidden = true;
        return;
      }
      var code = document.getElementById("cc-atlas-code");
      var name = document.getElementById("cc-atlas-name");
      var meta = document.getElementById("cc-atlas-meta");
      if (code) code.textContent = item.code || item.title || "";
      if (name) name.textContent = item.title || "";
      if (meta) {
        meta.textContent = item.reach
          ? item.reach + " no celular, em 4 semanas"
          : (item.city_label || "");
      }
      card.hidden = false;
    }

    function fitMap(rows) {
      if (!atlas) return;
      var size = atlas.getSize && atlas.getSize();
      if (size && (size.x < 8 || size.y < 8)) return;
      var pts = rows.filter(function (item) { return item.lat != null && item.lng != null; });
      if (!pts.length) return;
      if (pts.length === 1) {
        var zoom = pts[0].place_type === "aeroporto" ? 13 : 15;
        atlas.setView([pts[0].lat, pts[0].lng], zoom);
        return;
      }
      var bounds = L.latLngBounds(pts.map(function (item) { return [item.lat, item.lng]; }));
      atlas.fitBounds(bounds.pad(0.22));
    }

    function scheduleFit(rows) {
      window.clearTimeout(fitTimer);
      fitTimer = window.setTimeout(function () { fitMap(rows); }, 180);
    }

    function apply() {
      var rows = visible();
      var slugs = {};
      rows.forEach(function (item) { slugs[item.slug] = true; });
      picks.forEach(function (pick) {
        var on = !!slugs[pick.getAttribute("data-slug")];
        pick.hidden = !on;
        pick.classList.toggle("is-on", rows.length === 1 && on);
        if (rows.length === 1 && on) pick.setAttribute("aria-current", "true");
        else pick.removeAttribute("aria-current");
      });
      cols.forEach(function (col) {
        var any = col.querySelector(".cc-pick[data-slug]:not([hidden])");
        col.hidden = !any;
      });
      chips.forEach(function (chip) {
        var on = (chip.getAttribute("data-tipo") || "") === state.tipo;
        chip.classList.toggle("is-on", on);
      });
      typeLinks.forEach(function (link) {
        var on = (link.getAttribute("data-tipo") || "") === state.tipo;
        if (on) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
      if (input && input.value !== state.q) input.value = state.q;
      if (openBtn) {
        openBtn.hidden = rows.length !== 1;
        openBtn.textContent = "Abrir";
      }
      if (empty) {
        if (!rows.length) {
          empty.hidden = false;
          empty.textContent = state.q
            ? 'Nenhum place com “' + state.q + '”. Veja aeroportos, shoppings ou parques.'
            : "Nenhum place neste recorte. Veja aeroportos, shoppings ou parques.";
        } else {
          empty.hidden = true;
          empty.textContent = "";
        }
      }
      Object.keys(markers).forEach(function (slug) {
        var entry = markers[slug];
        var show = !!slugs[slug];
        if (show) {
          if (!atlas.hasLayer(entry.marker)) entry.marker.addTo(atlas);
          entry.marker.setStyle({
            fillOpacity: rows.length === 1 ? 1 : 0.92,
            radius: rows.length === 1 ? 9 : 7,
            weight: rows.length === 1 ? 3 : 2
          });
        } else if (atlas.hasLayer(entry.marker)) {
          atlas.removeLayer(entry.marker);
        }
      });
      var focus = rows.length === 1 ? rows[0] : null;
      paintCard(focus);
      paintHero(focus || ((state.tipo || state.q) && rows[0]) || bySlug(featuredSlug) || places[0]);
      scheduleFit(rows);
      writeQuery();
    }

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        state.tipo = chip.getAttribute("data-tipo") || "";
        apply();
      });
    });
    typeLinks.forEach(function (link) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        state.tipo = link.getAttribute("data-tipo") || "";
        apply();
      });
    });
    if (input) {
      input.addEventListener("input", function () {
        state.q = input.value || "";
        apply();
      });
      input.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
          if (mega && !mega.hidden) return;
          state.q = "";
          state.tipo = "";
          apply();
          event.preventDefault();
        }
        if (event.key === "ArrowDown") {
          var first = document.querySelector(".cc-pick[data-slug]:not([hidden])");
          if (first) first.focus();
          event.preventDefault();
        }
      });
    }
    if (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var rows = visible();
        if (rows.length === 1 && rows[0].href) window.location.href = rows[0].href;
      });
    }
    document.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      var shown = Array.prototype.slice.call(document.querySelectorAll(".cc-pick[data-slug]:not([hidden])"));
      if (!shown.length) return;
      var index = shown.indexOf(document.activeElement);
      if (index < 0) return;
      index += event.key === "ArrowDown" ? 1 : -1;
      if (index < 0) index = shown.length - 1;
      if (index >= shown.length) index = 0;
      shown[index].focus();
      event.preventDefault();
    });

    var mapNode = document.getElementById("cc-atlas");
    if (mapNode && typeof L !== "undefined") {
      var start = bySlug(featuredSlug) || places[0] || {};
      atlas = L.map(mapNode, { scrollWheelZoom: false, attributionControl: true })
        .setView([start.lat || -19.92, start.lng || -43.94], 6);
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        attribution: "Tiles &copy; Esri",
        maxZoom: 19
      }).addTo(atlas);
      places.forEach(function (item) {
        if (item.lat == null || item.lng == null) return;
        var marker = L.circleMarker([item.lat, item.lng], {
          radius: 7,
          color: "#fff",
          weight: 2,
          fillColor: item.color || "#167A3A",
          fillOpacity: 0.92
        });
        marker.bindTooltip((item.code || item.title) + " · " + (item.city_label || ""), {
          direction: "top",
          opacity: 1
        });
        marker.on("click", function () {
          if (item.href) window.location.href = item.href;
        });
        marker.addTo(atlas);
        markers[item.slug] = { marker: marker, item: item };
      });
      window.setTimeout(function () { atlas.invalidateSize(); }, 200);
      window.addEventListener("resize", function () {
        if (atlas) atlas.invalidateSize();
      });
      if (window.IntersectionObserver) {
        var atlasWatch = new IntersectionObserver(function (entries) {
          if (!entries.some(function (entry) { return entry.isIntersecting; })) return;
          atlas.invalidateSize();
          fitMap(visible());
        }, { threshold: 0.15 });
        atlasWatch.observe(mapNode);
      }
    }

    var query = readQuery();
    state.q = query.q;
    state.tipo = query.tipo;
    apply();
  }

  bootIndex();

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
  }).sort(function (a, b) {
    var ae = (a.scope || "") === "external" ? 1 : 0;
    var be = (b.scope || "") === "external" ? 1 : 0;
    return ae - be;
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
        apps: point.apps || [],
        portals: point.portals || [],
        image: point.image_url || "",
        color: point.color || "#167A3A",
        scope: point.scope || "internal",
        scope_label: point.scope_label || (point.scope === "external" ? "Halo" : "No sítio"),
        defense: point.defense || point.commercial || point.note || "",
        investment: point.investment || "",
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
        apps: zone.apps || [],
        portals: zone.portals || [],
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

  function channelItems(items) {
    return (items || []).map(function (item) {
      if (!item) return null;
      if (typeof item === "string") return { name: item, why: "" };
      var name = item.name || "";
      if (!name) return null;
      return { name: name, why: item.why || "" };
    }).filter(Boolean);
  }

  function paintChannelList(id, wrapId, items) {
    var list = document.getElementById(id);
    var wrap = document.getElementById(wrapId);
    var rows = channelItems(items);
    if (list) {
      list.innerHTML = rows.map(function (item) {
        return "<li" + (item.why ? ' title="' + escapeHtml(item.why) + '"' : "") + ">" +
          escapeHtml(item.name) + "</li>";
      }).join("");
    }
    if (wrap) wrap.hidden = !rows.length;
    return rows.length;
  }

  function paintChannels(item) {
    var apps = paintChannelList("zoneApps", "zoneAppsWrap", item && item.apps);
    var portals = paintChannelList("zonePortals", "zonePortalsWrap", item && item.portals);
    var box = document.getElementById("zoneChannels");
    if (box) box.hidden = !(apps || portals);
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
    if (!primed || !item || !item.id || !history.replaceState) return;
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
      if (on && primed && chip.scrollIntoView) {
        chip.scrollIntoView({ inline: "center", block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
      }
    });
    document.querySelectorAll(".cc-area[data-zone]").forEach(function (card) {
      card.classList.toggle("is-on", card.getAttribute("data-zone") === item.id);
    });
    Object.keys(layers).forEach(function (key) {
      paintLayer(key, key === item.id);
    });
    setText("zoneName", item.name);
    setText("zoneScope", item.scope_label);
    setText("zoneCommercial", item.defense || item.commercial);
    setText("zoneRadius", item.radius);
    setText("zoneReach", item.reach);
    setText("zoneInvest", item.investment || (place.investment && place.investment.label) || "");
    setFlag("zoneReachFlag", item.reach_status === "to_validate");
    var formats = document.getElementById("zoneFormats");
    if (formats) {
      formats.textContent = (item.formats || []).join(", ");
      formats.hidden = !(item.formats && item.formats.length);
    }
    paintChannels(item);
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
    if (primed) persist(item);
    if (map && item.lat != null) {
      var zoom = zoomFor(item.radius_m);
      if (!primed || reduceMotion) {
        map.setView([item.lat, item.lng], zoom);
      } else {
        map.flyTo([item.lat, item.lng], zoom, { duration: 0.55 });
      }
    }
    primed = true;
  }

  var catalog = items();
  if (nav && catalog.length) {
    nav.innerHTML = catalog.map(function (item, index) {
      return '<button type="button" class="cc-zone-chip" role="tab" data-zone="' +
        escapeHtml(item.id) + '" data-scope="' + escapeHtml(item.scope || "internal") +
        '" aria-selected="' + (index === 0 ? "true" : "false") + '">' +
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
    if (window.IntersectionObserver) {
      var mapWatch = new IntersectionObserver(function (entries) {
        if (!entries.some(function (entry) { return entry.isIntersecting; }) || !map) return;
        map.invalidateSize();
      }, { threshold: 0.15 });
      mapWatch.observe(mapNode);
    }
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

  document.querySelectorAll(".cc-area[data-zone]").forEach(function (card) {
    card.addEventListener("click", function (event) {
      var item = catalog.find(function (entry) {
        return entry.id === card.getAttribute("data-zone");
      });
      if (!item) return;
      event.preventDefault();
      applyItem(item);
      var mapa = document.getElementById("mapa");
      if (mapa) mapa.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    });
  });

})();
