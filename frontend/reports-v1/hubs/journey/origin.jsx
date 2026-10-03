import React, {useState} from 'react';
import {number} from '../shared.jsx';

// Same keys as ORIGIN_GROUPS in reports_journey.py: an unknown ?origem= would make the API answer 400 and hide the picker.
export const ORIGINS = ['direct', 'google_ads', 'organic', 'social', 'referral', 'other', 'unknown'];

const readOrigin = () => {try {const value = new URLSearchParams(location.search).get('origem') || ''; return ORIGINS.includes(value) ? value : '';} catch {return '';}};

/** Origin choice kept in the address bar (?origem=), so a filtered view can be shared and survives a reload. */
export function useOrigin() {
  const [origin, setOriginState] = useState(readOrigin);
  const setOrigin = value => {
    setOriginState(value);
    try {const url = new URL(location.href); if (value) url.searchParams.set('origem', value); else url.searchParams.delete('origem'); history.replaceState(history.state, '', url);} catch {/* address bar is a convenience */}
  };
  return [origin, setOrigin];
}

/** Origin selector: every group with its sessions; Direto and Origem desconhecida always show, even at zero. */
export function OriginPicker({groups, value, onChange, total}) {
  return <div className="rs-nav__origins">
    <div className="rs-segmented rs-segmented--sm" role="group" aria-label="Origem das sessões">
      <button type="button" aria-pressed={!value} onClick={() => onChange('')}>Todas <small>{number(total)}</small></button>
      {groups.filter(item => item.sessions > 0 || ['direct', 'unknown'].includes(item.origin) || item.origin === value).map(item =>
        <button type="button" key={item.origin} aria-pressed={value === item.origin} title={item.hint} onClick={() => onChange(item.origin)}>{item.label} <small>{number(item.sessions)}</small></button>)}
    </div>
  </div>;
}
