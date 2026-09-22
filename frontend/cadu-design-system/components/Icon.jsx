import React from 'react';

export function Icon({name, size = 18, className = ''}) {
  const paths = {
    home: <><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5M9.5 20v-6h5v6"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    compose: <><path d="m14.5 5.5 4 4"/><path d="M5 19h4l10.5-10.5a2.8 2.8 0 0 0-4-4L5 15v4Z"/><path d="M13.5 6.5 17.5 10.5"/></>,
    newChat: <><path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.375 2.625a1 1 0 0 1 1.414 0l2.586 2.586a1 1 0 0 1 0 1.414L12 17l-4 1 1-4Z"/></>,
    folder: <><path d="M3 7.5h7l2 2h9v9H3z"/><path d="M3 7.5V5h7l2 2"/></>,
    file: <><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></>,
    image: <><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="m4 17 5-5 3.5 3.5 2-2L20 18"/></>,
    link: <><path d="M9.5 14.5 14.5 9"/><path d="M7.5 17H6a4 4 0 0 1 0-8h3M16.5 7H18a4 4 0 1 1 0 8h-3"/></>,
    browser: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 6.5h.01M10 6.5h.01"/></>,
    drive: <><path d="m9 4-6 11 3 5h12l3-5-6-11z"/><path d="m9 4 6 11M15 4 9 15M3 15h18"/></>,
    brand: <><path d="M12 3a9 9 0 1 0 9 9"/><path d="M12 7a5 5 0 1 0 5 5"/><circle cx="12" cy="12" r="1"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></>,
    menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
    close: <path d="m6 6 12 12M18 6 6 18"/>,
    arrowUp: <path d="M12 19V5M6 11l6-6 6 6"/>,
    pulse: <path d="M3 12h4l2-6 4 12 2-6h6"/>,
    audio: <><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"/></>,
    history: <><path d="M4 12a8 8 0 1 0 2.4-5.7L4 8"/><path d="M4 4v4h4M12 8v5l3 2"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/></>,
    external: <><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13v7H4V6h7"/></>,
    download: <><path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 20h14"/></>,
    copy: <><rect x="8" y="8" width="11" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h2"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    alert: <><circle cx="12" cy="12" r="9"/><path d="M12 7.5v6M12 17h.01"/></>,
    chevron: <path d="m9 6 6 6-6 6"/>,
    undo: <><path d="M9 7 4 12l5 5"/><path d="M5 12h8a6 6 0 0 1 6 6"/></>,
    redo: <><path d="m15 7 5 5-5 5"/><path d="M19 12h-8a6 6 0 0 0-6 6"/></>,
    quote: <><path d="M7 10h4v8H5v-5a5 5 0 0 1 5-5"/><path d="M17 10h4v8h-6v-5a5 5 0 0 1 5-5"/></>,
    list: <><path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01"/></>,
    table: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M9 5v14M15 5v14"/></>,
  };
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
