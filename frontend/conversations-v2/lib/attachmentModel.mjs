export const MAX_ATTACHMENTS = 3;
export const MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024;

const acceptedExtension = /\.(png|jpe?g|webp|gif|pdf|txt|csv|md|json|docx|xlsx|pptx)$/i;

export const attachmentIssues = Object.freeze({
  limit: Object.freeze({
    title: 'Limite de anexos',
    detail: 'Envie no máximo três arquivos.',
  }),
  invalid: Object.freeze({
    title: 'Arquivo não aceito',
    detail: 'Use imagem, PDF, texto ou Office de até 15 MB.',
  }),
});

export function validateAttachment(file) {
  if (!file?.size || file.size > MAX_ATTACHMENT_BYTES || !acceptedExtension.test(file.name || '')) {
    return attachmentIssues.invalid;
  }
  return null;
}

export function createStagedAttachment(file, destination, previewUrl = '') {
  return {
    localId: crypto.randomUUID(),
    name: file.name,
    file,
    previewUrl,
    id: null,
    source: null,
    destination,
    uploading: false,
    error: false,
    intake: {state: 'pending'},
  };
}
