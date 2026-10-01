import React, {useState} from 'react';
import {Button, CalendarCell, CalendarGrid, Dialog, DialogTrigger, Heading, I18nProvider, Popover, RangeCalendar} from 'react-aria-components';
import {parseDate} from '@internationalized/date';
import {ChevronLeft, ChevronRight, Calendar} from '@untitledui/icons';
import {PRESETS, addDays, formatDay, formatRange, matchPreset, todayIso} from './friendlyDates.js';
import './date-range.css';

/** Untitled-style range picker: presets on the left, calendar in the middle, apply/cancel at the bottom. */
export function ReportsDateRange({value, onChange, maxDays = 90}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value);
  const today = todayIso();
  const minDate = addDays(today, -(maxDays - 1));
  const begin = next => {if (next) setDraft(value); setOpen(next);};
  const apply = () => {onChange(draft); setOpen(false);};
  const preset = matchPreset(draft.start, draft.end);
  return <I18nProvider locale="pt-BR"><DialogTrigger isOpen={open} onOpenChange={begin}>
    <Button className="rdr-trigger" aria-label={`Período: ${formatRange(value.start, value.end)}`}><Calendar size={16} aria-hidden="true"/><span>{formatRange(value.start, value.end)}</span><ChevronRight size={16} className="rdr-caret" aria-hidden="true"/></Button>
    <Popover placement="bottom end" className="rdr-popover">
      <Dialog className="rdr-dialog" aria-label="Escolher período">
        <div className="rdr-body">
          <ul className="rdr-presets" aria-label="Atalhos">{PRESETS.map(item => <li key={item.id}><button type="button" className={preset === item.id ? 'is-active' : ''} onClick={() => setDraft(item.range())}>{item.label}</button></li>)}</ul>
          <RangeCalendar className="rdr-calendar" aria-label="Período" visibleDuration={{months: 1}} minValue={parseDate(minDate)} maxValue={parseDate(today)}
            value={{start: parseDate(draft.start), end: parseDate(draft.end)}} onChange={range => setDraft({start: range.start.toString(), end: range.end.toString()})}>
            <header><Button slot="previous" aria-label="Mês anterior"><ChevronLeft size={18}/></Button><Heading/><Button slot="next" aria-label="Próximo mês"><ChevronRight size={18}/></Button></header>
            <CalendarGrid>{date => <CalendarCell date={date}/>}</CalendarGrid>
          </RangeCalendar>
        </div>
        <footer>
          <div className="rdr-fields"><span>{formatDay(draft.start)}</span><i aria-hidden="true">–</i><span>{formatDay(draft.end)}</span></div>
          <div className="rdr-actions"><button type="button" className="rdr-secondary" onClick={() => setOpen(false)}>Cancelar</button><button type="button" className="rdr-primary" onClick={apply}>Aplicar</button></div>
        </footer>
      </Dialog>
    </Popover>
  </DialogTrigger></I18nProvider>;
}
