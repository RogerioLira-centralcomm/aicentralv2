import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './styles.css';
import '../cadu-design-system/styles.css';
import {ThemeProvider, WorkspaceAccount, WorkspaceBrand, WorkspaceBrands, WorkspaceHome, WorkspaceLegacyChrome, WorkspaceProject, WorkspaceProjects} from '../cadu-design-system';

const root = document.getElementById('cadu-conversations-v2-root') || document.getElementById('cadu-workspace-legacy-chrome-root');
const bootstrapNode = document.getElementById('cadu-conversations-v2-bootstrap') || document.getElementById('cadu-workspace-legacy-chrome-bootstrap');

if (root && bootstrapNode) {
  try {
    const bootstrap = JSON.parse(bootstrapNode.textContent);
    const workspaceMode = bootstrap.homeMode || bootstrap.projectMode || bootstrap.brandMode || bootstrap.brandsMode || bootstrap.projectsMode || bootstrap.accountMode || bootstrap.legacyMode;
    createRoot(root).render(<ThemeProvider skin={workspaceMode ? 'workspace' : 'conversations'} theme={workspaceMode ? 'light' : 'dark'} persistKey={workspaceMode ? 'cadu-workspace-theme' : 'cadu-conversations-theme'}>{bootstrap.homeMode ? <WorkspaceHome bootstrap={bootstrap}/> : bootstrap.projectMode ? <WorkspaceProject bootstrap={bootstrap}/> : bootstrap.brandMode ? <WorkspaceBrand bootstrap={bootstrap}/> : bootstrap.brandsMode ? <WorkspaceBrands bootstrap={bootstrap}/> : bootstrap.projectsMode ? <WorkspaceProjects bootstrap={bootstrap}/> : bootstrap.accountMode ? <WorkspaceAccount bootstrap={bootstrap}/> : bootstrap.legacyMode ? <WorkspaceLegacyChrome bootstrap={bootstrap}/> : <App bootstrap={bootstrap}/>}</ThemeProvider>);
  } catch (error) {
    root.innerHTML = `<p role="alert" style="padding:24px;color:${root.classList.contains('cv-account-root') ? '#17302c' : '#edf7f5'}">Não foi possível abrir esta área. Atualize a página.</p>`;
    console.error(error);
  }
}
