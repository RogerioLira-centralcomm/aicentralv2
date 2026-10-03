import React from 'react';
import {createRoot} from 'react-dom/client';
import LabApp from './LabApp';
import './styles.css';

const root = document.getElementById('cadu-studio-lab-root');
const data = document.getElementById('cadu-studio-lab-bootstrap');
if (root && data) {
  try {
    createRoot(root).render(<LabApp bootstrap={JSON.parse(data.textContent || '{}')}/>);
  } catch (error) {
    root.textContent = 'Não foi possível abrir o Lab. Atualize a página.';
    console.error(error);
  }
}
