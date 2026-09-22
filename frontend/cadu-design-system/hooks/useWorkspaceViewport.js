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
      frame = window.requestAnimationFrame(() => {
        const next = snapshot();
        document.documentElement.style.setProperty('--workspace-visual-height', `${next.visualHeight}px`);
        document.documentElement.toggleAttribute('data-workspace-keyboard-open', next.keyboardOpen);
        setState(next);
      });
    };
    update();
    media.addEventListener('change', update);
    viewport?.addEventListener('resize', update);
    window.addEventListener('orientationchange', update);
    return () => {
      window.cancelAnimationFrame(frame);
      media.removeEventListener('change', update);
      viewport?.removeEventListener('resize', update);
      window.removeEventListener('orientationchange', update);
      document.documentElement.style.removeProperty('--workspace-visual-height');
      document.documentElement.removeAttribute('data-workspace-keyboard-open');
    };
  }, []);
  return state;
}
