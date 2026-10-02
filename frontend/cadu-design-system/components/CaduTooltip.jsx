import React from 'react';
import {Focusable, OverlayArrow, Tooltip, TooltipTrigger} from 'react-aria-components';

/**
 * Untitled UI tooltip. Wraps one pressable child (a react-aria Button or any
 * focusable element) and shows a short label with an optional shortcut hint.
 * React Aria buttons drop the native `title`, so icon-only actions use this.
 */
export function CaduTooltip({label, shortcut, placement = 'top', delay = 350, children}) {
  if (!label) return children;
  const trigger = React.isValidElement(children) && typeof children.type === 'string'
    ? <Focusable>{children}</Focusable>
    : children;
  return <TooltipTrigger delay={delay} closeDelay={0}>
    {trigger}
    <Tooltip placement={placement} offset={8} className="cadu-ds-tooltip">
      <OverlayArrow className="cadu-ds-tooltip__arrow"><svg width={10} height={6} viewBox="0 0 10 6" aria-hidden="true"><path d="M0 0 5 6 10 0"/></svg></OverlayArrow>
      <span>{label}</span>
      {shortcut && <kbd className="cadu-ds-tooltip__kbd">{shortcut}</kbd>}
    </Tooltip>
  </TooltipTrigger>;
}
