import React, {useRef} from 'react';

function Selector({label, value, items = [], onChange, emptyLabel, className = ''}) {
  const menu = useRef(null);
  const selected = items.find(item => String(item.id) === String(value));
  const choose = id => { onChange?.(id); menu.current?.removeAttribute('open'); };
  return <details ref={menu} className={`cadu-ds-selector ${className}`}>
    <summary aria-label={label}><span>{selected?.name || emptyLabel}</span><i aria-hidden="true">⌄</i></summary>
    <div className="cadu-ds-selector-menu" role="menu" aria-label={label}>
      <button type="button" role="menuitem" aria-current={!value || undefined} onClick={() => choose('')}>{emptyLabel}</button>
      {items.map(item => <button key={item.id} type="button" role="menuitem" aria-current={String(item.id) === String(value) ? 'true' : undefined} onClick={() => choose(item.id)}>{item.name}</button>)}
    </div>
  </details>;
}

export function CaduSolutionSwitcher({logo, solutions = [], activeId, onSelect}) {
  return <details className="cadu-ds-solution-switcher">
    <summary aria-label="Abrir soluções Cadu">{logo ? <img src={logo} alt="Cadu"/> : <span aria-hidden="true">❮❮</span>}</summary>
    <nav aria-label="Soluções Cadu">{solutions.map(solution => solution.href
      ? <a key={solution.id} href={solution.href} aria-current={activeId === solution.id ? 'page' : undefined}>{solution.icon && <img src={solution.icon} alt=""/>}<span><b>{solution.name}</b><small>{solution.description}</small></span></a>
      : <button key={solution.id} type="button" onClick={() => onSelect?.(solution)} aria-current={activeId === solution.id ? 'page' : undefined}>{solution.icon && <img src={solution.icon} alt=""/>}<span><b>{solution.name}</b><small>{solution.description}</small></span></button>)}</nav>
  </details>;
}

export function AgencySwitcher(props) {
  return <Selector label="Agência ativa" emptyLabel="Selecionar agência" {...props} className="cadu-ds-selector--agency"/>;
}

export function ProjectSelector({agencyName, ...props}) {
  return <Selector label={`Projeto${agencyName ? ` da agência ${agencyName}` : ''}`} emptyLabel="Selecionar projeto" {...props} className="cadu-ds-selector--project"/>;
}
