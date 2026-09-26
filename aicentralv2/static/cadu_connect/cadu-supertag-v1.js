/* Cadu Super Tag v1: consent-gated, first-party, batched measurement. */
(function () {
  'use strict';
  var script = document.currentScript;
  var siteId = script && script.getAttribute('data-cadu-site');
  var configUrl = script && script.getAttribute('data-cadu-config');
  if (!siteId || !configUrl || !window.crypto || !window.crypto.randomUUID) return;

  var endpoint = configUrl.replace(/\/config\.json(?:\?.*)?$/, '/collect');
  var config = null;
  var consented = false;
  var started = false;
  var buffer = [];
  var maxBuffer = 100;
  var visitorId = null;
  var sessionId = null;
  var lastPath = '';
  var lastClickAt = 0;
  var seenVisibility = Object.create(null);
  var lastScrollDepth = 0;
  var flushTimer = 0;
  var flushInFlight = false;
  var observers = [];
  var listenersInstalled = false;
  var visibilityDomReadyScheduled = false;
  var cookieName = 'cadu_stg_' + siteId.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 24);

  function readCookie(name) {
    var prefix = name + '=';
    var part = document.cookie.split('; ').find(function (value) { return value.indexOf(prefix) === 0; });
    return part ? decodeURIComponent(part.slice(prefix.length)) : '';
  }

  function writeCookie(value, days) {
    document.cookie = cookieName + '=' + encodeURIComponent(value) + '; Max-Age=' + (days * 86400) +
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

  function referrerHost() {
    try { return document.referrer ? new URL(document.referrer).hostname : ''; }
    catch (_) { return ''; }
  }

  function viewport() {
    return {width: Math.min(window.innerWidth || 0, 10000), height: Math.min(window.innerHeight || 0, 10000)};
  }

  function event(kind, data, name) {
    if (!started || !consented || buffer.length >= maxBuffer) return false;
    var size = viewport();
    buffer.push({event_id: crypto.randomUUID(), visitor_id: visitorId, session_id: sessionId,
      kind: kind, event_name: name || undefined, path: location.pathname || '/', referrer_host: referrerHost(),
      attribution: readAttribution(), data: data || {}, viewport_width: size.width,
      viewport_height: size.height, occurred_at: new Date().toISOString(), consent: 'granted'});
    if (buffer.length >= 10) flush(false);
    return true;
  }

  function flush(beacon) {
    if (!consented || !buffer.length || flushInFlight) return;
    var batch = buffer.slice(0, 25);
    var body = JSON.stringify({events: batch});
    if (beacon && navigator.sendBeacon) {
      try {
        if (navigator.sendBeacon(endpoint, new Blob([body], {type: 'text/plain;charset=UTF-8'}))) {
          buffer.splice(0, batch.length);
          return;
        }
      } catch (_) { /* Use fetch fallback below. */ }
    }
    flushInFlight = true;
    fetch(endpoint, {method: 'POST', mode: 'cors', keepalive: true,
      headers: {'Content-Type': 'text/plain;charset=UTF-8'}, body: body})
      .then(function (response) { if (response.ok) buffer.splice(0, batch.length); })
      .catch(function () {})
      .finally(function () {
        flushInFlight = false;
        if (consented && buffer.length >= 10) flush(false);
      });
  }

  function trackPage() {
    if (!started || !consented) return;
    var path = location.pathname || '/';
    if (path === lastPath) return;
    lastPath = path;
    seenVisibility = Object.create(null);
    lastScrollDepth = 0;
    event('page_view');
    observeMarkedElements();
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
          if (started && consented) observeMarkedElements();
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

  function start() {
    if (!config || !consented || started) return;
    started = true;
    visitorId = readCookie(cookieName) || crypto.randomUUID();
    writeCookie(visitorId, config.audience_days || 90);
    try {
      sessionId = sessionStorage.getItem(cookieName + '_session') || crypto.randomUUID();
      sessionStorage.setItem(cookieName + '_session', sessionId);
    } catch (_) { sessionId = crypto.randomUUID(); }
    trackPage();
    if (!listenersInstalled) {
      listenersInstalled = true;
      document.addEventListener('click', function (eventObject) {
        var target = eventObject.target && eventObject.target.closest ?
          eventObject.target.closest('a,button,[role="button"],[data-cadu-element]') : null;
        if (!target || target.closest('input,textarea,select,[contenteditable="true"],[data-cadu-ignore]')) return;
        var now = Date.now();
        if (now - lastClickAt < 250) return;
        lastClickAt = now;
        var href = target.getAttribute('href') || '';
        var kind = /(?:wa\.me|api\.whatsapp\.com)/i.test(href) ? 'whatsapp_click' : 'click';
        var size = viewport();
        event(kind, {x: Math.max(0, Math.min(1000, Math.round(eventObject.clientX / Math.max(size.width, 1) * 1000))),
          y: Math.max(0, Math.min(1000, Math.round(eventObject.clientY / Math.max(size.height, 1) * 1000))),
          element_id: elementId(target)});
      }, true);
      document.addEventListener('submit', function (eventObject) {
        var form = eventObject.target;
        if (!form || form.tagName !== 'FORM' || form.closest('[data-cadu-ignore]')) return;
        var id = form.getAttribute('data-cadu-form');
        event('form_submit', id && /^[A-Za-z0-9_-]{1,80}$/.test(id) ? {form_id: id} : {});
      }, true);
      window.addEventListener('scroll', function () {
        if (!started || !consented) return;
        var doc = document.documentElement;
        var max = Math.max(doc.scrollHeight - window.innerHeight, 1);
        var percent = Math.min(100, Math.floor((window.scrollY || 0) / max * 4 + 1) * 25);
        if (percent > lastScrollDepth) {
          lastScrollDepth = percent;
          event('scroll_depth', {depth: percent});
        }
      }, {passive: true});
      window.addEventListener('popstate', trackPage);
      window.addEventListener('hashchange', trackPage);
      if (window.navigation && window.navigation.addEventListener) {
        window.navigation.addEventListener('navigatesuccess', trackPage);
      }
      window.addEventListener('pagehide', function () { flush(true); });
    }
    flushTimer = window.setInterval(function () { flush(false); }, 5000);
    observeMarkedElements();
  }

  function setConsent(value) {
    consented = value === true || value === 'granted';
    if (consented) start();
    else {
      started = false;
      buffer = [];
      lastPath = '';
      visitorId = null;
      sessionId = null;
      try { sessionStorage.removeItem(cookieName + '_session'); } catch (_) { /* Storage may be blocked. */ }
      if (flushTimer) window.clearInterval(flushTimer);
      flushTimer = 0;
      observers.forEach(function (observer) { observer.disconnect(); });
      observers = [];
      document.cookie = cookieName + '=; Max-Age=0; Path=/; SameSite=Lax' +
        (location.protocol === 'https:' ? '; Secure' : '');
    }
  }

  window.CaduSuperTag = Object.freeze({
    setConsent: setConsent,
    trackPage: trackPage,
    trackEvent: function (name) {
      if (typeof name !== 'string' || !/^[A-Za-z][A-Za-z0-9_]{0,79}$/.test(name)) return false;
      return event('custom_event', {}, name);
    },
    trackConversion: function (name) {
      if (typeof name !== 'string' || !/^[A-Za-z][A-Za-z0-9_]{0,79}$/.test(name)) return false;
      return event('conversion', {}, name);
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
      if (consented) start();
    })
    .catch(function () {});
})();
