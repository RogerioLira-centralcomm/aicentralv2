import React from 'react';
import StudioNavbar from '../../cadu-studio-ui/StudioNavbar';

export function StudioTopbar({links, projects, project, onProjectChange, bootstrap, sessionName = 'Nova sessão de edição', onHistory = () => window.dispatchEvent(new Event('cadu:studio-history')), onNewSession = () => window.dispatchEvent(new Event('cadu:studio-new-session'))}) {
  const options = projects.map(item => ({id: String(item.id), name: item.name, brandName: item.brand_name || item.brandName || item.client_name || ''}));
  return <StudioNavbar active="editor" links={links} user={bootstrap.user} projects={options} projectId={project?.id ? String(project.id) : ''}
    onProjectChange={onProjectChange} credits={{available: bootstrap.credits, usagePercent: bootstrap.usagePercent}}/>;
}
