import React from 'react';
import {createRoot} from 'react-dom/client';
import {LeadsApp} from './LeadsApp.jsx';
import './styles.css';

const boot = JSON.parse(document.getElementById('leads-v3-bootstrap')?.textContent || '{}');
createRoot(document.getElementById('leads-v3-root')).render(<LeadsApp boot={boot}/>);
