import React, {useEffect, useRef, useState} from 'react';
import {Dialog, Modal, ModalOverlay} from 'react-aria-components';
import {Button} from '../untitled-kit/button';
import {CaduPanel} from './CaduPanel';

/** Right-side drawer. Asks before discarding edited fields and animates in and out. */
export function CaduDrawer({open, onOpenChange, onDiscard, title, description, context, icon, footer, size = 'md', className = '', children}) {
  const confirmButton = useRef(null);
  const body = useRef(null);
  const baseline = useRef(null);
  const values = () => JSON.stringify(Array.from(body.current?.querySelectorAll('input,select,textarea') || []).map(field => [field.name, field.type, field.value, field.checked]));
  const [dirty, setDirty] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  useEffect(() => { if (!open) { setDirty(false); setConfirmClose(false); } }, [open]);
  useEffect(() => { if (open) baseline.current = values(); }, [open]);
  useEffect(() => { if (confirmClose) confirmButton.current?.focus(); }, [confirmClose]);
  const close = () => { if (dirty) setConfirmClose(true); else onOpenChange(false); };
  const discard = () => { onDiscard?.(); onOpenChange(false); };
  return <ModalOverlay className="cadu-ds-overlay cadu-ds-overlay--drawer" isOpen={open} onOpenChange={value => { if (!value) close(); }} isDismissable>
    <Modal className={`cadu-ds-drawer cadu-ds-drawer--${size} ${className}`.trim()}>
      <Dialog aria-label={title} className="cadu-ds-drawer__dialog">
        <CaduPanel as="div" title={title} description={description} context={context} icon={icon} onClose={close} footer={footer}>
          {confirmClose && <section className="cadu-ds-drawer__discard" role="alert">
            <h3>Descartar alterações?</h3>
            <p>Os campos preenchidos ainda podem não ter sido salvos.</p>
            <div><Button ref={confirmButton} type="button" color="secondary" size="sm" onPress={() => setConfirmClose(false)}>Continuar editando</Button><Button type="button" color="primary-destructive" size="sm" onPress={discard}>Descartar e fechar</Button></div>
          </section>}
          <div ref={body} hidden={confirmClose} onChangeCapture={() => setDirty(values() !== baseline.current)}>{children}</div>
        </CaduPanel>
      </Dialog>
    </Modal>
  </ModalOverlay>;
}
