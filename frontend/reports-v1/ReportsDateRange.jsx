import React, {useState} from 'react';
import {Button as AriaButton, CalendarCell, CalendarGrid, Dialog, DialogTrigger, Heading, I18nProvider, Popover, RangeCalendar} from 'react-aria-components';
import {parseDate} from '@internationalized/date';
import {ChevronLeft, ChevronRight, Calendar} from '@untitledui/icons';
import {PRESETS, addDays, formatDay, formatRange, matchPreset, todayIso} from './friendlyDates.js';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
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
    <Button color="secondary" size="sm" className="rdr-trigger" iconLeading={Calendar} aria-label={`Período: ${formatRange(value.start, value.end)}`}>{formatRange(value.start, value.end)}</Button>
    <Popover placement="bottom end" className="rdr-popover">
      <Dialog className="rdr-dialog" aria-label="Escolher período">
        <div className="rdr-body">
          <ul className="rdr-presets" aria-label="Atalhos">{PRESETS.map(item => <li key={item.id}><Button color="tertiary" size="sm" className={`w-full justify-start ${preset === item.id ? 'bg-active text-secondary_hover' : ''}`} onPress={() => setDraft(item.range())}>{item.label}</Button></li>)}</ul>
          <RangeCalendar className="rdr-calendar" aria-label="Período" visibleDuration={{months: 1}} minValue={parseDate(minDate)} maxValue={parseDate(today)}
            value={{start: parseDate(draft.start), end: parseDate(draft.end)}} onChange={range => setDraft({start: range.start.toString(), end: range.end.toString()})}>
            <header><AriaButton slot="previous" aria-label="Mês anterior"><ChevronLeft size={18}/></AriaButton><Heading/><AriaButton slot="next" aria-label="Próximo mês"><ChevronRight size={18}/></AriaButton></header>
            <CalendarGrid>{date => <CalendarCell date={date}/>}</CalendarGrid>
          </RangeCalendar>
        </div>
        <footer>
          <div className="rdr-fields"><span>{formatDay(draft.start)}</span><i aria-hidden="true">–</i><span>{formatDay(draft.end)}</span></div>
          <div className="rdr-actions"><Button color="secondary" size="sm" onPress={() => setOpen(false)}>Cancelar</Button><Button color="primary" size="sm" onPress={apply}>Aplicar</Button></div>
        </footer>
      </Dialog>
    </Popover>
  </DialogTrigger></I18nProvider>;
}
