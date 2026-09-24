import React, {useRef, useState} from 'react';
import {CaduDialog} from './CaduDialog';

export function ProjectCreateDialog({action, csrfToken, brands = [], initialBrandId = '', onCreated, onClose}) {
  const nameInput = useRef(null);
  const folderInput = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [files, setFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState('');
  const selectFolder = event => {
    const selected = Array.from(event.target.files || []).filter(file => !file.name.startsWith('.'));
    const totalBytes = selected.reduce((sum, file) => sum + Number(file.size || 0), 0);
    if (selected.length > 100) { setError('Escolha uma pasta com até 100 arquivos por vez.'); setFiles([]); event.target.value = ''; return; }
    if (totalBytes > 250 * 1024 * 1024) { setError('A pasta selecionada ultrapassa 250 MB. Escolha menos arquivos.'); setFiles([]); event.target.value = ''; return; }
    setError(''); setFiles(selected);
  };
  const close = () => { if (!busy) onClose?.(); };

  const submit = async event => {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    setBusy(true); setError('');
    try {
      const response = await fetch(action, {
        method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json', 'Accept':'application/json', 'X-CSRF-Token':csrfToken},
        body:JSON.stringify({name:form.get('name'), description:form.get('description'), brand_id:form.get('brand_id') || null}),
      });
      const value = await response.json().catch(() => ({}));
      if (!response.ok || !value.project) throw new Error(value.error || 'Não foi possível criar o projeto.');
      let importedFiles = 0;
      let failedImports = 0;
      if (files.length && value.project.upload_url) {
        for (let index = 0; index < files.length; index += 1) {
          setUploadProgress(`Preparando arquivo ${index + 1} de ${files.length}…`);
          const body = new FormData(); body.append('_csrf', csrfToken); body.append('file', files[index]);
          try {
            const upload = await fetch(value.project.upload_url, {method:'POST', credentials:'same-origin', headers:{'Accept':'application/json', 'X-CSRF-Token':csrfToken, 'X-Cadu-Triage':'1'}, body});
            if (!upload.ok) throw new Error('upload failed');
            importedFiles += 1;
          } catch (_) { failedImports += 1; }
        }
      }
      await onCreated?.({...value.project, importedFiles, failedImports});
      onClose?.();
    } catch (submitError) {
      setError(submitError.message || 'Não foi possível criar o projeto.');
      setBusy(false);
    }
  };

  return <CaduDialog className="cadu-ds-project-dialog cadu-ds-project-create-dialog" label="Criar projeto" initialFocusRef={nameInput} onClose={close}>
    <form className="cadu-ds-project-form" aria-busy={busy} onSubmit={submit}>
      <header className="cadu-ds-project-create-dialog__header">
        <div><p className="cadu-ds-project-dialog__eyebrow">Novo espaço de trabalho</p><h2>Criar projeto</h2><p>Reúna conversas, referências, arquivos e conteúdos em um só lugar.</p></div>
        <button type="button" disabled={busy} onClick={close} aria-label="Fechar">×</button>
      </header>
      <label>Nome do projeto<input ref={nameInput} name="name" required minLength="2" maxLength="150" autoComplete="off" placeholder="Ex.: Campanha de lançamento"/></label>
      <label>O que é este projeto?<textarea name="description" required minLength="2" rows="3" maxLength="4000" placeholder="Conte em poucas palavras o que você vai reunir ou realizar aqui."/></label>
      <label>Marca associada <small>Você pode alterar depois.</small><select name="brand_id" defaultValue={initialBrandId}><option value="">Sem marca</option>{brands.map(brand => <option key={brand.id} value={brand.id}>{brand.name}</option>)}</select></label>
      <section className="cadu-ds-project-create-folder"><span>Pastas de origem <small>Opcional</small></span><input ref={folderInput} type="file" multiple directory="" webkitdirectory="" hidden onChange={selectFolder}/>{files.length ? <div className="cadu-ds-project-create-folder__selected"><b>{files[0]?.webkitRelativePath?.split('/')[0] || 'Arquivos selecionados'}</b><small>{files.length} arquivo{files.length === 1 ? '' : 's'} · serão enviados para revisão no projeto</small><button type="button" disabled={busy} onClick={() => { setFiles([]); if (folderInput.current) folderInput.current.value = ''; }}>Remover pasta</button></div> : <button type="button" disabled={busy} onClick={() => folderInput.current?.click()}>Adicionar uma pasta neste computador <span aria-hidden="true">⌄</span></button>}</section>
      {uploadProgress && <p className="cadu-ds-project-create-dialog__progress" role="status">{uploadProgress}</p>}
      <p className="cadu-ds-project-create-dialog__scope">O projeto será criado no espaço deste cliente. Você pode associar uma marca depois.</p>
      {error && <p className="cadu-ds-project-upload-error" role="alert">{error}</p>}
      <footer><button className="is-primary" disabled={busy}>{busy ? 'Criando…' : 'Criar projeto'}</button></footer>
    </form>
  </CaduDialog>;
}
