import React from 'react';
import {Icon} from './Icon';
import {CaduButton} from './CaduButton';

export function CatalogError({message}) {
  if (!message) return null;
  return <div className="cadu-ds-catalog-error" role="alert"><b>Não foi possível carregar este catálogo.</b><span>{message}</span><button type="button" onClick={() => window.location.reload()}>Tentar novamente</button></div>;
}

export function CatalogFilters({items = []}) {
  return <nav className="untitled-catalog-filters" aria-label="Filtros do catálogo">{items.map(item => <a key={item.value} href={item.href} aria-current={item.active ? 'page' : undefined}>{item.label}{item.count !== undefined && <span>{item.count}</span>}</a>)}</nav>;
}

export function WorkspaceCatalog({eyebrow, title, description, actionLabel, actionSize = 'md', onAction, error, filters, query, onQueryChange, queryLabel, countLabel, children, resultCount, totalCount, searchRef}) {
  const supportingCopy = description || (title === 'Marcas'
    ? 'Identidades, ativos e projetos organizados por marca.'
    : title === 'Projetos' ? 'Contextos de trabalho prontos para continuar.' : '');
  return <section className="untitled-catalog-page">
    <header className="untitled-catalog-header"><div>{eyebrow && <p>{eyebrow}</p>}<h1>{title}</h1>{supportingCopy && <span>{supportingCopy}</span>}</div>{actionLabel && <CaduButton type="button" size={actionSize} iconLeading={<span aria-hidden="true">+</span>} onClick={onAction}>{actionLabel}</CaduButton>}</header>
    <CatalogError message={error}/>
    <div className="untitled-catalog-controls"><CatalogFilters items={filters}/><label className="untitled-catalog-search"><span aria-hidden="true"><Icon name="search" size={17}/></span><input ref={searchRef} type="search" value={query} onChange={event => onQueryChange(event.target.value)} placeholder={queryLabel} aria-label={queryLabel}/>{query && <button type="button" onClick={() => { onQueryChange(''); searchRef?.current?.focus(); }} aria-label="Limpar busca"><Icon name="close" size={16}/></button>}</label><small aria-live="polite">{resultCount !== undefined && totalCount !== undefined && resultCount !== totalCount ? `${resultCount} de ${totalCount} resultados` : countLabel}</small></div>
    {!error && children}
  </section>;
}
