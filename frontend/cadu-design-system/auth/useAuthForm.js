import {useCallback, useRef, useState} from 'react';
import {revealField, useAuthViewport} from './useAuthViewport';
import {firstInvalid, hasErrors} from './validation.mjs';

/**
 * Form state for the access screens. The form still posts natively (the server renders the next screen);
 * this only validates before sending, keeps the first wrong field in view above the keyboard and guards the
 * submit against double taps and against a stuck spinner after the browser restores the page from cache.
 *
 * validators: {field: (value, allValues) => 'message' | ''}, listed in the visual order of the form.
 */
export function useAuthForm(initial, validators, {overlay = false} = {}) {
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [overlayVisible, setOverlayVisible] = useState(false);
  const refs = useRef({});
  const timer = useRef(0);
  const order = Object.keys(validators);

  const restore = useCallback(() => {
    window.clearTimeout(timer.current);
    setLoading(false);
    setOverlayVisible(false);
  }, []);
  useAuthViewport({onRestore: restore});

  const check = (name, nextValues) => validators[name]?.(nextValues[name], nextValues) || '';

  const bind = name => ({
    value: values[name],
    error: errors[name],
    inputRef: node => { refs.current[name] = node; },
    onChange: event => {
      const next = {...values, [name]: event.target.value};
      setValues(next);
      // Errors appear on blur or submit, never while the person is still typing; once shown, they clear as soon
      // as the field (or the one it depends on, like the password for its confirmation) is fixed.
      setErrors(current => Object.fromEntries(order.map(field => [field, current[field] ? check(field, next) : ''])));
    },
    // Empty fields wait for the submit: tapping "Esqueci minha senha" must not paint the form red.
    onBlur: () => { if (values[name]) setErrors(current => ({...current, [name]: check(name, values)})); },
  });

  const handleSubmit = event => {
    if (loading) { event.preventDefault(); return; }
    const found = Object.fromEntries(order.map(name => [name, check(name, values)]));
    setErrors(found);
    if (hasErrors(found)) {
      event.preventDefault();
      const target = refs.current[firstInvalid(found, order)];
      target?.focus({preventScroll: true});
      revealField(target);
      return;
    }
    setLoading(true);
    // A fast server answer (wrong password) reloads the page before this shows, so it never flashes.
    if (overlay) timer.current = window.setTimeout(() => setOverlayVisible(true), 600);
  };

  return {values, bind, loading, overlayVisible, handleSubmit};
}
