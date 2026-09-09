(() => {
  'use strict';

  const stage = document.querySelector('#pvStage');
  const pieces = [...document.querySelectorAll('[data-piece]')];
  const progress = [...document.querySelectorAll('[data-go-to]')];

  const formatTime = (seconds) => {
    if (!Number.isFinite(seconds)) return '0:00';
    const minutes = Math.floor(seconds / 60);
    return `${minutes}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
  };

  progress.forEach((button) => {
    button.addEventListener('click', () => {
      pieces[Number(button.dataset.goTo)]?.scrollIntoView({
        behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
        block: 'nearest',
        inline: 'start',
      });
    });
  });

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const index = Number(entry.target.dataset.piece);
        progress.forEach((button, buttonIndex) => {
          if (buttonIndex === index) button.setAttribute('aria-current', 'true');
          else button.removeAttribute('aria-current');
        });
      });
    }, { root: innerWidth > 700 ? stage : null, threshold: 0.6 });
    pieces.forEach((piece) => observer.observe(piece));
  }

  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('[data-carousel]').forEach((carousel) => {
    const slides = [...carousel.querySelectorAll('[data-carousel-slide]')];
    const dots = [...carousel.querySelectorAll('[data-carousel-go]')];
    const transitionMs = Math.max(
      0,
      Math.min(5000, Number(carousel.dataset.transitionMs) || 360),
    );
    const autoplayMs = Math.max(3200, transitionMs + 1200);
    let active = Math.max(0, slides.findIndex((slide) => slide.classList.contains('is-active')));
    let timer = null;
    const show = (nextIndex, userInitiated = false) => {
      if (slides.length < 2) return;
      active = (nextIndex + slides.length) % slides.length;
      slides.forEach((slide, index) => {
        const selected = index === active;
        slide.classList.toggle('is-active', selected);
        slide.setAttribute('aria-hidden', String(!selected));
      });
      dots.forEach((dot, index) => {
        if (index === active) dot.setAttribute('aria-current', 'true');
        else dot.removeAttribute('aria-current');
      });
      if (userInitiated) {
        carousel.classList.add('is-flipping');
        window.setTimeout(
          () => carousel.classList.remove('is-flipping'),
          transitionMs,
        );
      }
    };
    const stop = () => {
      if (timer) window.clearInterval(timer);
      timer = null;
    };
    const start = () => {
      stop();
      if (
        slides.length > 1
        && carousel.dataset.autoplay === 'true'
        && !reducedMotion
        && !document.hidden
      ) timer = window.setInterval(() => show(active + 1), autoplayMs);
    };
    carousel._carousel = { show, start, stop, get active() { return active; } };
    carousel.addEventListener('pointerenter', stop);
    carousel.addEventListener('pointerleave', start);
    carousel.addEventListener('focusin', stop);
    carousel.addEventListener('focusout', start);
    start();
  });

  document.addEventListener('visibilitychange', () => {
    document.querySelectorAll('[data-carousel]').forEach((carousel) => {
      if (document.hidden) carousel._carousel?.stop();
      else carousel._carousel?.start();
    });
  });

  document.addEventListener('click', (event) => {
    const carouselControl = event.target.closest(
      '[data-carousel-action], [data-carousel-go]',
    );
    if (carouselControl) {
      const carousel = carouselControl.closest('[data-carousel]');
      const controller = carousel?._carousel;
      if (!controller) return;
      const target = carouselControl.dataset.carouselGo;
      const next = target !== undefined
        ? Number(target)
        : controller.active + (
          carouselControl.dataset.carouselAction === 'previous' ? -1 : 1
        );
      controller.show(next, true);
      controller.start();
      return;
    }

    const flip = event.target.closest('.pv-flip');
    if (flip) {
      flip.classList.toggle('is-flipped');
      flip.setAttribute('aria-pressed', String(flip.classList.contains('is-flipped')));
      return;
    }

    const quizOption = event.target.closest('.pv-quiz button');
    if (quizOption) {
      quizOption.closest('.pv-quiz').querySelectorAll('button').forEach((button) => {
        button.classList.toggle('is-selected', button === quizOption);
      });
      return;
    }

    const hotspot = event.target.closest('.pv-hotspot');
    if (hotspot) {
      hotspot.closest('.pv-image-wrap').classList.toggle('has-note');
      return;
    }

    const control = event.target.closest('[data-video-action]');
    if (!control) return;
    const frame = control.closest('.pv-media-frame');
    const video = frame.querySelector('video');
    if (control.dataset.videoAction === 'play') {
      if (video.paused) video.play();
      else video.pause();
    } else if (control.dataset.videoAction === 'mute') {
      video.muted = !video.muted;
      control.innerHTML = `<i class="fa-solid fa-volume-${video.muted ? 'xmark' : 'high'}"></i>`;
    } else if (control.dataset.videoAction === 'fullscreen') {
      frame.requestFullscreen?.();
    }
  });

  document.querySelectorAll('.pv-video').forEach((video) => {
    const player = video.parentElement.querySelector('.pv-player');
    const play = player.querySelector('[data-video-action="play"]');
    const range = player.querySelector('input');
    const time = player.querySelector('time');
    const sync = () => {
      range.value = video.duration ? String((video.currentTime / video.duration) * 100) : '0';
      time.textContent = formatTime(video.currentTime);
      play.innerHTML = `<i class="fa-solid fa-${video.paused ? 'play' : 'pause'}"></i>`;
    };
    video.addEventListener('timeupdate', sync);
    video.addEventListener('play', sync);
    video.addEventListener('pause', sync);
    video.addEventListener('ended', sync);
    range.addEventListener('input', () => {
      if (video.duration) video.currentTime = (Number(range.value) / 100) * video.duration;
    });
  });

  document.querySelectorAll('.pv-drag').forEach((handle) => {
    let dragging = false;
    const move = (event) => {
      if (!dragging) return;
      const bounds = handle.parentElement.getBoundingClientRect();
      const position = Math.max(5, Math.min(95, ((event.clientX - bounds.left) / bounds.width) * 100));
      handle.style.left = `${position}%`;
    };
    handle.addEventListener('pointerdown', (event) => {
      dragging = true;
      handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', () => { dragging = false; });
    handle.addEventListener('pointercancel', () => { dragging = false; });
  });
})();
