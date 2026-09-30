import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import React,{useState,useEffect,useRef} from 'react';
import {Dialog, Modal, ModalOverlay} from 'react-aria-components';
import {Button} from './untitled-kit/src/components/base/buttons/button.tsx';

export function ReportsDrawer({open, onOpenChange, onDiscard, title, description, context, children}) {
  const confirmButton=useRef(null),body=useRef(null),baseline=useRef(null);
  const values=()=>JSON.stringify(Array.from(body.current?.querySelectorAll('input,select,textarea')||[]).map(field=>[field.name,field.type,field.value,field.checked]));
  const [dirty,setDirty]=useState(false),[confirmClose,setConfirmClose]=useState(false);
  useEffect(()=>{if(!open){setDirty(false);setConfirmClose(false);}},[open]);
  useEffect(()=>{if(open)baseline.current=values();},[open]);
  useEffect(()=>{if(confirmClose)confirmButton.current?.focus();},[confirmClose]);
  const close=()=>{if(dirty)setConfirmClose(true);else onOpenChange(false);};
  const discard=()=>{onDiscard?.();onOpenChange(false);};
  if (!open) return null;
  return <ModalOverlay className="reports-untitled-overlay" isOpen={open} onOpenChange={value=>{if(!value)close();}} isDismissable>
    <Modal className="reports-untitled-drawer"><Dialog aria-label={title} className="reports-untitled-drawer__dialog">
      <ReportsPanelShell as="div" title={title} description={description} context={context} onClose={close}>{confirmClose&&<section role="alert"><h3>Descartar alterações?</h3><p>Os campos preenchidos ainda podem não ter sido salvos.</p><button ref={confirmButton} type="button" className="reports-ui-button" onClick={()=>setConfirmClose(false)}>Continuar editando</button><Button type="button" color="primary-destructive" onPress={discard}>Descartar e fechar</Button></section>}<div ref={body} hidden={confirmClose} onChangeCapture={()=>setDirty(values()!==baseline.current)}>{children}</div></ReportsPanelShell>
    </Dialog></Modal>
  </ModalOverlay>;
}
