export function edgeMetricLabel(metric){
  if(!metric)return null;
  const observation=metric.observation;
  if(observation?.status==='no_data')return 'Sem dados no período';
  if(observation?.status==='unmeasured')return 'Conexão sem medição';
  if(observation?.status==='no_origin')return 'Sem sessões na origem';
  const sessions=observation?observation.sessions:metric.sessions;
  const rate=observation?observation.rate:metric.rate;
  if(sessions==null)return 'Conexão sem medição';
  return `${Number(sessions).toLocaleString('pt-BR')} · ${rate==null?'Taxa indisponível':`${rate}%`}`;
}
