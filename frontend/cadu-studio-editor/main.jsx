import React from 'react';
import {createRoot} from 'react-dom/client';
import {ThemeProvider} from '../cadu-design-system/ThemeProvider';
import StudioEditorApp from './StudioEditorApp';
import './styles.css';
import '../cadu-design-system/styles.css';

const root = document.getElementById('cadu-studio-editor-root');
const bootstrapNode = document.getElementById('cadu-studio-editor-bootstrap');

if (root && bootstrapNode) {
  try {
    const bootstrap = JSON.parse(bootstrapNode.textContent || '{}');
    createRoot(root).render(<ThemeProvider skin="studio" theme="dark" persistKey="cadu-studio-theme"><StudioEditorApp bootstrap={bootstrap}/></ThemeProvider>);
  } catch (error) {
    root.innerHTML = '<p role="alert" style="padding:24px;color:#edf7f5">Não foi possível abrir o Cadu Studio Editor. Atualize a página.</p>';
    console.error(error);
  }
}
