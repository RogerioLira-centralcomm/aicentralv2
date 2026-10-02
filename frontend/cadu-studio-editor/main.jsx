import React from 'react';
import {createRoot} from 'react-dom/client';
import StudioEditorApp from './StudioEditorApp';
import './styles.css';

const root = document.getElementById('cadu-studio-editor-root');
const bootstrapNode = document.getElementById('cadu-studio-editor-bootstrap');

if (root && bootstrapNode) {
  try {
    const bootstrap = JSON.parse(bootstrapNode.textContent || '{}');
    document.documentElement.dataset.caduTheme = 'dark';
    createRoot(root).render(<StudioEditorApp bootstrap={bootstrap}/>);
  } catch (error) {
    root.innerHTML = '<p role="alert" style="padding:24px;color:#edf7f5">Não foi possível abrir o Cadu Studio Editor. Atualize a página.</p>';
    console.error(error);
  }
}
