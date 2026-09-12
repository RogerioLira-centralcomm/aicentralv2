(function () {
  function toast(node, text, error) {
    if (!node) {
      window.alert(text);
      return;
    }
    node.hidden = false;
    node.classList.toggle("is-error", !!error);
    node.textContent = text;
  }

  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var value = button.getAttribute("data-copy") || "";
      if (!value) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(function () {
          button.textContent = "Link copiado";
        }).catch(function () {
          window.alert(value);
        });
      } else {
        window.alert(value);
      }
    });
  });

  var form = document.getElementById("pl-form");
  var root = document.querySelector("[data-places-form]");
  if (!form || !root) return;
  var statusNode = document.querySelector(".pl-form-status");
  var busy = false;

  function value(name) {
    var field = form.elements[name];
    return field ? String(field.value || "").trim() : "";
  }

  function numberOrNull(raw) {
    if (raw === undefined || raw === null || raw === "") return null;
    var n = Number(String(raw).replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }

  function collectPoints() {
    var rows = document.querySelectorAll("#pl-points-body tr");
    return Array.prototype.map.call(rows, function (row) {
      return {
        id: (row.querySelector("[name=point_id]") || {}).value || "",
        name: (row.querySelector("[name=point_name]") || {}).value || "",
        kind: (row.querySelector("[name=point_kind]") || {}).value || "marco",
        lat: numberOrNull((row.querySelector("[name=point_lat]") || {}).value),
        lng: numberOrNull((row.querySelector("[name=point_lng]") || {}).value),
        image_url: (row.querySelector("[name=point_image]") || {}).value || ""
      };
    }).filter(function (item) {
      return item.name && item.lat != null && item.lng != null;
    });
  }

  function payload() {
    return {
      title: value("title"),
      slug: value("slug"),
      code: value("code"),
      operator: value("operator"),
      place_type: value("place_type"),
      city: value("city"),
      status: value("status") || "draft",
      subtitle: value("subtitle"),
      payload: {
        geo: { lat: numberOrNull(value("geo_lat")), lng: numberOrNull(value("geo_lng")), zoom: 15 },
        catchment: {
          population: {
            label: value("catchment_pop_label"),
            value: numberOrNull(value("catchment_pop_value")),
            source: value("catchment_pop_source"),
            source_status: value("catchment_pop_status") || "official"
          },
          density: {
            label: value("catchment_density_label"),
            source: value("catchment_density_source"),
            source_status: "estimate"
          },
          impacted: { label: value("catchment_impacted_label"), source_status: "estimate" },
          neighborhoods: value("catchment_neighborhoods").split(",").map(function (item) { return item.trim(); }).filter(Boolean),
          profile: value("catchment_profile")
        },
        points: collectPoints(),
        media: {
          hero_url: value("hero_url"),
          map_url: value("map_url"),
          og_url: value("og_url")
        }
      }
    };
  }

  function jsonFetch(url, method, body) {
    return fetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: body ? JSON.stringify(body) : undefined
    }).then(function (response) {
      return response.json().then(function (data) {
        return { ok: response.ok, body: data };
      });
    });
  }

  function setBusy(on, message) {
    busy = !!on;
    document.querySelectorAll(".pl-desk button, .pl-desk .cx-btn").forEach(function (button) {
      if (button.getAttribute("data-copy") != null) return;
      button.disabled = !!on;
    });
    if (on && message) toast(statusNode, message);
  }

  document.querySelectorAll(".pl-tabs button").forEach(function (button) {
    button.addEventListener("click", function () {
      var tab = button.getAttribute("data-tab");
      document.querySelectorAll(".pl-tabs button").forEach(function (item) {
        item.classList.toggle("is-on", item === button);
      });
      document.querySelectorAll("[data-panel]").forEach(function (panel) {
        panel.hidden = panel.getAttribute("data-panel") !== tab;
      });
      if (tab === "pontos") window.setTimeout(ensureMap, 40);
    });
  });

  var hits = document.getElementById("pl-hits");
  var searchBtn = document.getElementById("pl-place-search");
  if (searchBtn) {
    searchBtn.addEventListener("click", function () {
      var q = (document.getElementById("pl-place-q") || {}).value || "";
      jsonFetch("/places/api/search?q=" + encodeURIComponent(q), "GET").then(function (result) {
        if (!result.ok) throw new Error((result.body && result.body.error) || "Busca falhou.");
        var rows = result.body.data || [];
        hits.hidden = !rows.length;
        hits.innerHTML = rows.map(function (item) {
          return '<li><button type="button" data-hit>' + item.title +
            '<small>' + (item.label || "") + ' · ' + item.lat.toFixed(5) + ', ' + item.lng.toFixed(5) + '</small></button></li>';
        }).join("");
        hits.querySelectorAll("[data-hit]").forEach(function (button, index) {
          button.addEventListener("click", function () {
            var item = rows[index];
            form.elements.title.value = item.title;
            if (item.city && form.elements.city) form.elements.city.value = item.city;
            form.elements.geo_lat.value = item.lat;
            form.elements.geo_lng.value = item.lng;
            toast(statusNode, "Lugar preenchido. Salve ou finalize a importação.");
            ensureMap();
          });
        });
      }).catch(function (error) {
        toast(statusNode, error.message, true);
      });
    });
  }

  function savePlace() {
    var placeId = root.getAttribute("data-place-id");
    var url = placeId ? "/places/api/" + placeId : "/places/api";
    return jsonFetch(url, placeId ? "PUT" : "POST", payload()).then(function (result) {
      if (!result.ok || !result.body.success) {
        throw new Error((result.body && result.body.error) || "Não foi possível salvar.");
      }
      var saved = result.body.data || {};
      if (saved.id) {
        root.setAttribute("data-place-id", String(saved.id));
        if (!placeId && window.history && window.history.replaceState) {
          window.history.replaceState({}, "", "/places/" + saved.id);
        }
      }
      return saved;
    });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true, "Salvando…");
    savePlace().then(function () {
      toast(statusNode, "Place salvo.");
    }).catch(function (error) {
      toast(statusNode, error.message, true);
    }).finally(function () {
      setBusy(false);
    });
  });

  function placeAction(path, body, okText, waitText) {
    if (busy) return;
    setBusy(true, waitText || "Processando…");
    savePlace().then(function (saved) {
      var placeId = saved.id || root.getAttribute("data-place-id");
      if (!placeId) throw new Error("Salve o place primeiro.");
      return jsonFetch("/places/api/" + placeId + path, "POST", body || {});
    }).then(function (result) {
      if (!result.ok || !result.body.success) {
        throw new Error((result.body && result.body.error) || "Não foi possível concluir.");
      }
      toast(statusNode, okText);
      window.location.reload();
    }).catch(function (error) {
      toast(statusNode, error.message, true);
      setBusy(false);
    });
  }

  var importBtn = document.getElementById("pl-import");
  if (importBtn) importBtn.addEventListener("click", function () {
    placeAction("/import", {}, "Importação finalizada com GPT-5.", "Pesquisando a região e finalizando com GPT-5…");
  });
  var researchBtn = document.getElementById("pl-research");
  if (researchBtn) researchBtn.addEventListener("click", function () {
    placeAction("/research", {}, "Região pesquisada.", "Pesquisando a região…");
  });
  var reviewBtn = document.getElementById("pl-review");
  if (reviewBtn) reviewBtn.addEventListener("click", function () {
    placeAction("/review", {}, "Ficha revisada com GPT-5.", "Revisando com GPT-5…");
  });
  var suggestBtn = document.getElementById("pl-suggest");
  if (suggestBtn) suggestBtn.addEventListener("click", function () {
    placeAction("/suggest-points", {}, "Pontos sugeridos.", "Localizando pontos…");
  });
  var heroBtn = document.getElementById("pl-gen-hero");
  if (heroBtn) heroBtn.addEventListener("click", function () {
    placeAction("/images", { kind: "hero" }, "Hero gerado.", "Gerando hero no Image 2…");
  });
  var mapBtn = document.getElementById("pl-gen-map");
  if (mapBtn) mapBtn.addEventListener("click", function () {
    placeAction("/images", { kind: "map" }, "Mapa gerado.", "Gerando mapa no Image 2…");
  });
  var ogBtn = document.getElementById("pl-gen-og");
  if (ogBtn) ogBtn.addEventListener("click", function () {
    placeAction("/images", { kind: "og" }, "Cartão gerado.", "Gerando cartão no Image 2…");
  });
  var pointsImgBtn = document.getElementById("pl-gen-points");
  if (pointsImgBtn) pointsImgBtn.addEventListener("click", function () {
    placeAction("/images", { kind: "points" }, "Fotos dos pontos geradas.", "Gerando interiores dos pontos no Image 2…");
  });
  var publishBtn = document.getElementById("pl-publish");
  if (publishBtn) publishBtn.addEventListener("click", function () {
    placeAction("/publish", {}, "Place publicado.");
  });
  var unpublishBtn = document.getElementById("pl-unpublish");
  if (unpublishBtn) unpublishBtn.addEventListener("click", function () {
    placeAction("/unpublish", {}, "Place em rascunho.");
  });

  var pointsBody = document.getElementById("pl-points-body");
  var rowTpl = document.getElementById("pl-point-row");
  var addPoint = document.getElementById("pl-add-point");
  if (addPoint && rowTpl && pointsBody) {
    addPoint.addEventListener("click", function () {
      pointsBody.appendChild(rowTpl.content.cloneNode(true));
    });
    pointsBody.addEventListener("click", function (event) {
      var gen = event.target.closest("[data-gen-point]");
      if (gen) {
        placeAction("/images", { kind: "point", point_id: gen.getAttribute("data-gen-point") }, "Foto do ponto gerada.", "Gerando o interior do ponto…");
        return;
      }
      var button = event.target.closest("[data-remove-point]");
      if (button) button.closest("tr").remove();
    });
  }

  var map;
  var markers = [];
  function ensureMap() {
    var node = document.getElementById("pl-admin-map");
    if (!node || typeof L === "undefined") return;
    var lat = numberOrNull(value("geo_lat")) || -19.92;
    var lng = numberOrNull(value("geo_lng")) || -43.94;
    if (!map) {
      map = L.map(node).setView([lat, lng], 14);
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        attribution: "Tiles © Esri"
      }).addTo(map);
      map.on("click", function (event) {
        if (!rowTpl || !pointsBody) return;
        pointsBody.appendChild(rowTpl.content.cloneNode(true));
        var row = pointsBody.lastElementChild;
        row.querySelector("[name=point_lat]").value = event.latlng.lat.toFixed(6);
        row.querySelector("[name=point_lng]").value = event.latlng.lng.toFixed(6);
        drawMarkers();
      });
    } else {
      map.setView([lat, lng], map.getZoom());
      map.invalidateSize();
    }
    drawMarkers();
  }

  function drawMarkers() {
    if (!map) return;
    markers.forEach(function (marker) { map.removeLayer(marker); });
    markers = collectPoints().map(function (point) {
      return L.marker([point.lat, point.lng]).addTo(map).bindPopup(point.name + "<br>" + point.lat + ", " + point.lng);
    });
  }
})();
