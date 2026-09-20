import React from 'react';
import {CaduDialog} from '../../cadu-design-system/components/CaduDialog';

export function StudioModal({title, children, onClose}) {
  return <CaduDialog className="se-modal" titleId="studio-modal-title" closeOnBackdrop onClose={onClose}><header><h2 id="studio-modal-title">{title}</h2><button type="button" onClick={onClose} aria-label="Fechar">×</button></header>{children}</CaduDialog>;
}
