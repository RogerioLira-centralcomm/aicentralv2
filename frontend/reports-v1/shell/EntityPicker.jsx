import React, {useState} from 'react';
import {Button, Dialog, DialogTrigger, Popover} from 'react-aria-components';
import {Check, ChevronDown, SearchLg} from '@untitledui/icons';

const initials = name => String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();
// A linked brand's logo replaces the initials; a logo that fails to load falls back to them.
function Badge({name, muted, logo}) {
  const [broken, setBroken] = useState(false);
  if (logo && !muted && !broken) return <span aria-hidden="true" className="rs-picker__avatar has-logo"><img src={logo} alt="" onError={() => setBroken(true)}/></span>;
  return <span aria-hidden="true" className={`rs-picker__avatar${muted ? ' is-muted' : ''}`}>{muted ? '·' : initials(name)}</span>;
}

/**
 * Friendly chooser for clients: avatar, name, optional detail line and a search box once the list grows.
 * `items` are {id, name, meta, logo}; `allLabel` adds a leading option for "no filter" and `extra` more fixed options (e.g. Sem cliente).
 */
export function EntityPicker({label, value, items, onChange, allLabel, allValue = '', extra = [], searchAfter = 6, placement = 'bottom end', block = false, compact = false}) {
  const [query, setQuery] = useState('');
  const fixed = [...(allLabel ? [{id: allValue, name: allLabel, fixed: true}] : []), ...extra.map(item => ({...item, fixed: true}))];
  const needle = query.trim().toLowerCase();
  const shown = items.filter(item => !needle || `${item.name} ${item.meta || ''}`.toLowerCase().includes(needle));
  const current = [...fixed, ...items].find(item => String(item.id) === String(value)) || fixed[0] || items[0];
  return <DialogTrigger onOpenChange={open => {if (!open) setQuery('');}}>
    <Button className={`rs-picker__trigger${block ? ' is-block' : ''}${compact ? ' is-compact' : ''}`} aria-label={`${label}: ${current?.name || ''}`}>
      <Badge name={current?.name} muted={current?.fixed} logo={current?.logo}/>
      <span className="rs-picker__name">{current?.name || label}</span>
      <ChevronDown size={16} aria-hidden="true"/>
    </Button>
    <Popover placement={placement} className="rs-picker__popover">
      <Dialog aria-label={label} className="rs-picker__dialog">
        {({close}) => <>
          {items.length > searchAfter && <label className="rs-picker__search"><SearchLg size={16} aria-hidden="true"/>
            <input type="search" autoFocus placeholder={`Buscar ${label.toLowerCase()}`} aria-label={`Buscar ${label.toLowerCase()}`} value={query} onChange={event => setQuery(event.target.value)}/></label>}
          <ul role="listbox" aria-label={label} className="rs-picker__list">
            {[...(needle ? [] : fixed), ...shown].map(item => {
              const selected = String(item.id) === String(value);
              return <li key={`${item.fixed ? 'f' : 'i'}${item.id}`} role="option" aria-selected={selected}>
                <button type="button" className={selected ? 'is-selected' : undefined} onClick={() => {onChange(String(item.id)); close();}}>
                  <Badge name={item.name} muted={item.fixed} logo={item.logo}/>
                  <span className="rs-picker__text"><strong>{item.name}</strong>{item.meta && <small>{item.meta}</small>}</span>
                  {selected && <Check size={16} aria-hidden="true"/>}
                </button>
              </li>;
            })}
            {needle && !shown.length && <li className="rs-picker__empty">Nenhum resultado</li>}
          </ul>
        </>}
      </Dialog>
    </Popover>
  </DialogTrigger>;
}
