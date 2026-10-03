import React from 'react';
import {ArrowLeft, ArrowRight, Check, Lock01, Mail01, User01} from '@untitledui/icons';
import {Button} from '../untitled-kit/button';
import {AuthFrame, PageHeading} from './AuthShell';
import {AuthField, EMAIL_INPUT, GoogleButton, PasswordField, PasswordRules, SubmitButton} from './AuthFields';
import {useAuthForm} from './useAuthForm';
import {copyFor} from './brandCopy';
import {validateConfirmation, validateEmail, validateLoginPassword, validateName, validateNewPassword} from './validation.mjs';

const hidden = (name, value) => value ? <input type="hidden" name={name} value={value}/> : null;

export function Login({bootstrap}) {
  const corporate = Boolean(bootstrap.isCorporate);
  const copy = copyFor(bootstrap);
  const form = useAuthForm({email: bootstrap.email || '', password: ''}, {
    email: value => validateEmail(value, {corporate}),
    password: validateLoginPassword,
  }, {overlay: true});
  return <AuthFrame bootstrap={bootstrap} overlay={form.overlayVisible}>
    <PageHeading title={copy.loginTitle} description={copy.loginDescription} />
    <GoogleButton href={bootstrap.googleUrl} label="Continuar com Google" />
    <div className="cadu-auth-divider"><span>{copy.loginDivider}</span></div>
    <form action={bootstrap.formAction} method="POST" onSubmit={form.handleSubmit} className="cadu-auth-form" noValidate>
      {hidden('next', bootstrap.next)}
      {corporate ? <>
        <AuthField id="email_local" label="Email" icon={Mail01} placeholder="seu.nome" autoComplete="username" hint="Use seu acesso CentralComm." {...EMAIL_INPUT} type="text" {...form.bind('email')} />
        <input type="hidden" name="email" value="" />
      </> : <AuthField id="email" label="Email de trabalho" icon={Mail01} placeholder="nome@empresa.com" autoComplete="username" {...EMAIL_INPUT} {...form.bind('email')} />}
      <PasswordField id="password" label="Senha" icon={Lock01} placeholder="Digite sua senha" autoComplete="current-password"
        labelAction={<Button href={bootstrap.forgotUrl} color="link-color" size="sm">Esqueci minha senha</Button>} {...form.bind('password')} />
      <SubmitButton loading={form.loading}>Entrar</SubmitButton>
    </form>
    {!corporate && <p className="cadu-auth-switch">Ainda não tem uma conta? <a href={bootstrap.signupUrl}>Criar conta</a></p>}
  </AuthFrame>;
}

export function Signup({bootstrap}) {
  const form = useAuthForm({name: bootstrap.signupName || '', email: bootstrap.signupEmail || '', password: '', confirm_password: ''}, {
    name: validateName,
    email: value => validateEmail(value),
    password: validateNewPassword,
    confirm_password: (value, all) => validateConfirmation(all.password, value),
  }, {overlay: true});
  const errors = (bootstrap.signupErrors || []).map(message => ['error', message]);
  return <AuthFrame bootstrap={{...bootstrap, messages: [...(bootstrap.messages || []), ...errors]}} signup overlay={form.overlayVisible}>
    <PageHeading eyebrow="Comece com um projeto real" title="Crie a base do seu próximo projeto" description="Reúna marca, briefing e fontes para o time continuar sem reconstruir o contexto." />
    <GoogleButton href={bootstrap.googleUrl} label="Criar conta com Google" />
    <p className="cadu-auth-google-note">Use sua conta Google para entrar sem criar mais uma senha.</p>
    <div className="cadu-auth-divider"><span>ou crie com email</span></div>
    <form action={bootstrap.formAction} method="POST" onSubmit={form.handleSubmit} className="cadu-auth-form" noValidate>
      {hidden('next', bootstrap.next)}
      <AuthField id="name" label="Nome completo" icon={User01} placeholder="Como podemos chamar você?" autoComplete="name" enterKeyHint="next" autoCapitalize="words" {...form.bind('name')} />
      <AuthField id="email" label="Email de trabalho" icon={Mail01} placeholder="nome@empresa.com" autoComplete="email" {...EMAIL_INPUT} {...form.bind('email')} />
      <PasswordField id="password" label="Senha" icon={Lock01} placeholder="Digite uma senha" autoComplete="new-password" enterKeyHint="next" {...form.bind('password')} />
      <PasswordRules value={form.values.password}/>
      <PasswordField id="confirm_password" label="Confirmar senha" icon={Lock01} placeholder="Repita a senha" autoComplete="new-password" {...form.bind('confirm_password')} />
      <SubmitButton loading={form.loading} icon={Check}>Criar conta</SubmitButton>
    </form>
    <p className="cadu-auth-switch cadu-auth-switch--signup">Já tem uma conta? <a href={bootstrap.loginUrl}>Entrar</a></p>
  </AuthFrame>;
}

