export {MEASURED_TYPES,NODE_STATUSES,hasRealPath,isMeasured,isPlanned,nodeStatus} from './flowValidation.js';

export const NODE_STATUS_LABELS={planned:'Planejado',in_production:'Em produção',ready:'Pronto',live:'No ar'};
export const SPEC_FIELDS=[
  ['goal','Objetivo do passo','textarea',500],['suggested_path','Endereço sugerido','text',500],
  ['headline','Título ou mensagem principal','text',200],['content','Conteúdo e blocos','textarea',2000],
  ['cta','Chamada para ação','text',200],['owner','Responsável','text',120],['due_date','Prazo','date',10],
  ['references','Referências','textarea',2000],['notes','Observações','textarea',2000],
];
