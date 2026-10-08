import React, {useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduDialog} from '../cadu-design-system/components/CaduDialog.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';

/**
 * One share control for every shareable screen (plan, final plan, doc): a button that opens the link,
 * with copy, optional new link and switch off. The open link needs no login; the person who shares decides.
 */
export function ShareControl({title, description, url, enabled, busy = false, canRotate = false, disabled = false, onToggle, variant = 'secondary'}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [confirmingRotate, setConfirmingRotate] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard?.writeText(url); setCopied(true); window.setTimeout(() => setCopied(false), 2000); } catch { /* manual copy from the field */ }
  };
  // Confirmed inline: a portal-based dialog would sit behind this native modal.
  const rotate = async () => { await onToggle(true, true); setConfirmingRotate(false); };
  return <>
    <CaduButton variant={variant} disabled={disabled} loading={busy} onClick={() => setOpen(true)}>
      <Icon name="link" size={16}/>{enabled ? 'Link público' : 'Compartilhar'}</CaduButton>
    {open && <CaduDialog className="planner-dialog planner-share" closeOnBackdrop onClose={() => setOpen(false)}>{({titleId}) => <div className="planner-share__body">
      <header><h2 id={titleId}>{title}</h2>
        <CaduButton variant="tertiary" size="sm" aria-label="Fechar" onClick={() => setOpen(false)}><Icon name="close" size={18}/></CaduButton></header>
      <p>{description}</p>
      {enabled && url
        ? <>
          <CaduInput label="Link público" readOnly value={url} onFocus={event => event.target.select()}/>
          <p className="planner-muted">Qualquer pessoa com este link vê a versão atual, só para leitura, sem login.</p>
          {confirmingRotate && <p role="alert" className="planner-share__warn">O link atual deixa de funcionar para quem já o recebeu. Criar um novo?</p>}
          {confirmingRotate
            ? <footer className="planner-share__actions">
              <CaduButton variant="tertiary" disabled={busy} onClick={() => setConfirmingRotate(false)}>Manter o atual</CaduButton>
              <CaduButton loading={busy} onClick={rotate}>Sim, criar novo link</CaduButton>
            </footer>
            : <footer className="planner-share__actions">
              {canRotate && <CaduButton variant="tertiary" disabled={busy} onClick={() => setConfirmingRotate(true)}>Criar novo link</CaduButton>}
              <CaduButton variant="tertiary" loading={busy} onClick={() => onToggle(false)}>Desativar link</CaduButton>
              <CaduButton onClick={copy}><Icon name={copied ? 'check' : 'link'} size={16}/>{copied ? 'Copiado' : 'Copiar link'}</CaduButton>
            </footer>}
        </>
        : <footer className="planner-share__actions">
          <CaduButton variant="secondary" onClick={() => setOpen(false)}>Fechar</CaduButton>
          <CaduButton loading={busy} onClick={() => onToggle(true)}><Icon name="link" size={16}/>Ativar link público</CaduButton>
        </footer>}
    </div>}</CaduDialog>}
  </>;
}
