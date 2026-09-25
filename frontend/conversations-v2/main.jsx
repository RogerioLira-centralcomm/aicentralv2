import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './styles.css';
import '../cadu-design-system/styles.css';
import '../cadu-design-system/workspace-chrome.css';
import './components/ArtifactPane.css';
import {ThemeProvider, WorkspaceAccount, WorkspaceBrand, WorkspaceBrands, WorkspaceHome, WorkspaceLegacyChrome, WorkspaceNotificationsProvider, WorkspaceProject, WorkspaceProjects} from '../cadu-design-system';

class ChatRenderBoundary extends React.Component {
  state = {error: null};

  static getDerivedStateFromError(error) {
    return {error};
  }

  componentDidCatch(error, info) {
    console.error('Falha ao renderizar o Cadu Chat', error, info);
  }

  render() {
    if (this.state.error) {
      return <section role="alert" style={{display:'grid', minHeight:'100dvh', placeContent:'center', gap:12, padding:24, background:'#101719', color:'#eef5f3', fontFamily:'Inter,system-ui,sans-serif'}}>
        <strong style={{fontSize:18}}>Não foi possível abrir o chat.</strong>
        <span style={{maxWidth:560, color:'#a9bfba', fontSize:13, lineHeight:1.5}}>Ocorreu um erro ao montar a tela. Atualize a página; os detalhes foram registrados para diagnóstico.</span>
        <button type="button" onClick={() => window.location.reload()} style={{justifySelf:'start', minHeight:38, padding:'0 14px', border:0, borderRadius:8, background:'#65d8cb', color:'#052522', fontWeight:700, cursor:'pointer'}}>Atualizar chat</button>
      </section>;
    }
    return this.props.children;
  }
}

const root = document.getElementById('cadu-conversations-v2-root') || document.getElementById('cadu-workspace-legacy-chrome-root');
const bootstrapNode = document.getElementById('cadu-conversations-v2-bootstrap') || document.getElementById('cadu-workspace-legacy-chrome-bootstrap');

if (root && bootstrapNode) {
  try {
    const bootstrap = JSON.parse(bootstrapNode.textContent);
    const workspaceMode = bootstrap.homeMode || bootstrap.projectMode || bootstrap.brandMode || bootstrap.brandsMode || bootstrap.projectsMode || bootstrap.accountMode || bootstrap.legacyMode;
    const surface = bootstrap.homeMode ? <WorkspaceHome bootstrap={bootstrap}/> : bootstrap.projectMode ? <WorkspaceProject bootstrap={bootstrap}/> : bootstrap.brandMode ? <WorkspaceBrand bootstrap={bootstrap}/> : bootstrap.brandsMode ? <WorkspaceBrands bootstrap={bootstrap}/> : bootstrap.projectsMode ? <WorkspaceProjects bootstrap={bootstrap}/> : bootstrap.accountMode ? <WorkspaceAccount bootstrap={bootstrap}/> : bootstrap.legacyMode ? <WorkspaceLegacyChrome bootstrap={bootstrap}/> : <App bootstrap={bootstrap}/>;
    createRoot(root).render(<ChatRenderBoundary><ThemeProvider skin={workspaceMode ? 'workspace' : 'conversations'} theme={workspaceMode ? 'light' : 'dark'} persistKey={workspaceMode ? 'cadu-workspace-theme' : 'cadu-conversations-theme'} locked={!workspaceMode}><WorkspaceNotificationsProvider bootstrap={bootstrap}>{surface}</WorkspaceNotificationsProvider></ThemeProvider></ChatRenderBoundary>);
  } catch (error) {
    root.innerHTML = `<p role="alert" style="padding:24px;color:${root.classList.contains('cv-account-root') ? '#17302c' : '#edf7f5'}">Não foi possível abrir esta área. Atualize a página.</p>`;
    console.error(error);
  }
} else if (root) {
  root.innerHTML = '<p role="alert" style="padding:24px;color:#edf7f5">A configuração do chat não carregou. Atualize a página; se o problema continuar, avise o suporte.</p>';
  console.error('Não foi possível montar o Cadu Chat: elemento de configuração ausente.');
}
