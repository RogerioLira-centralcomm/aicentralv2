import React from 'react';
import {Dialog, Modal, ModalOverlay} from 'react-aria-components';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';

export function ReportsConfirmDialog({open, title, description, confirmLabel, busy, onCancel, onConfirm}) {
  if (!open) return null;
  return <ModalOverlay className="reports-untitled-overlay reports-confirm-overlay" isOpen={open} onOpenChange={value => {if (!value && !busy) onCancel();}} isDismissable={!busy}>
    <Modal className="reports-confirm-modal"><Dialog aria-label={title} className="reports-confirm-dialog">
      <h2>{title}</h2><p>{description}</p>
      <div className="reports-confirm-actions"><Button color="secondary" onPress={onCancel} isDisabled={busy}>Cancelar</Button><Button color="primary-destructive" onPress={onConfirm} isDisabled={busy} isLoading={busy}>{confirmLabel}</Button></div>
    </Dialog></Modal>
  </ModalOverlay>;
}
