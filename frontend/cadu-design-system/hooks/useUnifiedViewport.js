import {useEffect, useState} from 'react';

const PHONE_QUERY = '(max-width: 767px)';
const TABLET_QUERY = '(min-width: 768px) and (max-width: 1199px)';
const KEYBOARD_THRESHOLD = 120;
const CHAT_QUERIES = {phone: PHONE_QUERY, tablet: TABLET_QUERY};

function readViewport(baselineHeight = window.innerHeight, queries = CHAT_QUERIES) {
  const viewport = window.visualViewport;
  const visualHeight = Math.round(viewport?.height || window.innerHeight);
  const visualWidth = Math.round(viewport?.width || window.innerWidth);
  const offsetTop = Math.round(viewport?.offsetTop || 0);
  const editable = document.activeElement?.matches?.('textarea, input:not([type="checkbox"]):not([type="radio"]), [contenteditable="true"]');
  const keyboardInset = Math.max(0, window.innerHeight - visualHeight - offsetTop, baselineHeight - visualHeight - offsetTop);
  return {
    layout: window.matchMedia(queries.phone).matches ? 'phone' : window.matchMedia(queries.tablet).matches ? 'tablet' : 'desktop',
    isMobile: window.matchMedia(queries.phone).matches,
    visualHeight,
    visualWidth,
    offsetTop,
    keyboardInset,
    keyboardOpen: Boolean(editable && keyboardInset > KEYBOARD_THRESHOLD),
    orientation: visualWidth > visualHeight ? 'landscape' : 'portrait',
  };
}

export function useUnifiedViewport(queries = CHAT_QUERIES) {
  const [state, setState] = useState(() => readViewport(undefined, queries));
  useEffect(() => {
    const root = document.documentElement;
    const viewport = window.visualViewport;
    const phone = window.matchMedia(queries.phone);
    const tablet = window.matchMedia(queries.tablet);
    let frame = 0;
    let baselineHeight = viewport?.height || window.innerHeight;
    // iOS can leave the page nudged sideways after focusing a field; bring it back once the field loses focus.
    const resetSideScroll = () => window.setTimeout(() => { if (window.scrollX || (window.visualViewport?.offsetLeft || 0) > 0) window.scrollTo(0, window.scrollY); }, 120);
    const sync = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const active = document.activeElement;
        const editable = active?.matches?.('textarea, input:not([type="checkbox"]):not([type="radio"]), [contenteditable="true"]');
        const height = viewport?.height || window.innerHeight;
        if (!editable) baselineHeight = height;
        const next = readViewport(baselineHeight, queries);
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
    document.addEventListener('focusout', resetSideScroll);
    return () => {
      window.cancelAnimationFrame(frame);
      for (const media of [phone, tablet]) media.removeEventListener?.('change', sync);
      viewport?.removeEventListener('resize', sync);
      viewport?.removeEventListener('scroll', sync);
      window.removeEventListener('resize', sync);
      window.removeEventListener('orientationchange', sync);
      document.removeEventListener('focusin', sync);
      document.removeEventListener('focusout', sync);
      document.removeEventListener('focusout', resetSideScroll);
      for (const name of ['--cv-visual-height', '--cv-visual-width', '--cv-visual-offset-top', '--cv-keyboard-height', '--workspace-visual-height']) root.style.removeProperty(name);
      root.classList.remove('cv-keyboard-open');
      root.removeAttribute('data-workspace-keyboard-open');
    };
  }, []);
  return state;
}
