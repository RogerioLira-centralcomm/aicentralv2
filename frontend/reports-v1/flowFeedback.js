export const plural = (count, singular, multiple) => `${count} ${count === 1 ? singular : multiple}`;

export function savedAgo(savedAt, now = Date.now()) {
  if (!savedAt) return 'Salvo';
  const minutes = Math.max(0, Math.floor((now - savedAt) / 60000));
  if (minutes < 1) return 'Salvo agora';
  return `Salvo há ${plural(minutes, 'minuto', 'minutos')}`;
}

export function publishBlocked(issues) {
  return issues.some(issue => issue.severity === 'error' || issue.severity === 'bloqueante');
}
