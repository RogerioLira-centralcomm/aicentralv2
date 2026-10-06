import React, {useEffect} from 'react';
import {WorkspaceContextSidebar} from './WorkspaceContextSidebar';
import {EntityNavigator} from './WorkspaceEntityPortal';
import {Icon} from './Icon';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';

export function WorkspaceLegacyChrome({bootstrap}) {
  const {isMobile} = useWorkspaceViewport();
  const railActive = {inicio: 'home', conversas: 'conversas', 'conversas-v2': 'conversas', projetos: 'projetos', marcas: 'marcas', conta: 'conta', observabilidade: 'conta'}[bootstrap.active] || '';
  const urls = bootstrap.urls || {};
  const sideNavs = {
    observabilidade: {label: 'Conta', activeId: 'observabilidade', items: [
      ['perfil', 'Perfil', 'brand', 'profile'], ['agencia', 'Agência', 'home', 'agencia'], ['equipe', 'Equipe', 'users', 'equipe'], ['integracoes', 'Integrações', 'plugin', 'integracoes'],
      ['planos', 'Plano', 'plan', 'plans'], ['uso', 'Uso', 'analysis', 'usage'], ['creditos', 'Créditos', 'history', 'credits'], ['faturamento', 'Faturamento', 'file', 'faturamento'], ['observabilidade', 'Observabilidade do Cadu', 'pulse', 'observability']]},
    docs: {label: 'Biblioteca', activeId: 'docs', items: [['docs', 'Documentos', 'file', 'docs'], ['skills', 'Skills personalizadas', 'plugin', 'skills']]},
    skills: {label: 'Biblioteca', activeId: 'skills', items: [['docs', 'Documentos', 'file', 'docs'], ['skills', 'Skills personalizadas', 'plugin', 'skills']]},
  }[bootstrap.active];
  const accountNav = sideNavs && bootstrap.surface !== 'editor' ? sideNavs.items.filter(([, , , key]) => urls[key]).map(([id, label, icon, key]) => ({id, label, icon, href: urls[key]})) : [];
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
    {isMobile ? <WorkspaceMobileChrome title={bootstrap.title || bootstrap.contextName || 'Workspace'} links={bootstrap.urls} logo={bootstrap.caduMark} solutionIcons={bootstrap.solutionIcons}/> : <WorkspaceContextSidebar mode="home" rail bootstrap={bootstrap} links={bootstrap.urls} active={railActive}/>}
    {!isMobile && accountNav.length > 0 && <EntityNavigator label={sideNavs.label} items={accountNav} activeId={sideNavs.activeId} identity={<><span className="cadu-ds-entity-nav__project-mark"><Icon name="home"/></span><span><small>{sideNavs.label}</small><b title={bootstrap.contextName}>{bootstrap.contextName || sideNavs.label}</b></span></>}/>}
  </>;
}