export function ForgotPassword({bootstrap}) {
  const copy = copyFor(bootstrap);
  const form = useAuthForm({email: ''}, {email: value => validateEmail(value)});
  if (bootstrap.requestSent) return <AuthFrame bootstrap={{...bootstrap, messages: []}} visual={false}>
    <section className="cadu-auth-result" role="status">
      <span className="cadu-auth-result-icon"><Mail01 size={26} aria-hidden="true"/></span>
      <PageHeading title="Verifique seu email" description="Se houver uma conta ativa para esse endereço, o link para criar uma nova senha chegará em alguns minutos." />
      <div className="cadu-auth-result-note"><Lock01 size={16} aria-hidden="true"/><span>O link expira em 1 hora. Confira também a caixa de spam.</span></div>
      <Button href={bootstrap.loginUrl} size="lg" color="primary" iconTrailing={ArrowRight} className="cadu-auth-wide">Voltar para o login</Button>
      <Button href={bootstrap.formAction} size="md" color="link-gray" iconLeading={ArrowLeft}>Tentar outro email</Button>
    </section>
  </AuthFrame>;
  return <AuthFrame bootstrap={bootstrap} visual={false}>
    <PageHeading title="Recupere seu acesso" description={copy.forgotDescription} />
    <form action={bootstrap.formAction} method="POST" onSubmit={form.handleSubmit} className="cadu-auth-form" noValidate>
      <AuthField id="email" label={copy.forgotLabel} icon={Mail01} placeholder={copy.forgotPlaceholder} autoComplete="username" {...EMAIL_INPUT} enterKeyHint="send" {...form.bind('email')} />
      <SubmitButton loading={form.loading}>Enviar link</SubmitButton>
      <Button href={bootstrap.loginUrl} size="md" color="link-gray" iconLeading={ArrowLeft}>Voltar para o login</Button>
    </form>
  </AuthFrame>;
}

export function ResetPassword({bootstrap}) {
  const form = useAuthForm({password: '', confirm_password: ''}, {
    password: validateNewPassword,
    confirm_password: (value, all) => validateConfirmation(all.password, value),
  });
  return <AuthFrame bootstrap={bootstrap} visual={false}>
    <PageHeading title="Crie uma nova senha" description={`Olá, ${bootstrap.userName || 'tudo bem'}. Use pelo menos 8 caracteres para proteger sua conta.`} />
    <form action={bootstrap.formAction} method="POST" onSubmit={form.handleSubmit} className="cadu-auth-form" noValidate>
      <PasswordField id="password" label="Nova senha" icon={Lock01} placeholder="Crie uma senha" autoComplete="new-password" enterKeyHint="next" {...form.bind('password')} />
      <PasswordRules value={form.values.password}/>
      <PasswordField id="confirm_password" label="Confirme a senha" icon={Lock01} placeholder="Repita a nova senha" autoComplete="new-password" {...form.bind('confirm_password')} />
      <SubmitButton loading={form.loading} icon={Check}>Salvar nova senha</SubmitButton>
      <Button href={bootstrap.loginUrl} size="md" color="link-gray" iconLeading={ArrowLeft}>Voltar para o login</Button>
    </form>
  </AuthFrame>;
}
