import {useEffect} from 'react';

const KEYBOARD_THRESHOLD = 120;

export function useConversationViewport() {
  useEffect(() => {
    const viewport = window.visualViewport;
    const root = document.documentElement;
    let frame = 0;

    const syncViewport = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const height = Math.round(viewport?.height || window.innerHeight);
        const keyboardOpen = Boolean(viewport && window.innerHeight - viewport.height > KEYBOARD_THRESHOLD);
        root.style.setProperty('--cv-visual-height', `${height}px`);
        root.classList.toggle('cv-keyboard-open', keyboardOpen);
      });
    };

    syncViewport();
    viewport?.addEventListener('resize', syncViewport, {passive: true});
    viewport?.addEventListener('scroll', syncViewport, {passive: true});
    window.addEventListener('orientationchange', syncViewport, {passive: true});

    return () => {
      window.cancelAnimationFrame(frame);
      viewport?.removeEventListener('resize', syncViewport);
      viewport?.removeEventListener('scroll', syncViewport);
      window.removeEventListener('orientationchange', syncViewport);
      root.style.removeProperty('--cv-visual-height');
      root.classList.remove('cv-keyboard-open');
    };
  }, []);
}
