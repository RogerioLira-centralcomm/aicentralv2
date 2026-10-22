import React from 'react';
import {createRoot} from 'react-dom/client';
import {LeadsApp} from './LeadsApp.jsx';
import {AskProvider} from './ui.jsx';
import './styles.css';

/** Um erro de renderização não deixa a mesa em branco: mostra o aviso e o botão de recarregar. */
class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = {error: null}; }
  static getDerivedStateFromError(error) { return {error}; }
  componentDidCatch(error, info) { console.error('Leads v3:', error, info?.componentStack); }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="lv3-empty lv3-crash" role="alert">
        <strong>A mesa de leads encontrou um erro.</strong>
        <p>Nada foi perdido no banco. Recarregue a página para continuar.</p>
        <button type="button" className="lv3-btn lv3-btn--primary lv3-btn--md" onClick={() => window.location.reload()}>Recarregar</button>
      </div>
    );
  }
}

const boot = JSON.parse(document.getElementById('leads-v3-bootstrap')?.textContent || '{}');
createRoot(document.getElementById('leads-v3-root')).render(<ErrorBoundary><AskProvider><LeadsApp boot={boot}/></AskProvider></ErrorBoundary>);
