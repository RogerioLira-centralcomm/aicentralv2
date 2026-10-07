import React, {useEffect, useRef, useState} from 'react';
import {XClose} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import './reports-wizard.css';

/**
 * Full-screen guided flow shared by the Reports setup wizards: one question per step, a scene per step,
 * progress that can go back, Escape to leave. The caller supplies the steps and renders each one.
 *
 * steps: [{key, label, art, title, text, optional?, focus?}] · art is a file in `artBase`; `focus` is the vertical % kept visible when the scene becomes a banner (tablet).
 * renderStep(index) → the fields · canContinue(index) → boolean · onFinish() → promise (the caller closes on success)
 * onNext(index) → optional promise run before leaving a step (a thrown error stays on the step and is shown).
 */
export function ReportsWizard({label, steps, artBase, renderStep, canContinue = () => true, onNext, onFinish, onClose, finishLabel = 'Concluir', busy = false, error = ''}) {
  const [step, setStep] = useState(0);
  const [moving, setMoving] = useState(false);
  const [stepError, setStepError] = useState('');
  const [reached, setReached] = useState(0);
  const panel = useRef(null);
  const last = step === steps.length - 1;
  const current = steps[step];
  const go = next => {const bounded = Math.max(0, Math.min(steps.length - 1, next)); setStep(bounded); setReached(value => Math.max(value, bounded));};
  useEffect(() => {panel.current?.querySelector('input, select, textarea, button.rw__option')?.focus?.({preventScroll: true});}, [step]);
  useEffect(() => {
    const onKey = event => {if (event.key === 'Escape' && !busy) onClose();};
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    addEventListener('keydown', onKey);
    return () => {removeEventListener('keydown', onKey); document.body.style.overflow = previous;};
  }, [busy, onClose]);
  const submit = async event => {
    event.preventDefault();
    if (!canContinue(step) || busy || moving) return;
    setStepError('');
    if (last) {onFinish(); return;}
    if (onNext) {
      setMoving(true);
      try {await onNext(step);} catch (failure) {setStepError(failure.message || 'Não foi possível continuar.'); setMoving(false); return;}
      setMoving(false);
    }
    go(step + 1);
  };
  // The page behind the wizard stays mounted (it keeps its state); make it inert so Tab and screen readers stay in the dialog.
  const dialog = useRef(null);
  useEffect(() => {
    const quieted = [];
    for (let node = dialog.current; node && node.id !== 'cadu-reports-v1-root' && node.parentElement; node = node.parentElement) {
      for (const sibling of node.parentElement.children) {
        if (sibling !== node && !sibling.inert) {sibling.inert = true; quieted.push(sibling);}
      }
    }
    return () => quieted.forEach(element => {element.inert = false;});
  }, []);
  return <div ref={dialog} className="rw untitled-scope" role="dialog" aria-modal="true" aria-label={label}>
    <header className="rw__bar">
      <span className="rw__brand"><img src="/static/images/cadu/products/connect-icon.png" alt=""/>Reports</span>
      <span className="rw__title">{label}</span>
      <Button size="sm" color="tertiary" iconLeading={XClose} isDisabled={busy} onPress={onClose}>Sair</Button>
    </header>
    <aside className="rw__art" aria-hidden="true">
      {steps.map((item, index) => <img key={item.key} className={`rw__scene${index === step ? ' is-current' : ''}`} style={item.focus ? {'--rw-focus': item.focus} : undefined} src={artBase + item.art} alt="" loading={index === 0 ? 'eager' : 'lazy'}/>)}
    </aside>
    <main className="rw__main">
      <ol className="rw__progress" aria-label="Progresso">
        <li className="rw__count">{step + 1} de {steps.length}</li>
        {steps.map((item, index) => <li key={item.key}><button type="button" aria-label={`Ir para ${item.label}`} disabled={index > reached}
          className={index <= step ? 'is-done' : ''} onClick={() => go(index)}/></li>)}
      </ol>
      <form ref={panel} className="rw__panel" onSubmit={submit}>
        <h2>{current.title}</h2>
        <p className="rw__lead">{current.text}</p>
        {renderStep(step)}
        {(stepError || error) && <p role="alert" className="rw__error">{stepError || error}</p>}
        <div className="rw__nav">
          <Button type="button" size="lg" color="secondary" isDisabled={step === 0 || busy || moving} onPress={() => {setStepError(''); go(step - 1);}}>Voltar</Button>
          <Button type="submit" size="lg" color="primary" isDisabled={!canContinue(step) || busy || moving} isLoading={(busy && last) || moving}>{last ? finishLabel : 'Continuar'}</Button>
        </div>
        {current.optional && !last && <p className="rw__skip"><button type="button" onClick={() => go(steps.length - 1)}>Pular e revisar</button></p>}
      </form>
    </main>
  </div>;
}
