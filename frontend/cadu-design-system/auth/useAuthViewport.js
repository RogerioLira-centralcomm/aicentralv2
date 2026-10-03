import {useEffect} from 'react';

const KEYBOARD_MIN = 120;

/** Scroll the focused control to the middle of what is still visible, once the keyboard animation settles. */
export function revealField(element) {
  if (!element || typeof element.scrollIntoView !== 'function') return;
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  element.scrollIntoView({block: 'center', behavior: reduce ? 'auto' : 'smooth'});
}

/**
 * Keyboard and viewport handling for the access screens.
 * - Publishes the height covered by the on-screen keyboard as --auth-kb (iOS Safari keeps the layout viewport
 *   and overlays the keyboard; Chrome resizes the layout, so the value stays 0 there) and an is-keyboard-open class.
 * - Brings the focused field into view when the keyboard opens or the focus moves to another field.
 * - Calls onRestore when the page comes back from the back/forward cache, where a submit that already left
 *   would otherwise keep the button spinning forever.
 */
export function useAuthViewport({onRestore} = {}) {
  useEffect(() => {
    const root = document.documentElement;
    const viewport = window.visualViewport;
    const coarse = window.matchMedia?.('(pointer: coarse)').matches;
    let frame = 0;
    let timer = 0;
    const isField = element => element && /^(INPUT|TEXTAREA|SELECT)$/.test(element.tagName);
    const sync = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const covered = viewport ? Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop) : 0;
        const open = covered > KEYBOARD_MIN;
        root.style.setProperty('--auth-kb', open ? `${Math.round(covered)}px` : '0px');
        root.classList.toggle('is-keyboard-open', open);
        if (open && isField(document.activeElement)) revealField(document.activeElement);
      });
    };
    const onFocusIn = event => {
      if (!coarse || !isField(event.target)) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => revealField(event.target), 320);
    };
    const onPageShow = event => { if (event.persisted) onRestore?.(); };
    viewport?.addEventListener('resize', sync);
    viewport?.addEventListener('scroll', sync);
    document.addEventListener('focusin', onFocusIn);
    window.addEventListener('pageshow', onPageShow);
    return () => {
      viewport?.removeEventListener('resize', sync);
      viewport?.removeEventListener('scroll', sync);
      document.removeEventListener('focusin', onFocusIn);
      window.removeEventListener('pageshow', onPageShow);
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timer);
      root.classList.remove('is-keyboard-open');
      root.style.removeProperty('--auth-kb');
    };
  }, [onRestore]);
}
