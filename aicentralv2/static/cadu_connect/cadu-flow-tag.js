/* Cadu Reports Funnel Flow V2. Each client has one loader URL; the published flow code selects its flow. */
(function () {
  'use strict';
  var script = document.currentScript;
  var key = script && script.getAttribute('data-cadu-key');
  var clientId = script && script.getAttribute('data-cadu-client');
  var flowCode = script && script.getAttribute('data-cadu-flow');
  if (!key || !clientId || !flowCode || !window.crypto || !window.crypto.randomUUID) return;
  var endpointBase = new URL('/connect/api/v1/reports/flow/collect/' + encodeURIComponent(flowCode || ''), script.src);
  var endpoint = endpointBase.href + '?key=' + encodeURIComponent(key) + '&client_id=' + encodeURIComponent(clientId);
  var visitorKey = 'cadu_flow_visitor_' + key;
  var sessionKey = 'cadu_flow_session_' + key;
  function id(storage, name) {
    try {
      var value = storage.getItem(name);
      if (!value) { value = crypto.randomUUID(); storage.setItem(name, value); }
      return value;
    } catch (_) { return crypto.randomUUID(); }
  }
  // Session-scoped identifiers; no third-party cookie or personal form capture.
  var storage;
  try { storage = window.sessionStorage; } catch (_) { storage = null; }
  var visitor = id(storage, visitorKey);
  var session = id(storage, sessionKey);
  var attributionKey = 'cadu_flow_attribution_' + key;
  function currentAttribution() {
    var query = new URLSearchParams(location.search);
    var attribution = {
      utm_source: query.get('utm_source') || '',
      utm_medium: query.get('utm_medium') || '',
      utm_campaign: query.get('utm_campaign') || '',
      utm_id: query.get('utm_id') || '',
      click_id: query.get('gclid') || query.get('gbraid') || query.get('wbraid') || query.get('fbclid') || ''
    };
    try {
      if (attribution.utm_source || attribution.utm_medium || attribution.utm_campaign || attribution.utm_id || attribution.click_id) {
        storage.setItem(attributionKey, JSON.stringify(attribution));
      } else {
        attribution = JSON.parse(storage.getItem(attributionKey) || '{}');
      }
    } catch (_) { /* Tracking still works when storage is unavailable. */ }
    return attribution && typeof attribution === 'object' ? attribution : {};
  }
  var lastPage = '';
  var lastPageAt = 0;
  var eventWindow = Date.now();
  var eventCount = 0;
  function send(kind, eventName) {
    if (Date.now() - eventWindow > 60000) { eventWindow = Date.now(); eventCount = 0; }
    if (eventCount >= 100) return;
    eventCount += 1;
    var attribution = currentAttribution();
    var data = JSON.stringify({flow_code: flowCode, kind: kind, event_name: eventName || '', visitor_id: visitor, session_id: session,
      path: location.pathname, referrer: document.referrer, attribution: attribution});
    fetch(endpoint, {method: 'POST', mode: 'cors', keepalive: true,
      headers: {'Content-Type': 'application/json'}, body: data}).catch(function () {});
  }
  function trackPage() {
    var attribution = currentAttribution();
    var signature = location.origin + location.pathname + '|' + (attribution.utm_id || '') + '|' + (attribution.utm_campaign || '');
    var now = Date.now();
    if (signature === lastPage && now - lastPageAt < 1000) return;
    lastPage = signature;
    lastPageAt = now;
    send('page_view');
  }
  var lastActionAt = 0;
  function trackAction(kind) {
    var now = Date.now();
    if (now - lastActionAt < 700) return;
    lastActionAt = now;
    send(kind);
  }
  window.CaduFlow = Object.freeze({
    getVisitorId: function () { return visitor; },
    getSessionId: function () { return session; },
    trackEvent: function (eventName) {
      if (typeof eventName !== 'string' || !eventName.trim()) return false;
      send('custom_event', eventName.trim().slice(0, 120));
      return true;
    },
    trackPage: trackPage
  });
  dispatchEvent(new CustomEvent('cadu:flow-ready', {detail: {visitorId: visitor}}));
  trackPage();
  document.addEventListener('submit', function (event) {
    if (event.target && event.target.tagName === 'FORM') trackAction('form_submit');
  }, true);
  document.addEventListener('click', function (event) {
    var target = event.target && event.target.closest ? event.target.closest('a,button,[role="button"]') : null;
    if (target) {
      var href = target.getAttribute('href') || '';
      var label = (target.getAttribute('aria-label') || target.textContent || '').trim().toLowerCase();
      if (/wa\.me|api\.whatsapp\.com/i.test(href) || /whats?app/.test(label)) trackAction('whatsapp_click');
      else trackAction('click');
    }
  }, true);
  var pushState = history.pushState;
  history.pushState = function () { var result = pushState.apply(this, arguments); setTimeout(trackPage, 0); return result; };
  addEventListener('popstate', trackPage);
  var timer = setInterval(function () {
    if (document.visibilityState === 'visible') send('heartbeat');
  }, 30000);
  addEventListener('pagehide', function () { clearInterval(timer); }, {once: true});
})();
