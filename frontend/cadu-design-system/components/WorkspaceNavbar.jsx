import React from 'react';
import {CaduSolutionSwitcher} from './WorkspaceSelectors';
import {WorkspaceAccountControl} from './WorkspaceFeedback';

export function WorkspaceNavbar({logo, solutions = [], activeId = 'workspace', className = '', children, actions, user, accountOpen = false, onOpenAccount}) {
  return <header className={`cadu-ds-home-navbar ${className}`.trim()}>
    <CaduSolutionSwitcher logo={logo} solutions={solutions} activeId={activeId}/>
    {children}
    <div className="cadu-ds-project-navbar__spacer"/>
    {actions}
    {user && <div className="cadu-ds-home-navbar__account"><WorkspaceAccountControl user={user} open={accountOpen} onOpen={onOpenAccount}/></div>}
  </header>;
}
