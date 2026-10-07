import React, {useEffect, useId, useRef, useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {LogoTile} from './PlannerUi.jsx';

/**
 * A listbox dropdown drawn by the Planner (the native <select> popup cannot be styled).
 * options: [{value, label, count?, logo?}]. Arrow keys move, Enter picks, Escape closes.
 */
export function PlannerSelect({label, value, options, onChange, ariaLabel, className = ''}) {
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const root = useRef(null);
  const listId = useId();
  const selected = options.findIndex(option => option.value === value);
  // A chosen value the facets no longer list (other filters narrowed them) still shows its own name, never "Todos".
  const current = options[selected] || (value ? {value, label: value} : options[0]);

  useEffect(() => {
    if (!open) return undefined;
    const outside = event => { if (!root.current?.contains(event.target)) setOpen(false); };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  useEffect(() => {
    if (open) root.current?.querySelector('[data-cursor="true"]')?.scrollIntoView({block: 'nearest'});
  }, [open, cursor]);

  const show = () => { setCursor(Math.max(0, selected)); setOpen(true); };
  const pick = option => { setOpen(false); if (option.value !== value) onChange(option.value); root.current?.querySelector('button')?.focus(); };
  const onKeyDown = event => {
    if (event.key === 'Escape') { setOpen(false); return; }
    if (!['ArrowDown', 'ArrowUp', 'Enter', ' ', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    if (!open) { show(); return; }
    if (event.key === 'ArrowDown') setCursor(index => Math.min(options.length - 1, index + 1));
    else if (event.key === 'ArrowUp') setCursor(index => Math.max(0, index - 1));
    else if (event.key === 'Home') setCursor(0);
    else if (event.key === 'End') setCursor(options.length - 1);
    else pick(options[cursor]);
  };

  return <div className={`planner-select ${className}`} ref={root} onKeyDown={onKeyDown}>
    <button type="button" className="planner-select__trigger" aria-haspopup="listbox" aria-expanded={open} aria-controls={listId} aria-label={ariaLabel || label}
      onClick={() => (open ? setOpen(false) : show())}>
      <span className="planner-select__text">{label && <small>{label}</small>}
        <span className="planner-select__value">{current?.logo && <LogoTile src={current.logo} name={current.label} icon="share" size="xs"/>}<b>{current?.label}</b></span></span>
      <Icon name="chevron" size={16}/>
    </button>
    {open && <ul className="planner-select__list" id={listId} role="listbox" aria-label={ariaLabel || label}>
      {options.map((option, index) => <li key={option.value} role="option" aria-selected={option.value === value} data-cursor={index === cursor}
        className={`${option.value === value ? 'is-selected' : ''}${index === cursor ? ' is-cursor' : ''}`}
        onMouseEnter={() => setCursor(index)} onClick={() => pick(option)}>
        {option.logo && <LogoTile src={option.logo} name={option.label} icon="share" size="xs"/>}
        <span>{option.label}</span>
        {option.count !== undefined && <em>{option.count}</em>}
        {option.value === value && <Icon name="check" size={16}/>}
      </li>)}
    </ul>}
  </div>;
}
