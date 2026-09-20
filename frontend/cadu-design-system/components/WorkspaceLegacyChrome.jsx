import React, {useEffect, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceNavbar} from './WorkspaceNavbar';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {workspaceSolutionItems} from '../workspaceSolutions';

export function WorkspaceLegacyChrome({bootstrap}) {
  const [accountOpen, setAccountOpen] = useState(false);
  const solutions = workspaceSolutionItems(bootstrap);
  const active = {inicio: 'home', projetos: 'projects', marcas: 'brands', docs: 'docs', skills: 'skills'}[bootstrap.active] || bootstrap.active;
  useEffect(() => {
    const root = document.getElementById('cadu-workspace-legacy-chrome-root');
    const shell = root?.closest('.workspace-app-shell');
    const main = shell?.querySelector('.workspace-app-main');
    if (!shell || !main) return undefined;
    const surface = bootstrap.surface || ({docs: 'table', observabilidade: 'table', integracoes: 'catalog', skills: 'catalog', conversas: 'conversation', marcas: 'detail', projetos: 'detail'}[bootstrap.active] || 'settings');
    shell.dataset.workspaceReactShell = 'true';
    main.dataset.workspaceSurface = surface;
    return () => {
      delete shell.dataset.workspaceReactShell;
      delete main.dataset.workspaceSurface;
    };
  }, [bootstrap.active, bootstrap.surface]);
  const navigation = [
    ['home', 'Início', bootstrap.urls.home],
    ['projects', 'Projetos', bootstrap.urls.projects],
    ['brands', 'Marcas', bootstrap.urls.brands],
    ['docs', 'Docs', bootstrap.urls.docs],
    ['skills', 'Skills', bootstrap.urls.skills],
  ].filter(([, , href]) => href).map(([id, title, href]) => ({id, kind: 'navigation', title, href, active: active === id}));
  const open = item => item?.href && window.location.assign(item.href);
  return <>
    <WorkspaceNavbar className="cadu-ds-legacy-navbar" logo={bootstrap.caduMark} solutions={solutions} user={bootstrap.user} onOpenAccount={() => setAccountOpen(true)}><strong>{bootstrap.title || 'Workspace'}</strong></WorkspaceNavbar>
    <CaduDock shortcutItems={navigation} usagePercent={bootstrap.usagePercent} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenResource={open} onOpenUsage={() => setAccountOpen(true)}/>
    <WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>
  </>;
}
