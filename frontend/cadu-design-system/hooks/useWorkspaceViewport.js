import {useEffect, useState} from 'react';

const query = '(max-width: 760px)';

function snapshot() {
  const viewport = window.visualViewport;
  return {
    isMobile: window.matchMedia(query).matches,
    visualHeight: Math.round(viewport?.height || window.innerHeight),
    keyboardOpen: Boolean(viewport && window.innerHeight - viewport.height > 120),
  };
}

export function useWorkspaceViewport() {
  const [state, setState] = useState(snapshot);
  useEffect(() => {
    const media = window.matchMedia(query);
    const viewport = window.visualViewport;
    let frame = 0;
    const update = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => setState(snapshot()));
    };
    media.addEventListener('change', update);
    viewport?.addEventListener('resize', update);
    window.addEventListener('orientationchange', update);
    return () => {
      window.cancelAnimationFrame(frame);
      media.removeEventListener('change', update);
      viewport?.removeEventListener('resize', update);
      window.removeEventListener('orientationchange', update);
    };
  }, []);
  return state;
}
