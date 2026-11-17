/* Fogos de artifício na tela cheia de "PI encaminhado": explosões em sequência, com rastro, por cerca de 10 segundos.
 * Esc fecha; sem animação para quem pede menos movimento. */
(function () {
  'use strict';
  var area = document.querySelector('[data-pe-festa]');
  if (!area) return;
  document.body.appendChild(area);                     /* fora do conteúdo: cobre a barra lateral e o topo, a tela inteira */
  document.documentElement.classList.add('pe-festa-aberta');
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && area.dataset.saida) window.location.href = area.dataset.saida; });
  var canvas = area.querySelector('canvas');
  if (!canvas || (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
  var ctx = canvas.getContext('2d'), w = 0, h = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
  var cores = ['#12b76a', '#34d399', '#fbbf24', '#ffffff', '#7ddcb0', '#fb923c', '#60a5fa'];
  var particulas = [], foguetes = [], fim = Date.now() + 10000, proximo = 0;
  function ajustar() {
    w = window.innerWidth; h = window.innerHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function explodir(x, y) {
    var base = cores[(Math.random() * cores.length) | 0], n = 90 + ((Math.random() * 60) | 0), forca = 3.2 + Math.random() * 3.2;
    for (var i = 0; i < n; i++) {
      var a = (Math.PI * 2 * i) / n + Math.random() * .15, v = forca * (.55 + Math.random() * .6);
      particulas.push({ x: x, y: y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, vida: 1, dec: .008 + Math.random() * .008, r: 1.6 + Math.random() * 1.8,
                        c: Math.random() < .3 ? cores[(Math.random() * cores.length) | 0] : base });
    }
  }
  function lancar() {
    foguetes.push({ x: w * (.1 + Math.random() * .8), y: h + 10, alvo: h * (.12 + Math.random() * .42), vy: -(11 + Math.random() * 4) });
  }
  function quadro(t) {
    ctx.globalCompositeOperation = 'destination-out';           /* apaga aos poucos: deixa o rastro das partículas */
    ctx.fillStyle = 'rgba(0, 0, 0, .22)'; ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = 'lighter';
    if (Date.now() < fim && t > proximo) {
      lancar(); if (Math.random() < .55) lancar();
      proximo = t + 220 + Math.random() * 320;
    }
    foguetes = foguetes.filter(function (f) {
      f.y += f.vy; f.vy *= .988;
      ctx.fillStyle = '#fde68a'; ctx.fillRect(f.x - 1, f.y, 3, 12);
      if (f.y <= f.alvo || f.vy > -2) { explodir(f.x, f.y); return false; }
      return true;
    });
    particulas = particulas.filter(function (p) {
      p.x += p.vx; p.y += p.vy; p.vy += .055; p.vx *= .988; p.vy *= .988; p.vida -= p.dec;
      if (p.vida <= 0) return false;
      ctx.globalAlpha = Math.max(p.vida, 0); ctx.fillStyle = p.c;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (.5 + p.vida * .5), 0, 6.2832); ctx.fill();
      return true;
    });
    ctx.globalAlpha = 1;
    if (Date.now() < fim || particulas.length || foguetes.length) requestAnimationFrame(quadro);
    else { ctx.globalCompositeOperation = 'source-over'; ctx.clearRect(0, 0, w, h); }
  }
  ajustar();
  window.addEventListener('resize', ajustar);
  requestAnimationFrame(quadro);
})();
