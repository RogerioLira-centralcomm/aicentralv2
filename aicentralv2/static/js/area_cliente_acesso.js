/* Área do Cliente · telas de acesso.
   1) Painel escuro: troca imagem e tagline a cada 3 s, em crossfade. Parado com prefers-reduced-motion,
      com a aba escondida e no celular (painel some). Só começa depois da tela de carregamento.
   2) Botão de olho nos campos de senha: mostra e esconde o texto. */
(function () {
  var box = document.querySelector('[data-ac-slides]');
  if (box) {
    var slides = box.querySelectorAll('.ac-split__slide');
    var dots = document.querySelectorAll('.ac-split__dots span');
    var mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
    var atual = 0, timer = null;
    var mostrar = function (i) {
      slides[atual].classList.remove('is-on');
      if (dots[atual]) dots[atual].classList.remove('is-on');
      atual = i;
      slides[atual].classList.add('is-on');
      if (dots[atual]) dots[atual].classList.add('is-on');
    };
    var podeTrocar = function () {
      return slides.length > 1 && !(mq && mq.matches) && !document.hidden && box.offsetParent !== null;
    };
    var passo = function () { if (podeTrocar()) mostrar((atual + 1) % slides.length); };
    /* Com movimento reduzido ou painel oculto (celular) o timer nem começa. */
    var iniciar = function () {
      if (timer || slides.length < 2 || (mq && mq.matches) || box.offsetParent === null) return;
      timer = setInterval(passo, 3000);
    };
    /* A tela de carregamento dura ~3 s: a primeira troca vem depois que o cartão aparece. */
    setTimeout(iniciar, document.getElementById('ac-splash') ? 3200 : 0);
  }

  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest && ev.target.closest('[data-ac-eye]');
    if (!btn) return;
    ev.preventDefault();
    var campo = btn.parentNode.querySelector('input');
    if (!campo) return;
    var ver = campo.type === 'password';
    campo.type = ver ? 'text' : 'password';
    btn.setAttribute('aria-pressed', ver ? 'true' : 'false');
    btn.setAttribute('aria-label', ver ? 'Esconder senha' : 'Mostrar senha');
    btn.classList.toggle('is-on', ver);
    campo.focus();
  });
})();
