import React from 'react';

/**
 * Ilustrações do Cadu Planner. Hoje cada espaço mostra um placeholder abstrato
 * na paleta do Planner; a arte final entra no mesmo lugar, com o mesmo nome de
 * arquivo, sem mexer nas telas.
 *
 * Cada espaço traz o briefing de criação (2D ou 3D) no próprio placeholder
 * (<desc> do SVG e data-illustration-brief) e em docs/design/planner-illustrations.md.
 * Arte final: /static/cadu_planner/illustrations/<slot>.webp (e .svg para 2D),
 * fundo transparente, 2x o tamanho exibido.
 */
const PALETTE = 'Paleta Cadu Planner: verde #067647 (principal), #079455, #17B26A, #75E0A7, #DCFAE6, fundo #F6FEF9; neutros #101828, #475467, #D0D5DD, #F2F4F7. Sem outras cores; luz suave de cima à esquerda; sem texto na arte.';

export const ILLUSTRATIONS = {
  'radar-scan': {
    size: [240, 160], style: '3D',
    brief: `3D isométrico, estilo argila fosca: uma antena de radar verde sobre uma base de papel dobrado, varrendo um mapa com três pontos de sinal que acendem (notícia, busca, rede social como ícones simples). Ondas concêntricas em #75E0A7 translúcido. Uso: tela do Radar enquanto a busca roda. ${PALETTE}`,
  },
  'radar-empty': {
    size: [240, 160], style: '2D',
    brief: `2D vetorial, traço fino 2px #067647 e preenchimentos chapados: luneta apontada para um horizonte com nuvens e um pequeno brilho. Transmite "ainda não procuramos". Uso: Radar sem oportunidades. ${PALETTE}`,
  },
  'balance': {
    size: [200, 140], style: '3D',
    brief: `3D isométrico, argila fosca: balança de pratos em que cada prato tem blocos de cores diferentes (tela de TV, celular, jornal, fone) se equilibrando; um dos blocos desce suavemente para o lugar. Uso: carregando o balanceamento de mídia. ${PALETTE}`,
  },
  'review': {
    size: [200, 140], style: '2D',
    brief: `2D vetorial: prancheta com lista de checagem em que três itens recebem um check verde, uma lupa sobre o último item. Formas arredondadas, sombra chapada #DCFAE6. Uso: revisão final do plano. ${PALETTE}`,
  },
  'plan-building': {
    size: [240, 160], style: '3D',
    brief: `3D isométrico, argila fosca: blocos de montar empilhando-se em degraus (briefing, audiência, canais, verba), o último bloco descendo com um leve brilho verde. Uso: Cadu montando ou recalculando o plano. ${PALETTE}`,
  },
  'time-saved': {
    size: [56, 56], style: '2D',
    brief: `2D vetorial minimalista, ícone-ilustração: ampulheta inclinada com a areia em #17B26A e um raio pequeno ao lado. Deve funcionar em 28px. Uso: selo discreto de tempo economizado. ${PALETTE}`,
  },
};

const shapes = {
  'radar-scan': <>
    <circle cx="120" cy="92" r="58" className="ill__ring"/><circle cx="120" cy="92" r="38" className="ill__ring"/><circle cx="120" cy="92" r="18" className="ill__ring"/>
    <path d="M120 92 L172 64 A58 58 0 0 1 178 92 Z" className="ill__sweep"/>
    <circle cx="88" cy="70" r="5" className="ill__dot"/><circle cx="150" cy="118" r="5" className="ill__dot ill__dot--late"/><circle cx="160" cy="76" r="4" className="ill__dot ill__dot--later"/>
  </>,
  'radar-empty': <>
    <path d="M40 120 Q120 80 200 120" className="ill__line"/><circle cx="168" cy="52" r="10" className="ill__soft"/>
    <rect x="76" y="78" width="70" height="18" rx="9" transform="rotate(-20 110 87)" className="ill__solid"/>
  </>,
  'balance': <>
    <path d="M100 30 V112 M60 112 H140" className="ill__line"/><path d="M40 52 H160" className="ill__line ill__tilt"/>
    <rect x="30" y="56" width="22" height="16" rx="4" className="ill__solid ill__tilt"/><rect x="148" y="56" width="22" height="22" rx="4" className="ill__soft ill__tilt"/>
  </>,
  'review': <>
    <rect x="62" y="22" width="76" height="98" rx="10" className="ill__card"/>
    {[44, 64, 84].map((y, index) => <g key={y}><rect x="76" y={y} width="12" height="12" rx="3" className={index < 2 ? 'ill__solid' : 'ill__soft'}/><rect x="94" y={y + 3} width="32" height="6" rx="3" className="ill__muted"/></g>)}
  </>,
  'plan-building': <>
    {[[70, 108, 100], [86, 88, 68], [102, 68, 36]].map(([x, y, w], index) => <rect key={y} x={x} y={y} width={w} height="18" rx="5" className={index === 2 ? 'ill__solid ill__drop' : 'ill__soft'}/>)}
  </>,
  'time-saved': <><circle cx="28" cy="28" r="20" className="ill__soft"/><path d="M20 16 H36 L28 28 L36 40 H20 L28 28 Z" className="ill__solid"/></>,
};

/** Placeholder da ilustração `slot`; `busy` anima de leve (respeita movimento reduzido). */
export function Illustration({slot, busy = false, className = ''}) {
  const spec = ILLUSTRATIONS[slot];
  if (!spec) return null;
  const [width, height] = spec.size;
  return <svg className={`ill${busy ? ' is-busy' : ''} ${className}`} viewBox={`0 0 ${width} ${height}`} width={width} height={height}
    aria-hidden="true" focusable="false" data-illustration-slot={slot} data-illustration-style={spec.style} data-illustration-brief={spec.brief}>
    <desc>{`Placeholder ${slot} (${spec.style}). Briefing: ${spec.brief}`}</desc>
    <rect width={width} height={height} rx="16" className="ill__bg"/>
    {shapes[slot]}
  </svg>;
}

/** Bloco de espera com ilustração, título e etapas opcionais. */
export function IllustratedWait({slot, title, description, children}) {
  return <div className="ill-wait" role="status" aria-live="polite">
    <Illustration slot={slot} busy/>
    <div><strong>{title}</strong>{description && <p>{description}</p>}{children}</div>
  </div>;
}
