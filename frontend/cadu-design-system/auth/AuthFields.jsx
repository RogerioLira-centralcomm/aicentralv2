import React, {useState} from 'react';
import {AlertCircle, ArrowRight, Check, CheckCircle, Eye, EyeOff, InfoCircle} from '@untitledui/icons';
import {CaduTextField} from '../components/CaduField';
import {Button} from '../untitled-kit/button';
import {MIN_PASSWORD} from './validation.mjs';

/** Keyboard hints that keep mobile keyboards from "fixing" emails and passwords. */
export const EMAIL_INPUT = {type: 'email', inputMode: 'email', autoCapitalize: 'none', autoCorrect: 'off', spellCheck: false, enterKeyHint: 'next'};
const SECRET_INPUT = {autoCapitalize: 'none', autoCorrect: 'off', spellCheck: false};

/** Cadu text field (Untitled Input) with the access-screen defaults: leading icon, 16px text, inline error. */
export function AuthField({id, name, label, icon: LeadIcon, labelAction, hint, error, trailing, inputRef, ...rest}) {
  return <div className={`cadu-auth-field${labelAction ? ' has-action' : ''}`}>
    {labelAction && <div className="cadu-auth-label-action">{labelAction}</div>}
    <CaduTextField id={id} name={name || id} label={label} hint={hint} error={error} inputRef={inputRef} trailing={trailing}
      leading={LeadIcon ? <span className="cadu-auth-leading" aria-hidden="true"><LeadIcon size={18}/></span> : undefined}
      wrapperClassName="cadu-auth-control" {...rest}/>
  </div>;
}

/** Password field with a show/hide control that never takes the focus (the keyboard stays open). */
export function PasswordField({id = 'password', label = 'Senha', autoComplete = 'current-password', placeholder, enterKeyHint = 'go', icon, ...rest}) {
  const [visible, setVisible] = useState(false);
  return <AuthField id={id} label={label} icon={icon} type={visible ? 'text' : 'password'} autoComplete={autoComplete}
    placeholder={placeholder} enterKeyHint={enterKeyHint} {...SECRET_INPUT} {...rest}
    trailing={<button type="button" className="cadu-auth-toggle" aria-label={visible ? 'Ocultar senha' : 'Mostrar senha'} aria-pressed={visible}
      onMouseDown={event => event.preventDefault()} onClick={() => setVisible(value => !value)}>{visible ? <EyeOff size={18}/> : <Eye size={18}/>}</button>}/>;
}

/** Live checklist for a new password: shows what is still missing without waiting for the server. */
export function PasswordRules({value}) {
  const enough = String(value || '').length >= MIN_PASSWORD;
  return <ul className="cadu-auth-rules" aria-label="Requisitos da senha">
    <li className={enough ? 'is-ok' : ''}><Check size={14} aria-hidden="true"/><span>Pelo menos {MIN_PASSWORD} caracteres</span></li>
  </ul>;
}

export function SubmitButton({children, loading = false, loadingLabel = 'Aguarde…', icon = ArrowRight}) {
  return <Button type="submit" size="lg" color="primary" isLoading={loading} showTextWhileLoading iconTrailing={loading ? undefined : icon} className="cadu-auth-wide">
    {loading ? loadingLabel : children}
  </Button>;
}

const GoogleMark = () => <svg className="cadu-auth-google-mark" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
  <path fill="#4285F4" d="M23.5 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.45a5.52 5.52 0 0 1-2.39 3.62v3h3.87c2.27-2.09 3.57-5.17 3.57-8.81Z"/>
  <path fill="#34A853" d="M12 24c3.24 0 5.96-1.07 7.94-2.92l-3.87-3a7.2 7.2 0 0 1-10.7-3.78H1.39v3.1A12 12 0 0 0 12 24Z"/>
  <path fill="#FBBC05" d="M5.37 14.3a7.2 7.2 0 0 1 0-4.6v-3.1H1.39a12 12 0 0 0 0 10.8l3.98-3.1Z"/>
  <path fill="#EA4335" d="M12 4.75c1.76 0 3.34.61 4.59 1.8l3.43-3.43A11.5 11.5 0 0 0 12 0 12 12 0 0 0 1.39 6.6l3.98 3.1A7.2 7.2 0 0 1 12 4.75Z"/>
</svg>;

export function GoogleButton({href, label}) {
  return <Button href={href} size="lg" color="secondary" iconLeading={<GoogleMark/>} className="cadu-auth-wide">{label}</Button>;
}

const NOTICE_ICON = {error: AlertCircle, success: CheckCircle, warning: AlertCircle, info: InfoCircle};

/** Server messages (flash) shown above the form. The login failure text is kept deliberately vague. */
export function FlashMessages({messages = []}) {
  const readable = messages
    .map(([category, message]) => [category, message === 'Email ou senha incorretos.' ? 'Não foi possível entrar. Confira seu email e sua senha e tente novamente.' : message])
    .filter((entry, index, all) => all.findIndex(item => item[0] === entry[0] && item[1] === entry[1]) === index);
  if (!readable.length) return null;
  return <div className="cadu-auth-flashes" aria-live="polite">{readable.map(([category, message], index) => {
    const kind = NOTICE_ICON[category] ? category : 'error';
    const NoticeIcon = NOTICE_ICON[kind];
    return <div className={`cadu-auth-flash is-${kind}`} role={kind === 'error' ? 'alert' : 'status'} key={`${category}-${message}-${index}`}><NoticeIcon size={18} aria-hidden="true"/><span>{message}</span></div>;
  })}</div>;
}
