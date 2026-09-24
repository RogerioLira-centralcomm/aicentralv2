import React from 'react';
import {Icon} from '../lib/icons';
import {safeUrl} from '../lib/api';

export function LibraryView({library, projectName = '', overview = null, onClose, onOpenResource}) {
  const totalItems = library.groups.reduce((sum, group) => sum + group.items.length, 0);
  return <section className="cv-library-view" aria-label="Biblioteca">
    <header className="cv-library-view__header">
      <button type="button" onClick={onClose} aria-label="Voltar à conversa"><Icon name="chevron" size={18}/><span>Conversa</span></button>
      <h2>{projectName ? 'Arquivos do projeto' : 'Biblioteca'}</h2>
    </header>
    <div className="cv-library-view__scroll">
      {library.loading && <p role="status">Carregando biblioteca…</p>}
      {library.error && <div role="alert"><p>{library.error}</p><button type="button" onClick={onClose}>Voltar à conversa</button></div>}
      {!library.loading && !library.error && overview && <section className="cv-library-overview" aria-label="Visão geral do projeto">
        <header><div><small>Projeto</small><h3>{overview.name || projectName}</h3>{overview.description && <p>{overview.description}</p>}</div>{overview.status && <span className="cv-library-overview__status">{overview.status}</span>}</header>
        <div className="cv-library-overview__stats"><div><b>{overview.fileCount}</b><span>arquivos</span></div><div><b>{overview.conversationCount}</b><span>conversas</span></div><div><b>{overview.brands?.length || 0}</b><span>marcas</span></div><div><b>{totalItems}</b><span>itens nesta biblioteca</span></div></div>
        {!!overview.brands?.length && <div className="cv-library-overview__brands"><span>Marcas vinculadas</span>{overview.brands.map((brand, index) => <b key={brand.ref || brand.name || index}>{brand.name || brand.title || 'Marca'}</b>)}</div>}
      </section>}
      {!library.loading && !library.error && <div className="cv-library-clusters" aria-label="Grupos de arquivos">{library.groups.map(group => <div key={group.id}><span>{group.title}</span><b>{group.items.length}</b></div>)}</div>}
      {!library.loading && !library.error && library.groups.map(group => <section key={group.id} className="cv-library-view__group">
        <header><h3>{group.title}</h3><span>{group.items.length}</span></header>
        {group.items.length ? <div className={group.layout === 'list' ? 'cv-library-view__list' : 'cv-library-view__grid'}>{group.items.map(item => <button type="button" key={item.id} onClick={() => onOpenResource(item)}>
          {group.layout !== 'list' && safeUrl(item.preview || item.url) ? <img src={safeUrl(item.preview || item.url)} alt="" loading="lazy"/> : <span className="cv-library-view__file"><Icon name="file" size={20}/></span>}
          <span><strong>{item.title}</strong>{item.detail && <small>{item.detail}</small>}</span>
        </button>)}</div> : <p>Nenhum item nesta seção.</p>}
      </section>)}
    </div>
  </section>;
}
