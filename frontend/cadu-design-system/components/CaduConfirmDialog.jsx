import React from 'react';
import {CaduModal} from './CaduModal';
import {CaduButton} from './CaduButton';

/** Short confirmation for a consequential action. `tone="danger"` styles the confirm button as destructive. */
export function CaduConfirmDialog({open, title, description, confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', tone = 'danger', busy = false, onCancel, onConfirm}) {
  if (!open) return null;
  return <CaduModal className="cadu-ds-confirm__dialog" closeOnBackdrop={!busy} onClose={() => { if (!busy) onCancel(); }}>
    {({titleId}) => <>
      <h2 id={titleId}>{title}</h2>
      {description && <p>{description}</p>}
      <div className="cadu-ds-confirm__actions">
        <CaduButton variant="secondary" size="sm" onClick={onCancel} disabled={busy}>{cancelLabel}</CaduButton>
        <CaduButton variant={tone === 'danger' ? 'danger' : 'primary'} size="sm" onClick={onConfirm} disabled={busy} loading={busy}>{confirmLabel}</CaduButton>
      </div>
    </>}
  </CaduModal>;
}
