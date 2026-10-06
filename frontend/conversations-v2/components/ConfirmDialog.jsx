import React from 'react';
import {CaduConfirmDialog} from '../../cadu-design-system/components/CaduConfirmDialog';

/** Confirmation before discarding edits: the shared Untitled dialog, dark through the chat kit. */
export function ConfirmDialog({request, onResolve}) {
  return <CaduConfirmDialog open={Boolean(request)} title="Descartar alterações?" description={request?.copy} confirmLabel="Descartar" cancelLabel="Continuar editando" tone="danger" onCancel={() => onResolve(false)} onConfirm={() => onResolve(true)}/>;
}
