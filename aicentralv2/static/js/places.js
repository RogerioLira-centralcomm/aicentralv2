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

  function bindCopy(scope) {
    (scope || document).querySelectorAll("[data-copy]").forEach(function (button) {
      if (button.getAttribute("data-copy-bound")) return;
      button.setAttribute("data-copy-bound", "1");
      button.addEventListener("click", function () {
        var value = button.getAttribute("data-copy") || "";
        if (!value) return;
        var original = button.textContent;
        var done = function () {
          button.textContent = "Copiado";
          window.setTimeout(function () {
            button.textContent = original;
          }, 1600);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(value).then(done).catch(function () {
            window.alert(value);
          });
        } else {
          window.alert(value);
        }
      });
    });
  }

  bindCopy(document);

  var form = document.getElementById("pl-form");
  var root = document.querySelector("[data-places-form]");
  if (!form || !root) return;

  var statusNode = document.querySelector(".pl-form-status");
  var kinds = readJson("pl-point-kinds", []);
  var place = readJson("pl-place-data", {});
  var busy = false;
  var map;
  var markers = [];

  function readJson(id, fallback) {
    var node = document.getElementById(id);
    if (!node) return fallback;
    try {
      return JSON.parse(node.textContent || "null") || fallback;
    } catch (error) {
      return fallback;
    }
  }

  function value(name) {
    var field = form.elements[name];
    return field ? String(field.value || "").trim() : "";
  }

  function setValue(name, raw) {
    var field = form.elements[name];
    if (field) field.value = raw == null ? "" : raw;
  }

  function numberOrNull(raw) {
    if (raw === undefined || raw === null || raw === "") return null;
    var n = Number(String(raw).replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }

  function slug(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 40);
  }

  function formatNamedList(items) {
    return (items || []).map(function (item) {
      if (!item) return "";
      if (typeof item === "string") return item;
      if (!item.name) return "";
      return item.why ? (item.name + " — " + item.why) : item.name;
    }).filter(Boolean).join("; ");
  }

  function parseNamedList(raw) {
    return String(raw || "").split(";").map(function (part) {
      var bits = part.split(/\s[—–-]\s/);
      if (bits.length === 1) bits = part.split(":");
      var name = String(bits[0] || "").trim();
      if (!name) return null;
      return {
        name: name,
        why: String(bits.slice(1).join(" — ") || "").trim(),
        confidence: "estimate"
      };
    }).filter(Boolean);
  }

  function collectPoints() {
    return Array.prototype.map.call(document.querySelectorAll("#pl-points-body tr.pl-point-row"), function (row) {
      var extra = row.nextElementSibling && row.nextElementSibling.classList.contains("pl-point-extra")
      ? row.nextElementSibling
      : null;
      var name = (row.querySelector("[name=point_name]") || {}).value || "";
      var id = (row.querySelector("[name=point_id]") || {}).value || slug(name);
      return {
        id: id,
        name: name,
        kind: (row.querySelector("[name=point_kind]") || {}).value || "marco",
        lat: numberOrNull((row.querySelector("[name=point_lat]") || {}).value),
        lng: numberOrNull((row.querySelector("[name=point_lng]") || {}).value),
        image_url: (row.querySelector("[name=point_image]") || {}).value || "",
        radius_m: numberOrNull((row.querySelector("[name=point_radius]") || {}).value),
        reach: (row.querySelector("[name=point_reach]") || {}).value || "",
        formats: String(((extra && extra.querySelector("[name=point_formats]") || {}).value) || "")
          .split(",")
          .map(function (item) { return item.trim(); })
          .filter(Boolean),
        apps: parseNamedList((extra && extra.querySelector("[name=point_apps]") || {}).value),
        portals: parseNamedList((extra && extra.querySelector("[name=point_portals]") || {}).value)
      };
    }).filter(function (item) {
      return item.name;
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
        inventory: (place && place.inventory) || {},
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
      }).catch(function () {
        return { ok: false, body: { error: "A resposta não veio em JSON. Tente de novo." } };
      });
    });
  }

  function setBusy(on, message) {
    busy = !!on;
    root.classList.toggle("is-busy", !!on);
    root.setAttribute("aria-busy", on ? "true" : "false");
    if (on && message) toast(statusNode, message);
  }

  function currentTab() {
    var params = new URLSearchParams(window.location.search);
    return params.get("tab") || "lugar";
  }

  function showTab(tab) {
    var id = tab || "lugar";
    document.querySelectorAll(".pl-trail button").forEach(function (button) {
      button.classList.toggle("is-on", button.getAttribute("data-tab") === id);
    });
    document.querySelectorAll("[data-panel]").forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-panel") !== id;
    });
    if (window.history && window.history.replaceState) {
      var url = new URL(window.location.href);
      url.searchParams.set("tab", id);
      window.history.replaceState({}, "", url.pathname + url.search);
    }
    if (id === "pontos") window.setTimeout(ensureMap, 40);
  }

  function updateTrail() {
    var done = {
      lugar: !!(place.title && place.geo && place.geo.lat),
      bacia: !!(place.research && (place.research.reviewed_at || place.research.notes) || (place.catchment && place.catchment.population && place.catchment.population.label)),
      pontos: !!(place.points && place.points.length),
      arte: !!(place.media && (place.media.hero_url || place.media.map_url)),
      publicar: place.status === "published"
    };
    document.querySelectorAll(".pl-trail button").forEach(function (button) {
      button.classList.toggle("is-done", !!done[button.getAttribute("data-tab")]);
    });
  }

  function kindOptions(selected) {
    return kinds.map(function (item) {
      return '<option value="' + escapeHtml(item.id) + '"' + (item.id === selected ? " selected" : "") + ">" + escapeHtml(item.label) + "</option>";
    }).join("");
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function pointRowHtml(item) {
    item = item || {};
    var id = item.id || "";
    var photo = item.image_url
      ? '<img src="' + escapeHtml(item.image_url) + '" alt="">'
      : '<span class="pl-point-empty">sem foto</span>';
    return (
      '<tr class="pl-point-row">' +
        '<td class="pl-point-media">' +
          '<input type="hidden" name="point_id" value="' + escapeHtml(id) + '">' +
          '<input type="hidden" name="point_image" value="' + escapeHtml(item.image_url || "") + '">' +
          '<input type="hidden" name="point_radius" value="' + escapeHtml(item.radius_m || "") + '">' +
          '<input type="hidden" name="point_reach" value="' + escapeHtml(item.reach || "") + '">' +
          photo +
        "</td>" +
        '<td><input class="cx-input" name="point_name" value="' + escapeHtml(item.name || "") + '"></td>' +
        '<td><select class="cx-select" name="point_kind">' + kindOptions(item.kind || "marco") + "</select></td>" +
        '<td><input class="cx-input" name="point_lat" value="' + (item.lat == null ? "" : item.lat) + '"></td>' +
        '<td><input class="cx-input" name="point_lng" value="' + (item.lng == null ? "" : item.lng) + '"></td>' +
        "<td>" +
          '<button type="button" class="cx-btn cx-btn-ghost" data-gen-point="' + escapeHtml(id || item.name || "") + '">Gerar foto</button> ' +
          '<button type="button" class="cx-btn cx-btn-ghost" data-remove-point>Tirar</button>' +
        "</td>" +
      "</tr>" +
      '<tr class="pl-point-extra">' +
        '<td colspan="6">' +
          '<div class="pl-point-channels">' +
            '<label>Apps<input class="cx-input" name="point_apps" value="' + escapeHtml(formatNamedList(item.apps)) + '" placeholder="Instagram — Stories na praça; iFood — almoço"></label>' +
            '<label>Portais<input class="cx-input" name="point_portals" value="' + escapeHtml(formatNamedList(item.portals)) + '" placeholder="G1 — intervalo; Folha — ticket alto"></label>' +
            '<label>Formatos<input class="cx-input" name="point_formats" value="' + escapeHtml((item.formats || []).join(", ")) + '" placeholder="Display no app, Portais"></label>' +
          "</div>" +
        "</td>" +
      "</tr>"
    );
  }

  function renderPoints(points) {
    var body = document.getElementById("pl-points-body");
    if (!body) return;
    body.innerHTML = (points || []).map(pointRowHtml).join("");
    drawMarkers();
  }

  function renderMedia(data) {
    var pack = document.querySelector("[data-media-pack]");
    if (!pack) return;
    var figures = [];
    var media = (data && data.media) || {};
    if (media.hero_url) figures.push({ url: media.hero_url, label: "Hero" });
    if (media.map_url) figures.push({ url: media.map_url, label: "Mapa" });
    if (media.og_url) figures.push({ url: media.og_url, label: "Cartão" });
    (data.points || []).forEach(function (item) {
      if (item.image_url) figures.push({ url: item.image_url, label: item.name });
    });
    pack.innerHTML = figures.map(function (item) {
      return "<figure><img src=\"" + escapeHtml(item.url) + "\" alt=\"" + escapeHtml(item.label) + "\"><figcaption>" + escapeHtml(item.label) + "</figcaption></figure>";
    }).join("");
    var spec = document.querySelector("[data-image-spec]");
    if (spec && data.images && data.images.spec) {
      spec.textContent = "Uma foto por vez. Busca referência real no Firecrawl e gera no modelo " + (data.images.spec.model || "do aeroporto") + " em " + (data.images.spec.resolution || "2K") + ".";
    }
  }

  function applyPlace(data) {
    if (!data) return;
    place = data;
    if (data.id) {
      root.setAttribute("data-place-id", String(data.id));
      if (window.history && window.history.replaceState) {
        var tab = currentTab();
        window.history.replaceState({}, "", "/places/" + data.id + "?tab=" + encodeURIComponent(tab));
      }
    }
    if (data.title) setValue("title", data.title);
    if (data.slug) setValue("slug", data.slug);
    if (data.code) setValue("code", data.code);
    if (data.operator) setValue("operator", data.operator);
    if (data.subtitle) setValue("subtitle", data.subtitle);
    if (data.status) setValue("status", data.status);
    if (data.geo) {
      if (data.geo.lat != null) setValue("geo_lat", data.geo.lat);
      if (data.geo.lng != null) setValue("geo_lng", data.geo.lng);
    }
    var catchment = data.catchment || {};
    var population = catchment.population || {};
    var density = catchment.density || {};
    var impacted = catchment.impacted || {};
    if (population.label) setValue("catchment_pop_label", population.label);
    if (population.value != null) setValue("catchment_pop_value", population.value);
    if (population.source) setValue("catchment_pop_source", population.source);
    if (population.source_status) setValue("catchment_pop_status", population.source_status);
    if (density.label) setValue("catchment_density_label", density.label);
    if (density.source) setValue("catchment_density_source", density.source);
    if (impacted.label) setValue("catchment_impacted_label", impacted.label);
    if (catchment.neighborhoods) setValue("catchment_neighborhoods", catchment.neighborhoods.join(", "));
    if (catchment.profile) setValue("catchment_profile", catchment.profile);
    if (data.media) {
      if (data.media.hero_url) setValue("hero_url", data.media.hero_url);
      if (data.media.map_url) setValue("map_url", data.media.map_url);
      if (data.media.og_url) setValue("og_url", data.media.og_url);
    }
    var titleNode = document.querySelector("[data-identity-title]");
    if (titleNode) titleNode.textContent = data.title || "Novo place";
    var codeNode = document.querySelector("[data-identity-code]");
    if (codeNode) codeNode.textContent = data.code || "—";
    var meta = [];
    if (data.city_label) meta.push(data.city_label);
    if (data.metrics && data.metrics.passengers && data.metrics.passengers.label) {
      meta.push(data.metrics.passengers.label + " passageiros");
    }
    if (data.ai_cost_label && data.ai_cost_label !== "—") meta.push(data.ai_cost_label);
    var metaNode = document.querySelector("[data-identity-meta]");
    if (metaNode) metaNode.textContent = meta.join(" · ");
    var notes = document.querySelector("[data-research-notes]");
    if (notes) notes.textContent = (data.research && (data.research.review || data.research.notes)) || "";
    var warnings = ((data.pipeline || {}).warnings || []).slice();
    var warnNode = document.querySelector("[data-pipeline-warnings]");
    if (warnNode) {
      warnNode.hidden = !warnings.length;
      warnNode.textContent = warnings.join(" ");
    }
    var costNode = document.querySelector("[data-cost-label]");
    if (costNode) costNode.value = data.ai_cost_label || "—";
    var share = document.querySelector("[data-share-url]");
    if (share) share.textContent = data.share_url || "";
    var shareLink = document.querySelector("[data-share-link]");
    var copyBtn = document.querySelector(".pl-head-actions [data-copy]");
    if (shareLink) {
      if (data.share_url) {
        shareLink.href = data.share_url;
        shareLink.target = "_blank";
        shareLink.rel = "noopener noreferrer";
        shareLink.hidden = false;
        shareLink.textContent = data.status === "published" ? "Página pública" : "Prévia";
      } else {
        shareLink.hidden = true;
      }
    }
    if (copyBtn) {
      if (data.share_url) {
        copyBtn.setAttribute("data-copy", data.share_url);
        copyBtn.hidden = false;
      } else {
        copyBtn.hidden = true;
      }
    }
    var qr = document.querySelector("[data-qr]");
    if (qr && data.qr_svg) {
      qr.innerHTML = data.qr_svg;
      qr.hidden = false;
    }
    renderPoints(data.points || []);
    renderInventory(data);
    renderMedia(data);
    updateTrail();
    bindCopy(root);
  }

  function formatReviewedAt(raw) {
    if (!raw) return "";
    var date = new Date(raw);
    if (isNaN(date.getTime())) return raw;
    return date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
  }

  function renderInventory(data) {
    var box = document.querySelector("[data-inventory-report]");
    if (!box) return;
    var inventory = (data && data.inventory) || {};
    var points = (data && data.points) || [];
    var hasLead = !!inventory.lead;
    var hasItems = points.some(function (item) {
      return (item.apps && item.apps.length) || (item.portals && item.portals.length);
    });
    box.hidden = !(hasLead || hasItems);
    var lead = document.querySelector("[data-inventory-lead]");
    if (lead) lead.textContent = inventory.lead || "";
    var meta = document.querySelector("[data-inventory-meta]");
    if (meta) {
      var bits = [];
      if (inventory.reviewed_at) bits.push(formatReviewedAt(inventory.reviewed_at));
      if (inventory.model) bits.push(inventory.model.replace(/^openai\//, ""));
      meta.textContent = bits.join(" · ");
    }
    var notes = document.querySelector("[data-inventory-notes]");
    if (notes) notes.textContent = inventory.notes || "";
    var list = document.querySelector("[data-inventory-points]");
    if (!list) return;
    list.innerHTML = points.filter(function (item) {
      return item.name && ((item.apps && item.apps.length) || (item.portals && item.portals.length) || (item.formats && item.formats.length));
    }).map(function (item) {
      return (
        '<article class="pl-report-card">' +
          "<h3>" + escapeHtml(item.name) + "</h3>" +
          (item.apps && item.apps.length ? "<p><strong>Apps.</strong> " + escapeHtml(formatNamedList(item.apps)) + "</p>" : "") +
          (item.portals && item.portals.length ? "<p><strong>Portais.</strong> " + escapeHtml(formatNamedList(item.portals)) + "</p>" : "") +
          (item.formats && item.formats.length ? "<p><strong>Formatos.</strong> " + escapeHtml(item.formats.join(", ")) + "</p>" : "") +
        "</article>"
      );
    }).join("");
  }

  function savePlace() {
    var placeId = root.getAttribute("data-place-id");
    var url = placeId ? "/places/api/" + placeId : "/places/api";
    return jsonFetch(url, placeId ? "PUT" : "POST", payload()).then(function (result) {
      if (!result.ok || !result.body.success) {
        throw new Error((result.body && result.body.error) || "Não foi possível salvar.");
      }
      applyPlace(result.body.data || {});
      return result.body.data || {};
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

  document.querySelectorAll(".pl-trail button").forEach(function (button) {
    button.addEventListener("click", function () {
      showTab(button.getAttribute("data-tab"));
    });
  });

  document.querySelectorAll("[data-next-tab]").forEach(function (button) {
    button.addEventListener("click", function () {
      showTab(button.getAttribute("data-next-tab"));
    });
  });

  var hits = document.getElementById("pl-hits");
  var searchBtn = document.getElementById("pl-place-search");
  if (searchBtn) {
    searchBtn.addEventListener("click", function () {
      var q = ((document.getElementById("pl-place-q") || {}).value || "").trim();
      if (q.length < 2) {
        toast(statusNode, "Informe pelo menos duas letras para buscar o lugar.", true);
        return;
      }
      jsonFetch("/places/api/search?q=" + encodeURIComponent(q), "GET").then(function (result) {
        if (!result.ok) throw new Error((result.body && result.body.error) || "Busca falhou.");
        var rows = result.body.data || [];
        hits.hidden = !rows.length;
        hits.innerHTML = rows.map(function (item) {
          var lat = Number(item.lat);
          var lng = Number(item.lng);
          var coord = Number.isFinite(lat) && Number.isFinite(lng)
            ? lat.toFixed(5) + ", " + lng.toFixed(5)
            : "sem coordenada";
          return "<li><button type=\"button\" data-hit>" + escapeHtml(item.title) +
            "<small>" + escapeHtml(item.label || "") + " · " + coord + "</small></button></li>";
        }).join("");
        hits.querySelectorAll("[data-hit]").forEach(function (button, index) {
          button.addEventListener("click", function () {
            var item = rows[index];
            setValue("title", item.title);
            if (item.city) setValue("city", item.city);
            setValue("geo_lat", numberOrNull(item.lat));
            setValue("geo_lng", numberOrNull(item.lng));
            toast(statusNode, "Lugar preenchido. Continue para fechar a ficha.");
            showTab("bacia");
          });
        });
      }).catch(function (error) {
        toast(statusNode, error.message, true);
      });
    });
  }

  function placeAction(path, body, okText, waitText, nextTab) {
    if (busy) return Promise.reject(new Error("Aguarde o passo atual."));
    setBusy(true, waitText || "Processando…");
    return savePlace().then(function (saved) {
      var placeId = saved.id || root.getAttribute("data-place-id");
      if (!placeId) throw new Error("Salve o place primeiro.");
      return jsonFetch("/places/api/" + placeId + path, "POST", body || {});
    }).then(function (result) {
      if (!result.ok || !result.body.success) {
        throw new Error((result.body && result.body.error) || "Não foi possível concluir.");
      }
      applyPlace(result.body.data || {});
      toast(statusNode, okText);
      if (nextTab) showTab(nextTab);
      return result.body.data || {};
    }).catch(function (error) {
      toast(statusNode, error.message, true);
      throw error;
    }).finally(function () {
      setBusy(false);
    });
  }

  var importBtn = document.getElementById("pl-import");
  if (importBtn) {
    importBtn.addEventListener("click", function () {
      placeAction("/import", {}, "Ficha fechada. Os pontos já estão na lista.", "Fechando a ficha. Isso leva cerca de um minuto…", "pontos");
    });
  }
  var enrichBtn = document.getElementById("pl-enrich");
  if (enrichBtn) {
    enrichBtn.addEventListener("click", function () {
      placeAction("/enrich", {}, "Pontos enriquecidos. Apps e portais estão na reportina.", "Pesquisando apps e portais de cada raio. Isso leva cerca de um minuto…", "pontos");
    });
  }

  function queueJobs(data) {
    if (data && data.image_queue && data.image_queue.length) return data.image_queue;
    var jobs = [];
    var media = (data && data.media) || {};
    if (!media.hero_url) jobs.push({ kind: "hero", label: "Hero" });
    if (!media.map_url) jobs.push({ kind: "map", label: "Mapa" });
    (data.points || []).forEach(function (item) {
      if (item.name && !item.image_url) {
        jobs.push({ kind: "point", point_id: item.id || item.name, label: item.name });
      }
    });
    return jobs;
  }

  function paintQueue(jobs, index, errorText) {
    var box = document.querySelector("[data-image-queue]");
    if (!box) return;
    box.hidden = !jobs.length;
    var title = document.querySelector("[data-queue-title]");
    var step = document.querySelector("[data-queue-step]");
    var bar = document.querySelector("[data-queue-bar]");
    var list = document.querySelector("[data-queue-list]");
    var current = jobs[index];
    if (title) title.textContent = errorText ? "A fila parou" : (index >= jobs.length ? "Fotos prontas" : "Gerando fotos");
    if (step) {
      step.textContent = current
        ? (index + 1) + " de " + jobs.length + " · " + current.label + ". Cada foto leva cerca de um minuto."
        : (errorText || "Fila concluída.");
    }
    if (bar) bar.style.setProperty("--pct", Math.round((Math.min(index, jobs.length) / Math.max(jobs.length, 1)) * 100) + "%");
    if (list) {
      list.innerHTML = jobs.map(function (job, i) {
        var state = i < index ? "is-done" : (i === index ? (errorText ? "is-error" : "is-on") : "");
        var mark = i < index ? "Pronto · " : (i === index ? (errorText ? "Falhou · " : "Agora · ") : "");
        return "<li class=\"" + state + "\">" + mark + escapeHtml(job.label) + "</li>";
      }).join("");
    }
  }

  function generateOne(job) {
    var placeId = root.getAttribute("data-place-id");
    if (!placeId) return Promise.reject(new Error("Salve o place primeiro."));
    return jsonFetch("/places/api/" + placeId + "/images", "POST", {
      kind: job.kind,
      point_id: job.point_id || ""
    }).then(function (result) {
      if (!result.ok || !result.body.success) {
        throw new Error((result.body && result.body.error) || "Não foi possível gerar a foto.");
      }
      applyPlace(result.body.data || {});
      return result.body.data || {};
    });
  }

  function runQueue(jobs) {
    jobs = jobs || queueJobs(place);
    if (!jobs.length) {
      toast(statusNode, "Não falta foto neste place.");
      return Promise.resolve(place);
    }
    showTab("arte");
    var index = 0;
    paintQueue(jobs, 0);
    setBusy(true, "Gerando " + jobs[0].label + "…");
    function next() {
      if (index >= jobs.length) {
        paintQueue(jobs, index);
        toast(statusNode, "Fotos geradas.");
        setBusy(false);
        return place;
      }
      paintQueue(jobs, index);
      toast(statusNode, "Gerando " + jobs[index].label + " (" + (index + 1) + " de " + jobs.length + ")…");
      return generateOne(jobs[index]).then(function () {
        index += 1;
        return next();
      }).catch(function (error) {
        paintQueue(jobs, index, error.message);
        toast(statusNode, error.message, true);
        setBusy(false);
        throw error;
      });
    }
    return savePlace().then(next);
  }

  var queueBtn = document.getElementById("pl-gen-queue");
  if (queueBtn) queueBtn.addEventListener("click", function () {
    if (busy) return;
    runQueue();
  });
  var heroBtn = document.getElementById("pl-gen-hero");
  if (heroBtn) heroBtn.addEventListener("click", function () {
    if (busy) return;
    runQueue([{ kind: "hero", label: "Hero" }]);
  });
  var mapBtn = document.getElementById("pl-gen-map");
  if (mapBtn) mapBtn.addEventListener("click", function () {
    if (busy) return;
    runQueue([{ kind: "map", label: "Mapa" }]);
  });
  var publishBtn = document.getElementById("pl-publish");
  if (publishBtn) publishBtn.addEventListener("click", function () {
    placeAction("/publish", {}, "Place publicado.", "Publicando…");
  });
  var unpublishBtn = document.getElementById("pl-unpublish");
  if (unpublishBtn) unpublishBtn.addEventListener("click", function () {
    placeAction("/unpublish", {}, "Place em rascunho.", "Despublicando…");
  });

  var pointsBody = document.getElementById("pl-points-body");
  var addPoint = document.getElementById("pl-add-point");
  if (addPoint && pointsBody) {
    addPoint.addEventListener("click", function () {
      pointsBody.insertAdjacentHTML("beforeend", pointRowHtml({}));
    });
    pointsBody.addEventListener("click", function (event) {
      var gen = event.target.closest("[data-gen-point]");
      if (gen) {
        var row = gen.closest("tr");
        var id = gen.getAttribute("data-gen-point") || (row.querySelector("[name=point_id]") || {}).value;
        var name = (row.querySelector("[name=point_name]") || {}).value || "Ponto";
        if (busy) return;
        runQueue([{ kind: "point", point_id: id || name, label: name }]);
        return;
      }
      var button = event.target.closest("[data-remove-point]");
      if (button) {
        var row = button.closest("tr");
        var extra = row && row.nextElementSibling;
        if (extra && extra.classList.contains("pl-point-extra")) extra.remove();
        if (row) row.remove();
        drawMarkers();
      }
    });
  }

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
        if (!pointsBody) return;
        var n = pointsBody.querySelectorAll("tr.pl-point-row").length + 1;
        pointsBody.insertAdjacentHTML("beforeend", pointRowHtml({
          name: "Ponto " + n,
          lat: event.latlng.lat.toFixed(6),
          lng: event.latlng.lng.toFixed(6)
        }));
        drawMarkers();
      });
      window.addEventListener("resize", function () {
        if (map) map.invalidateSize();
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
    markers = collectPoints().filter(function (point) {
      return point.lat != null && point.lng != null;
    }).map(function (point) {
      return L.marker([point.lat, point.lng]).addTo(map).bindPopup(
        escapeHtml(point.name) + "<br>" + point.lat + ", " + point.lng
      );
    });
  }

  applyPlace(place);
  showTab(currentTab());
})();
