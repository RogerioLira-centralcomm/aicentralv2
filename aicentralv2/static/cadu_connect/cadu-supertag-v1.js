/* Cadu Super Tag v1: consent-gated, first-party, batched measurement. */
(function () {
  'use strict';
  var script = document.currentScript;
  var siteId = script && script.getAttribute('data-cadu-site');
  var configUrl = script && script.getAttribute('data-cadu-config');
  if (!siteId || !configUrl || !window.crypto || !window.crypto.randomUUID) return;

  var parsedConfigUrl;
  try { parsedConfigUrl = new URL(configUrl, location.href); } catch (_) { return; }
  if (!/^https?:$/.test(parsedConfigUrl.protocol) || !/\/connect\/public\/supertag\/v1\/[A-Za-z0-9_-]+\/config\.json$/.test(parsedConfigUrl.pathname)) return;
  var endpointUrl = new URL(parsedConfigUrl.href);
  endpointUrl.pathname = endpointUrl.pathname.replace(/\/config\.json$/, '/collect');
  endpointUrl.search = '';
  endpointUrl.hash = '';
  var endpoint = endpointUrl.href;
  var consentUrl = endpoint.replace(/\/collect$/, '/consent');
  var identifyUrl = endpoint.replace(/\/collect$/, '/identify');
  var consentMode = script.getAttribute('data-cadu-consent') || 'auto';
  var config = null;
  var consented = false;
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
  var consentUi = null;
  var consentState = 'unknown';
  var activeController = null;
  var hasConsentManager = false;
  var consentResolved = false;
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

  function existingConsent() {
    try {
      if (window.__tcfapi) {
        hasConsentManager = true;
        window.__tcfapi('addEventListener', 2, function (tcData, success) {
          if (success && tcData && (tcData.eventStatus === 'tcloaded' || tcData.eventStatus === 'useractioncomplete')) {
            setConsent(!!(tcData.purpose && tcData.purpose.consents && tcData.purpose.consents[1]));
            consentResolved = true;
          }
        });
        return true;
      }
      if (window.OnetrustActiveGroups != null) {
        hasConsentManager = true;
        consentResolved = true;
        setConsent(String(window.OnetrustActiveGroups).split(',').indexOf('C0002') !== -1);
        return true;
      }
      if (window.Cookiebot && window.Cookiebot.consent) {
        hasConsentManager = true;
        consentResolved = true;
        setConsent(!!window.Cookiebot.consent.statistics);
        return true;
      }
      var consent = document.cookie.split('; ').find(function (part) { return part.indexOf('cadu_consent=') === 0; });
      if (consent) { setConsent(consent.slice('cadu_consent='.length) === 'granted'); return true; }
      var stored = localStorage.getItem('cadu_analytics_consent');
      if (stored === 'granted' || stored === 'denied') { setConsent(stored === 'granted'); return true; }
    } catch (_) { /* CMP APIs and storage may be unavailable. */ }
    return false;
  }

  function showConsentPromptDeferred(fromCmp) {
    window.setTimeout(function () {
      if (!hasConsentManager && !consentResolved && consentMode !== 'manual' && consentState === 'unknown') showConsentPrompt();
    }, 3000);
  }

  function showConsentPrompt() {
    if (consentUi || consentState !== 'unknown' || !document.body) return;
    consentUi = document.createElement('aside');
    consentUi.setAttribute('role', 'dialog');
    consentUi.setAttribute('aria-label', 'Preferências de privacidade');
    consentUi.style.cssText = 'position:fixed;z-index:2147483647;bottom:16px;left:16px;max-width:380px;padding:16px;background:#fff;color:#18212f;border:1px solid #d7dce2;border-radius:12px;box-shadow:0 8px 32px #0003;font:14px/1.45 system-ui,sans-serif';
    var message = document.createElement('p');
    message.textContent = 'Podemos usar dados de navegação anônimos para melhorar este site?';
    message.style.margin = '0 0 12px'; consentUi.appendChild(message);
    [['Aceitar analytics', true], ['Recusar', false]].forEach(function (choice) {
      var button = document.createElement('button');
      button.type = 'button'; button.textContent = choice[0];
      button.style.cssText = 'margin-right:8px;padding:8px 12px;border:1px solid #667085;border-radius:7px;background:#fff;color:#18212f;cursor:pointer';
      button.addEventListener('click', function () {
        fetch(consentUrl, {method:'POST',mode:'cors',credentials:'omit',headers:{'Content-Type':'application/json'},body:JSON.stringify({analytics:choice[1]})}).catch(function () {});
        try { localStorage.setItem('cadu_analytics_consent', choice[1] ? 'granted' : 'denied'); } catch (_) { /* Optional persistence. */ }
        consentUi.remove(); consentUi = null; setConsent(choice[1]);
      });
      consentUi.appendChild(button);
    });
    document.body.appendChild(consentUi);
  }

  function viewport() {
    return {width: Math.min(window.innerWidth || 0, 10000), height: Math.min(window.innerHeight || 0, 10000)};
  }

  function documentBox() {
    var root = document.documentElement, body = document.body;
    if (!root || !body) return null;
    var width = Math.max(root.scrollWidth || 0, body.scrollWidth || 0, window.innerWidth || 0);
    var height = Math.max(root.scrollHeight || 0, body.scrollHeight || 0, window.innerHeight || 0);
    if (width < 1 || height < 1 || height > 100000) return null;
    return {width: width, height: height, scrollX: window.pageXOffset || 0, scrollY: window.pageYOffset || 0};
  }

  function event(kind, data, name, pathOverride) {
    if (!started || !consented || buffer.length >= maxBuffer) return false;
    if (kind !== 'heartbeat' && kind !== 'page_leave') {
      if (freshSessionIfIdle() && kind !== 'page_view') trackPage();
      lastMeaningfulAt = Date.now();
      try { sessionStorage.setItem(cookieName + '_active_at', String(lastMeaningfulAt)); } catch (_) { /* Optional persistence. */ }
    }
    var size = viewport();
    buffer.push({event_id: crypto.randomUUID(), visitor_id: visitorId, session_id: sessionId,
      kind: kind, event_name: name || undefined, path: pathOverride || location.pathname || '/', referrer_host: referrerHost(),
      attribution: attributionForSession(), data: data || {}, viewport_width: size.width,
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
    activeController = typeof AbortController !== 'undefined' ? new AbortController() : null;
    fetch(endpoint, {method: 'POST', mode: 'cors', keepalive: true,
      signal: activeController ? activeController.signal : undefined,
      headers: {'Content-Type': 'text/plain;charset=UTF-8'}, body: body})
      .then(function (response) { if (response.ok) buffer.splice(0, batch.length); })
      .catch(function () {})
      .finally(function () {
        activeController = null;
        flushInFlight = false;
        if (consented && buffer.length >= 10) flush(false);
      });
  }

  function trackPage() {
    if (!started || !consented) return;
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
    event('page_view', {}, undefined, activePath);
    observeMarkedElements();
  }

  function pauseActivePage() {
    if (!pageActiveSince) return;
    pageActiveDuration += Math.max(0, Date.now() - pageActiveSince);
    pageActiveSince = 0;
  }

  function resumeActivePage() {
    if (started && consented && lastPath && !pageActiveSince && document.visibilityState === 'visible') {
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
      lastMeaningfulAt = Number(sessionStorage.getItem(cookieName + '_active_at')) || Date.now();
      sessionAttribution = JSON.parse(sessionStorage.getItem(cookieName + '_attribution') || 'null');
      sessionStorage.setItem(cookieName + '_session', sessionId);
      campaignScope = sessionStorage.getItem(cookieName + '_campaign') || '';
    } catch (_) { sessionId = crypto.randomUUID(); lastMeaningfulAt = Date.now(); sessionAttribution = null; }
    currentCampaignScope();
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
        var doc = documentBox();
        var data = {x: Math.max(0, Math.min(1000, Math.round(eventObject.clientX / Math.max(size.width, 1) * 1000))),
          y: Math.max(0, Math.min(1000, Math.round(eventObject.clientY / Math.max(size.height, 1) * 1000))),
          element_id: elementId(target)};
        if (doc) {
          // Position inside the whole page, so clicks made at different scroll offsets land in the same place.
          data.dx = Math.max(0, Math.min(1000, Math.round((eventObject.clientX + doc.scrollX) / doc.width * 1000)));
          data.dy = Math.max(0, Math.min(1000, Math.round((eventObject.clientY + doc.scrollY) / doc.height * 1000)));
          data.dh = doc.height;
        }
        event(kind, data);
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
      window.addEventListener('pagehide', function () { leaveCurrentPage(); flush(true); });
      document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'hidden') pauseActivePage();
        else resumeActivePage();
      });
    }
    flushTimer = window.setInterval(function () { flush(false); }, 5000);
    heartbeatTimer = window.setInterval(function () {
      if (started && consented && document.visibilityState === 'visible') event('heartbeat');
    }, 30000);
    observeMarkedElements();
  }

  function setConsent(value) {
    consented = value === true || value === 'granted';
    consentResolved = true;
    consentState = consented ? 'granted' : 'denied';
    if (consentUi) { consentUi.remove(); consentUi = null; }
    if (consented) start();
    else {
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
  }

  window.CaduSuperTag = Object.freeze({
    setConsent: setConsent,
    trackPage: trackPage,
    getVisitorId: function () { return consented ? visitorId : null; },
    getSessionId: function () { return consented ? sessionId : null; },
    identify: function (identity) {
      if (!started || !consented || !identity || typeof identity !== 'object') return Promise.resolve(false);
      if (freshSessionIfIdle()) trackPage();
      var name = typeof identity.name === 'string' ? identity.name.trim().slice(0, 120) : '';
      var email = typeof identity.email === 'string' ? identity.email.trim().slice(0, 254) : '';
      var phone = typeof identity.phone === 'string' ? identity.phone.trim().slice(0, 40) : '';
      if (!email && !phone) return Promise.resolve(false);
      return fetch(identifyUrl, {method:'POST', mode:'cors', credentials:'omit',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({visitor_id:visitorId,session_id:sessionId,name:name,email:email,phone:phone,campaign:currentCampaignScope(),consent:'granted'})
      }).then(function (response) { return response.ok; }).catch(function () { return false; });
    },
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
  existingConsent();
  window.addEventListener('cadu:consent', function () { hasConsentManager = true; });
  window.addEventListener('CookiebotOnAccept', function () { hasConsentManager = true; consentResolved = true; setConsent(!!(window.Cookiebot && window.Cookiebot.consent && window.Cookiebot.consent.statistics)); });
  window.addEventListener('CookiebotOnDecline', function () { hasConsentManager = true; consentResolved = true; setConsent(false); });
  window.addEventListener('OneTrustGroupsUpdated', function () { hasConsentManager = true; consentResolved = true; setConsent(String(window.OnetrustActiveGroups || '').split(',').indexOf('C0002') !== -1); });
  fetch(configUrl, {mode: 'cors', credentials: 'omit', cache: 'force-cache'})
    .then(function (response) { if (!response.ok) throw new Error('config'); return response.json(); })
    .then(function (value) {
      if (value.site_id !== siteId) return;
      config = value;
      consentMode = value.consent_mode || consentMode;
      if (consented) start();
      else if (consentMode !== 'manual' && !hasConsentManager && !consentResolved) showConsentPromptDeferred(false);
    })
    .catch(function () {});
})();
