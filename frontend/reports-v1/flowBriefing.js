import {FLOW_STAGES,stageFor,editableStage} from './flowStages.js';

export const PAGE_TYPE_LABELS={home:'Home',service:'Serviço',institutional:'Institucional',contact:'Contato',case:'Case',content:'Conteúdo',other:'Outro'};
export const ROLE_LABELS={none:'Não definida',entry:'Entrada',institutional:'Institucional',offer:'Oferta',content:'Conteúdo',intent:'Intenção',form:'Formulário',checkout:'Finalização de compra',conversion:'Confirmação',legal:'Página legal',error:'Erro'};

const PATH_TYPES=[
  [/^\/?$/,'home'],[/(contato|orcamento|fale-|agendar|reuniao)/i,'contact'],[/(case|portfolio|resultado|cliente)/i,'case'],
  [/(servico|solucao|solucoes|produto|plano|oferta)/i,'service'],[/(sobre|quem-somos|institucional|equipe|empresa)/i,'institutional'],
  [/(blog|artigo|conteudo|material|noticia|guia)/i,'content'],
];
const norm=value=>String(value||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();

/** What the board would pick for a step, from its address, name and place in the flow. */
export function recommend(node){
  const text=norm(`${node.path||node.spec?.suggested_path||''} ${node.title||''}`);
  const thanks=/(obrigad|thank|confirmacao|sucesso-envio)/.test(text);
  const type=node.type==='conversion'||thanks?'other':(PATH_TYPES.find(([re])=>re.test(text.trim()||'/'))?.[1]||'other');
  const stage=thanks||node.type==='conversion'?'conversion':editableStage({...node,stage:undefined,pageType:type});
  const role=thanks||node.type==='conversion'?'conversion':node.type==='error'?'error':({entry:'entry',intent:'intent',conversion:'conversion',support:'legal'})[stage]||({service:'offer',institutional:'institutional',case:'content',content:'content',home:'entry',contact:'intent'})[type]||'content';
  return {pageType:type,stage,role};
}

const BLOCKS={
  home:['Hero com proposta de valor e CTA principal','Serviços ou soluções em destaque','Prova social (logos, números, depoimentos)','Chamada final para contato'],
  service:['Hero com a promessa do serviço','Como funciona / etapas','Benefícios e diferenciais','Prova social ou case relacionado','FAQ','CTA repetido ao longo da página'],
  institutional:['Quem somos e propósito','Time e história','Diferenciais e valores','Prova social','CTA para contato'],
  contact:['Título curto e promessa de resposta','Formulário enxuto (nome, e-mail, telefone, mensagem)','Canais alternativos (WhatsApp, e-mail)','Confirmação de envio e próxima etapa'],
  case:['Resumo do desafio','Estratégia aplicada','Resultados com números','Depoimento do cliente','CTA para conversar sobre um projeto parecido'],
  content:['Título e resumo','Corpo do conteúdo com subtítulos','Conteúdos relacionados','CTA contextual'],
  other:['Mensagem principal','Conteúdo de apoio','CTA claro para o próximo passo'],
};
const CTA={home:'Fale com a gente',service:'Solicitar proposta',institutional:'Conheça nosso trabalho',contact:'Enviar mensagem',case:'Quero resultados como este',content:'Continuar navegando',other:'Continuar'};

/** Everything the board already knows around a step: brand, site, neighbours, conversion. */
export function briefingContext(node,config,{clientName='',host='',flowName=''}={}){
  const nodes=config?.nodes||[],edges=config?.edges||[];
  const byId=new Map(nodes.map(item=>[item.id,item]));
  const title=id=>byId.get(id)?.title;
  const from=edges.filter(edge=>edge.to===node.id).map(edge=>title(edge.from)).filter(Boolean);
  const to=edges.filter(edge=>edge.from===node.id).map(edge=>title(edge.to)).filter(Boolean);
  const rec=recommend(node);
  const type=node.pageType&&node.pageType!=='other'&&node.pageTypeStatus!=='unresolved'?node.pageType:rec.pageType;
  const conversions=nodes.filter(item=>item.type==='conversion').map(item=>item.title).filter(Boolean);
  const siteHost=node.host||host;
  return {brand:clientName,host:siteHost,flowName,from,to,type,stage:FLOW_STAGES.find(item=>item.id===(node.stage&&node.stage!=='source'?node.stage:rec.stage))?.label||'',conversions,
    path:node.path||node.spec?.suggested_path||'',title:node.title||'Página'};
}

/** Suggested values for the fields people would otherwise type; saved values win. */
export function suggestedSpec(node,ctx){
  const spec=node.spec||{};
  const where=ctx.brand||ctx.host;
  const goal=ctx.to.length?`Levar o visitante de ${ctx.from[0]||'a jornada'} até ${ctx.to[0]}`:`Cumprir o papel de “${ctx.title}” na jornada${where?` de ${where}`:''}`;
  return {
    goal:spec.goal||`${goal}.`,
    suggested_path:spec.suggested_path||ctx.path||'',
    headline:spec.headline||'',
    content:spec.content||(BLOCKS[ctx.type]||BLOCKS.other).map(item=>`- ${item}`).join('\n'),
    cta:spec.cta||CTA[ctx.type]||CTA.other,
    owner:spec.owner||'',due_date:spec.due_date||'',
    references:spec.references||'',notes:spec.notes||'',
  };
}

const date=value=>value?value.split('-').reverse().join('/'):'a definir';
const line=(label,value)=>value?`${label}: ${value}`:false;

export function teamBriefing(ctx,spec){
  const rows=[
    `BRIEFING DE PÁGINA — ${ctx.title}`,'',
    line('Marca',ctx.brand),line('Site',ctx.host),line('Fluxo',ctx.flowName),line('Endereço previsto',spec.suggested_path),
    line('Tipo de página',PAGE_TYPE_LABELS[ctx.type]),line('Etapa da jornada',ctx.stage),'',
    'OBJETIVO',spec.goal,'',
    'POSIÇÃO NA JORNADA',ctx.from.length?`Chega de: ${ctx.from.join(', ')}`:'Sem origem definida.',ctx.to.length?`Leva para: ${ctx.to.join(', ')}`:'Sem próximo passo definido.',
    ctx.conversions.length?`Conversão do fluxo: ${ctx.conversions.join(', ')}`:'','',
    spec.headline&&`TÍTULO / MENSAGEM PRINCIPAL\n${spec.headline}\n`,
    'CONTEÚDO E BLOCOS',spec.content,'',
    'CHAMADA PARA AÇÃO',spec.cta,'',
    spec.references&&`REFERÊNCIAS\n${spec.references}\n`,
    spec.notes&&`OBSERVAÇÕES\n${spec.notes}\n`,
    'MEDIÇÃO','Manter a Super Tag instalada e o endereço final igual ao previsto, para a página entrar na medição do fluxo.','',
    line('Responsável',spec.owner||'a definir'),line('Prazo',date(spec.due_date)),
  ];
  return rows.filter(item=>item!==false&&item!==undefined&&item!==null).join('\n').replace(/\n{3,}/g,'\n\n').trim();
}

export function agentBriefing(ctx,spec){
  const lines=[
    'Você é um designer e redator de landing pages. Crie a página descrita abaixo, pronta para implementação.','',
    '## Contexto',
    line('- Marca',ctx.brand),line('- Site',ctx.host),line('- Página',`${ctx.title}${spec.suggested_path?` (${spec.suggested_path})`:''}`),
    line('- Tipo',PAGE_TYPE_LABELS[ctx.type]),line('- Etapa da jornada',ctx.stage),
    ctx.from.length?`- Vem de: ${ctx.from.join(', ')}`:'',ctx.to.length?`- Leva para: ${ctx.to.join(', ')}`:'',
    ctx.conversions.length?`- Conversão final do fluxo: ${ctx.conversions.join(', ')}`:'','',
    '## Objetivo',spec.goal,'',
    spec.headline&&`## Mensagem principal\n${spec.headline}\n`,
    '## Blocos esperados',spec.content,'',
    '## Chamada para ação',spec.cta,'',
    spec.references&&`## Referências\n${spec.references}\n`,
    spec.notes&&`## Restrições e observações\n${spec.notes}\n`,
    '## Regras',
    '- Use apenas informações fornecidas aqui; marque como [A CONFIRMAR] o que faltar, sem inventar números ou depoimentos.',
    '- Escreva em português do Brasil, com tom coerente com a marca.',
    '- Um objetivo por página e um CTA principal.',
    '- Mantenha o endereço previsto para a Super Tag medir a visita.','',
    '## Entrega',
    '1. Estrutura da página, bloco a bloco, com o texto final de cada bloco.',
    '2. Título SEO (até 60 caracteres) e meta description (até 155).',
    '3. Lista do que precisa de imagem ou vídeo, com a descrição de cada um.',
  ];
  return lines.filter(item=>item!==false&&item!==undefined&&item!==null).join('\n').replace(/\n{3,}/g,'\n\n').trim();
}
