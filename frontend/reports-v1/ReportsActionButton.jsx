import React from 'react';
import {Button} from './untitled-kit/src/components/base/buttons/button.tsx';

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
  const resolvedType = type || (onClick ? 'button' : 'submit');
  const resolvedColor = color || (className.includes('danger')
    ? 'secondary-destructive'
    : /(?:text-button|inline-link|campaign-open|report-inline)/.test(className)
      ? 'link-color'
      : resolvedType === 'submit' ? 'primary' : 'secondary');
  return <Button
    {...rest}
    type={resolvedType}
    color={resolvedColor}
    isDisabled={Boolean(disabled || isDisabled)}
    onPress={onClick}
    className={`reports-ui-button ${className}`.trim()}
  >{children}</Button>;
}
