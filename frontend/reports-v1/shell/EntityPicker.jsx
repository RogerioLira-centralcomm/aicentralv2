import React, {useState} from 'react';
import {Dialog, DialogTrigger, Popover} from 'react-aria-components';
import {Check, ChevronDown, SearchLg} from '@untitledui/icons';

const initials = name => String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();
const Badge = ({name, muted}) => <span aria-hidden="true" className={`rs-picker__avatar${muted ? ' is-muted' : ''}`}>{muted ? '·' : initials(name)}</span>;

/**
 * Friendly chooser for clients: avatar, name, optional detail line and a search box once the list grows.
 * `items` are {id, name, meta}; `allLabel` adds a leading option for "no filter" and `extra` more fixed options (e.g. Sem cliente).
 */
export function EntityPicker({label, value, items, onChange, allLabel, allValue = '', extra = [], searchAfter = 6}) {
  const [query, setQuery] = useState('');
  const fixed = [...(allLabel ? [{id: allValue, name: allLabel, fixed: true}] : []), ...extra.map(item => ({...item, fixed: true}))];
  const needle = query.trim().toLowerCase();
  const shown = items.filter(item => !needle || `${item.name} ${item.meta || ''}`.toLowerCase().includes(needle));
  const current = [...fixed, ...items].find(item => String(item.id) === String(value)) || fixed[0] || items[0];
  return <DialogTrigger onOpenChange={open => {if (!open) setQuery('');}}>
    <button type="button" className="rs-picker__trigger" aria-label={`${label}: ${current?.name || ''}`} aria-haspopup="dialog">
      <Badge name={current?.name} muted={current?.fixed}/>
      <span className="rs-picker__name">{current?.name || label}</span>
      <ChevronDown size={16} aria-hidden="true"/>
    </button>
    <Popover placement="bottom end" className="rs-picker__popover">
      <Dialog aria-label={label} className="rs-picker__dialog">
        {({close}) => <>
          {items.length > searchAfter && <label className="rs-picker__search"><SearchLg size={16} aria-hidden="true"/>
            <input type="search" autoFocus placeholder={`Buscar ${label.toLowerCase()}`} aria-label={`Buscar ${label.toLowerCase()}`} value={query} onChange={event => setQuery(event.target.value)}/></label>}
          <ul role="listbox" aria-label={label} className="rs-picker__list">
            {[...(needle ? [] : fixed), ...shown].map(item => {
              const selected = String(item.id) === String(value);
              return <li key={`${item.fixed ? 'f' : 'i'}${item.id}`} role="option" aria-selected={selected}>
                <button type="button" className={selected ? 'is-selected' : undefined} onClick={() => {onChange(String(item.id)); close();}}>
                  <Badge name={item.name} muted={item.fixed}/>
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
