import React from 'react';
import {createRoot} from 'react-dom/client';
import AudioStudioApp from './AudioStudioApp';
import './styles.css';

const root = document.getElementById('cadu-studio-audio-root');
const data = document.getElementById('cadu-studio-audio-bootstrap');
if (root && data) {
  try {
    createRoot(root).render(<AudioStudioApp bootstrap={JSON.parse(data.textContent || '{}')}/>);
  } catch (error) {
    root.textContent = 'Não foi possível abrir o Studio Áudio. Atualize a página.';
    console.error(error);
  }
}
