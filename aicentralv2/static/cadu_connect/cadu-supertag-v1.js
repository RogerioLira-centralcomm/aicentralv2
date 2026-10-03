/* Cadu Super Tag v1: first-party, batched measurement.
 * Install with one line: <script async src=".../v1/supertag.js" data-cadu-site="ID"></script>. Everything else (enhanced
 * measurement switches, form capture, retention) comes from the site's config.json, edited in the Reports panel.
 * Consent belongs to the website (its banner and privacy policy); the tag collects by default and only stops on an
 * explicit opt-out: CaduSuperTag.setConsent(false) or a `cadu:consent` event with {analytics: false}.
 * Technical safety is fixed: no query string, hash or e-mail in paths, never passwords, cards or documents. */
(function () {
  'use strict';
  // document.currentScript also points to a tag injected by a loader (Google Tag Manager's custom HTML). If a loader
  // ever runs us without it, or without the attribute, the tag looks for its own <script> and for ?id= in its URL.
  var tagSource = /\/(?:v1\/supertag|cadu-supertag-v1(?:\.min)?)\.js(?:[?#]|$)/;
  var script = document.currentScript;
  if (!script || !script.getAttribute('data-cadu-site')) script = findOwnScript() || script;
  var siteId = script && (script.getAttribute('data-cadu-site') || siteFromSource(script.src));

  function findOwnScript() {
    var candidates = document.querySelectorAll('script[data-cadu-site][src]');
    for (var index = 0; index < candidates.length; index++) {
      if (tagSource.test(candidates[index].src)) return candidates[index];
    }
    return null;
  }

  function siteFromSource(src) {
    try { return new URL(src, location.href).searchParams.get('id') || ''; } catch (_) { return ''; }
  }
  if (!siteId || !/^[A-Za-z0-9_-]{1,64}$/.test(siteId) || !window.crypto || !window.crypto.randomUUID) return;
  // Old snippets carry data-cadu-config; the one-line snippet lets the tag find the config next to its own URL.
  var configUrl = script.getAttribute('data-cadu-config') || defaultConfigUrl();
  if (!configUrl) return;

  function defaultConfigUrl() {
    var source;
    try { source = new URL(script.src, location.href); } catch (_) { return ''; }
    var prefix = source.pathname.replace(/\/(?:v1\/supertag|static\/cadu_connect\/cadu-supertag-v1(?:\.min)?)\.js$/, '');
    if (prefix === source.pathname) prefix = '';
    return source.origin + prefix + '/connect/public/supertag/v1/' + siteId + '/config.json';
  }

  var parsedConfigUrl;
  try { parsedConfigUrl = new URL(configUrl, location.href); } catch (_) { return; }
  if (!/^https?:$/.test(parsedConfigUrl.protocol) || !/\/connect\/public\/supertag\/v1\/[A-Za-z0-9_-]+\/config\.json$/.test(parsedConfigUrl.pathname)) return;
  var endpointUrl = new URL(parsedConfigUrl.href);
  endpointUrl.pathname = endpointUrl.pathname.replace(/\/config\.json$/, '/collect');
  endpointUrl.search = '';
  endpointUrl.hash = '';
  var endpoint = endpointUrl.href;
  var identifyUrl = endpoint.replace(/\/collect$/, '/identify');
  var leadUrl = endpoint.replace(/\/collect$/, '/lead');
  var cookieName = 'cadu_stg_' + siteId.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 24);
  var optOutKey = cookieName + '_optout';
  var config = null;
  var optedOut = false;
  var started = false;
  var buffer = [];
  var maxBuffer = 100;
  var visitorId = null;
  var sessionId = null;
  var lastPath = '';
  var activePath = '';
  var pageActiveSince = 0;
  var pageActiveDuration = 0;
  var lastClickAt = 0;
  var seenVisibility = Object.create(null);
  var lastScrollDepth = 0;
  var campaignScope = '';
  var sessionAttribution = null;
  var lastMeaningfulAt = 0;
  var sessionIdleMs = 30 * 60 * 1000;
  var flushTimer = 0;
  var heartbeatTimer = 0;
  var flushInFlight = false;
  var observers = [];
  var listenersInstalled = false;
  var visibilityDomReadyScheduled = false;
  var activeController = null;
  try { optedOut = localStorage.getItem(optOutKey) === '1'; } catch (_) { /* Storage may be blocked. */ }

  function readCookie(name) {
    var prefix = name + '=';
    var part = document.cookie.split('; ').find(function (value) { return value.indexOf(prefix) === 0; });
    return part ? decodeURIComponent(part.slice(prefix.length)) : '';
  }

  function writeCookie(value, days) {
    document.cookie = cookieName + '=' + encodeURIComponent(value) + '; Max-Age=' + (Math.min(days, 395) * 86400) +
      '; Path=/; SameSite=Lax' + (location.protocol === 'https:' ? '; Secure' : '');
  }

  function readAttribution() {
    var query = new URLSearchParams(location.search);
    var values = {};
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_id'].forEach(function (key) {
      var value = query.get(key);
      if (value && value.length <= 160 && value.indexOf('@') === -1) values[key] = value;
    });
    var clickId = query.get('gclid') || query.get('gbraid') || query.get('wbraid') || query.get('fbclid');
    if (clickId && clickId.length <= 160) values.click_id = clickId;
    return values;
  }

  function currentCampaignScope() {
    if (!campaignScope) {
      var attribution = readAttribution();
      campaignScope = (attribution.utm_id || attribution.utm_campaign || '').trim().toLowerCase();
      if (campaignScope) {
        try { sessionStorage.setItem(cookieName + '_campaign', campaignScope); } catch (_) { /* Optional session persistence. */ }
      }
    }
    return campaignScope;
  }

  function attributionForSession() {
    if (!sessionAttribution) {
      var current = readAttribution();
      if (Object.keys(current).length) {
        sessionAttribution = current;
        try { sessionStorage.setItem(cookieName + '_attribution', JSON.stringify(current)); } catch (_) { /* Optional persistence. */ }
      }
    }
    return sessionAttribution || {};
  }

  function freshSessionIfIdle() {
    if (!lastMeaningfulAt || Date.now() - lastMeaningfulAt <= sessionIdleMs) return false;
    sessionId = crypto.randomUUID();
    lastMeaningfulAt = Date.now();
    campaignScope = '';
    sessionAttribution = null;
    lastPath = '';
    activePath = '';
    pageActiveSince = 0;
    pageActiveDuration = 0;
    try {
      sessionStorage.setItem(cookieName + '_session', sessionId);
      sessionStorage.removeItem(cookieName + '_campaign');
      sessionStorage.removeItem(cookieName + '_attribution');
    } catch (_) { /* Storage may be blocked. */ }
    currentCampaignScope();
    return true;
  }

  function referrerHost() {
    try { return document.referrer ? new URL(document.referrer).hostname : ''; }
    catch (_) { return ''; }
  }

  function viewport() {
    return {width: Math.min(window.innerWidth || 0, 10000), height: Math.min(window.innerHeight || 0, 10000)};
  }

  // Screen size, pixel ratio and orientation travel with the page view; system and browser are read from the request on the server.
  function screenData() {
    var data = {};
    try {
      var screenBox = window.screen;
      if (screenBox && screenBox.width > 0 && screenBox.height > 0) {
        data.sw = Math.min(Math.max(Math.round(screenBox.width), 1), 10000);
        data.sh = Math.min(Math.max(Math.round(screenBox.height), 1), 10000);
      }
      if (window.devicePixelRatio > 0) data.dpr = Math.min(Math.max(window.devicePixelRatio, 0.5), 10);
      data.orient = (window.innerHeight || 0) >= (window.innerWidth || 0) ? 'portrait' : 'landscape';
    } catch (_) { /* Optional context. */ }
    return data;
  }

  function documentBox() {
    var root = document.documentElement, body = document.body;
    if (!root || !body) return null;
    var width = Math.max(root.scrollWidth || 0, body.scrollWidth || 0, window.innerWidth || 0);
    var height = Math.max(root.scrollHeight || 0, body.scrollHeight || 0, window.innerHeight || 0);
    if (width < 1 || height < 1 || height > 100000) return null;
    return {width: width, height: height, scrollX: window.pageXOffset || 0, scrollY: window.pageYOffset || 0};
  }

  // Enhanced measurement switches from config.enhanced; a missing key (or an old config) means on.
  function measures(key) {
    var enhanced = config && config.enhanced;
    return !enhanced || typeof enhanced !== 'object' || enhanced[key] !== false;
  }

  var DOWNLOAD_EXT = /\.(pdf|docx?|xlsx?|xlsm|pptx?|pps|csv|txt|rtf|odt|ods|odp|epub|zip|rar|7z|gz|tgz|tar|exe|msi|dmg|pkg|apk|key|mp3|wav|wma|m4a|mp4|mpe?g|mov|avi|wmv)$/i;
  var WHATSAPP = /^whatsapp:|(?:^|\/\/)(?:wa\.me|api\.whatsapp\.com|web\.whatsapp\.com|chat\.whatsapp\.com)(?:[\/:?#]|$)/i;

  function bareHost(host) { return String(host || '').toLowerCase().replace(/^www\./, ''); }

  // What a link is, from its href alone. Only the kind, the host and the file extension ever leave the browser:
  // never the path, the query string, the phone number or the e-mail address.
  function classifyLink(anchor) {
    var href = anchor && anchor.getAttribute('href');
    if (!href) return null;
    var raw = href.trim();
    if (/^tel:/i.test(raw)) return {type: 'contact', channel: 'phone'};
    if (/^mailto:/i.test(raw)) return {type: 'contact', channel: 'email'};
    if (WHATSAPP.test(raw)) return {type: 'contact', channel: 'whatsapp'};
    var url;
    try { url = new URL(raw, location.href); } catch (_) { return null; }
    if (!/^https?:$/.test(url.protocol)) return null;
    if (WHATSAPP.test('//' + url.hostname + '/')) return {type: 'contact', channel: 'whatsapp'};
    var external = bareHost(url.hostname) !== bareHost(location.hostname);
    var ext = url.pathname.match(DOWNLOAD_EXT);
    if (ext || anchor.hasAttribute('download')) {
      var found = ext ? ext[1].toLowerCase() : (url.pathname.match(/\.([a-z0-9]{1,8})$/i) || [])[1];
      return {type: 'download', ext: found ? found.toLowerCase() : '', host: external ? url.hostname.toLowerCase() : ''};
    }
    return external ? {type: 'outbound', host: url.hostname.toLowerCase()} : null;
  }

  // Returns the event id, so a form submit can link the lead it captures to its own event.
  function pushEvent(kind, data, name, pathOverride) {
    if (!started || optedOut || buffer.length >= maxBuffer) return null;
    if (kind !== 'heartbeat' && kind !== 'page_leave') {
      if (freshSessionIfIdle() && kind !== 'page_view') trackPage();
      lastMeaningfulAt = Date.now();
      try { sessionStorage.setItem(cookieName + '_active_at', String(lastMeaningfulAt)); } catch (_) { /* Optional persistence. */ }
    }
    var size = viewport();
    var id = crypto.randomUUID();
    buffer.push({event_id: id, visitor_id: visitorId, session_id: sessionId,
      kind: kind, event_name: name || undefined, path: pathOverride || location.pathname || '/', referrer_host: referrerHost(),
      attribution: attributionForSession(), data: data || {}, viewport_width: size.width,
      viewport_height: size.height, occurred_at: new Date().toISOString()});
    if (buffer.length >= 10) flush(false);
    return id;
  }

  function event(kind, data, name, pathOverride) {
    return pushEvent(kind, data, name, pathOverride) !== null;
  }

  function idsOf(batch) {
    var ids = Object.create(null);
    batch.forEach(function (item) { ids[item.event_id] = true; });
    return ids;
  }

  // Removes by id, never by position: a beacon may have emptied the buffer while a fetch was still on its way.
  function removeSent(ids) {
    buffer = buffer.filter(function (item) { return !ids[item.event_id]; });
  }

  function beaconAll() {
    // Leaving the page: everything goes out now, including what an unfinished fetch carries (repeated ids are ignored).
    while (buffer.length) {
      var batch = buffer.slice(0, 25);
      try {
        if (!navigator.sendBeacon(endpoint, new Blob([JSON.stringify({events: batch})], {type: 'text/plain;charset=UTF-8'}))) return false;
      } catch (_) { return false; }
      removeSent(idsOf(batch));
    }
    return true;
  }

  function flush(beacon) {
    if (optedOut || !buffer.length) return;
    if (beacon && navigator.sendBeacon && beaconAll()) return;
    if (flushInFlight) return;
    var batch = buffer.slice(0, 25);
    var ids = idsOf(batch);
    flushInFlight = true;
    activeController = typeof AbortController !== 'undefined' ? new AbortController() : null;
    fetch(endpoint, {method: 'POST', mode: 'cors', keepalive: true,
      signal: activeController ? activeController.signal : undefined,
      headers: {'Content-Type': 'text/plain;charset=UTF-8'}, body: JSON.stringify({events: batch})})
      .then(function (response) {
        // A 4xx (other than 429) will never be accepted: drop the batch instead of resending it forever.
        if (response.ok || (response.status >= 400 && response.status < 500 && response.status !== 429)) removeSent(ids);
      })
      .catch(function () {})
      .finally(function () {
        activeController = null;
        flushInFlight = false;
        if (!optedOut && buffer.length >= 10) flush(false);
      });
  }

  function trackHistoryPage() {
    if (measures('page_changes')) trackPage();
  }

  // pushState/replaceState also run for filters, query strings and scroll-spy hashes: only a new path is a new page.
  function onHistoryApi() {
    if ((location.pathname || '/') !== activePath) trackHistoryPage();
  }

  function trackPage() {
    if (!started || optedOut) return;
    freshSessionIfIdle();
    var path = location.pathname || '/';
    if (location.hash && path === lastPath) path += location.hash.slice(0, 120);
    if (path === lastPath) return;
    if (lastPath) leaveCurrentPage();
    lastPath = path;
    activePath = location.pathname || '/';
    pageActiveDuration = 0;
    pageActiveSince = document.visibilityState === 'visible' ? Date.now() : 0;
    seenVisibility = Object.create(null);
    lastScrollDepth = 0;
    event('page_view', screenData(), undefined, activePath);
    observeMarkedElements();
  }

  function pauseActivePage() {
    if (!pageActiveSince) return;
    pageActiveDuration += Math.max(0, Date.now() - pageActiveSince);
    pageActiveSince = 0;
  }

  function resumeActivePage() {
    if (started && !optedOut && lastPath && !pageActiveSince && document.visibilityState === 'visible') {
      pageActiveSince = Date.now();
    }
  }

  function leaveCurrentPage() {
    if (!lastPath) return;
    pauseActivePage();
    event('page_leave', {duration_ms: Math.min(600000, Math.round(pageActiveDuration))}, undefined, activePath || '/');
    lastPath = '';
    activePath = '';
    pageActiveDuration = 0;
  }

  function elementId(target) {
    var value = target && target.getAttribute && target.getAttribute('data-cadu-element');
    return value && /^[A-Za-z0-9_-]{1,80}$/.test(value) ? value : undefined;
  }

  function observeMarkedElements() {
    if (!config || !config.visibility_enabled || !('IntersectionObserver' in window)) return;
    observers.forEach(function (observer) { observer.disconnect(); });
    observers = [];
    if (document.readyState === 'loading') {
      if (!visibilityDomReadyScheduled) {
        visibilityDomReadyScheduled = true;
        document.addEventListener('DOMContentLoaded', function () {
          visibilityDomReadyScheduled = false;
          if (started && !optedOut) observeMarkedElements();
        }, {once: true});
      }
      return;
    }
    var nodes = document.querySelectorAll('[data-cadu-track]');
    if (!nodes.length) return;
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var id = elementId(entry.target);
        if (!id || !entry.isIntersecting) return;
        var ratio = entry.intersectionRatio >= 0.99 ? 100 : entry.intersectionRatio >= 0.75 ? 75 :
          entry.intersectionRatio >= 0.5 ? 50 : entry.intersectionRatio >= 0.25 ? 25 : 0;
        if (!ratio || ratio <= (seenVisibility[id] || 0)) return;
        seenVisibility[id] = ratio;
        event('visibility', {element_id: id, ratio: ratio});
      });
    }, {threshold: [0.25, 0.5, 0.75, 1]});
    Array.prototype.slice.call(nodes, 0, 200).forEach(function (node) { observer.observe(node); });
    observers.push(observer);
  }

  // Who converted: name, e-mail and phone found in a valid form, plus extra fields the site chose by name.
  // Passwords, cards, documents (CPF/CNPJ/RG), tokens, hidden fields and honeypots are never read.
  var BLOCKED_TYPES = /^(password|hidden|file|submit|button|reset|image)$/i;
  var BLOCKED_AUTOCOMPLETE = /(^|\s)(cc-[a-z-]+|current-password|new-password|one-time-code)(\s|$)/i;
  var BLOCKED_NAME = /senha|pass|card|cartao|cartão|cvv|cvc|token|captcha|csrf|cpf|cnpj|(^|[^a-z])rg($|[^a-z])/i;
  var DOCUMENT_VALUE = /^\s*(\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2})\s*$/;
  var MAX_LEAD_FIELDS = 20;

  function fieldKey(field) {
    return field.getAttribute('name') || field.id || '';
  }

  function looksHidden(field) {
    if (field.closest('[aria-hidden="true"],[data-cadu-ignore]')) return true;
    var box = field.getBoundingClientRect();
    if (!box.width || !box.height) return true;
    var pageWidth = Math.max(document.documentElement.scrollWidth || 0, window.innerWidth || 0);
    if (box.right <= 0 || box.left >= pageWidth || box.bottom + (window.pageYOffset || 0) <= 0) return true;
    var style = window.getComputedStyle ? window.getComputedStyle(field) : null;
    return !!style && (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0);
  }

  function contactKind(field) {
    var auto = (field.getAttribute('autocomplete') || '').toLowerCase();
    var type = (field.getAttribute('type') || '').toLowerCase();
    var key = fieldKey(field).toLowerCase();
    if (/(^|\s)email(\s|$)/.test(auto) || type === 'email' || /e-?mail/.test(key)) return 'email';
    if (/(^|\s)tel(-national)?(\s|$)/.test(auto) || type === 'tel' || /(^|[^a-z])(tel|telefone|fone|phone|celular|whats|whatsapp|mobile)/.test(key)) return 'phone';
    if (/(^|\s)(name|given-name|family-name)(\s|$)/.test(auto)) return 'name';
    if (!/company|empresa|user|login|organiza/.test(key) && /(^|[^a-z])(nome|name|fullname|sobrenome)([^a-z]|$)/.test(key)) return 'name';
    return '';
  }

  function readLead(form) {
    var capture = (config && config.form_capture) || {};
    if (capture.enabled === false) return null;
    var extras = Array.isArray(capture.fields) ? capture.fields : [];
    var lead = {name: '', email: '', phone: '', fields: {}};
    var count = 0;
    var elements = form.elements ? Array.prototype.slice.call(form.elements) : [];
    for (var i = 0; i < elements.length && count < MAX_LEAD_FIELDS; i++) {
      var field = elements[i];
      if (!/^(INPUT|SELECT|TEXTAREA)$/.test(field.tagName) || field.disabled) continue;
      var type = (field.getAttribute('type') || '').toLowerCase();
      if (BLOCKED_TYPES.test(type) || BLOCKED_AUTOCOMPLETE.test(field.getAttribute('autocomplete') || '')) continue;
      var key = fieldKey(field);
      if (BLOCKED_NAME.test(key) || BLOCKED_NAME.test(field.id || '')) continue;
      if ((type === 'checkbox' || type === 'radio') && !field.checked) continue;
      if (looksHidden(field)) continue;
      var value = String(field.value || '').trim().slice(0, field.tagName === 'TEXTAREA' ? 2000 : 200);
      if (!value) continue;
      var kind = contactKind(field);
      if (kind === 'phone') {
        if (!lead.phone) { lead.phone = value.slice(0, 40); count += 1; }
        continue;
      }
      if (DOCUMENT_VALUE.test(value) || /\d{13,19}/.test(value.replace(/[\s.-]/g, ''))) continue;
      if (kind === 'email') {
        if (!lead.email) { lead.email = value.slice(0, 254); count += 1; }
      } else if (kind === 'name') {
        lead.name = (lead.name ? lead.name + ' ' + value : value).slice(0, 200);
        count += 1;
      } else if (key && extras.indexOf(key) !== -1 && !Object.prototype.hasOwnProperty.call(lead.fields, key)) {
        lead.fields[key] = value;
        count += 1;
      }
    }
    return lead.name || lead.email || lead.phone || Object.keys(lead.fields).length ? lead : null;
  }

  function sendLead(form, eventId, formId) {
    var lead;
    try { lead = readLead(form); } catch (_) { return; }
    if (!lead) return;
    var body = JSON.stringify({event_id: eventId, visitor_id: visitorId, session_id: sessionId, form_id: formId || undefined,
      path: location.pathname || '/', occurred_at: new Date().toISOString(),
      name: lead.name, email: lead.email, phone: lead.phone, fields: lead.fields});
    // A beacon survives the redirect to the thank-you page.
    try {
      if (navigator.sendBeacon && navigator.sendBeacon(leadUrl, new Blob([body], {type: 'text/plain;charset=UTF-8'}))) return;
    } catch (_) { /* Use fetch below. */ }
    fetch(leadUrl, {method: 'POST', mode: 'cors', keepalive: true, credentials: 'omit',
      headers: {'Content-Type': 'text/plain;charset=UTF-8'}, body: body}).catch(function () {});
  }

  // Embedded HTML5 <video>: start, 25/50/75% and complete, once per element and page view.
  var videoState = typeof WeakMap !== 'undefined' ? new WeakMap() : null;
  function onVideo(eventObject) {
    var media = eventObject.target;
    if (!videoState || !started || optedOut || !media || media.tagName !== 'VIDEO' || !measures('video')) return;
    if (media.closest && media.closest('[data-cadu-ignore]')) return;
    var state = videoState.get(media);
    if (!state || state.page !== lastPath) { state = {page: lastPath, started: false, progress: 0, done: false}; videoState.set(media, state); }
    if (eventObject.type === 'play' && !state.started) {
      state.started = true;
      event('video', {action: 'start'});
    } else if (eventObject.type === 'timeupdate' && media.duration > 0 && isFinite(media.duration)) {
      var percent = media.currentTime / media.duration * 100;
      var mark = percent >= 75 ? 75 : percent >= 50 ? 50 : percent >= 25 ? 25 : 0;
      if (mark > state.progress && state.started) {
        state.progress = mark;
        event('video', {action: 'progress', percent: mark});
      }
    } else if (eventObject.type === 'ended' && !state.done) {
      state.done = true;
      event('video', {action: 'complete'});
    }
  }

  // Short readable name of the clicked element for the heatmap ranking: its accessible name, visible text, image alt
  // or, for icon links, the destination. Anything that looks like personal data (e-mail, phone, document) is dropped.
  function elementLabel(target) {
    var text = target.getAttribute('aria-label') || '';
    if (!text.trim()) text = target.innerText || target.textContent || '';
    if (!text.trim()) {
      var image = target.querySelector && target.querySelector('img[alt]');
      text = (image && image.getAttribute('alt')) || target.getAttribute('title') || '';
    }
    if (!text.trim() && target.tagName === 'A') {
      try {
        var url = new URL(target.getAttribute('href') || '', location.href);
        if (/^https?:$/.test(url.protocol)) text = bareHost(url.hostname) !== bareHost(location.hostname) ? bareHost(url.hostname) : url.pathname;
      } catch (_) { text = ''; }
    }
    text = text.replace(/\s+/g, ' ').trim();
    if (!text || /@|\d[\d .()/-]{6,}\d|\d{4,}/.test(text)) return undefined;
    return text.length > 60 ? text.slice(0, 59) + '…' : text;
  }

  function elementKind(target) {
    var visibleText = (target.innerText || target.textContent || '').trim();
    if (!visibleText && target.querySelector && target.querySelector('img')) return 'image';
    if (!visibleText) return 'icon';
    return target.tagName === 'A' ? 'link' : target.tagName === 'BUTTON' || target.getAttribute('role') === 'button' ? 'button' : 'element';
  }

  function clickPosition(eventObject, target) {
    var size = viewport();
    var doc = documentBox();
    var data = {x: Math.max(0, Math.min(1000, Math.round(eventObject.clientX / Math.max(size.width, 1) * 1000))),
      y: Math.max(0, Math.min(1000, Math.round(eventObject.clientY / Math.max(size.height, 1) * 1000))),
      element_id: elementId(target), el_kind: elementKind(target)};
    var label = elementLabel(target);
    if (label) data.el_label = label;
    if (doc) {
      // Position inside the whole page, so clicks made at different scroll offsets land in the same place.
      data.dx = Math.max(0, Math.min(1000, Math.round((eventObject.clientX + doc.scrollX) / doc.width * 1000)));
      data.dy = Math.max(0, Math.min(1000, Math.round((eventObject.clientY + doc.scrollY) / doc.height * 1000)));
      data.dh = doc.height;
    }
    return data;
  }

  // gtag-style parameters: only a numeric value and a currency code travel; anything else is ignored.
  function eventParams(params) {
    var data = {};
    if (!params || typeof params !== 'object') return data;
    var value = params.value;
    if (typeof value === 'string' && /^\d+(?:[.,]\d+)?$/.test(value.trim())) value = Number(value.trim().replace(',', '.'));
    if (typeof value === 'number' && isFinite(value) && value >= 0 && value <= 1e9) data.value = Math.round(value * 100) / 100;
    if (typeof params.currency === 'string' && /^[A-Za-z]{3}$/.test(params.currency)) data.currency = params.currency.toUpperCase();
    return data;
  }

  function validName(name) {
    return typeof name === 'string' && /^[A-Za-z][A-Za-z0-9_]{0,79}$/.test(name);
  }

  function start() {
    if (!config || optedOut || started) return;
    started = true;
    visitorId = readCookie(cookieName) || crypto.randomUUID();
    writeCookie(visitorId, config.audience_days || 365);
    try {
      sessionId = sessionStorage.getItem(cookieName + '_session') || crypto.randomUUID();
      lastMeaningfulAt = Number(sessionStorage.getItem(cookieName + '_active_at')) || Date.now();
      sessionAttribution = JSON.parse(sessionStorage.getItem(cookieName + '_attribution') || 'null');
      sessionStorage.setItem(cookieName + '_session', sessionId);
      campaignScope = sessionStorage.getItem(cookieName + '_campaign') || '';
    } catch (_) { sessionId = crypto.randomUUID(); lastMeaningfulAt = Date.now(); sessionAttribution = null; }
    currentCampaignScope();
    trackPage();
    if (!listenersInstalled) {
      listenersInstalled = true;
      // One delegated listener detects everything: no data-cadu-* attribute is needed on links or buttons.
      document.addEventListener('click', function (eventObject) {
        var target = eventObject.target && eventObject.target.closest ?
          eventObject.target.closest('a,button,[role="button"],[data-cadu-element]') : null;
        if (!target || target.closest('input,textarea,select,[contenteditable="true"],[data-cadu-ignore]')) return;
        var now = Date.now();
        if (now - lastClickAt < 250) return;
        lastClickAt = now;
        var link = classifyLink(target.closest('a[href]'));
        var contacts = measures('contacts');
        if (link && link.type === 'contact' && link.channel === 'whatsapp' && contacts) {
          // WhatsApp keeps its own kind, which also feeds the click map.
          event('whatsapp_click', clickPosition(eventObject, target));
        } else if (measures('clicks')) {
          event('click', clickPosition(eventObject, target));
        }
        if (!link) return;
        if (link.type === 'contact' && link.channel !== 'whatsapp' && contacts) event('contact_click', {channel: link.channel});
        else if (link.type === 'outbound' && measures('outbound')) event('outbound_click', {link_host: link.host});
        else if (link.type === 'download' && measures('downloads')) {
          var file = {};
          if (link.ext) file.file_ext = link.ext;
          if (link.host) file.link_host = link.host;
          event('file_download', file);
        }
      }, true);
      document.addEventListener('submit', function (eventObject) {
        if (!measures('forms')) return;
        var form = eventObject.target;
        if (!form || form.tagName !== 'FORM' || form.closest('[data-cadu-ignore]')) return;
        var id = form.getAttribute('data-cadu-form');
        var valid = typeof form.checkValidity === 'function' ? form.checkValidity() : true;
        var data = {valid: valid};
        if (id && /^[A-Za-z0-9_-]{1,80}$/.test(id)) data.form_id = id;
        var eventId = pushEvent('form_submit', data);
        if (eventId && valid) sendLead(form, eventId, data.form_id);
        // The page usually navigates right after a submit.
        flush(true);
      }, true);
      window.addEventListener('scroll', function () {
        if (!started || optedOut || !measures('scroll')) return;
        var doc = document.documentElement;
        var max = Math.max(doc.scrollHeight - window.innerHeight, 1);
        var percent = Math.min(100, Math.floor((window.scrollY || 0) / max * 4 + 1) * 25);
        if (percent > lastScrollDepth) {
          lastScrollDepth = percent;
          event('scroll_depth', {depth: percent});
        }
      }, {passive: true});
      // Single-page apps: history changes count as page views (the same path is never counted twice).
      window.addEventListener('popstate', trackHistoryPage);
      window.addEventListener('hashchange', trackHistoryPage);
      if (window.navigation && window.navigation.addEventListener) {
        window.navigation.addEventListener('navigatesuccess', trackHistoryPage);
      }
      ['pushState', 'replaceState'].forEach(function (method) {
        var original = window.history && window.history[method];
        if (typeof original !== 'function') return;
        try {
          window.history[method] = function () {
            var result = original.apply(this, arguments);
            window.setTimeout(onHistoryApi, 0);
            return result;
          };
        } catch (_) { /* A frozen history object keeps working without SPA page views. */ }
      });
      ['play', 'timeupdate', 'ended'].forEach(function (type) { document.addEventListener(type, onVideo, true); });
      window.addEventListener('pagehide', function () { leaveCurrentPage(); flush(true); });
      document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'hidden') pauseActivePage();
        else resumeActivePage();
      });
    }
    flushTimer = window.setInterval(function () { flush(false); }, 5000);
    heartbeatTimer = window.setInterval(function () {
      if (started && !optedOut && document.visibilityState === 'visible') event('heartbeat');
    }, 30000);
    observeMarkedElements();
  }

  function stop() {
    started = false;
    buffer = [];
    lastPath = '';
    activePath = '';
    pageActiveSince = 0;
    pageActiveDuration = 0;
    visitorId = null;
    sessionId = null;
    sessionAttribution = null;
    lastMeaningfulAt = 0;
    try { sessionStorage.removeItem(cookieName + '_session'); } catch (_) { /* Storage may be blocked. */ }
    try { sessionStorage.removeItem(cookieName + '_campaign'); } catch (_) { /* Storage may be blocked. */ }
    try { sessionStorage.removeItem(cookieName + '_attribution'); } catch (_) { /* Storage may be blocked. */ }
    try { sessionStorage.removeItem(cookieName + '_active_at'); } catch (_) { /* Storage may be blocked. */ }
    if (flushTimer) window.clearInterval(flushTimer);
    if (heartbeatTimer) window.clearInterval(heartbeatTimer);
    if (activeController) activeController.abort();
    flushTimer = 0;
    heartbeatTimer = 0;
    observers.forEach(function (observer) { observer.disconnect(); });
    observers = [];
    document.cookie = cookieName + '=; Max-Age=0; Path=/; SameSite=Lax' +
      (location.protocol === 'https:' ? '; Secure' : '');
  }

  // Explicit opt-out only: false/'denied' stops and remembers it on this browser; true/'granted' resumes.
  function setConsent(value) {
    if (value === true || value === 'granted') {
      optedOut = false;
      try { localStorage.removeItem(optOutKey); } catch (_) { /* Storage may be blocked. */ }
      start();
    } else if (value === false || value === 'denied') {
      optedOut = true;
      try { localStorage.setItem(optOutKey, '1'); } catch (_) { /* Storage may be blocked. */ }
      stop();
    }
  }

  window.CaduSuperTag = Object.freeze({
    setConsent: setConsent,
    trackPage: trackPage,
    getVisitorId: function () { return optedOut ? null : visitorId; },
    getSessionId: function () { return optedOut ? null : sessionId; },
    identify: function (identity) {
      if (!started || optedOut || !identity || typeof identity !== 'object') return Promise.resolve(false);
      if (freshSessionIfIdle()) trackPage();
      var name = typeof identity.name === 'string' ? identity.name.trim().slice(0, 120) : '';
      var email = typeof identity.email === 'string' ? identity.email.trim().slice(0, 254) : '';
      var phone = typeof identity.phone === 'string' ? identity.phone.trim().slice(0, 40) : '';
      if (!email && !phone) return Promise.resolve(false);
      return fetch(identifyUrl, {method:'POST', mode:'cors', credentials:'omit', keepalive: true,
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({visitor_id:visitorId,session_id:sessionId,name:name,email:email,phone:phone,campaign:currentCampaignScope(),path:location.pathname || '/'})
      }).then(function (response) { return response.ok; }).catch(function () { return false; });
    },
    // gtag-style: event('lead_enviado', {value: 120, currency: 'BRL'}); {conversion: true} counts it as a conversion.
    // 'page_view' records the current page (for SPAs that route on their own).
    event: function (name, params) {
      if (name === 'page_view') { trackPage(); return started && !optedOut; }
      if (!validName(name)) return false;
      return event(params && params.conversion === true ? 'conversion' : 'custom_event', eventParams(params), name);
    },
    trackEvent: function (name, params) {
      if (!validName(name)) return false;
      return event('custom_event', eventParams(params), name);
    },
    trackConversion: function (name, params) {
      if (!validName(name)) return false;
      return event('conversion', eventParams(params), name);
    }
  });
  window.addEventListener('cadu:consent', function (eventObject) {
    var detail = eventObject && eventObject.detail;
    if (detail && Object.prototype.hasOwnProperty.call(detail, 'analytics')) setConsent(detail.analytics);
  });
  fetch(configUrl, {mode: 'cors', credentials: 'omit', cache: 'force-cache'})
    .then(function (response) { if (!response.ok) throw new Error('config'); return response.json(); })
    .then(function (value) {
      if (value.site_id !== siteId) return;
      config = value;
      start();
    })
    .catch(function () {});
})();
