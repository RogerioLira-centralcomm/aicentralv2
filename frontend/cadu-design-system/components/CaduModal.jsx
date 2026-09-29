import React, {useEffect, useId} from 'react';
import {Dialog, Modal, ModalOverlay} from '../untitled-kit/modal';

export function CaduModal({className = '', label, titleId, initialFocusRef, closeOnBackdrop = false, onClose, children}) {
  const generatedTitleId = useId();
  const labelledBy = titleId || (!label ? generatedTitleId : undefined);
  useEffect(() => {
    const opener = document.activeElement;
    const frame = requestAnimationFrame(() => initialFocusRef?.current?.focus());
    return () => {
      cancelAnimationFrame(frame);
      if (opener && document.contains(opener)) opener.focus?.();
    };
  }, [initialFocusRef]);
  return <ModalOverlay data-cadu-untitled-overlay="" isOpen isDismissable={closeOnBackdrop} onOpenChange={open => { if (!open) onClose?.(); }}>
    <Modal className="cadu-untitled-modal">
      <Dialog className={`cadu-untitled-modal-content ${className}`} aria-label={label} aria-labelledby={labelledBy}>
        {typeof children === 'function' ? children({titleId: labelledBy || generatedTitleId}) : children}
      </Dialog>
    </Modal>
  </ModalOverlay>;
}
