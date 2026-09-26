/* Cadu Planner's first-party monitor. It never forwards events to ad platforms. */
(function () {
  'use strict';
  var script = document.currentScript;
  if (!script) return;
  var token = script.getAttribute('data-site-token') || '';
  var endpoint = script.getAttribute('data-endpoint') || '';
  if (!/^[0-9a-f-]{36}$/i.test(token) || !/^https:\/\//i.test(endpoint)) return;

  var testMode = new URLSearchParams(window.location.search).get('cadu_test') === '1'
    || document.cookie.split(';').some(function (part) { return part.trim() === 'cadu_monitor_test=1'; });
  if (testMode) {
    document.cookie = 'cadu_monitor_test=1; Max-Age=3600; Path=/; SameSite=Lax; Secure';
  }
  var visitorId;
  try {
    visitorId = sessionStorage.getItem('cadu_monitor_session');
    if (!visitorId) {
      visitorId = window.crypto && window.crypto.randomUUID
        ? window.crypto.randomUUID().replace(/-/g, '')
        : Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem('cadu_monitor_session', visitorId);
    }
  } catch (_error) {
    visitorId = window.crypto && window.crypto.randomUUID
      ? window.crypto.randomUUID().replace(/-/g, '')
      : Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  function send(eventType, funnelId) {
    var payload = {
      visitor_id: visitorId,
      event_type: eventType,
      path: window.location.pathname.slice(0, 500) || '/',
      is_test: testMode
    };
    if (funnelId) payload.funnel_id = String(funnelId);
    var body;
    try {
      body = new Blob([JSON.stringify(payload)], { type: 'text/plain;charset=UTF-8' });
      if (navigator.sendBeacon && navigator.sendBeacon(endpoint, body)) return;
      window.fetch(endpoint, { method: 'POST', mode: 'no-cors', credentials: 'omit',
        keepalive: true, headers: { 'Content-Type': 'text/plain;charset=UTF-8' }, body: JSON.stringify(payload) })
        .catch(function () {});
    } catch (_error) {}
  }

  send('page_view');
  window.CaduPlannerMonitor = {
    conversion: function (funnelId) {
      if (funnelId) send('conversion', funnelId);
    }
  };
  var heartbeat = window.setInterval(function () {
    if (document.visibilityState === 'visible') send('heartbeat');
  }, 60000);
  window.addEventListener('pagehide', function () { window.clearInterval(heartbeat); }, { once: true });
}());
