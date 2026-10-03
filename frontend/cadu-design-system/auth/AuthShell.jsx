import React from 'react';
import {Check} from '@untitledui/icons';
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

export function ToolRail({tools, compact = false}) {
  return <aside className={`cadu-auth-tools ${compact ? 'is-compact' : ''}`} aria-label="Ferramentas incluídas no Cadu">
    <div className="cadu-auth-tools-intro">
      <span className="cadu-auth-tools-kicker">Cadu Workspace</span>
      <h2>Uma conta para o trabalho continuar.</h2>
      <p>Projeto, criação e resultado usam a mesma base.</p>
    </div>
    <ul>{tools.map(tool => <li key={tool.id}>
      <span className="cadu-auth-tool-icon"><img src={tool.icon} alt="" /></span>
      <span><strong>{tool.name}</strong><small>{tool.description}</small></span>
      <Check size={15} aria-hidden="true"/>
    </li>)}</ul>
  </aside>;
}

function VisualPanel({bootstrap, signup = false}) {
  const copy = copyFor(bootstrap);
  return <aside className={`cadu-auth-visual ${signup ? 'is-signup' : ''}`} style={{'--cadu-auth-image': `url(${bootstrap.imageUrl})`}} aria-hidden="true">
    <div className="cadu-auth-visual-overlay" />
    <div className="cadu-auth-visual-copy">
      <span>{signup ? 'Tudo conectado' : copy.visualKicker}</span>
      <strong>{signup ? 'Seu primeiro projeto já começa com uma base.' : copy.visualText}</strong>
    </div>
  </aside>;
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
 * Layout of every access screen: brand header, one card, and an optional side panel.
 * Wide screens split card | panel; tablets and phones use a single centered column so a keyboard never
 * has to share the screen with a decorative image.
 */
export function AuthFrame({bootstrap, children, visual = true, signup = false, overlay = false}) {
  const tools = bootstrap.tools?.length ? bootstrap.tools : DEFAULT_TOOLS;
  const side = signup
    ? <aside className="cadu-auth-signup-rail"><VisualPanel bootstrap={bootstrap} signup/><ToolRail tools={tools}/></aside>
    : visual ? <VisualPanel bootstrap={bootstrap}/> : null;
  return <div className={`cadu-auth-page ${signup ? 'is-signup' : ''} ${visual ? 'has-visual' : ''}`}>
    <header className="cadu-auth-header"><Brand bootstrap={bootstrap}/></header>
    <main className="cadu-auth-main">
      <section className="cadu-auth-card">
        <FlashMessages messages={bootstrap.messages}/>
        {children}
      </section>
      {side}
    </main>
    {signup && <details className="cadu-auth-mobile-tools"><summary>Ferramentas incluídas no Cadu</summary><ToolRail tools={tools} compact/></details>}
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
