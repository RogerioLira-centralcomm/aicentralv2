(function () {
  'use strict';

  var root = document.querySelector('[data-slide-deck]');
  if (!root) return;

  var slides = Array.prototype.slice.call(root.querySelectorAll('.slide'));
  var total = slides.length;
  var current = 1;
  var charts = {};

  var currentEl = document.getElementById('current');
  var totalEl = document.getElementById('total');
  var progress = document.getElementById('progressBar');
  var noteEl = document.getElementById('presenterNote');
  var indexEl = document.getElementById('indexPanel');

  if (totalEl) totalEl.textContent = String(total);

  function chartColors() {
    return {
      mint: '#5EEAD4',
      fill: 'rgba(94, 234, 212, 0.18)',
      tick: 'rgba(248, 250, 252, 0.62)',
      grid: 'rgba(248, 250, 252, 0.08)'
    };
  }

  function initCharts() {
    if (typeof window.Chart === 'undefined') return;
    var colors = chartColors();
    root.querySelectorAll('canvas[data-chart]').forEach(function (canvas) {
      var spec;
      try {
        spec = JSON.parse(canvas.getAttribute('data-chart') || '{}');
      } catch (error) {
        return;
      }
      if (charts[canvas.id]) return;
      charts[canvas.id] = new window.Chart(canvas, {
        type: spec.type || 'bar',
        data: {
          labels: spec.labels || [],
          datasets: [{
            data: spec.data || [],
            backgroundColor: colors.fill,
            borderColor: colors.mint,
            borderWidth: 2,
            borderRadius: 6,
            maxBarThickness: 72
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  return String(ctx.parsed.y) + (spec.suffix || '');
                }
              }
            }
          },
          scales: {
            x: {
              grid: { color: colors.grid },
              ticks: { color: colors.tick, font: { family: 'IBM Plex Sans' } }
            },
            y: {
              grid: { color: colors.grid },
              ticks: {
                color: colors.tick,
                callback: function (value) {
                  return value + (spec.suffix || '');
                }
              }
            }
          }
        }
      });
    });
  }

  function showSlide(n) {
    if (n < 1) n = 1;
    if (n > total) n = total;
    current = n;
    slides.forEach(function (slide, index) {
      slide.classList.toggle('active', index === n - 1);
    });
    if (currentEl) currentEl.textContent = String(n);
    if (progress) progress.style.width = ((n / total) * 100) + '%';
    var note = slides[n - 1] ? slides[n - 1].getAttribute('data-note') : '';
    if (noteEl) {
      noteEl.textContent = note || '';
      if (!note) noteEl.hidden = true;
    }
    if (window.location.hash !== '#' + n) {
      history.replaceState(null, '', '#' + n);
    }
  }

  function nextSlide() { showSlide(current + 1); }
  function prevSlide() { showSlide(current - 1); }

  function toggleNotes() {
    if (!noteEl || !noteEl.textContent) return;
    noteEl.hidden = !noteEl.hidden;
  }

  function toggleIndex() {
    if (!indexEl) return;
    indexEl.hidden = !indexEl.hidden;
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(function () {});
      return;
    }
    document.exitFullscreen().catch(function () {});
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowRight' || event.key === ' ' || event.key === 'PageDown') {
      event.preventDefault();
      nextSlide();
    }
    if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
      event.preventDefault();
      prevSlide();
    }
    if (event.key === 'Home') {
      event.preventDefault();
      showSlide(1);
    }
    if (event.key === 'End') {
      event.preventDefault();
      showSlide(total);
    }
    if (event.key === 'n' || event.key === 'N') toggleNotes();
    if (event.key === 'i' || event.key === 'I' || event.key === 'Escape') {
      if (event.key === 'Escape' && indexEl && !indexEl.hidden) {
        event.preventDefault();
        indexEl.hidden = true;
        return;
      }
      if (event.key !== 'Escape') toggleIndex();
    }
    if (event.key === 'f' || event.key === 'F') toggleFullscreen();
  });

  document.addEventListener('click', function (event) {
    if (event.target.closest('.nav-controls, .deck-tools, .index-panel, a, button')) return;
    nextSlide();
  });

  var prevBtn = document.getElementById('prevSlide');
  var nextBtn = document.getElementById('nextSlide');
  if (prevBtn) prevBtn.addEventListener('click', prevSlide);
  if (nextBtn) nextBtn.addEventListener('click', nextSlide);

  var notesBtn = document.getElementById('toggleNotes');
  var indexBtn = document.getElementById('toggleIndex');
  var fullBtn = document.getElementById('toggleFullscreen');
  if (notesBtn) notesBtn.addEventListener('click', toggleNotes);
  if (indexBtn) indexBtn.addEventListener('click', toggleIndex);
  if (fullBtn) fullBtn.addEventListener('click', toggleFullscreen);

  root.querySelectorAll('[data-jump]').forEach(function (button) {
    button.addEventListener('click', function () {
      showSlide(Number(button.getAttribute('data-jump')) || 1);
      if (indexEl) indexEl.hidden = true;
    });
  });

  initCharts();
  var fromHash = Number(String(window.location.hash || '').replace('#', ''));
  showSlide(fromHash > 0 ? fromHash : 1);
})();
