(function () {
  'use strict';
  const nav = document.querySelector('[data-public-nav]');
  const menu = document.querySelector('[data-public-menu]');
  const menuButton = document.querySelector('[data-public-menu-button]');
  const carousel = document.querySelector('[data-carousel]');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function updateNav() { nav?.classList.toggle('is-fixed', nav.classList.contains('public-nav--inner') || window.scrollY > 28); }
  window.addEventListener('scroll', updateNav, {passive: true});
  updateNav();

  menuButton?.addEventListener('click', () => {
    const open = !menu.classList.contains('is-open');
    menu.classList.toggle('is-open', open);
    menuButton.setAttribute('aria-expanded', String(open));
  });
  menu?.addEventListener('click', (event) => {
    if (!event.target.closest('a')) return;
    menu.classList.remove('is-open');
    menuButton?.setAttribute('aria-expanded', 'false');
  });

  if (!carousel) return;
  const track = carousel.querySelector('[data-carousel-track]');
  const slides = [...carousel.querySelectorAll('[data-carousel-slide]')];
  const status = carousel.querySelector('[data-carousel-status]');
  let index = 0;

  function visibleCount() { return window.innerWidth <= 600 ? 1 : window.innerWidth <= 860 ? 2 : 3; }
  function render() {
    const max = Math.max(0, slides.length - visibleCount());
    index = Math.max(0, Math.min(index, max));
    const gap = parseFloat(getComputedStyle(track).gap) || 0;
    const width = slides[0]?.getBoundingClientRect().width || 0;
    track.style.transform = `translate3d(${-index * (width + gap)}px,0,0)`;
    status.textContent = `${index + 1} / ${slides.length}`;
  }
  carousel.querySelector('[data-carousel-prev]')?.addEventListener('click', () => { index -= 1; render(); });
  carousel.querySelector('[data-carousel-next]')?.addEventListener('click', () => { index += 1; render(); });
  window.addEventListener('resize', render, {passive: true});
  if (reducedMotion.matches) track.style.transition = 'none';
  render();
}());
