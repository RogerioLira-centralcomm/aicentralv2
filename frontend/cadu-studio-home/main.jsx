import React from 'react';
import {createRoot} from 'react-dom/client';
import StudioHomeApp from './StudioHomeApp';
import './styles.css';

const root = document.getElementById('cadu-studio-home-root');
const data = document.getElementById('cadu-studio-home-bootstrap');
if (root && data) {
  try {
    createRoot(root).render(<StudioHomeApp bootstrap={JSON.parse(data.textContent || '{}')}/>);
  } catch (error) {
    root.textContent = 'Não foi possível abrir o Studio. Atualize a página.';
    console.error(error);
  }
}
