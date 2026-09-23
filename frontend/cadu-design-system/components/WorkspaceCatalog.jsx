import React from 'react';

export function CatalogError({message}) {
  if (!message) return null;
  return <div className="cadu-ds-catalog-error" role="alert"><b>Não foi possível carregar este catálogo.</b><span>{message}</span><button type="button" onClick={() => window.location.reload()}>Tentar novamente</button></div>;
}

export function CatalogFilters({items = []}) {
  return <nav className="untitled-catalog-filters" aria-label="Filtros do catálogo">{items.map(item => <a key={item.value} href={item.href} aria-current={item.active ? 'page' : undefined}>{item.label}</a>)}</nav>;
}

export function WorkspaceCatalog({eyebrow, title, description, actionLabel, onAction, error, filters, query, onQueryChange, queryLabel, countLabel, children}) {
  const supportingCopy = description || (title === 'Marcas'
    ? 'Identidades, ativos e projetos organizados por marca.'
    : title === 'Projetos' ? 'Contextos de trabalho prontos para continuar.' : '');
  return <section className="untitled-catalog-page">
    <header className="untitled-catalog-header"><div>{eyebrow && <p>{eyebrow}</p>}<h1>{title}</h1>{supportingCopy && <span>{supportingCopy}</span>}</div><button type="button" onClick={onAction}>+ {actionLabel}</button></header>
    <CatalogError message={error}/>
    <div className="untitled-catalog-controls"><CatalogFilters items={filters}/><label className="untitled-catalog-search"><span aria-hidden="true">⌕</span><input value={query} onChange={event => onQueryChange(event.target.value)} placeholder={queryLabel} aria-label={queryLabel}/></label><small>{countLabel}</small></div>
    {!error && children}
  </section>;
}
