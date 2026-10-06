import React from 'react';

const ART = '/static/images/planner/illustrations/';
const FALLBACK = `${ART}radar-scan.webp`;
// Uma cena por fase da busca. As três são o MESMO enquadramento (mesma cidade, mesma antena), só muda o que o mascote faz:
// por isso a troca com fade parece uma animação contínua e o anel de órbitas fica sempre sobre a antena.
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
 * Ilustração animada da espera do Radar, no mesmo espírito da análise de marcas: três órbitas finas, com um ponto
 * cada, girando em velocidades diferentes ao redor do centro, mais um feixe de radar. As cenas trocam com fade
 * conforme a etapa. Sem as imagens novas, cai na arte atual. Em "movimento reduzido" tudo fica parado.
 */
export function RadarAnimation({steps, scene, running = true, className = ''}) {
  const active = scene ?? sceneFor(steps);
  return <div className={`radar-anim${running ? ' is-running' : ''} ${className}`} aria-hidden="true" data-scene={active}>
    {SCENES.map((file, index) => <img key={file} className={`radar-anim__scene${index === active ? ' is-current' : ''}`} src={ART + file} alt=""
      width="960" height="640" decoding="async" onError={event => { if (event.currentTarget.getAttribute('src') !== FALLBACK) event.currentTarget.setAttribute('src', FALLBACK); }}/>)}
    <span className="radar-anim__sweep"/>
    <span className="radar-anim__orbit radar-anim__orbit--one"><i/></span>
    <span className="radar-anim__orbit radar-anim__orbit--two"><i/></span>
    <span className="radar-anim__orbit radar-anim__orbit--three"><i/></span>
    <span className="radar-anim__core"/>
  </div>;
}
