import React, {useEffect, useId, useRef} from 'react';
import './tokens.css';
import './dialog.css';

/** Native modal for Studio tools: focus return, Escape and optional backdrop close. */
export default function StudioDialog({className = '', label, titleId, initialFocusRef, closeOnBackdrop = false, onClose, children}) {
  const dialog = useRef(null);
  const generatedTitleId = useId();
  const labelledBy = titleId || (!label ? generatedTitleId : undefined);
  useEffect(() => {
    const opener = document.activeElement;
    const node = dialog.current;
    if (!node?.open) {
      node?.showModal();
      initialFocusRef?.current?.focus();
    }
    return () => {
      if (node?.open) node.close();
      if (opener && typeof opener.focus === 'function' && document.contains(opener)) opener.focus();
    };
  }, [initialFocusRef]);
  const backdropClick = event => {
    if (!closeOnBackdrop || event.target !== dialog.current) return;
    const rect = dialog.current.getBoundingClientRect();
    const inside = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
    if (!inside) onClose?.();
  };
  return <dialog ref={dialog} className={`csu-dialog ${className}`} aria-label={label} aria-labelledby={labelledBy}
    onMouseDown={backdropClick} onCancel={event => { event.preventDefault(); onClose?.(); }}>
    {typeof children === 'function' ? children({titleId: labelledBy || generatedTitleId}) : children}
  </dialog>;
}
