import React, {useEffect, useState} from 'react';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Callout} from './ReportsBlocks.jsx';
import {json} from './reportsCommon.jsx';

/** Preview of the result e-mail (logo, illustration, preliminary result, screenshot, public link) and an explicit send. */
export function LinkEmailDrawer({run, data, save, busy, onClose}) {
  const [to, setTo] = useState('');
  const [note, setNote] = useState('');
  const [preview, setPreview] = useState(null);
  const [state, setState] = useState({sent: '', error: ''});
  useEffect(() => {
    if (!run) return;
    setPreview(null); setState({sent: '', error: ''});
    json(`/connect/api/v2/reports/link-tests/${run.id}/email-preview?client_id=${encodeURIComponent(data.client.client_id)}`).then(setPreview).catch(failure => setState({sent: '', error: failure.message}));
  }, [run?.id]);
  const send = async event => {
    event.preventDefault(); setState({sent: '', error: ''});
    try {const body = await save(`/link-tests/${run.id}/email`, {to, note}, false); setState({sent: body.to, error: ''});}
    catch (failure) {setState({sent: '', error: failure.message || 'Não foi possível enviar.'});}
  };
  return <ReportsDrawer open={Boolean(run)} onOpenChange={value => {if (!value) onClose();}} title="Enviar resultado por e-mail" context={run?.url || ''} description="O e-mail leva o resultado preliminar, o print da página e o link do relatório público.">
    <form className="untitled-scope flex flex-col gap-5" onSubmit={send}>
      <ReportsFieldInput label="Destinatário" required type="email" maxLength={254} value={to} onChange={event => setTo(event.target.value)} placeholder="cliente@empresa.com"/>
      <ReportsFieldInput label="Recado (opcional)" maxLength={500} value={note} onChange={event => setNote(event.target.value)} placeholder="Uma linha para o cliente"/>
      {state.sent && <Callout tone="brand" title="E-mail enviado">Enviado para {state.sent}.</Callout>}
      {state.error && <Callout tone="gray" title="Não foi possível concluir">{state.error}</Callout>}
      <Button type="submit" size="md" color="primary" isDisabled={busy || !to} isLoading={busy}>Enviar e-mail</Button>
      <section><h3 className="text-sm font-semibold text-primary">Pré-visualização</h3>
        {preview ? <iframe title="Pré-visualização do e-mail" sandbox="allow-same-origin" srcDoc={preview.html} className="mt-2 h-[560px] w-full rounded-lg ring-1 ring-secondary"/> : <p className="mt-2 text-sm text-tertiary">{state.error ? '' : 'Carregando…'}</p>}
      </section>
    </form>
  </ReportsDrawer>;
}
