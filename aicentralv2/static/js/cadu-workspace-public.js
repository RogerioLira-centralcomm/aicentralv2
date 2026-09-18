(function () {
  'use strict';

  var mobile = window.matchMedia('(max-width: 600px)');
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var root = document.documentElement;
  var body = document.body;
  var hero = document.querySelector('.ws-hero--photo');
  var carousel = document.querySelector('[data-ws-carousel]');
  var carouselTrack = carousel && carousel.querySelector('[data-ws-carousel-track]');
  var carouselSlides = carousel ? Array.from(carousel.querySelectorAll('[data-ws-carousel-slide]')) : [];
  var carouselIndex = 0;
  var carouselTimer = 0;

  function carouselVisibleCount() { return window.matchMedia('(max-width: 720px)').matches ? 1 : 3; }
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

  }

  function requestUpdate() {
    if (!frame) frame = window.requestAnimationFrame(updateScrollEffects);
  }

  function moveCarousel(nextIndex) {
    if (!carouselTrack || !carouselSlides.length) return;
    var visible = carouselVisibleCount();
    var maxIndex = Math.max(carouselSlides.length - visible, 0);
    carouselIndex = nextIndex > maxIndex ? 0 : (nextIndex < 0 ? maxIndex : nextIndex);
    var slideWidth = carouselSlides[0].getBoundingClientRect().width;
    var styles = window.getComputedStyle(carouselTrack);
    var gap = parseFloat(styles.columnGap || styles.gap || '0') || 0;
    carouselTrack.style.transform = 'translateX(-' + (carouselIndex * (slideWidth + gap)).toFixed(1) + 'px)';
    carouselSlides.forEach(function (slide, index) {
      var active = index >= carouselIndex && index < carouselIndex + visible;
      slide.classList.toggle('is-active', active);
      slide.setAttribute('aria-hidden', active ? 'false' : 'true');
    });
  }

  if (carousel) {
    moveCarousel(0);
    if (!reduced.matches && carouselSlides.length > 1) {
      function startCarousel() {
        if (!carouselTimer && !document.hidden) carouselTimer = window.setInterval(function () { moveCarousel(carouselIndex + 1); }, 3000);
      }
      function stopCarousel() {
        if (carouselTimer) { window.clearInterval(carouselTimer); carouselTimer = 0; }
      }
      document.addEventListener('visibilitychange', function () {
        if (document.hidden) stopCarousel(); else startCarousel();
      });
      carousel.addEventListener('mouseenter', stopCarousel);
      carousel.addEventListener('mouseleave', startCarousel);
      carousel.addEventListener('focusin', stopCarousel);
      carousel.addEventListener('focusout', startCarousel);
      startCarousel();
    }
    window.addEventListener('resize', function () { moveCarousel(carouselIndex); });
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
