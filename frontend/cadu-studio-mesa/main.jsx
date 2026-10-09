import React from 'react';
import {createRoot} from 'react-dom/client';
import {MesaApp} from './MesaApp.jsx';
import {setCatalog} from './formats.js';
import './styles.css';

const boot = JSON.parse(document.getElementById('cadu-studio-mesa-bootstrap')?.textContent || '{}');
setCatalog(boot.formatCatalog);
createRoot(document.getElementById('cadu-studio-mesa-root')).render(<MesaApp boot={boot}/>);
