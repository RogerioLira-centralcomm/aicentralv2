import React from 'react';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {CaduTooltip} from '../cadu-design-system/components/CaduTooltip.jsx';

/** Untitled UI button with the legacy Reports action contract. */
export function ReportsActionButton({
  onClick,
  disabled,
  isDisabled,
  type,
  color,
  className = '',
  children,
  title,
  tooltip,
  shortcut,
  tooltipPlacement,
  ...rest
}) {
  const resolvedType = type || 'button';
  const resolvedColor = color || (className.includes('danger')
    ? 'secondary-destructive'
    : /(?:text-button|inline-link|campaign-open|report-inline)/.test(className)
      ? 'link-color'
      : resolvedType === 'submit' ? 'primary' : 'tertiary');
  // React Aria drops `title`, so a title becomes a real tooltip instead of vanishing.
  const label = tooltip ?? title;
  const button = <Button
    {...rest}
    type={resolvedType}
    color={resolvedColor}
    data-reports-tone={resolvedColor}
    isDisabled={Boolean(disabled || isDisabled)}
    onPress={onClick}
    className={`reports-ui-button ${className}`.trim()}
  >{children}</Button>;
  return label ? <CaduTooltip label={label} shortcut={shortcut} placement={tooltipPlacement}>{button}</CaduTooltip> : button;
}
