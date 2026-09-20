import React from 'react';

function Selector({label, value, items = [], onChange, emptyLabel, className = ''}) {
  return <label className={`cadu-ds-selector ${className}`}>
    <span className="cadu-ds-sr-only">{label}</span>
    <select value={value || ''} onChange={event => onChange?.(event.target.value)} aria-label={label}>
      <option value="">{emptyLabel}</option>
      {items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select>
  </label>;
}

export function CaduSolutionSwitcher({logo, solutions = [], activeId, onSelect}) {
  return <details className="cadu-ds-solution-switcher">
    <summary aria-label="Abrir soluções Cadu">{logo ? <img src={logo} alt="Cadu"/> : <span aria-hidden="true">❮❮</span>}</summary>
    <nav aria-label="Soluções Cadu">{solutions.map(solution => <button key={solution.id} type="button" onClick={() => onSelect?.(solution)} aria-current={activeId === solution.id ? 'page' : undefined}>{solution.icon && <img src={solution.icon} alt=""/>}<span><b>{solution.name}</b><small>{solution.description}</small></span></button>)}</nav>
  </details>;
}

export function AgencySwitcher(props) {
  return <Selector label="Agência ativa" emptyLabel="Selecionar agência" {...props} className="cadu-ds-selector--agency"/>;
}

export function ProjectSelector({agencyName, ...props}) {
  return <Selector label={`Projeto${agencyName ? ` da agência ${agencyName}` : ''}`} emptyLabel="Selecionar projeto" {...props} className="cadu-ds-selector--project"/>;
}
