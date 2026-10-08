import React, {useCallback, useRef, useState} from 'react';
import {CaduConfirmDialog} from '../cadu-design-system/components/CaduConfirmDialog.jsx';

/**
 * Promise-based confirmation with the design-system dialog, in place of window.confirm.
 * `const [confirm, dialog] = useConfirm()`; render `{dialog}` once and `await confirm({title, description, ...})`.
 */
export function useConfirm() {
  const [options, setOptions] = useState(null);
  const resolver = useRef(null);
  const confirm = useCallback(next => new Promise(resolve => {
    resolver.current = resolve;
    setOptions(next);
  }), []);
  const settle = value => {
    resolver.current?.(value);
    resolver.current = null;
    setOptions(null);
  };
  const dialog = <CaduConfirmDialog open={Boolean(options)} title={options?.title || ''} description={options?.description}
    confirmLabel={options?.confirmLabel || 'Continuar'} cancelLabel={options?.cancelLabel || 'Cancelar'}
    tone={options?.tone || 'primary'} onCancel={() => settle(false)} onConfirm={() => settle(true)}/>;
  return [confirm, dialog];
}
