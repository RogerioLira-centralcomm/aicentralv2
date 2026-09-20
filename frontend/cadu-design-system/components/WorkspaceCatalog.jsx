import React from 'react';

export function CatalogError({message}) {
  if (!message) return null;
  return <div className="cadu-ds-catalog-error" role="alert"><b>Não foi possível carregar este catálogo.</b><span>{message}</span><button type="button" onClick={() => window.location.reload()}>Tentar novamente</button></div>;
}

export function CatalogFilters({items = []}) {
  return <nav className="cadu-ds-catalog-filters" aria-label="Filtros do catálogo">{items.map(item => <a key={item.value} href={item.href} aria-current={item.active ? 'page' : undefined}>{item.label}</a>)}</nav>;
}

export function WorkspaceCatalog({eyebrow, title, description, actionLabel, onAction, error, filters, query, onQueryChange, queryLabel, countLabel, children}) {
  return <section className="cadu-ds-brands-content">
    <header><div><p>{eyebrow}</p><h1>{title}</h1><span>{description}</span></div><button type="button" className="is-primary" onClick={onAction}>{actionLabel}</button></header>
    <CatalogError message={error}/>
    <CatalogFilters items={filters}/>
    <div className="cadu-ds-brands-tools"><input value={query} onChange={event => onQueryChange(event.target.value)} placeholder={queryLabel} aria-label={queryLabel}/><span>{countLabel}</span></div>
    {!error && children}
  </section>;
}
