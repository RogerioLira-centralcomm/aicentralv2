import {FLOW_STAGES,stageFor} from './flowStages.js';

const roleLabels={none:'Não definida',entry:'Entrada',institutional:'Institucional',offer:'Oferta',content:'Conteúdo',intent:'Intenção',form:'Formulário',checkout:'Finalização de compra',conversion:'Confirmação',legal:'Página legal',error:'Erro'};
const sourceLabels={user:'usuário',manual:'usuário',ai:'sugestão',rule:'regra',typesafe:'sugestão',blueprint:'montagem assistida'};
export const flowStageLabel=node=>FLOW_STAGES.find(stage=>stage.id===stageFor(node))?.label||'Etapa não definida';
export const flowRoleLabel=role=>roleLabels[role]||'Função não definida';
export const flowRoleSourceLabel=source=>sourceLabels[source]||'origem não informada';
