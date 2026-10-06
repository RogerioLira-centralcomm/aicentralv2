import React from 'react';
import {SolutionSidebar} from './SolutionSidebar';
import {workspaceMobileDestinationItems} from '../workspaceSolutions';
import {workspaceUserPhoto} from '../workspaceIdentity.mjs';

/**
 * Workspace navigation for internal pages: the same SolutionSidebar used by Reports and Planner.
 * `sections` are the page's own entries (Conta, Marca, Projeto); the global Workspace entries follow.
 */
export function WorkspaceSidebar({bootstrap, active, sections = [], sectionsLabel = '', onNavigate}) {
  const urls = bootstrap.urls || {};
  const global = workspaceMobileDestinationItems(urls).map(item => ({id: `workspace:${item.id}`, label: item.name, icon: item.icon, href: item.href}));
  const groups = [
    ...(sections.length ? [{label: sectionsLabel, items: sections}] : []),
    {label: 'Workspace', items: global},
  ];
  return <SolutionSidebar solution="Workspace" accent="var(--cadu-accent)" storageKey="workspace-sidebar" active={active}
    activeSolutionId="workspace" solutionLogo={bootstrap.caduMark} solutionIcons={bootstrap.solutionIcons || {}} solutionUrls={urls.solutions || {}}
    groups={groups} userName={bootstrap.user?.name || 'Minha conta'} accountLabel={bootstrap.contextName || undefined}
    userAvatar={workspaceUserPhoto(bootstrap.user) || ''} creditsUrl={urls.credits} profileUrl={urls.profile} onNavigate={onNavigate}/>;
}
