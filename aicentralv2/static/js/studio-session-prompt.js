/* "Continue or start new?" prompt for when work is already open. Vídeo uses it today; Editar and Criar can ask the same way. */
const STYLE_ID = 'studioSessionPromptStyle';
const CSS = `.studio-session-prompt{width:min(460px,calc(100vw - 32px));padding:22px;border:1px solid rgba(184,207,217,.25);border-radius:14px;background:#161f28;color:#eef2f6;box-shadow:0 28px 80px rgba(0,0,0,.55)}
.studio-session-prompt::backdrop{background:rgba(3,7,10,.7);backdrop-filter:blur(8px)}
.studio-session-prompt h2{margin:0 0 8px;font-size:18px}.studio-session-prompt p{margin:0 0 16px;color:#aebac7;font-size:14px;line-height:1.5}
.studio-session-prompt button{display:grid;gap:2px;width:100%;margin-top:8px;padding:12px 14px;border:1px solid rgba(184,207,217,.18);border-radius:10px;background:#1d2833;color:inherit;font:inherit;text-align:left;cursor:pointer}
.studio-session-prompt button:hover,.studio-session-prompt button:focus-visible{border-color:#6be0c1;background:#243844}.studio-session-prompt button span{color:#8d99a5;font-size:12px}`;

/** Resolves 'continue', 'new' or 'dismissed' (Esc). Only 'new' is a choice to start over: 'continue' and 'dismissed' both keep the open work, so closing the dialog never discards anything. */
export function askSession({title = 'Sessão em aberto', message, continueLabel = 'Continuar sessão em aberto', continueHint = '', newLabel = 'Nova sessão', newHint = ''}) {
  if (!document.getElementById(STYLE_ID)) {
    const style = document.createElement('style');
    style.id = STYLE_ID; style.textContent = CSS; document.head.append(style);
  }
  return new Promise(resolve => {
    const dialog = document.createElement('dialog');
    dialog.className = 'studio-session-prompt';
    const heading = document.createElement('h2'); heading.textContent = title;
    const text = document.createElement('p'); text.textContent = message;
    const choose = value => { dialog.close(); dialog.remove(); resolve(value); };
    const option = (label, hint, value) => {
      const button = document.createElement('button'); button.type = 'button';
      const strong = document.createElement('strong'); strong.textContent = label;
      const small = document.createElement('span'); small.textContent = hint;
      button.append(strong, small); button.addEventListener('click', () => choose(value)); return button;
    };
    dialog.append(heading, text, option(continueLabel, continueHint, 'continue'), option(newLabel, newHint, 'new'));
    dialog.addEventListener('cancel', event => { event.preventDefault(); choose('dismissed'); });
    document.body.append(dialog); dialog.showModal();
  });
}
