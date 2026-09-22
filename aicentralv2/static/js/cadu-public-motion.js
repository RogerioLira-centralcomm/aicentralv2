(function () {
  'use strict';

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const blockSelector = [
    'main > section:not(.public-hero)',
    '.public-inner > header',
    '.public-inner > section',
    '.solution-page > section',
    '.solution-switcher',
    '.article-page > header',
    '.article-page > section',
    '.article-page > aside',
    '.article-more',
    '.result-card',
    '.ws-legal-intro',
    '.ws-legal-layout',
  ].join(',');
  const mediaSelector = [
    '.public-editorial-image',
    '.solution-hero > img',
    '.solution-example > img',
    '.article-page > header > img',
    '.ws-page-editorial',
    '.contact-aside > img',
  ].join(',');

  const blocks = [...document.querySelectorAll(blockSelector)];
  const media = [...document.querySelectorAll(mediaSelector)]
    .filter((element) => !blocks.some((block) => block === element));
  const elements = [...new Set([...blocks, ...media])];
  if (!elements.length) return;

  blocks.forEach((element) => element.dataset.caduReveal = 'block');
  media.forEach((element) => element.dataset.caduReveal = 'media');
  document.documentElement.classList.add('cadu-motion-ready');

  if (reducedMotion.matches || !('IntersectionObserver' in window)) {
    elements.forEach((element) => element.classList.add('is-cadu-visible'));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-cadu-visible');
      observer.unobserve(entry.target);
    });
  }, {rootMargin: '0px 0px -8% 0px', threshold: .08});

  elements.forEach((element) => observer.observe(element));
}());
