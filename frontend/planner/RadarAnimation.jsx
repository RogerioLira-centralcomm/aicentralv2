import React from 'react';

const ART = '/static/images/planner/illustrations/';
// Enquanto as três cenas novas não existem, o próprio mascote do Planner ocupa o quadrado.
const FALLBACK = `${ART}mascote-planner.webp`;
// Um quadrado padronizado, com o mascote no meio. Uma cena por fase da busca: só mudam a pose e o objeto na mão
// (binóculo, lupa com check, cartões com lâmpada). Mesma posição e mesmo tamanho nas três, para o fade parecer movimento.
export const SCENES = ['radar-anim-1-buscando.webp', 'radar-anim-2-conferindo.webp', 'radar-anim-3-angulos.webp'];
const SCENE_OF_STEP = {buzz: 0, check: 1, angles: 2, save: 2};

/** Cena que combina com o que o Radar está fazendo agora (ou com a última etapa concluída). */
export function sceneFor(steps = []) {
  const current = steps.find(step => step.status === 'running');
  if (current) return SCENE_OF_STEP[current.key] ?? 0;
  const done = steps.filter(step => step.status === 'done');
  return done.length ? SCENE_OF_STEP[done[done.length - 1].key] ?? 0 : 0;
}

/**
 * Espera do Radar no mesmo espírito da análise de marcas: o mascote no centro de um disco claro e três órbitas finas,
 * com um ponto cada, girando em velocidades diferentes. As cenas trocam com fade conforme a etapa. Sem as imagens novas,
 * cai no mascote do Planner. Em "movimento reduzido" tudo fica parado.
 */
export function RadarAnimation({steps, scene, running = true, className = ''}) {
  const active = scene ?? sceneFor(steps);
  return <div className={`radar-anim${running ? ' is-running' : ''} ${className}`} aria-hidden="true" data-scene={active}>
    <span className="radar-anim__disc"/>
    {SCENES.map((file, index) => <img key={file} className={`radar-anim__scene${index === active ? ' is-current' : ''}`} src={ART + file} alt=""
      width="512" height="512" decoding="async" onError={event => { if (event.currentTarget.getAttribute('src') !== FALLBACK) event.currentTarget.setAttribute('src', FALLBACK); }}/>)}
    <i className="radar-anim__orbit radar-anim__orbit--one"/><i className="radar-anim__orbit radar-anim__orbit--two"/><i className="radar-anim__orbit radar-anim__orbit--three"/>
  </div>;
}
