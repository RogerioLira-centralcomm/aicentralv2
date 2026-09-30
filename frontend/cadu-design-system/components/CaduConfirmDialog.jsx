import React from 'react';
import {Dialog, Modal, ModalOverlay} from 'react-aria-components';
import {Button} from '../untitled-kit/button';

/** Short confirmation for a consequential action. `tone="danger"` styles the confirm button as destructive. */
export function CaduConfirmDialog({open, title, description, confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', tone = 'danger', busy = false, onCancel, onConfirm}) {
  return <ModalOverlay className="cadu-ds-overlay cadu-ds-overlay--center" isOpen={open} onOpenChange={value => { if (!value && !busy) onCancel(); }} isDismissable={!busy}>
    <Modal className="cadu-ds-confirm">
      <Dialog aria-label={title} className="cadu-ds-confirm__dialog">
        <h2>{title}</h2>
        {description && <p>{description}</p>}
        <div className="cadu-ds-confirm__actions">
          <Button color="secondary" size="sm" onPress={onCancel} isDisabled={busy}>{cancelLabel}</Button>
          <Button color={tone === 'danger' ? 'primary-destructive' : 'primary'} size="sm" onPress={onConfirm} isDisabled={busy} isLoading={busy}>{confirmLabel}</Button>
        </div>
      </Dialog>
    </Modal>
  </ModalOverlay>;
}
