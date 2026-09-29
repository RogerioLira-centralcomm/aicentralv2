import React from 'react';
import {NativeSelect} from './untitled-kit/src/components/base/select/select-native.tsx';

const optionText = value => {
  if (value == null || typeof value === 'boolean') return '';
  if (Array.isArray(value)) return value.map(optionText).join('');
  if (React.isValidElement(value)) return optionText(value.props.children);
  return String(value);
};

const collectOptions = nodes => React.Children.toArray(nodes).flatMap(node => {
  if (!React.isValidElement(node)) return [];
  if (node.type === React.Fragment) return collectOptions(node.props.children);
  if (node.type !== 'option') return [];
  return [{value: String(node.props.value ?? optionText(node.props.children)), label: optionText(node.props.children), disabled: Boolean(node.props.disabled)}];
});

/** Adapts existing option lists to the official native Untitled UI Select. */
export function ReportsNativeSelect({children, className = '', ...props}) {
  return <NativeSelect {...props} options={collectOptions(children)} size="sm" className={`reports-ui-select ${className}`.trim()} />;
}
