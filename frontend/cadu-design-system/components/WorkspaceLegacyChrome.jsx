import React, {useEffect} from 'react';
import {WorkspaceContextSidebar} from './WorkspaceContextSidebar';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';

export function WorkspaceLegacyChrome({bootstrap}) {
  const {isMobile} = useWorkspaceViewport();
  const railActive = {inicio: 'home', conversas: 'conversas', 'conversas-v2': 'conversas', projetos: 'projetos', marcas: 'marcas', conta: 'conta'}[bootstrap.active] || '';
  useEffect(() => {
    const root = document.getElementById('cadu-workspace-legacy-chrome-root');
    const shell = root?.closest('.workspace-app-shell');
    const main = shell?.querySelector('.workspace-app-main');
    if (!shell || !main) return undefined;
    const surface = bootstrap.surface || ({docs: 'table', observabilidade: 'table', skills: 'catalog', conversas: 'conversation', marcas: 'detail', projetos: 'detail'}[bootstrap.active] || 'settings');
    shell.dataset.workspaceReactShell = 'true';
    main.dataset.workspaceSurface = surface;
    return () => {
      delete shell.dataset.workspaceReactShell;
      delete main.dataset.workspaceSurface;
    };
  }, [bootstrap.active, bootstrap.surface]);
  return <>
    {isMobile ? <WorkspaceMobileChrome title={bootstrap.title || bootstrap.contextName || 'Workspace'} links={bootstrap.urls}/> : <WorkspaceContextSidebar mode="home" rail bootstrap={bootstrap} links={bootstrap.urls} active={railActive}/>}
  </>;
}
