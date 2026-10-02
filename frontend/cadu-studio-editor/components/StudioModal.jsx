import React from 'react';
import StudioDialog from '../../cadu-studio-ui/StudioDialog';

export function StudioModal({title, children, onClose}) {
  return <StudioDialog className="se-modal" titleId="studio-modal-title" closeOnBackdrop onClose={onClose}><header><h2 id="studio-modal-title">{title}</h2><button type="button" onClick={onClose} aria-label="Fechar">×</button></header>{children}</StudioDialog>;
}
