import React, {useMemo, useState} from 'react';
import {CaduButton} from './CaduButton';
import {Icon} from './Icon';

const filters = [['all', 'Todos'], ['document', 'Documentos'], ['spreadsheet', 'Planilhas'], ['pdf', 'PDFs'], ['image', 'Imagens']];

function fileType(file) {
  const mime = String(file.mime || file.kind || '').toLowerCase();
  const name = String(file.title || file.name || '').toLowerCase();
  if (mime.includes('pdf') || name.endsWith('.pdf')) return 'pdf';
  if (mime.startsWith('image/') || ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'].some(ext => name.endsWith(ext))) return 'image';
  if (/spreadsheet|excel|csv|\.xlsx?$/.test(mime) || /\.(csv|xlsx?)$/.test(name)) return 'spreadsheet';
  if (/document|word|text\/|\.docx?$/.test(mime) || /\.(docx?|txt|md|rtf)$/.test(name)) return 'document';
  return 'other';
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat('pt-BR', {dateStyle: 'medium'}).format(date);
}

function statusLabel(value) {
  return ({completed: 'Indexado', queued: 'Na fila', processing: 'Processando', paused: 'Aguardando revisão', error: 'Falha na indexação', failed: 'Falha na indexação', saved: 'Salvo'})[String(value || '').toLowerCase()] || String(value || '');
}

export function WorkspaceFilesView({files = [], scope = 'project', onAdd, onOpenFile}) {
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const normalized = useMemo(() => files.map((file, index) => ({...file, _key: String(file.id || `${file.name || file.title}-${index}`), _type: fileType(file)})), [files]);
  const visible = normalized.filter(file => (filter === 'all' || file._type === filter) && (!query.trim() || `${file.title || file.name} ${file.mime || file.kind || ''}`.toLocaleLowerCase('pt-BR').includes(query.trim().toLocaleLowerCase('pt-BR'))));
  return <section className={`cadu-ds-files${scope === 'conversation' ? ' is-conversation' : ''}`} aria-label="Arquivos">
    <header className="cadu-ds-files__intro"><div><h2>Arquivos</h2><p>{scope === 'project' ? 'Documentos e materiais adicionados a este projeto.' : 'Anexos enviados nesta conversa.'}</p></div>{onAdd && <button type="button" className="is-primary" onClick={onAdd}><Icon name="plus" size={15}/>Adicionar arquivo</button>}</header>
    <div className="cadu-ds-files__toolbar"><nav aria-label="Filtrar arquivos por tipo">{filters.map(([id, label]) => <button type="button" key={id} className={filter === id ? 'is-active' : ''} aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}{id === 'all' && <small>{files.length}</small>}</button>)}</nav><label><Icon name="search" size={15}/><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar arquivos" aria-label="Buscar arquivos"/>{query && <CaduButton variant="tertiary" type="button" onClick={() => setQuery('')} aria-label="Limpar busca">×</CaduButton>}</label></div>
    {visible.length ? <div className="cadu-ds-files__list">{visible.map(file => <article key={file._key}>
      <span className={`cadu-ds-files__type is-${file._type}`}><Icon name={file._type === 'image' ? 'image' : file._type === 'pdf' ? 'pdf' : file._type === 'spreadsheet' ? 'table' : 'file'} size={18}/></span>
      <span className="cadu-ds-files__name"><b title={file.title || file.name}>{file.title || file.name || 'Arquivo'}</b><small>{[file.kind || file.mime || filters.find(item => item[0] === file._type)?.[1] || 'Arquivo', statusLabel(file.status), file.createdAt ? formatDate(file.createdAt) : ''].filter(Boolean).join(' · ')}</small></span>
      {file.size ? <small className="cadu-ds-files__size">{file.size}</small> : null}
      {file.href ? <a href={file.href} download aria-label={`Baixar ${file.title || file.name}`}>Baixar<Icon name="download" size={14}/></a> : onOpenFile ? <button type="button" onClick={() => onOpenFile(file)}>{file.actionLabel || 'Ver mensagem'}<Icon name="chevron" size={14}/></button> : <span className="cadu-ds-files__unavailable">Na base do projeto</span>}
    </article>)}</div> : <div className="cadu-ds-files__empty"><span><Icon name="file" size={22}/></span><b>{query ? 'Nenhum arquivo encontrado' : filter !== 'all' ? 'Nenhum arquivo deste tipo' : scope === 'project' ? 'Este projeto ainda não tem arquivos' : 'Esta conversa ainda não tem anexos'}</b><p>{query ? 'Tente outro nome ou limpe a busca.' : scope === 'project' ? 'Adicione documentos para manter o material do projeto em um só lugar.' : 'Os arquivos anexados às mensagens vão aparecer aqui.'}</p>{query && <CaduButton variant="secondary" type="button" onClick={() => {setQuery(''); setFilter('all');}}>Limpar busca</CaduButton>}</div>}
  </section>;
}
