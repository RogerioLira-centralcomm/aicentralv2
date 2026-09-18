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
  var carousel = document.querySelector('[data-ws-carousel]');
  var carouselTrack = carousel && carousel.querySelector('[data-ws-carousel-track]');
  var carouselSlides = carousel ? Array.from(carousel.querySelectorAll('[data-ws-carousel-slide]')) : [];
  var carouselStatus = carousel && carousel.querySelector('[data-ws-carousel-status]');
  var carouselIndex = 0;
  var frame = 0;

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function updateScrollEffects() {
    frame = 0;
    var y = window.scrollY || 0;
    body.classList.toggle('is-ws-scrolled', y > 12);

    if (flow && flowList && !reduced.matches) {
      var flowRect = flowList.getBoundingClientRect();
      flowSteps.forEach(function (step) {
        step.classList.toggle('is-active', step.getBoundingClientRect().top < window.innerHeight * 0.66);
      });
      if (mobile.matches) {
        var progress = clamp((window.innerHeight * 0.58 - flowRect.top) / Math.max(flowRect.height, 1), 0, 1);
        flowList.style.setProperty('--ws-flow-progress', (progress * 100).toFixed(1) + '%');
      }
    }

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
    carouselIndex = (nextIndex + carouselSlides.length) % carouselSlides.length;
    carouselTrack.style.transform = 'translateX(-' + (carouselIndex * 100) + '%)';
    carouselSlides.forEach(function (slide, index) {
      var active = index === carouselIndex;
      slide.classList.toggle('is-active', active);
      slide.setAttribute('aria-hidden', active ? 'false' : 'true');
    });
    if (carouselStatus) carouselStatus.textContent = (carouselIndex + 1) + ' de ' + carouselSlides.length;
  }

  if (carousel) {
    var previous = carousel.querySelector('[data-ws-carousel-prev]');
    var next = carousel.querySelector('[data-ws-carousel-next]');
    if (previous) previous.addEventListener('click', function () { moveCarousel(carouselIndex - 1); });
    if (next) next.addEventListener('click', function () { moveCarousel(carouselIndex + 1); });
    if (!reduced.matches && carouselSlides.length > 1) {
      window.setInterval(function () { moveCarousel(carouselIndex + 1); }, 6500);
    }
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
