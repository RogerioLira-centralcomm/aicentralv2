import React from 'react';
import {Dialog, Modal, ModalOverlay} from 'react-aria-components';
import {Button} from './untitled-kit/src/components/base/buttons/button.tsx';

export function ReportsDrawer({open, onOpenChange, title, description, context, children}) {
  if (!open) return null;
  return <ModalOverlay className="reports-untitled-overlay" isOpen={open} onOpenChange={onOpenChange} isDismissable>
    <Modal className="reports-untitled-drawer"><Dialog aria-label={title} className="reports-untitled-drawer__dialog">
      <div className="reports-untitled-drawer__head"><div><span>{context || 'Reports'}</span><h2>{title}</h2>{description && <p>{description}</p>}</div><Button className="reports-drawer-close" color="tertiary" onPress={() => onOpenChange(false)} aria-label={`Fechar ${title}`}>×</Button></div>
      {children}
    </Dialog></Modal>
  </ModalOverlay>;
}
