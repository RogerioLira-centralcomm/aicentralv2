import React from 'react';
import {Icon} from '../lib/icons';
import {safeUrl} from '../lib/api';

export function LibraryView({library, onClose, onOpenResource}) {
  return <section className="cv-library-view" aria-label="Biblioteca">
    <header className="cv-library-view__header">
      <button type="button" onClick={onClose} aria-label="Voltar à conversa"><Icon name="chevron" size={18}/><span>Conversa</span></button>
      <h2>Biblioteca</h2>
    </header>
    <div className="cv-library-view__scroll">
      {library.loading && <p role="status">Carregando biblioteca…</p>}
      {library.error && <div role="alert"><p>{library.error}</p><button type="button" onClick={onClose}>Voltar à conversa</button></div>}
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
