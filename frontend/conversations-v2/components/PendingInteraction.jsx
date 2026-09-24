import React from 'react';
import {Icon} from '../lib/icons';
import {meaningfulResponseBlocks} from '../lib/responseModel.mjs';

function normalizeQuestions(items) {
  return (Array.isArray(items) ? items : []).map(item => typeof item === 'string' ? {question: item} : item)
    .filter(item => item && (item.question || item.title || item.options?.length || item.allow_custom))
    .map((item, index) => ({...item, id: String(item.id || `question-${index + 1}`), question: String(item.question || item.title || 'Como deseja continuar?')}));
}

export function pendingInteraction(messages, running) {
  if (running || !messages?.length) return null;
  const message = messages[messages.length - 1];
  if (message?.role !== 'assistant' || message.kind === 'failure') return null;
  if (message.kind === 'action') {
    const name = String(message.action?.name || '');
    const presentation = name === 'projects.create_link_reference'
      ? {eyebrow: 'Adicionar referência', approve: 'Adicionar ao projeto', progress: 'Adicionando…', detail: 'O link será salvo sem leitura ou indexação automática.'}
      : name === 'projects.create_note'
        ? {eyebrow: 'Salvar anotação', approve: 'Salvar no projeto', progress: 'Salvando…', detail: 'A anotação ficará disponível no contexto do projeto.'}
        : name === 'projects.reindex_source'
          ? {eyebrow: 'Atualizar fonte', approve: 'Reindexar fonte', progress: 'Reindexando…', detail: 'O conteúdo da fonte será processado novamente.'}
          : name === 'brands.start_audit'
            ? {eyebrow: 'Iniciar auditoria', approve: 'Iniciar auditoria', progress: 'Iniciando…', detail: 'A análise será executada com o contexto disponível da marca.'}
            : name.startsWith('brands.')
              ? {eyebrow: 'Atualizar marca', approve: 'Confirmar alteração', progress: 'Atualizando…', detail: 'A alteração será aplicada à marca selecionada.'}
              : {eyebrow: 'Confirmar ação', approve: 'Confirmar', progress: 'Executando…', detail: 'Nada será alterado até você escolher uma opção.'};
    return {
      kind: 'action', message, eyebrow: presentation.eyebrow,
      question: message.action?.summary || 'Deseja concluir esta ação?',
      command: message.action?.command || message.action?.input?.command || message.action?.arguments?.command || '',
      detail: message.actionError || presentation.detail,
      error: Boolean(message.actionError), pending: Boolean(message.actionPending),
      options: [
        {id: 'approve', label: message.actionPending ? presentation.progress : presentation.approve, detail: 'Confirma e conclui esta ação.', approved: true, recommended: true},
        {id: 'decline', label: 'Agora não', detail: 'Mantém a conversa sem executar a ação.', approved: false},
      ],
    };
  }
  const response = message.response || {};
  const blocks = meaningfulResponseBlocks(response.blocks);
  const questionBlock = [...blocks].reverse().find(block => ['question', 'questions'].includes(block.type) && Array.isArray(block.items) && block.items.length);
  if (questionBlock) {
    const items = normalizeQuestions(questionBlock.items);
    if (items.length) return {kind: 'question', messageId: message.id, question: questionBlock.title || 'Responda para continuar', items};
  }
  const legacyQuestions = normalizeQuestions(response.questions);
  if (legacyQuestions.length) return {kind: 'question', messageId: message.id, question: 'Responda para continuar', items: legacyQuestions};
  const decision = [...blocks].reverse().find(block => block.type === 'decision' && Array.isArray(block.items) && block.items.length);
  const question = decision?.summary || decision?.title || '';
  const options = decision?.items?.map(item => ({
    id: item.id || item.title, label: item.title, detail: item.detail || '',
    prompt: item.prompt || `Continue usando a opção “${item.title}”.`, recommended: Boolean(item.recommended),
  })) || [];
  if (!question && !options.length) return null;
  const normalizedOptions = options.length ? options : [{id: 'write-answer', label: 'Responder', prompt: question, asContext: true, freeform: true}];
  return {question: question || 'Escolha como continuar', options: normalizedOptions.slice(0, 4)};
}

