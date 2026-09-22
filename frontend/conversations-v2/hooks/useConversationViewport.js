import {useEffect, useState} from 'react';

const PHONE_QUERY = '(max-width: 767px)';
const TABLET_QUERY = '(min-width: 768px) and (max-width: 1199px)';
const KEYBOARD_THRESHOLD = 120;

export function useConversationViewport() {
  const [layout, setLayout] = useState(() => typeof window === 'undefined' ? 'desktop' : window.matchMedia(PHONE_QUERY).matches ? 'phone' : window.matchMedia(TABLET_QUERY).matches ? 'tablet' : 'desktop');
  const [keyboardOpen, setKeyboardOpen] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const viewport = window.visualViewport;
    const phone = window.matchMedia(PHONE_QUERY);
    const tablet = window.matchMedia(TABLET_QUERY);
    let frame = 0;
    let baselineHeight = viewport?.height || window.innerHeight;

    const sync = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const height = Math.round(viewport?.height || window.innerHeight);
        const width = Math.round(viewport?.width || window.innerWidth);
        const offsetTop = Math.round(viewport?.offsetTop || 0);
        const active = document.activeElement;
        const editable = active?.matches?.('textarea, input:not([type="checkbox"]):not([type="radio"]), [contenteditable="true"]');
        if (!editable) baselineHeight = height;
        const keyboardHeight = Math.max(0, window.innerHeight - height - offsetTop, baselineHeight - height - offsetTop);
        const open = Boolean(editable && keyboardHeight > KEYBOARD_THRESHOLD);
        root.style.setProperty('--cv-visual-height', `${height}px`);
        root.style.setProperty('--cv-visual-width', `${width}px`);
        root.style.setProperty('--cv-visual-offset-top', `${offsetTop}px`);
        root.style.setProperty('--cv-keyboard-height', `${open ? keyboardHeight : 0}px`);
        root.classList.toggle('cv-keyboard-open', open);
        setKeyboardOpen(open);
        setLayout(phone.matches ? 'phone' : tablet.matches ? 'tablet' : 'desktop');
      });
    };

    sync();
    viewport?.addEventListener('resize', sync, {passive: true});
    viewport?.addEventListener('scroll', sync, {passive: true});
    window.addEventListener('resize', sync, {passive: true});
    window.addEventListener('orientationchange', sync, {passive: true});
    document.addEventListener('focusin', sync);
    document.addEventListener('focusout', sync);
    return () => {
      window.cancelAnimationFrame(frame);
      viewport?.removeEventListener('resize', sync);
      viewport?.removeEventListener('scroll', sync);
      window.removeEventListener('resize', sync);
      window.removeEventListener('orientationchange', sync);
      document.removeEventListener('focusin', sync);
      document.removeEventListener('focusout', sync);
      for (const name of ['--cv-visual-height', '--cv-visual-width', '--cv-visual-offset-top', '--cv-keyboard-height']) root.style.removeProperty(name);
      root.classList.remove('cv-keyboard-open');
    };
  }, []);

  return {layout, keyboardOpen};
}
