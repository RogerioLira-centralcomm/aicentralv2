(function () {
  'use strict';

  const configNode = document.getElementById('cadu-analytics-config');
  if (!configNode) return;
  let config = {};
  try { config = JSON.parse(configNode.textContent || '{}'); } catch (_) { return; }

  const consentKey = 'cadu_measurement_consent_v1';
  const safeText = value => String(value || '').trim().slice(0, 120);
  const safeDestination = value => {
    try {
      const url = new URL(String(value || ''), window.location.origin);
      return `${url.hostname}${url.pathname}`.slice(0, 120);
    } catch (_) { return ''; }
  };
  const pageContext = {
    page_type: safeText(config.pageType),
    content_group: safeText(config.contentGroup),
    product_interest: safeText(config.productInterest),
    content_topic: safeText(config.contentTopic),
    journey_stage: safeText(config.journeyStage),
  };

  function track(event, parameters) {
    if (!event) return;
    const payload = {...pageContext, ...(parameters || {})};
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({event, ...payload});
    window.dispatchEvent(new CustomEvent('cadu:analytics', {detail: {event, ...payload}}));
  }

  function loadScript(src, id) {
    if (!src || document.getElementById(id)) return;
    const script = document.createElement('script');
    script.id = id;
    script.async = true;
    script.src = src;
    document.head.appendChild(script);
  }

  function enableMeasurement() {
    window.gtag('consent', 'update', {
      analytics_storage: 'granted', ad_storage: 'granted',
      ad_user_data: 'granted', ad_personalization: 'granted',
    });
    if (config.gtmId) {
      window.dataLayer.push({'gtm.start': Date.now(), event: 'gtm.js'});
      loadScript(`https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(config.gtmId)}`, 'cadu-gtm');
    } else if (config.ga4Id) {
      loadScript(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(config.ga4Id)}`, 'cadu-ga4');
      window.gtag('js', new Date());
      window.gtag('config', config.ga4Id, {send_page_view: true});
    }
  }

  const consent = window.localStorage.getItem(consentKey);
  const banner = document.querySelector('[data-cadu-consent]');
  if (consent === 'granted') enableMeasurement();
  else if (consent !== 'denied' && banner) banner.hidden = false;

  banner?.querySelector('[data-consent-accept]')?.addEventListener('click', () => {
    window.localStorage.setItem(consentKey, 'granted');
    banner.hidden = true;
    enableMeasurement();
    track('consent_update', {measurement_consent: 'granted'});
  });
  banner?.querySelector('[data-consent-essential]')?.addEventListener('click', () => {
    window.localStorage.setItem(consentKey, 'denied');
    banner.hidden = true;
  });

  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link) return;
    const section = link.closest('[id], main, header, footer');
    track('cta_click', {
      cta_name: safeText(link.dataset.trackName || link.textContent),
      cta_location: safeText(link.dataset.trackLocation || section?.id || section?.tagName?.toLowerCase()),
      destination: safeDestination(link.dataset.trackDestination || link.getAttribute('href')),
    });
    const plan = link.closest('.ws-plans article');
    if (plan) {
      track('select_plan', {
        plan_name: safeText(plan.querySelector('h2')?.textContent),
        value: safeText(plan.querySelector('strong')?.textContent).replace(/[^0-9]/g, ''),
        currency: 'BRL',
      });
    }
  });

  const startedForms = new WeakSet();
  document.addEventListener('focusin', event => {
    const form = event.target.closest('form');
    if (!form || startedForms.has(form)) return;
    startedForms.add(form);
    track('form_start', {form_name: safeText(form.dataset.formName || window.location.pathname)});
  });
  document.addEventListener('submit', event => {
    const form = event.target.closest('form');
    if (!form) return;
    track('form_submit', {form_name: safeText(form.dataset.formName || window.location.pathname)});
  });

  const conversionNode = document.getElementById('cadu-conversion-event');
  if (conversionNode) {
    try {
      const conversion = JSON.parse(conversionNode.textContent || '{}');
      const eventId = safeText(conversion.event_id);
      const seenKey = `cadu_conversion_${eventId}`;
      if (conversion.event && eventId && !window.sessionStorage.getItem(seenKey)) {
        window.sessionStorage.setItem(seenKey, '1');
        track(safeText(conversion.event), {
          event_id: eventId,
          method: safeText(conversion.method),
          lead_source: safeText(conversion.lead_source),
          team_profile: safeText(conversion.team_profile),
          usage_range: safeText(conversion.usage_range),
          status_code: safeText(conversion.status_code),
          error_class: safeText(conversion.error_class),
        });
      }
    } catch (_) {}
  }

  window.CaduAnalytics = {track};
}());
