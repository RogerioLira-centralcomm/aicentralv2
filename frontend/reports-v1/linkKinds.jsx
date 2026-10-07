import React from 'react';

/** The three Link Tester analyses: one icon and accent color each, shared by the form, wizard, result and e-mail. */
export const LINK_KIND_META = {
  destination: {label: 'Destino e redirecionamentos', short: 'Destino', color: '#3974bd', soft: '#edf5ff'},
  media: {label: 'Medição de mídia', short: 'Mídia', color: '#0e9384', soft: '#e8f7f5'},
  agentic: {label: 'Presença para agentes', short: 'Agentes', color: '#7a5af8', soft: '#f1edff'},
};

export function KindIcon({kind, size = 36}) {
  const key = LINK_KIND_META[kind] ? kind : 'destination';
  return <img src={`/static/images/reports/illustrations/link-tester/lt-icon-${key}.png`} alt="" aria-hidden="true" width={size} height={size}
    className="shrink-0" style={{width: size, height: size}} loading="lazy"/>;
}
