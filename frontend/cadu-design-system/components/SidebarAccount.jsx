import React, {useEffect, useState} from 'react';
import {VisualIdentity} from './VisualIdentity';
import './SidebarAccount.css';

const SUMMARY_ENDPOINT = '/workspace/api/creditos/resumo';

const cleanPercent = value => {
  if (value === undefined || value === null || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.min(100, number)) : null;
};

/** Credit usage shared by every sidebar footer: server value first, then the live summary. */
export function useCreditUsage(initial, endpoint = SUMMARY_ENDPOINT) {
  const [percent, setPercent] = useState(() => cleanPercent(initial));
  useEffect(() => {
    let current = true;
    const refresh = () => fetch(endpoint, {credentials: 'same-origin', headers: {Accept: 'application/json'}})
      .then(response => response.ok ? response.json() : Promise.reject(new Error('Resumo indisponível')))
      .then(value => { const next = cleanPercent(value.monthly_usage_percentage); if (current && next !== null) setPercent(next); })
      .catch(() => {});
    refresh();
    const timer = window.setInterval(refresh, 60000);
    return () => { current = false; window.clearInterval(timer); };
  }, [endpoint]);
  return percent;
}

export const firstNameOf = name => String(name || '').trim().split(/\s+/)[0] || 'Conta';

/**
 * One footer for every product sidebar: the credit bar with its percentage on top,
 * then the photo and first name over the agency name. Colours come from --cadu-account-* so
 * light and dark sidebars share the same structure.
 */
export function SidebarAccount({userName, agencyName = '', avatar = '', fallbackAvatar = '', profileUrl, creditsUrl, usagePercent, active = false, className = ''}) {
  const percent = cleanPercent(usagePercent);
  const formatted = percent === null ? '' : `${new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 1}).format(percent)}%`;
  const first = firstNameOf(userName);
  const identity = <>
    <VisualIdentity src={avatar} fallbackSrc={fallbackAvatar} initials={userName || first} label={userName || first} imageAlt={`Foto de ${userName || first}`} className="cadu-sidebar-account__avatar"/>
    <span className="cadu-sidebar-account__text"><strong>{first}</strong>{agencyName && <small>{agencyName}</small>}</span>
  </>;
  return <div className={`cadu-sidebar-account ${className}`.trim()}>
    {creditsUrl && formatted && <a className={`cadu-sidebar-account__usage${percent >= 80 ? ' is-high' : ''}`} href={creditsUrl} aria-label={`Créditos: ${formatted} usados no mês`} title="Créditos e consumo"><span>{formatted}</span><i aria-hidden="true"><b style={{width: `${percent}%`}}/></i></a>}
    {profileUrl
      ? <a className={`cadu-sidebar-account__profile${active ? ' is-active' : ''}`} href={profileUrl} aria-current={active ? 'page' : undefined} aria-label={`Abrir conta de ${userName || first}`} title={userName || first}>{identity}</a>
      : <span className="cadu-sidebar-account__profile">{identity}</span>}
  </div>;
}