export function PendingInteraction({interaction, onPrompt, onDecision}) {
  if (!interaction || interaction.kind === 'question') return null;
  const freeform = interaction.kind !== 'action' && interaction.options.length === 1 && interaction.options[0].freeform;
  const choose = option => interaction.kind === 'action'
    ? onDecision(interaction.message, option.approved)
    : option.autoSubmit || !option.asContext ? onPrompt(option.prompt) : onPrompt('', {type: 'question', label: 'Respondendo', text: option.prompt});
  return <section className={`cv-pending-interaction ${interaction.kind === 'action' ? 'is-action' : ''}`} aria-label="Ação necessária">
    <div className="cv-pending-interaction__heading">{interaction.kind === 'action' && <span className="cv-pending-interaction__app"><Icon name="pulse" size={13}/>Terminal</span>}<span className="cv-pending-interaction__copy"><strong>{interaction.question}</strong>{interaction.detail && <i className={interaction.error ? 'is-error' : ''} role={interaction.error ? 'alert' : undefined}>{interaction.detail}</i>}</span>{freeform && <button type="button" className="cv-pending-interaction__respond" onClick={() => choose(interaction.options[0])}>Responder</button>}</div>
    {interaction.kind === 'action' && interaction.command && <details className="cv-pending-interaction__command"><summary><code>{interaction.command}</code><span>Expandir</span></summary><pre>{interaction.command}</pre></details>}
    {!freeform && !!interaction.options.length && <div className="cv-pending-interaction__options">{interaction.kind === 'action' ? <><button type="button" className="is-decline" disabled={interaction.pending} onClick={() => choose(interaction.options.find(option => !option.approved))}>Negar <kbd>Esc</kbd></button><button type="button" className="is-approve" disabled={interaction.pending} onClick={() => choose(interaction.options.find(option => option.approved))}>{interaction.pending ? interaction.options.find(option => option.approved)?.label : 'Permitir uma vez'} <kbd>↵</kbd></button></> : interaction.options.map(option => <button key={option.id} className={option.recommended ? 'is-recommended' : ''} type="button" disabled={interaction.pending} onClick={() => choose(option)}><span><b>{option.label}</b>{option.detail && <small>{option.detail}</small>}</span>{option.recommended && <em>Recomendada</em>}<Icon name="chevron" size={14}/></button>)}</div>}
  </section>;
}

export function QuestionSteps({interaction, onPrompt}) {
  const [step, setStep] = React.useState(0);
  const [answers, setAnswers] = React.useState({});
  const [customAnswers, setCustomAnswers] = React.useState({});
  const questions = interaction?.items || [];
  if (!questions.length) return null;
  const current = questions[Math.min(step, questions.length - 1)];
  const options = Array.isArray(current.options) ? current.options : [];
  const answer = String(customAnswers[current.id] || answers[current.id] || '').trim();
  const allowCustom = current.allow_custom !== false || options.length === 0;
  const canContinue = current.required === false || Boolean(answer);
  const saveAnswers = () => {
    const answered = questions.map(item => ({item, answer: String(customAnswers[item.id] || answers[item.id] || '').trim()}))
      .filter(({answer: value}) => value);
    if (!answered.length) return;
    const prompt = answered.map(({item, answer: value}) => /(?:renome|mudar|alterar|trocar).{0,45}nome|novo nome.{0,45}projeto/i.test(item.question)
      ? `Renomeie o projeto para “${value}”.` : `${item.question}: ${value}`).join('\n');
    onPrompt(prompt, {
      type: 'question_answers', label: interaction.question || 'Respostas às perguntas',
      text: answered.map(({item, answer: value}) => `${item.question}: ${value}`).join('\n'),
      answers: answered.map(({item, answer: value}) => ({id: item.id, question: item.question, answer: value})),
    }, {submit: true});
  };
  const continueStep = () => {
    if (!canContinue) return;
    if (step < questions.length - 1) setStep(value => value + 1);
    else saveAnswers();
  };
  return <section className="cv-question-steps" aria-label="Pergunta aguardando sua resposta" aria-live="polite">
    <header className="cv-question-steps__header">
      <span className="cv-question-steps__status"><Icon name="alert" size={14}/>Precisa da sua resposta</span>
      <span className="cv-question-steps__progress">Etapa {step + 1} de {questions.length}</span>
    </header>
    {interaction.question && questions.length > 1 && <p className="cv-question-steps__title">{interaction.question}</p>}
    <fieldset className="cv-question-steps__field">
      <legend>{current.question}</legend>
      {!!options.length && <div className="cv-question-steps__options">{options.map((option, index) => {
        const value = String(typeof option === 'string' ? option : option.value ?? option.label ?? option.title ?? '');
        const label = typeof option === 'string' ? option : option.label || option.title || value;
        const selected = !customAnswers[current.id] && answers[current.id] === value;
        return <button key={option.id || index} type="button" aria-pressed={selected} className={selected ? 'is-selected' : ''} onClick={() => {
          setAnswers(state => ({...state, [current.id]: value}));
          setCustomAnswers(state => ({...state, [current.id]: ''}));
        }}>{label}</button>;
      })}</div>}
      {allowCustom && <input aria-label={`Sua resposta para: ${current.question}`} value={customAnswers[current.id] || ''}
        onChange={event => setCustomAnswers(state => ({...state, [current.id]: event.target.value}))}
        placeholder={current.custom_placeholder || (options.length ? 'Ou escreva outra resposta…' : 'Escreva sua resposta…')}/>}
    </fieldset>
    <footer className="cv-question-steps__footer">
      {step > 0 && <button type="button" className="is-back" onClick={() => setStep(value => Math.max(0, value - 1))}>Voltar</button>}
      {current.required === false && <button type="button" className="is-back" onClick={() => { if (step < questions.length - 1) setStep(value => value + 1); else saveAnswers(); }}>Pular</button>}
      <button type="button" className="is-primary" disabled={!canContinue} onClick={continueStep}>{step < questions.length - 1 ? 'Próxima' : 'Responder e continuar'}</button>
    </footer>
  </section>;
}
