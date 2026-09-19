import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './styles.css';
import '../cadu-design-system/styles.css';
import {ThemeProvider} from '../cadu-design-system/ThemeProvider';

const root = document.getElementById('cadu-conversations-v2-root');
const bootstrapNode = document.getElementById('cadu-conversations-v2-bootstrap');

if (root && bootstrapNode) {
  try {
    const bootstrap = JSON.parse(bootstrapNode.textContent);
    createRoot(root).render(<ThemeProvider skin={bootstrap.homeMode ? 'workspace' : 'conversations'} theme="dark"><App bootstrap={bootstrap}/></ThemeProvider>);
  } catch (error) {
    root.innerHTML = '<p role="alert" style="padding:24px;color:#edf7f5">Não foi possível abrir a Conversas 2.0. Atualize a página.</p>';
    console.error(error);
  }
}
