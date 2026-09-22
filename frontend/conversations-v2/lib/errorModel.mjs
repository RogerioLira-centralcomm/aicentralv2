const CREDIT_MESSAGE = /saldo insuficiente:\s*(?:esta execução estima|a execução usou)\s*(\d+)\s+tokens?\s+e há\s*(\d+)\s+disponíveis\.?/i;

const number = value => {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
};

const formatCredits = value => new Intl.NumberFormat('pt-BR').format(value || 0);

export function chatFailure(error) {
  const raw = String(error?.message || '').trim();
  const status = Number(error?.status || 0);
  const details = error?.details && typeof error.details === 'object' ? error.details : {};
  const match = raw.match(CREDIT_MESSAGE);
  const required = number(details.required_tokens) ?? number(match?.[1]);
  const available = number(details.available_tokens) ?? number(match?.[2]);

  if (error?.code === 'credits_insufficient' || match) {
    const requirement = required === null
      ? 'Esta solicitação precisa de créditos disponíveis para ser iniciada.'
      : `Esta solicitação precisa de ${formatCredits(required)} créditos.`;
    const balance = available === null ? '' : ` O saldo disponível é ${formatCredits(available)}.`;
    return {
      kind: 'credits',
      title: available === 0 ? 'Seus créditos acabaram' : 'Créditos insuficientes',
      detail: `${requirement}${balance} Adicione créditos no Workspace para continuar.`,
      guidance: 'Depois de adicionar créditos, envie a solicitação novamente.',
    };
  }

  if (status === 403) return {
    kind: 'session',
    title: 'Atualize a página para continuar',
    detail: 'Sua sessão de trabalho precisa ser renovada antes de enviar esta mensagem.',
    guidance: 'A mensagem foi mantida no campo de edição.',
  };

  if (status === 400 || status === 422) return {
    kind: 'input',
    title: 'Revise esta solicitação',
    detail: 'Não foi possível processar o pedido como ele está.',
    guidance: 'A mensagem foi mantida no campo para você ajustar e enviar novamente.',
  };

  if (status === 503) return {
    kind: 'unavailable',
    title: 'Cadu Chat está temporariamente indisponível',
    detail: 'Não foi possível concluir esta solicitação agora.',
    guidance: 'Sua mensagem foi mantida no campo. Tente novamente em alguns instantes.',
  };

  return {
    kind: 'generic',
    title: 'Não foi possível concluir esta solicitação',
    detail: 'A conversa não foi processada.',
    guidance: 'Sua mensagem foi mantida no campo para você revisar ou tentar novamente.',
  };
}
