import React from 'react';
import {TextAreaBase} from '../cadu-design-system/untitled-kit/textarea-base.tsx';

export function ReportsTextArea({className = '', ...props}) {
  return <TextAreaBase {...props} size="sm" className={`reports-ui-textarea ${className}`.trim()} />;
}
