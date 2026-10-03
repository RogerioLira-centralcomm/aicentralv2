import React, {useMemo} from 'react';
import {createRoot} from 'react-dom/client';
import {ThemeProvider} from '../ThemeProvider';
import '../styles.css';
import './styles.css';
import {DEFAULT_TOOLS} from './AuthShell';
import {ForgotPassword, Login, ResetPassword, Signup} from './AuthPages';

const PAGES = {login: Login, signup: Signup, 'forgot-password': ForgotPassword, 'reset-password': ResetPassword};

function App({bootstrap}) {
  const tools = useMemo(() => bootstrap.tools?.length ? bootstrap.tools : DEFAULT_TOOLS, [bootstrap.tools]);
  const Page = PAGES[bootstrap.page] || Login;
  return <Page bootstrap={{...bootstrap, tools}}/>;
}

const node = document.getElementById('cadu-auth-root');
const dataNode = document.getElementById('cadu-auth-bootstrap');
if (node && dataNode) {
  try {
    const bootstrap = JSON.parse(dataNode.textContent || '{}');
    createRoot(node).render(<ThemeProvider skin="workspace" theme="light" persistKey="cadu-auth-theme" locked><App bootstrap={bootstrap}/></ThemeProvider>);
  } catch (error) {
    node.innerHTML = '<p role="alert" class="cadu-auth-fallback">Não foi possível abrir esta tela. Atualize a página.</p>';
    console.error(error);
  }
}
