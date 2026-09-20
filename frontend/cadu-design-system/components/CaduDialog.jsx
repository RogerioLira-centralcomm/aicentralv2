import React, {useEffect, useRef} from 'react';

/** A native modal with predictable focus, Escape handling and backdrop. */
export function CaduDialog({className = '', label, onClose, children}) {
  const dialog = useRef(null);
  useEffect(() => {
    const node = dialog.current;
    if (!node?.open) node?.showModal();
    return () => { if (node?.open) node.close(); };
  }, []);
  return <dialog ref={dialog} className={`cadu-ds-dialog ${className}`} aria-label={label} onCancel={event => { event.preventDefault(); onClose?.(); }}>
    {children}
  </dialog>;
}
