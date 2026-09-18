(function () {
  'use strict';

  var mobile = window.matchMedia('(max-width: 600px)');
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var root = document.documentElement;
  var body = document.body;
  var hero = document.querySelector('.ws-hero--photo');
  var flow = document.querySelector('[data-ws-flow]');
  var flowList = flow && flow.querySelector('ol');
  var flowSteps = flow ? Array.from(flow.querySelectorAll('li')) : [];
  var frame = 0;

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function updateScrollEffects() {
    frame = 0;
    var y = window.scrollY || 0;
    body.classList.toggle('is-ws-scrolled', y > 12);

    if (!mobile.matches || reduced.matches) return;

    if (hero) {
      var heroRect = hero.getBoundingClientRect();
      var shift = clamp(-heroRect.top * 0.07, 0, 34);
      hero.style.setProperty('--ws-hero-shift', shift.toFixed(1) + 'px');
    }

    if (flow && flowList) {
      var rect = flowList.getBoundingClientRect();
      var progress = clamp((window.innerHeight * 0.58 - rect.top) / Math.max(rect.height, 1), 0, 1);
      flowList.style.setProperty('--ws-flow-progress', (progress * 100).toFixed(1) + '%');
      flowSteps.forEach(function (step) {
        step.classList.toggle('is-active', step.getBoundingClientRect().top < window.innerHeight * 0.66);
      });
    }
  }

  function requestUpdate() {
    if (!frame) frame = window.requestAnimationFrame(updateScrollEffects);
  }

  root.classList.add('ws-motion-ready');

  var moments = document.querySelectorAll('[data-ws-moment]');
  if (reduced.matches || !('IntersectionObserver' in window)) {
    moments.forEach(function (moment) { moment.classList.add('is-in-view'); });
  } else {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-in-view');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.18, rootMargin: '0px 0px -8% 0px' });
    moments.forEach(function (moment) { observer.observe(moment); });
  }

  window.addEventListener('scroll', requestUpdate, { passive: true });
  window.addEventListener('resize', requestUpdate, { passive: true });
  updateScrollEffects();
}());
