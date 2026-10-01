import React, {useRef, useState} from 'react';
import {Dialog, Modal, ModalOverlay} from 'react-aria-components';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {json} from './reportsCommon.jsx';

/** A plan gets its site only when the team is ready to measure; addresses already typed must belong to it. */
export function FlowConnectSite({open, clientId, onConnect, onClose}) {
  const [url, setUrl] = useState('');
  const [check, setCheck] = useState(null);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const sequence = useRef(0);
  if (!open) return null;
  const verify = async () => {
    const value = url.trim();
    if (!value) return;
    const current = ++sequence.current;
    setChecking(true); setCheck(null); setError('');
    try {
      const result = await json(`/connect/api/v2/reports/supertag/site-check?client_id=${clientId}&url=${encodeURIComponent(value)}`);
      if (current === sequence.current) setCheck({...result, verifiedUrl: value});
    } catch (failure) {
      if (current === sequence.current) setCheck({error: failure.message});
    } finally {
      if (current === sequence.current) setChecking(false);
    }
  };
  const connect = async () => {
    if (!check || check.error || check.verifiedUrl !== url.trim()) return;
    setBusy(true); setError('');
    try {await onConnect(check.host);} catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const ready = Boolean(check && !check.error && check.verifiedUrl === url.trim());
  return <ModalOverlay className="cadu-ds-overlay cadu-ds-overlay--center" isOpen onOpenChange={value => {if (!value && !busy) onClose();}} isDismissable={!busy}>
    <Modal className="cadu-ds-confirm"><Dialog aria-label="Conectar site" className="cadu-ds-confirm__dialog flow-connect-site">
      <h2>Conectar site</h2>
      <p>O plano continua igual. Ao conectar o site, o Reports prepara a Super Tag para que os passos prontos possam ser medidos.</p>
      {error && <p className="reports-error" role="alert">{error}</p>}
      <div className="flow-connect-site__row">
        <label>URL do site<ReportsFieldInput type="url" value={url} placeholder="https://www.exemplo.com.br" onChange={event => {sequence.current++; setUrl(event.target.value); setCheck(null); setChecking(false);}}/></label>
        <Button color="secondary" onPress={verify} isDisabled={!url.trim() || checking}>{checking ? 'Verificando…' : 'Validar domínio'}</Button>
      </div>
      {check && <div className={`reports-flow-site-check${check.error ? ' has-error' : ''}`} role={check.error ? 'alert' : 'status'}>{check.error ? <p>{check.error}</p> : <><strong>{check.title || check.host}</strong><small>{check.host} · HTTP {check.status}</small></>}</div>}
      <div className="cadu-ds-confirm__actions"><Button color="secondary" onPress={onClose} isDisabled={busy}>Cancelar</Button><Button color="primary" onPress={connect} isDisabled={!ready || busy} isLoading={busy}>Conectar site</Button></div>
    </Dialog></Modal>
  </ModalOverlay>;
}
