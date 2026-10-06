import React from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {LogoTile} from './PlannerUi.jsx';

/**
 * Sticky bar at the foot of a shelf: how many items are in the plan, who they
 * are and the way forward. `chosen` are the ones in view; `count` is the truth.
 */
export function PlanBar({noun, count, chosen = [], href}) {
  if (!count) return null;
  const [one, many] = noun;
  return <div className="channel-bar" role="status">
    <strong>{count} {count === 1 ? one : many} no plano</strong>
    <span className="channel-bar__logos">{chosen.slice(0, 5).map(item => <LogoTile key={item.key} src={item.logo} name={item.name} icon="plan" size="sm"/>)}</span>
    {count > Math.min(chosen.length, 5) && <span className="channel-bar__more">+{count - Math.min(chosen.length, 5)}</span>}
    <a className="channel-bar__all" href={href}>Ver todos</a>
    <a className="channel-bar__go" href={href}>Revisar plano<Icon name="chevron" size={14}/></a>
  </div>;
}
