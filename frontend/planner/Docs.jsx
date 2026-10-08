import React, {useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduDialog} from '../cadu-design-system/components/CaduDialog.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';
import {CaduSelectField, CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {PlannerPanel} from './PlannerUi.jsx';
import {ShareControl} from './ShareControl.jsx';
import {useConfirm} from './useConfirm.jsx';
import {plainText} from './api.js';

const DOC_TYPES = [['documento', 'Documento'], ['briefing', 'Briefing'], ['apresentacao', 'Apresentação'], ['proposta', 'Proposta']];
const typeLabel = value => DOC_TYPES.find(([key]) => key === value)?.[1] || value || 'Documento';

function CreateDocDialog({onClose, onCreate, busy}) {
  return <CaduDialog className="planner-dialog" closeOnBackdrop onClose={onClose}>{({titleId}) => <form onSubmit={onCreate}>
    <header><h2 id={titleId}>Novo documento</h2><CaduButton variant="tertiary" size="sm" aria-label="Fechar" onClick={onClose}><Icon name="close" size={18}/></CaduButton></header>
    <CaduInput label="Título" name="title" required autoFocus/>
    <CaduSelectField label="Tipo" name="type" options={DOC_TYPES.map(([value, label]) => ({value, label}))}/>
    <footer><CaduButton variant="secondary" onClick={onClose}>Cancelar</CaduButton><CaduButton type="submit" loading={busy}>Criar documento</CaduButton></footer>
  </form>}</CaduDialog>;
}

function DocumentView({boot, request, notify, document: initial, startEditing, onChange}) {
  const [doc, setDoc] = useState(initial);
  const [editing, setEditing] = useState(startEditing);
  const [html, setHtml] = useState(initial.html || '');
  const [busy, setBusy] = useState('');
  const [confirm, confirmDialog] = useConfirm();
  const canWrite = boot.writesEnabled && doc.is_owner;
  const apply = next => { setDoc(next); setHtml(next.html || ''); onChange(next); };
  const run = async (key, action) => {
    setBusy(key);
    try { await action(); } catch (error) { notify({tone: 'error', message: error.message}); } finally { setBusy(''); }
  };
  const save = () => run('save', async () => {
    const data = await request(`/docs/${doc.id}`, {method: 'PUT', body: JSON.stringify({title: doc.title, html, status: doc.status || 'draft'})});
    apply(data.document);
    setEditing(false);
    notify({message: 'Documento salvo.'});
  });
  const review = () => run('review', async () => {
    const estimate = await request(`/docs/${doc.id}/review/estimate`);
    if (!await confirm({title: 'Revisar com o Cadu?', confirmLabel: 'Revisar',
      description: `Revisão em ${estimate.passes} etapas. Estimativa: ${Number(estimate.estimated_tokens).toLocaleString('pt-BR')} créditos.`})) return;
    const data = await request(`/docs/${doc.id}/review`, {method: 'POST', body: JSON.stringify({})});
    if (data.document) { apply(data.document); setEditing(false); }
  });
  const duplicate = () => run('duplicate', async () => {
    const data = await request(`/docs/${doc.id}/duplicate`, {method: 'POST', body: JSON.stringify({})});
    onChange(data.document, true);
    notify({message: 'Documento duplicado.'});
  });
  const setShare = enabled => run('share', async () => {
    const data = await request(`/docs/${doc.id}/share`, {method: 'POST', body: JSON.stringify({enabled})});
    apply(data.document);
    notify({message: enabled ? 'Link público do documento ativado.' : 'Link público do documento desativado.'});
  });

  return <>
    {confirmDialog}
    <PlannerHeader crumbs={[['Docs', boot.urls.docs]]} title={doc.title || 'Documento'}
      meta={<><CaduBadge tone="neutral">{typeLabel(doc.type)}</CaduBadge>{doc.share_enabled && <CaduBadge tone="brand">Público</CaduBadge>}</>}
      description={doc.updated_at ? `Atualizado em ${doc.updated_at}` : null}
      actions={canWrite ? (editing ? <>
        <CaduButton variant="secondary" onClick={() => { setHtml(doc.html || ''); setEditing(false); }}>Cancelar</CaduButton>
        <CaduButton loading={busy === 'save'} onClick={save}>Salvar alterações</CaduButton>
      </> : <>
        <CaduButton variant="secondary" loading={busy === 'duplicate'} onClick={duplicate}>Duplicar</CaduButton>
        <ShareControl title="Compartilhar o documento" description="Link aberto para o time ou o cliente ler este documento."
          url={doc.share_token ? new URL(`/docs/public/${doc.share_token}`, boot.urls.home).href : ''} enabled={Boolean(doc.share_enabled)}
          busy={busy === 'share'} onToggle={setShare}/>
        <CaduButton variant="secondary" loading={busy === 'review'} onClick={review}><Icon name="compose" size={16}/>Revisar com o Cadu</CaduButton>
        <CaduButton onClick={() => setEditing(true)}>Editar</CaduButton>
      </>) : null}/>
    <PlannerPanel>
      {editing ? <div className="planner-doc-editor">
        <CaduInput label="Título" value={doc.title || ''} onChange={event => setDoc({...doc, title: event.target.value})}/>
        <CaduTextAreaField label="Conteúdo (HTML)" value={html} onChange={event => setHtml(event.target.value)} rows={18}/>
      </div> : <article className="planner-doc-preview">{plainText(doc.html) || 'Documento sem texto para prévia.'}</article>}
    </PlannerPanel>
  </>;
}

export function DocsPage({boot, request, notify}) {
  const [documents, setDocuments] = useState(Array.isArray(boot.records) ? boot.records : []);
  const [open, setOpen] = useState(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);

  const openDoc = async summary => {
    try {
      const data = await request(`/docs/${summary.id}`);
      setOpen({document: data.document, editing: false});
    } catch (error) { notify({tone: 'error', message: error.message}); }
  };
  const create = async event => {
    event.preventDefault();
    setBusy(true);
    try {
      const data = await request('/docs', {method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget)))});
      setDocuments(current => [data.document, ...current]);
      setCreating(false);
      setOpen({document: data.document, editing: true});
    } catch (error) { notify({tone: 'error', message: error.message}); } finally { setBusy(false); }
  };
  const changed = (next, added = false) => setDocuments(current => added ? [next, ...current] : current.map(item => item.id === next.id ? {...item, ...next} : item));

  if (open) return <DocumentView key={open.document.id} boot={boot} request={request} notify={notify} document={open.document} startEditing={open.editing} onChange={changed}/>;
  return <>
    <PlannerHeader title="Docs" description={documents.length ? `${documents.length} ${documents.length === 1 ? 'documento' : 'documentos'}` : 'Briefings, propostas e apresentações do cliente.'}
      actions={boot.writesEnabled ? <CaduButton onClick={() => setCreating(true)}><Icon name="plus" size={16}/>Novo documento</CaduButton> : null}/>
    {documents.length ? <div className="pl-table pl-table--docs" role="table" aria-label="Documentos">
      <div className="pl-table__row pl-table__head" role="row"><span role="columnheader">Documento</span><span role="columnheader">Tipo</span><span role="columnheader">Acesso</span><span role="columnheader">Atualizado</span></div>
      {documents.map(item => <button type="button" className="pl-table__row" role="row" key={item.id} onClick={() => openDoc(item)}>
        <span role="cell" className="pl-table__name pl-table__with-icon"><Icon name="file" size={18}/><strong>{item.title}</strong></span>
        <span role="cell">{typeLabel(item.type)}</span>
        <span role="cell">{item.share_enabled ? <CaduBadge tone="brand">Link público</CaduBadge> : <span className="pl-table__muted">Privado</span>}</span>
        <span role="cell" className="pl-table__muted">{item.updated_at || '—'}</span>
      </button>)}
    </div> : <PlannerPanel className="planner-panel--flush"><CaduEmptyState title="Nenhum documento ainda" description="Crie um briefing ou uma proposta para compartilhar com o cliente." action={boot.writesEnabled ? <CaduButton onClick={() => setCreating(true)}>Criar documento</CaduButton> : null}/></PlannerPanel>}
    {creating && <CreateDocDialog busy={busy} onClose={() => setCreating(false)} onCreate={create}/>}
  </>;
}
