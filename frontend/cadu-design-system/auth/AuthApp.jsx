import React, {useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ThemeProvider} from '../ThemeProvider';
import '../styles.css';
import './styles.css';

const DEFAULT_TOOLS = [
  {id: 'workspace', name: 'Workspace', description: 'Projetos e contexto', icon: '/static/images/cadu/products/cadu-icon.png'},
  {id: 'planner', name: 'Planner', description: 'Planos e cenários', icon: '/static/images/cadu/products/planner-icon.png'},
  {id: 'studio', name: 'Studio', description: 'Criação e análise', icon: '/static/images/cadu/products/studio-icon.png'},
  {id: 'reports', name: 'Reports', description: 'Relatórios e resultados', icon: '/static/images/cadu/products/connect-icon.png'},
  {id: 'skills', name: 'Skills', description: 'Recursos e automações', icon: '/static/images/cadu/products/skills-icon.png'},
];

function Icon({name, size = 18}) {
  const paths = {
    arrow: <><path d="M4 12h15"/><path d="m13 6 6 6-6 6"/></>,
    arrowLeft: <><path d="M20 12H5"/><path d="m11 18-6-6 6-6"/></>,
    eye: <><path d="M2.5 12s3.5-5 9.5-5 9.5 5 9.5 5-3.5 5-9.5 5-9.5-5-9.5-5Z"/><circle cx="12" cy="12" r="2.2"/></>,
    eyeOff: <><path d="m3 3 18 18"/><path d="M10.6 6.2A11.7 11.7 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-3 3.5"/><path d="M6.4 6.4C3.7 8 2.5 12 2.5 12s3.5 6 9.5 6c1.1 0 2.1-.2 3-.5"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></>,
    user: <><circle cx="12" cy="8" r="3.5"/><path d="M5 20c.7-3.2 3-5 7-5s6.3 1.8 7 5"/></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function Brand({bootstrap}) {
  return <a className="cadu-auth-brand" href={bootstrap.brandUrl || '#'} aria-label={`Ir para ${bootstrap.brandName || 'Cadu Workspace'}`}>
    <img src={bootstrap.logoUrl} alt="" />
    <span>{bootstrap.brandName || 'Cadu Workspace'}</span>
  </a>;
}

function GoogleButton({href, label}) {
  return <a className="cadu-auth-google" href={href}>
    <span className="cadu-auth-google-mark" aria-hidden="true">G</span>
    <span>{label}</span>
  </a>;
}

function Field({label, id, type = 'text', icon, value, onChange, placeholder, autoComplete, name, required = true, minLength, autoCapitalize, inputMode, action, hint, labelAction}) {
  return <div className="cadu-auth-field">
    {labelAction ? <div className="cadu-auth-field-row"><label htmlFor={id}>{label}</label>{labelAction}</div> : <label htmlFor={id}>{label}</label>}
    <div className="cadu-auth-input-wrap">
      {icon && <span className="cadu-auth-input-icon"><Icon name={icon} size={17}/></span>}
      <input id={id} name={name || id} type={type} value={value} onChange={onChange} placeholder={placeholder} autoComplete={autoComplete} required={required} minLength={minLength} autoCapitalize={autoCapitalize} inputMode={inputMode} />
      {action}
    </div>
    {hint && <p className="cadu-auth-field-hint">{hint}</p>}
  </div>;
}

function PasswordField({label = 'Senha', id = 'password', value, onChange, autoComplete = 'current-password', hint, labelAction}) {
  const [visible, setVisible] = useState(false);
  return <Field label={label} id={id} name={id} type={visible ? 'text' : 'password'} icon="lock" value={value} onChange={onChange} placeholder={label === 'Senha' ? 'Digite sua senha' : 'Digite uma senha'} autoComplete={autoComplete} hint={hint} labelAction={labelAction} action={<button className="cadu-auth-input-action" type="button" onClick={() => setVisible(current => !current)} aria-label={visible ? 'Ocultar senha' : 'Mostrar senha'}>{<Icon name={visible ? 'eyeOff' : 'eye'} size={17}/>}</button>} />;
}

function SubmitButton({children, loading = false, icon = 'arrow'}) {
  return <button className="cadu-auth-submit" type="submit" disabled={loading} aria-busy={loading}>
    {loading ? <span className="cadu-auth-spinner" aria-hidden="true"/> : null}
    <span>{loading ? 'Aguarde…' : children}</span>
    {!loading && <Icon name={icon} size={17}/>}
  </button>;
}

function AuthTransition({bootstrap}) {
  return <div className="cadu-auth-transition" role="status" aria-live="polite">
    <div className="cadu-auth-transition-mark"><img src={bootstrap.caduLogoUrl || '/static/images/cadu/products/cadu-icon.png'} alt="" /></div>
    <strong>Entrando no Cadu Workspace</strong>
    <span>Preparando seu espaço de trabalho…</span>
  </div>;
}

function ToolRail({tools, compact = false}) {
  return <aside className={`cadu-auth-tools ${compact ? 'is-compact' : ''}`} aria-label="Ferramentas incluídas no Cadu">
    <div className="cadu-auth-tools-intro">
      <span className="cadu-auth-tools-kicker">Cadu Workspace</span>
      <h2>Uma conta para o trabalho continuar.</h2>
      <p>Projeto, criação e resultado usam a mesma base.</p>
    </div>
    <ul>{tools.map(tool => <li key={tool.id}>
      <span className="cadu-auth-tool-icon"><img src={tool.icon} alt="" /></span>
      <span><strong>{tool.name}</strong><small>{tool.description}</small></span>
      <Icon name="check" size={15}/>
    </li>)}</ul>
  </aside>;
}

function VisualPanel({bootstrap, signup = false}) {
  return <aside className={`cadu-auth-visual ${signup ? 'is-signup' : ''}`} style={{'--cadu-auth-image': `url(${bootstrap.imageUrl})`}} aria-hidden="true">
    <div className="cadu-auth-visual-overlay" />
    <div className="cadu-auth-visual-copy">
      <span>{signup ? 'Tudo conectado' : 'Cadu Workspace'}</span>
      <strong>{signup ? 'Seu primeiro projeto já começa com uma base.' : 'Retome o trabalho com o contexto por perto.'}</strong>
    </div>
  </aside>;
}

function AuthFrame({bootstrap, children, visual = true, signup = false, loading = false}) {
  const tools = bootstrap.tools?.length ? bootstrap.tools : DEFAULT_TOOLS;
  const sideContent = signup
    ? <aside className="cadu-auth-signup-rail"><VisualPanel bootstrap={bootstrap} signup/><ToolRail tools={tools}/></aside>
    : visual ? <VisualPanel bootstrap={bootstrap}/> : null;
  return <div className={`cadu-auth-page ${signup ? 'is-signup' : ''} ${visual ? 'has-visual' : ''}`}>
    <header className="cadu-auth-header"><Brand bootstrap={bootstrap}/></header>
    <main className="cadu-auth-main">
      <section className="cadu-auth-card">
        <FlashMessages messages={bootstrap.messages}/>
        {children}
      </section>
      {sideContent}
    </main>
    {signup && <details className="cadu-auth-mobile-tools"><summary>Ferramentas incluídas no Cadu</summary><ToolRail tools={tools} compact/></details>}
    {loading && <AuthTransition bootstrap={bootstrap}/>}
  </div>;
}

function PageHeading({eyebrow, title, description}) {
  return <header className="cadu-auth-heading">
    {eyebrow && <p className="cadu-auth-eyebrow">{eyebrow}</p>}
    <h1>{title}</h1>
    {description && <p>{description}</p>}
  </header>;
}

function Login({bootstrap}) {
  const [loading, setLoading] = useState(false);
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState(bootstrap.email || '');
  const isCorporate = Boolean(bootstrap.isCorporate);
  const handleSubmit = event => {
    if (loading) {
      event.preventDefault();
      return;
    }
    setLoading(true);
  };
  return <AuthFrame bootstrap={bootstrap} loading={loading}>
    <PageHeading title="Continue seu trabalho no Cadu" description="Entre para retomar projetos, fontes, decisões e entregas." />
    <GoogleButton href={bootstrap.googleUrl} label="Continuar com Google" />
    <div className="cadu-auth-divider"><span>ou entre com email</span></div>
    <form action={bootstrap.formAction} method="POST" onSubmit={handleSubmit} className="cadu-auth-form">
      {bootstrap.next && <input type="hidden" name="next" value={bootstrap.next}/>}
      {isCorporate ? <>
        <Field label="Email" id="email_local" name="email_local" icon="mail" value={email} onChange={event => setEmail(event.target.value)} placeholder="seu.nome" autoComplete="username" inputMode="email" autoCapitalize="none" hint="Use seu acesso CentralComm." />
        <input type="hidden" name="email" value="" />
      </> : <Field label="Email de trabalho" id="email" name="email" type="email" icon="mail" value={email} onChange={event => setEmail(event.target.value)} placeholder="nome@empresa.com" autoComplete="username" inputMode="email" autoCapitalize="none" />}
      <PasswordField value={password} onChange={event => setPassword(event.target.value)} labelAction={<a href={bootstrap.forgotUrl}>Esqueci minha senha</a>} />
      <SubmitButton loading={loading}>Entrar</SubmitButton>
    </form>
    {!isCorporate && <p className="cadu-auth-switch">Ainda não tem uma conta? <a href={bootstrap.signupUrl}>Criar conta</a></p>}
  </AuthFrame>;
}

function Signup({bootstrap}) {
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState(bootstrap.signupName || '');
  const [email, setEmail] = useState(bootstrap.signupEmail || '');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const mismatch = confirmation.length > 0 && password !== confirmation;
  const handleSubmit = event => {
    if (mismatch || loading) {
      event.preventDefault();
      return;
    }
    setLoading(true);
  };
  const errors = (bootstrap.signupErrors || []).map(message => ['error', message]);
  return <AuthFrame bootstrap={{...bootstrap, messages: [...(bootstrap.messages || []), ...errors]}} signup loading={loading}>
    <PageHeading eyebrow="Comece com um projeto real" title="Crie a base do seu próximo projeto" description="Reúna marca, briefing e fontes para o time continuar sem reconstruir o contexto." />
    <GoogleButton href={bootstrap.googleUrl} label="Criar conta com Google" />
    <p className="cadu-auth-google-note">Use sua conta Google para entrar sem criar mais uma senha.</p>
    <div className="cadu-auth-divider"><span>ou crie com email</span></div>
    <form action={bootstrap.formAction} method="POST" onSubmit={handleSubmit} className="cadu-auth-form">
      {bootstrap.next && <input type="hidden" name="next" value={bootstrap.next}/>}
      <Field label="Nome completo" id="name" name="name" icon="user" value={name} onChange={event => setName(event.target.value)} placeholder="Como podemos chamar você?" autoComplete="name" />
      <Field label="Email de trabalho" id="email" name="email" type="email" icon="mail" value={email} onChange={event => setEmail(event.target.value)} placeholder="nome@empresa.com" autoComplete="email" inputMode="email" autoCapitalize="none" />
      <PasswordField label="Senha" value={password} onChange={event => setPassword(event.target.value)} autoComplete="new-password" hint="Use pelo menos 8 caracteres." />
      <PasswordField label="Confirmar senha" id="confirm_password" value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="new-password" />
      {mismatch && <p className="cadu-auth-error" role="alert">As senhas não coincidem.</p>}
      <SubmitButton loading={loading} icon="check">Criar conta</SubmitButton>
    </form>
    <p className="cadu-auth-switch cadu-auth-switch--signup">Já tem uma conta? <a href={bootstrap.loginUrl}>Entrar</a></p>
  </AuthFrame>;
}

function ForgotPassword({bootstrap}) {
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('');
  if (bootstrap.requestSent) return <AuthFrame bootstrap={{...bootstrap, messages: []}} visual={false}>
    <section className="cadu-auth-result" role="status">
      <span className="cadu-auth-result-icon"><Icon name="mail" size={25}/></span>
      <PageHeading title="Verifique seu email" description="Se houver uma conta ativa para esse endereço, o link para criar uma nova senha chegará em alguns minutos." />
      <div className="cadu-auth-result-note"><Icon name="lock" size={16}/><span>O link expira em 1 hora. Confira também a caixa de spam.</span></div>
      <a className="cadu-auth-submit" href={bootstrap.loginUrl}><span>Voltar para o login</span><Icon name="arrow" size={17}/></a>
      <a className="cadu-auth-back" href={bootstrap.formAction}><Icon name="arrowLeft" size={16}/> Tentar outro email</a>
    </section>
  </AuthFrame>;
  return <AuthFrame bootstrap={bootstrap} visual={false}>
    <PageHeading title="Recupere seu acesso" description="Informe seu email e enviaremos um link para redefinir sua senha." />
    <form action={bootstrap.formAction} method="POST" onSubmit={() => setLoading(true)} className="cadu-auth-form">
      <Field label="Email de trabalho" id="email" name="email" type="email" icon="mail" value={email} onChange={event => setEmail(event.target.value)} placeholder="nome@empresa.com" autoComplete="username" inputMode="email" autoCapitalize="none" />
      <SubmitButton loading={loading} icon="arrow">Enviar link</SubmitButton>
      <a className="cadu-auth-back" href={bootstrap.loginUrl}><Icon name="arrowLeft" size={16}/> Voltar para o login</a>
    </form>
  </AuthFrame>;
}

function ResetPassword({bootstrap}) {
  const [loading, setLoading] = useState(false);
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [visible, setVisible] = useState(false);
  const mismatch = confirmation.length > 0 && password !== confirmation;
  const handleSubmit = event => {
    if (mismatch) {
      event.preventDefault();
      return;
    }
    setLoading(true);
  };
  return <AuthFrame bootstrap={bootstrap} visual={false}>
    <PageHeading title="Crie uma nova senha" description={`Olá, ${bootstrap.userName || 'tudo bem'}. Use pelo menos 8 caracteres para proteger sua conta.`} />
    <form action={bootstrap.formAction} method="POST" onSubmit={handleSubmit} className="cadu-auth-form">
      <Field label="Nova senha" id="password" name="password" type={visible ? 'text' : 'password'} icon="lock" value={password} onChange={event => setPassword(event.target.value)} placeholder="Crie uma senha com pelo menos 8 caracteres" autoComplete="new-password" minLength={8} action={<button className="cadu-auth-input-action" type="button" onClick={() => setVisible(current => !current)} aria-label={visible ? 'Ocultar senha' : 'Mostrar senha'}><Icon name={visible ? 'eyeOff' : 'eye'} size={17}/></button>} />
      <Field label="Confirme a senha" id="confirm_password" name="confirm_password" type={visible ? 'text' : 'password'} icon="lock" value={confirmation} onChange={event => setConfirmation(event.target.value)} placeholder="Repita a nova senha" autoComplete="new-password" minLength={8} />
      {mismatch && <p className="cadu-auth-error" role="alert">As senhas não coincidem.</p>}
      <SubmitButton loading={loading} icon="check">Salvar nova senha</SubmitButton>
      <a className="cadu-auth-back" href={bootstrap.loginUrl}><Icon name="arrowLeft" size={16}/> Voltar para o login</a>
    </form>
  </AuthFrame>;
}

function FlashMessages({messages = []}) {
  const readableMessages = messages
    .map(([category, message]) => [category, message === 'Email ou senha incorretos.' ? 'Não foi possível entrar. Confira seu email e sua senha e tente novamente.' : message])
    .filter((entry, index, all) => all.findIndex(item => item[0] === entry[0] && item[1] === entry[1]) === index);
  if (!readableMessages.length) return null;
  return <div className="cadu-auth-flashes" aria-live="assertive">{readableMessages.map(([category, message], index) => <div className={`cadu-auth-flash is-${category}`} role={category === 'error' ? 'alert' : 'status'} key={`${category}-${message}-${index}`}>{message}</div>)}</div>;
}

function App({bootstrap}) {
  const page = bootstrap.page || 'login';
  const tools = useMemo(() => bootstrap.tools?.length ? bootstrap.tools : DEFAULT_TOOLS, [bootstrap.tools]);
  const pageBootstrap = {...bootstrap, tools};
  return page === 'signup' ? <Signup bootstrap={pageBootstrap}/> : page === 'forgot-password' ? <ForgotPassword bootstrap={pageBootstrap}/> : page === 'reset-password' ? <ResetPassword bootstrap={pageBootstrap}/> : <Login bootstrap={pageBootstrap}/>;
}

const node = document.getElementById('cadu-auth-root');
const dataNode = document.getElementById('cadu-auth-bootstrap');
if (node && dataNode) {
  try {
    const bootstrap = JSON.parse(dataNode.textContent || '{}');
    createRoot(node).render(<ThemeProvider skin="workspace" theme="light" persistKey="cadu-auth-theme" locked><App bootstrap={bootstrap}/></ThemeProvider>);
  } catch (error) {
    node.innerHTML = '<p role="alert" class="cadu-auth-fallback">Não foi possível abrir esta tela. Atualize a página.</p>';
    console.error(error);
  }
}
