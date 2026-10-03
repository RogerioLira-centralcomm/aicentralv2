/** What the flow list says about data collection and results, from the per-flow numbers the API attaches (last 30 days). */
export const COLLECTION_DAYS = 30;

const stats = flow => flow?.stats || {};

export function flowItemCount(flow) {
  return (flow?.config?.nodes || []).length;
}

/** Whether the site is sending events: the tag's real traffic, not the availability monitor. */
export function flowCollection(flow) {
  const data = stats(flow);
  if (flow?.revoked_at) return {tone: 'bad', label: 'Tag revogada', hint: 'A Super Tag deste site foi revogada: nada é coletado.'};
  if (!flow?.allowed_host) return {tone: 'muted', label: 'Plano sem site', hint: 'Conecte um site para começar a medir.'};
  if (data.events > 0) return {tone: 'ok', label: 'Recebendo dados', lastEventAt: data.last_event_at,
    hint: `${data.events.toLocaleString('pt-BR')} eventos nos últimos ${COLLECTION_DAYS} dias`};
  if (flow.status !== 'published') return {tone: 'muted', label: 'Aguardando publicação', hint: 'Publique o fluxo e instale a Super Tag para coletar.'};
  return {tone: 'warn', label: 'Sem dados', hint: `Nenhum evento chegou nos últimos ${COLLECTION_DAYS} dias. Confira se a Super Tag está instalada no site.`};
}

/** Entries into the flow and how many of them converted. */
export function flowResults(flow) {
  const data = stats(flow);
  const entries = data.entry_sessions || data.sessions || 0;
  const converted = data.converted_sessions || 0;
  return {
    entries, conversions: data.conversions || 0, converted,
    rate: entries > 0 ? Math.min(100, (converted / entries) * 100) : null,
    hasData: (data.events || 0) > 0,
  };
}

export const formatRate = rate => rate == null ? '—' : `${rate.toLocaleString('pt-BR', {minimumFractionDigits: rate < 10 ? 1 : 0, maximumFractionDigits: 1})}%`;
