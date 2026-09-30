import React from 'react';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';

/** Untitled UI button with the legacy Reports action contract. */
export function ReportsActionButton({
  onClick,
  disabled,
  isDisabled,
  type,
  color,
  className = '',
  children,
  ...rest
}) {
  const resolvedType = type || 'button';
  const resolvedColor = color || (className.includes('danger')
    ? 'secondary-destructive'
    : /(?:text-button|inline-link|campaign-open|report-inline)/.test(className)
      ? 'link-color'
      : resolvedType === 'submit' ? 'primary' : 'tertiary');
  return <Button
    {...rest}
    type={resolvedType}
    color={resolvedColor}
    data-reports-tone={resolvedColor}
    isDisabled={Boolean(disabled || isDisabled)}
    onPress={onClick}
    className={`reports-ui-button ${className}`.trim()}
  >{children}</Button>;
}
