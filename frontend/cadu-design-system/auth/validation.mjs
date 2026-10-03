// Client-side checks for the access screens. They mirror the server rules (routes.py) so the person sees the
// problem next to the field instead of after a full reload; the server still validates everything.
export const MIN_PASSWORD = 8;
export const CORPORATE_DOMAIN = 'centralcomm.media';
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const LOCAL_PART = /^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$/i;

export function validateEmail(value, {corporate = false} = {}) {
  const text = String(value || '').trim();
  if (!text) return corporate ? 'Informe seu usuário.' : 'Informe seu email.';
  if (corporate) {
    const [local, domain, ...rest] = text.split('@');
    const valid = !rest.length && LOCAL_PART.test(local || '') && (domain === undefined || domain.toLowerCase() === CORPORATE_DOMAIN);
    return valid ? '' : `Use apenas o usuário ou o email @${CORPORATE_DOMAIN}.`;
  }
  return EMAIL.test(text) ? '' : 'Confira o email: falta algo como nome@empresa.com.';
}

export const validateName = value => String(value || '').trim().length >= 2 ? '' : 'Informe seu nome completo.';
export const validateLoginPassword = value => value ? '' : 'Informe sua senha.';
export const validateNewPassword = value => String(value || '').length >= MIN_PASSWORD ? '' : `Use pelo menos ${MIN_PASSWORD} caracteres.`;
export const validateConfirmation = (password, confirmation) => {
  if (!confirmation) return 'Repita a senha.';
  return password === confirmation ? '' : 'As senhas não coincidem.';
};

/** Name of the first field with an error, following the visual order of the form. */
export const firstInvalid = (errors, order) => order.find(name => errors[name]) || '';
export const hasErrors = errors => Object.values(errors).some(Boolean);
