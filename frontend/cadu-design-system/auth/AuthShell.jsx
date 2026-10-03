import React from 'react';
import {FlashMessages} from './AuthFields';
import {copyFor} from './brandCopy';

export const DEFAULT_TOOLS = [
  {id: 'workspace', name: 'Workspace', description: 'Projetos e contexto', icon: '/static/images/cadu/products/cadu-icon.png'},
  {id: 'planner', name: 'Planner', description: 'Planos e cenários', icon: '/static/images/cadu/products/planner-icon.png'},
  {id: 'studio', name: 'Studio', description: 'Criação e análise', icon: '/static/images/cadu/products/studio-icon.png'},
  {id: 'reports', name: 'Reports', description: 'Relatórios e resultados', icon: '/static/images/cadu/products/connect-icon.png'},
  {id: 'skills', name: 'Skills', description: 'Recursos e automações', icon: '/static/images/cadu/products/skills-icon.png'},
];

function Brand({bootstrap}) {
  return <a className="cadu-auth-brand" href={bootstrap.brandUrl || '#'} aria-label={`Ir para ${bootstrap.brandName || 'Cadu Workspace'}`}>
    <img src={bootstrap.logoUrl} alt="" />
    <span>{bootstrap.brandName || 'Cadu Workspace'}</span>
  </a>;
}

const SLIDES = {
  cadu: [
    {image: '/static/images/cadu/public-people/cadu-login-v1.jpg', kicker: 'Workspace', text: 'Cada cliente com o contexto por perto.'},
    {image: '/static/images/cadu/public-people/cadu-reports-detail-v1.jpg', kicker: 'Reports', text: 'Relatórios com dados reais, prontos para o cliente.'},
    {image: '/static/images/cadu/public-people/cadu-planner-session-v1.jpg', kicker: 'Planner', text: 'Planos e cenários que a equipe constrói junta.'},
    {image: '/static/images/cadu/public-people/cadu-studio-detail-v1.jpg', kicker: 'Studio', text: 'Criação e análise sem trocar de ferramenta.'},
    {image: '/static/images/cadu/public-people/cadu-connected-sources-v1.jpg', kicker: 'Fontes conectadas', text: 'Google Ads, site e CRM falando a mesma língua.'},
  ],
  centralx: [
    {image: '/static/images/centralx-login-city-v1.png', kicker: 'CentralX', text: 'O acesso interno da CentralComm.'},
    {image: '/static/images/centralx-login-city-v3.png', kicker: 'Operação', text: 'Clientes, mídia e entregas num só lugar.'},
    {image: '/static/images/centralx-login-city-v2.png', kicker: 'Resultados', text: 'Do dado ao relatório, com a equipe inteira.'},
  ],
};
const SLIDE_MS = 6500;

/** Full-screen background: slides cross-fade (opacity only), pause when the tab is hidden or motion is reduced. */
function Backdrop({bootstrap}) {
  const slides = SLIDES[bootstrap.product] || SLIDES.cadu;
  const [index, setIndex] = React.useState(0);
  React.useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return undefined;
    const timer = setInterval(() => { if (!document.hidden) setIndex(i => (i + 1) % slides.length); }, SLIDE_MS);
    return () => clearInterval(timer);
  }, [slides.length]);
  const current = slides[index];
  return <>
    <div className="cadu-auth-backdrop" aria-hidden="true">
      {slides.map((slide, i) => <div key={slide.image} className={`cadu-auth-slide ${i === index ? 'is-active' : ''}`}
        style={{backgroundImage: i === 0 || Math.abs(i - index) <= 1 || index === slides.length - 1 ? `url(${slide.image})` : undefined}} />)}
      <div className="cadu-auth-backdrop-shade" />
    </div>
    <div className="cadu-auth-caption" aria-hidden="true">
      <span>{current.kicker}</span>
      <strong key={index}>{current.text}</strong>
      <i>{slides.map((slide, i) => <b key={slide.image} className={i === index ? 'is-active' : ''} />)}</i>
    </div>
  </>;
}

/** Full-screen hand-off after a successful-looking submit. Only shown if the server takes a while to answer. */
function AuthTransition({bootstrap, signup}) {
  const copy = copyFor(bootstrap);
  return <div className="cadu-auth-transition" role="status" aria-live="polite">
    <div className="cadu-auth-transition-mark"><img src={bootstrap.caduLogoUrl || '/static/images/cadu/products/cadu-icon.png'} alt="" /></div>
    <strong>{signup ? 'Criando sua conta' : copy.transitionTitle}</strong>
    <span>{signup ? 'Preparando a base do seu primeiro projeto…' : copy.transitionText}</span>
  </div>;
}

/**
 * Layout of every access screen: full-screen backdrop, brand header and one card that always fits the first screen.
 * Tablets and phones keep the same backdrop, darker, so a keyboard never has to share space with anything else.
 */
export function AuthFrame({bootstrap, children, signup = false, overlay = false}) {
  const tools = bootstrap.tools?.length ? bootstrap.tools : DEFAULT_TOOLS;
  return <div className={`cadu-auth-page ${signup ? 'is-signup' : ''}`}>
    <Backdrop bootstrap={bootstrap}/>
    <header className="cadu-auth-header"><Brand bootstrap={bootstrap}/></header>
    <main className="cadu-auth-main">
      <section className="cadu-auth-card">
        <FlashMessages messages={bootstrap.messages}/>
        {children}
      </section>
    </main>
    {signup && <ul className="cadu-auth-chips" aria-label="Ferramentas incluídas">{tools.map(tool => <li key={tool.id}><img src={tool.icon} alt="" />{tool.name}</li>)}</ul>}
    {overlay && <AuthTransition bootstrap={bootstrap} signup={signup}/>}
  </div>;
}

export function PageHeading({eyebrow, title, description}) {
  return <header className="cadu-auth-heading">
    {eyebrow && <p className="cadu-auth-eyebrow">{eyebrow}</p>}
    <h1>{title}</h1>
    {description && <p>{description}</p>}
  </header>;
}
