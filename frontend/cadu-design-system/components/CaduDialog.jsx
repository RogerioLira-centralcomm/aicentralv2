import React, {useEffect, useId, useRef} from 'react';

/** A native modal with predictable focus, Escape handling and backdrop. */
export function CaduDialog({className = '', label, titleId, initialFocusRef, closeOnBackdrop = false, onClose, children}) {
  const dialog = useRef(null);
  const generatedTitleId = useId();
  const labelledBy = titleId || (!label ? generatedTitleId : undefined);
  useEffect(() => {
    const node = dialog.current;
    if (!node?.open) {
      node?.showModal();
      initialFocusRef?.current?.focus();
    }
    return () => { if (node?.open) node.close(); };
  }, [initialFocusRef]);
  const backdropClick = event => {
    if (!closeOnBackdrop || event.target !== dialog.current) return;
    const rect = dialog.current.getBoundingClientRect();
    const inside = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
    if (!inside) onClose?.();
  };
  return <dialog ref={dialog} className={`cadu-ds-dialog ${className}`} aria-label={label} aria-labelledby={labelledBy} onMouseDown={backdropClick} onCancel={event => { event.preventDefault(); onClose?.(); }}>
    {typeof children === 'function' ? children({titleId: labelledBy || generatedTitleId}) : children}
  </dialog>;
}
