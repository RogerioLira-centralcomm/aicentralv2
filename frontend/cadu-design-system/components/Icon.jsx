import React from 'react';

export function Icon({name, size = 18, className = ''}) {
  const paths = {
    home: <><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5M9.5 20v-6h5v6"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    compose: <><path d="m14.5 5.5 4 4"/><path d="M5 19h4l10.5-10.5a2.8 2.8 0 0 0-4-4L5 15v4Z"/><path d="M13.5 6.5 17.5 10.5"/></>,
    newChat: <><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></>,
    folder: <><path d="M3 7.5h7l2 2h9v9H3z"/><path d="M3 7.5V5h7l2 2"/></>,
    file: <><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></>,
    brand: <><path d="M12 3a9 9 0 1 0 9 9"/><path d="M12 7a5 5 0 1 0 5 5"/><circle cx="12" cy="12" r="1"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></>,
    menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
    close: <path d="m6 6 12 12M18 6 6 18"/>,
    arrowUp: <path d="M12 19V5M6 11l6-6 6 6"/>,
    pulse: <path d="M3 12h4l2-6 4 12 2-6h6"/>,
    history: <><path d="M4 12a8 8 0 1 0 2.4-5.7L4 8"/><path d="M4 4v4h4M12 8v5l3 2"/></>,
    external: <><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13v7H4V6h7"/></>,
    download: <><path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 20h14"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    chevron: <path d="m9 6 6 6-6 6"/>,
  };
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
