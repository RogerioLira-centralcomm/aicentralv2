import {useEffect, useState} from 'react';

const PHONE_QUERY = '(max-width: 767px)';
const TABLET_QUERY = '(min-width: 768px) and (max-width: 1199px)';
const KEYBOARD_THRESHOLD = 120;

function readViewport(baselineHeight = window.innerHeight) {
  const viewport = window.visualViewport;
  const visualHeight = Math.round(viewport?.height || window.innerHeight);
  const visualWidth = Math.round(viewport?.width || window.innerWidth);
  const offsetTop = Math.round(viewport?.offsetTop || 0);
  const editable = document.activeElement?.matches?.('textarea, input:not([type="checkbox"]):not([type="radio"]), [contenteditable="true"]');
  const keyboardInset = Math.max(0, window.innerHeight - visualHeight - offsetTop, baselineHeight - visualHeight - offsetTop);
  return {
    layout: window.matchMedia(PHONE_QUERY).matches ? 'phone' : window.matchMedia(TABLET_QUERY).matches ? 'tablet' : 'desktop',
    isMobile: window.matchMedia(PHONE_QUERY).matches,
    visualHeight,
    visualWidth,
    offsetTop,
    keyboardInset,
    keyboardOpen: Boolean(editable && keyboardInset > KEYBOARD_THRESHOLD),
    orientation: visualWidth > visualHeight ? 'landscape' : 'portrait',
  };
}

export function useUnifiedViewport() {
  const [state, setState] = useState(() => readViewport());
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
        const active = document.activeElement;
        const editable = active?.matches?.('textarea, input:not([type="checkbox"]):not([type="radio"]), [contenteditable="true"]');
        const height = viewport?.height || window.innerHeight;
        if (!editable) baselineHeight = height;
        const next = readViewport(baselineHeight);
        root.style.setProperty('--cv-visual-height', `${next.visualHeight}px`);
        root.style.setProperty('--cv-visual-width', `${next.visualWidth}px`);
        root.style.setProperty('--cv-visual-offset-top', `${next.offsetTop}px`);
        root.style.setProperty('--cv-keyboard-height', `${next.keyboardOpen ? next.keyboardInset : 0}px`);
        root.style.setProperty('--workspace-visual-height', `${next.visualHeight}px`);
        root.classList.toggle('cv-keyboard-open', next.keyboardOpen);
        root.toggleAttribute('data-workspace-keyboard-open', next.keyboardOpen);
        setState(next);
      });
    };
    sync();
    for (const media of [phone, tablet]) media.addEventListener?.('change', sync);
    viewport?.addEventListener('resize', sync, {passive: true});
    viewport?.addEventListener('scroll', sync, {passive: true});
    window.addEventListener('resize', sync, {passive: true});
    window.addEventListener('orientationchange', sync, {passive: true});
    document.addEventListener('focusin', sync);
    document.addEventListener('focusout', sync);
    return () => {
      window.cancelAnimationFrame(frame);
      for (const media of [phone, tablet]) media.removeEventListener?.('change', sync);
      viewport?.removeEventListener('resize', sync);
      viewport?.removeEventListener('scroll', sync);
      window.removeEventListener('resize', sync);
      window.removeEventListener('orientationchange', sync);
      document.removeEventListener('focusin', sync);
      document.removeEventListener('focusout', sync);
      for (const name of ['--cv-visual-height', '--cv-visual-width', '--cv-visual-offset-top', '--cv-keyboard-height', '--workspace-visual-height']) root.style.removeProperty(name);
      root.classList.remove('cv-keyboard-open');
      root.removeAttribute('data-workspace-keyboard-open');
    };
  }, []);
  return state;
}
