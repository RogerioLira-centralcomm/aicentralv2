(() => {
  const timer = document.querySelector('[data-release]');
  if (!timer) return;
  const target = new Date(timer.dataset.release).getTime();
  const fields = ['days', 'hours', 'minutes', 'seconds'];
  const render = () => {
    let remaining = Math.max(0, target - Date.now());
    const values = [Math.floor(remaining / 86400000), Math.floor(remaining / 3600000) % 24, Math.floor(remaining / 60000) % 60, Math.floor(remaining / 1000) % 60];
    fields.forEach((field, index) => { const el = timer.querySelector(`[data-${field}]`); if (el) el.textContent = String(values[index]).padStart(2, '0'); });
  };
  render(); window.setInterval(render, 1000);
  const signal = document.querySelector('[data-signal]');
  if (signal && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    signal.addEventListener('pointermove', (event) => {
      const rect = signal.getBoundingClientRect();
      signal.style.setProperty('--pointer-x', `${((event.clientX - rect.left) / rect.width - .5) * -12}px`);
      signal.style.setProperty('--pointer-y', `${((event.clientY - rect.top) / rect.height - .5) * -12}px`);
    });
    signal.addEventListener('pointerleave', () => { signal.style.setProperty('--pointer-x', '0px'); signal.style.setProperty('--pointer-y', '0px'); });
  }
})();
