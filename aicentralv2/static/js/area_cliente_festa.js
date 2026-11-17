/* Fogos de artifício atrás da tela de "PI enviado": explosões de partículas por ~7 segundos, uma vez.
 * Sem animação para quem pede menos movimento. */
(function () {
  'use strict';
  var area = document.querySelector('[data-pe-festa]');
  var canvas = area && area.querySelector('canvas');
  if (!canvas || (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
  var ctx = canvas.getContext('2d'), w = 0, h = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
  var cores = ['#12b76a', '#0e9f6e', '#f5b301', '#ffffff', '#7ddcb0', '#ff8a4c'];
  var particulas = [], foguetes = [], fim = Date.now() + 7000, ultimo = 0, proximo = 0;
  function ajustar() {
    var r = area.getBoundingClientRect();
    w = r.width; h = r.height;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function explodir(x, y) {
    var cor = cores[(Math.random() * cores.length) | 0], n = 46 + ((Math.random() * 26) | 0);
    for (var i = 0; i < n; i++) {
      var a = (Math.PI * 2 * i) / n + Math.random() * .2, v = 1.6 + Math.random() * 3.2;
      particulas.push({ x: x, y: y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, vida: 1, c: Math.random() < .25 ? cores[(Math.random() * cores.length) | 0] : cor });
    }
  }
  function lancar() {
    foguetes.push({ x: w * (.15 + Math.random() * .7), y: h, alvo: h * (.15 + Math.random() * .35), vy: -(7 + Math.random() * 3) });
  }
  function quadro(t) {
    ctx.clearRect(0, 0, w, h);
    if (Date.now() < fim && t > proximo) { lancar(); proximo = t + 380 + Math.random() * 520; }
    foguetes = foguetes.filter(function (f) {
      f.y += f.vy; f.vy *= .985;
      ctx.fillStyle = '#f5b301'; ctx.fillRect(f.x, f.y, 2, 8);
      if (f.y <= f.alvo || f.vy > -1.2) { explodir(f.x, f.y); return false; }
      return true;
    });
    particulas = particulas.filter(function (p) {
      p.x += p.vx; p.y += p.vy; p.vy += .045; p.vx *= .985; p.vida -= .012;
      if (p.vida <= 0) return false;
      ctx.globalAlpha = Math.max(p.vida, 0); ctx.fillStyle = p.c;
      ctx.beginPath(); ctx.arc(p.x, p.y, 2.1, 0, 6.2832); ctx.fill();
      return true;
    });
    ctx.globalAlpha = 1;
    if (Date.now() < fim || particulas.length || foguetes.length) requestAnimationFrame(quadro);
    else ctx.clearRect(0, 0, w, h);
  }
  ajustar();
  window.addEventListener('resize', ajustar);
  requestAnimationFrame(quadro);
})();
