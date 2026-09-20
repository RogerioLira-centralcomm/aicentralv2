import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './styles.css';
import '../cadu-design-system/styles.css';
import {ThemeProvider} from '../cadu-design-system/ThemeProvider';
import {WorkspaceHome} from '../cadu-design-system/components/WorkspaceHome';
import {WorkspaceProject} from '../cadu-design-system/components/WorkspaceProject';
import {WorkspaceBrands} from '../cadu-design-system/components/WorkspaceBrands';
import {WorkspaceProjects} from '../cadu-design-system/components/WorkspaceProjects';

const root = document.getElementById('cadu-conversations-v2-root');
const bootstrapNode = document.getElementById('cadu-conversations-v2-bootstrap');

if (root && bootstrapNode) {
  try {
    const bootstrap = JSON.parse(bootstrapNode.textContent);
    const workspaceMode = bootstrap.homeMode || bootstrap.projectMode || bootstrap.brandsMode || bootstrap.projectsMode;
    createRoot(root).render(<ThemeProvider skin={workspaceMode ? 'workspace' : 'conversations'} theme={workspaceMode ? 'light' : 'dark'} persistKey={workspaceMode ? 'cadu-workspace-theme' : 'cadu-conversations-theme'}>{bootstrap.homeMode ? <WorkspaceHome bootstrap={bootstrap}/> : bootstrap.projectMode ? <WorkspaceProject bootstrap={bootstrap}/> : bootstrap.brandsMode ? <WorkspaceBrands bootstrap={bootstrap}/> : bootstrap.projectsMode ? <WorkspaceProjects bootstrap={bootstrap}/> : <App bootstrap={bootstrap}/>}</ThemeProvider>);
  } catch (error) {
    root.innerHTML = '<p role="alert" style="padding:24px;color:#edf7f5">Não foi possível abrir a Conversas 2.0. Atualize a página.</p>';
    console.error(error);
  }
}
