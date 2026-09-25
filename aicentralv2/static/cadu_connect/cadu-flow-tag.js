/* Cadu Reports Funnel Flow V1. Load with: <script async src=".../cadu-flow-tag.js" data-cadu-key="..."></script> */
(function () {
  'use strict';
  var script = document.currentScript;
  var key = script && script.getAttribute('data-cadu-key');
  if (!key || !window.crypto || !window.crypto.randomUUID) return;
  var endpoint = new URL('/connect/api/v1/reports/flow/collect', script.src).href;
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
  var query = new URLSearchParams(location.search);
  var attributionKey = 'cadu_flow_attribution_' + key;
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
  window.CaduFlow = Object.freeze({getVisitorId: function () { return visitor; }});
  dispatchEvent(new CustomEvent('cadu:flow-ready', {detail: {visitorId: visitor}}));
  function send(kind) {
    var data = JSON.stringify({
      key: key, kind: kind, visitor_id: visitor, session_id: session,
      url: location.origin + location.pathname,
      referrer: document.referrer,
      utm_source: attribution.utm_source || '',
      utm_medium: attribution.utm_medium || '',
      utm_campaign: attribution.utm_campaign || '',
      utm_id: attribution.utm_id || '',
      click_id: attribution.click_id || ''
    });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(endpoint, new Blob([data], {type: 'text/plain'}));
    } else {
      fetch(endpoint, {method: 'POST', mode: 'no-cors', keepalive: true,
        headers: {'Content-Type': 'text/plain'}, body: data}).catch(function () {});
    }
  }
  send('page_view');
  var timer = setInterval(function () {
    if (document.visibilityState === 'visible') send('heartbeat');
  }, 30000);
  addEventListener('pagehide', function () { clearInterval(timer); }, {once: true});
})();
