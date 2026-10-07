import React from 'react';
import {Input} from '../untitled-kit/input';
import {NativeSelect} from '../untitled-kit/native-select';
import {Textarea} from '../untitled-kit/textarea';

const NATIVE_TYPES = new Set(['checkbox', 'radio', 'file', 'color', 'hidden', 'range', 'date', 'datetime-local', 'time', 'month', 'week']);

/** Text control: the same Input the Workspace uses. Native-only types keep the browser control. */
export function CaduTextField({type = 'text', className, size = 'md', ...rest}) {
  if (NATIVE_TYPES.has(type)) return <input {...rest} type={type} className={className}/>;
  return <Input {...rest} type={type} size={size} inputClassName={className}/>;
}

/** Native select driven by an `options` list or by <option> children. */
export function CaduSelectField({children, options, className = '', size = 'md', ...props}) {
  return <NativeSelect {...props} options={options || collectOptions(children)} size={size} className={`cadu-ds-select ${className}`.trim()}/>;
}

export function CaduTextAreaField(props) {
  return <Textarea {...props}/>;
}

const optionText = value => {
  if (value == null || typeof value === 'boolean') return '';
  if (Array.isArray(value)) return value.map(optionText).join('');
  if (React.isValidElement(value)) return optionText(value.props.children);
  return String(value);
};

function collectOptions(nodes) {
  return React.Children.toArray(nodes).flatMap(node => {
    if (!React.isValidElement(node)) return [];
    // The native list has no groups: an <optgroup> contributes its options, so none of them disappears.
    if (node.type === React.Fragment || node.type === 'optgroup') return collectOptions(node.props.children);
    if (node.type !== 'option') return [];
    return [{value: String(node.props.value ?? optionText(node.props.children)), label: optionText(node.props.children), disabled: Boolean(node.props.disabled)}];
  });
}
