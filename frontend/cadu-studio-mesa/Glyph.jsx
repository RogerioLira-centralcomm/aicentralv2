import React from 'react';

// Ícones de traço do set gerado com image 2.5 (static/images/radar-tipos), pintados com a cor do texto.
export function Glyph({name, size = 28}) {
  const url = `url(/static/images/radar-tipos/${name}.png)`;
  return <span className="mq-glyph" aria-hidden="true" style={{width: size, height: size, WebkitMaskImage: url, maskImage: url}}/>;
}

// Ícones de interface (SVG simples, 20px).
const PATHS = {
  plus: 'M12 5v14M5 12h14', minus: 'M5 12h14', fit: 'M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5', target: 'M12 3v3M12 18v3M3 12h3M18 12h3M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  download: 'M12 4v11m0 0-4-4m4 4 4-4M5 20h14', send: 'M5 12h13M13 6l6 6-6 6', close: 'M6 6l12 12M18 6 6 18', star: 'M12 4l2.4 5 5.6.6-4.2 3.8 1.2 5.6L12 16.3 7 19l1.2-5.6L4 9.6 9.6 9z',
  trash: 'M5 7h14M10 7V5h4v2M7 7l1 13h8l1-13', layers: 'M12 4 3 9l9 5 9-5zM3 14l9 5 9-5', grid: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z', back: 'M15 6l-6 6 6 6',
};
export function Ico({name, size = 18}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={PATHS[name]}/></svg>;
}
