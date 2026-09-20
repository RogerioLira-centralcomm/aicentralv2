import React, {useEffect, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {WorkspaceContextSidebar} from './WorkspaceContextSidebar';
import {openWorkspaceDetail} from '../workspaceNavigation';

export function WorkspaceLegacyChrome({bootstrap}) {
  const [accountOpen, setAccountOpen] = useState(false);
  const accountSurface = Boolean(bootstrap.accountSurface);
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
  return <>
    <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} shortcutItems={bootstrap.dock?.items || []} usagePercent={bootstrap.usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccountOpen(true)}/>
    {accountSurface && <WorkspaceContextSidebar mode="account" active={bootstrap.active} links={bootstrap.urls} agencyName={bootstrap.contextName || 'Cliente'}/>}
  </>;
}
