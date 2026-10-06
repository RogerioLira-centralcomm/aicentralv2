import React from 'react';
import {CaduDrawer} from './CaduDrawer';

/** Workspace form container: the same side drawer used by Reports and Planner, with the discard guard. */
export function WorkspaceDrawer({title, detail, onClose, children, size = 'md', className = ''}) {
  return <CaduDrawer open onOpenChange={value => { if (!value) onClose?.(); }} title={title} description={detail} size={size} className={`cadu-ds-workspace-drawer ${className}`.trim()}>
    {children}
  </CaduDrawer>;
}
