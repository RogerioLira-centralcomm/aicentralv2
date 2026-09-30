import React from 'react';
import {CaduTextAreaField} from '../cadu-design-system/components/CaduField.jsx';

export function ReportsTextArea({className = '', ...props}) {
  return <CaduTextAreaField {...props} className={`reports-ui-textarea ${className}`.trim()}/>;
}
