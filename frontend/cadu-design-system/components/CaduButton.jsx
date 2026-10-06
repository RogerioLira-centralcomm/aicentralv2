import React from 'react';
import {Button as UntitledButton} from '../untitled-kit/button';

const colors = {
  primary: 'primary',
  secondary: 'secondary',
  tertiary: 'tertiary',
  danger: 'primary-destructive',
  link: 'link-color',
};

/** Workspace action built from the official Untitled UI React v8 Button. */
export function CaduButton({variant = 'primary', size = 'sm', loading = false, disabled = false, onClick, onPress, className = '', children, ...props}) {
  return <UntitledButton color={colors[variant] || colors.primary} size={size} isLoading={loading} isDisabled={disabled} onPress={onPress || onClick} className={className} data-cadu-untitled-button="" data-cadu-variant={variant} {...props}>{children}</UntitledButton>;
}
