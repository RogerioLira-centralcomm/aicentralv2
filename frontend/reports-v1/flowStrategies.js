import {flowBlockRegistry} from './flowBlockRegistry.js';
import {stageX} from './flowStages.js';

// Curated starting points for planners: every measured step starts planned, with a production brief.
const ROW_HEIGHT = 170;
const MEASURED = new Set(['page','form','event','conversion','whatsapp','error']);

export const FLOW_STRATEGIES = Object.freeze([
  {
    id: 'leads-landing', name: 'Captação de leads com landing page', objective: 'Leads', siteKind: 'landing',
    summary: 'Anúncios levam a uma landing page com formulário. Quem não converte volta por remarketing.',
    channels: [['traffic.meta', true], ['traffic.google_search', true], ['traffic.instagram', false], ['traffic.linkedin', false], ['traffic.tiktok', false], ['traffic.retargeting', true]],
    steps: [
      {key: 'lp', kind: 'page.landing', title: 'Landing page da oferta', stage: 'entry', spec: {goal: 'Apresentar a oferta e levar ao formulário.', suggested_path: '/oferta', headline: 'Promessa principal da campanha', cta: 'Quero receber a proposta'}},
      {key: 'form', kind: 'page.form', title: 'Formulário de cadastro', stage: 'intent', spec: {goal: 'Captar nome, e-mail e telefone com o mínimo de campos.', content: 'Nome, e-mail, telefone e consentimento LGPD.', cta: 'Enviar'}},
      {key: 'lead', kind: 'conversion.lead', title: 'Lead captado', stage: 'conversion', spec: {goal: 'Contar o envio do formulário como lead.', notes: 'Evento sugerido: lead_enviado.'}},
    ],
    links: [['@paid', 'lp'], ['traffic.retargeting', 'lp', 'Remarketing'], ['lp', 'form'], ['form', 'lead']],
  },
  {
    id: 'leads-whatsapp', name: 'Conversa no WhatsApp', objective: 'Conversas e vendas', siteKind: 'landing',
    summary: 'A página leva a um clique no WhatsApp; o atendimento comercial segue no CRM.',
    channels: [['traffic.meta', true], ['traffic.instagram', true], ['traffic.google_search', false], ['traffic.tiktok', false]],
    steps: [
      {key: 'lp', kind: 'page.landing', title: 'Página com botão de WhatsApp', stage: 'entry', spec: {goal: 'Gerar confiança e levar ao botão de conversa.', suggested_path: '/fale-conosco', cta: 'Chamar no WhatsApp'}},
      {key: 'click', kind: 'event.whatsapp', title: 'Clique no WhatsApp', stage: 'intent', spec: {goal: 'Medir o clique no link do WhatsApp.', notes: 'Capturado automaticamente pela Super Tag.'}},
      {key: 'conversa', kind: 'conversion.lead', title: 'Conversa iniciada', stage: 'conversion', spec: {goal: 'Contar a conversa iniciada como resultado da campanha.'}},
      {key: 'atendimento', kind: 'crm.pipeline', title: 'Atendimento comercial', stage: 'support'},
      {key: 'venda', kind: 'crm.deal_won', title: 'Venda fechada', stage: 'support'},
      {key: 'perdida', kind: 'crm.deal_lost', title: 'Sem fechamento', stage: 'support'},
    ],
    links: [['@paid', 'lp'], ['lp', 'click'], ['click', 'conversa'], ['conversa', 'atendimento'], ['atendimento', 'venda', 'Ganhou'], ['atendimento', 'perdida', 'Perdeu']],
  },
  {
    id: 'event-webinar', name: 'Inscrição em evento ou webinar', objective: 'Inscrições e vendas', siteKind: 'landing',
    summary: 'Inscrição, lembretes até o dia e oferta durante o evento.',
    channels: [['traffic.meta', true], ['traffic.linkedin', true], ['traffic.youtube', false], ['communication.email', true]],
    steps: [
      {key: 'inscricao', kind: 'page.webinar', title: 'Página de inscrição', stage: 'entry', spec: {goal: 'Explicar o evento e levar à inscrição.', suggested_path: '/evento', headline: 'Tema, data e o que a pessoa leva', cta: 'Garantir minha vaga'}},
      {key: 'form', kind: 'page.form', title: 'Formulário de inscrição', stage: 'intent', spec: {content: 'Nome, e-mail e WhatsApp para lembretes.', cta: 'Inscrever'}},
      {key: 'inscrito', kind: 'conversion.signup', title: 'Inscrição confirmada', stage: 'conversion', spec: {goal: 'Contar cada inscrição confirmada.', notes: 'Evento sugerido: inscricao_confirmada.'}},
      {key: 'lembretes', kind: 'logic.delay', title: 'Lembretes até o evento', stage: 'conversion'},
      {key: 'sala', kind: 'page.webinar', title: 'Sala do evento', stage: 'support', spec: {goal: 'Receber os inscritos no dia e apresentar a oferta.', suggested_path: '/evento/ao-vivo'}},
      {key: 'compra', kind: 'conversion.purchase', title: 'Compra da oferta', stage: 'support', spec: {goal: 'Contar compras feitas a partir do evento.'}},
    ],
    links: [['@paid', 'inscricao'], ['communication.email', 'inscricao', 'Convite'], ['inscricao', 'form'], ['form', 'inscrito'], ['inscrito', 'lembretes'], ['lembretes', 'sala'], ['sala', 'compra']],
  },
  {
    id: 'ecommerce', name: 'Venda em e-commerce', objective: 'Compras', siteKind: 'ecommerce',
    summary: 'Do anúncio ao produto, carrinho e checkout, com recuperação de carrinho.',
    channels: [['traffic.google_search', true], ['traffic.meta', true], ['traffic.google_display', false], ['traffic.tiktok', false], ['traffic.retargeting', true], ['communication.email', true]],
    steps: [
      {key: 'produto', kind: 'page.sales', title: 'Página de produto', stage: 'entry', spec: {goal: 'Apresentar o produto e levar ao carrinho.', suggested_path: '/produto', cta: 'Adicionar ao carrinho'}},
      {key: 'carrinho', kind: 'page.generic', title: 'Carrinho', stage: 'exploration', spec: {suggested_path: '/carrinho', cta: 'Finalizar compra'}},
      {key: 'checkout', kind: 'page.checkout', title: 'Checkout', stage: 'intent', spec: {goal: 'Concluir pagamento com o menor atrito possível.', suggested_path: '/checkout'}},
      {key: 'compra', kind: 'conversion.purchase', title: 'Compra concluída', stage: 'conversion', spec: {goal: 'Contar o pedido pago.', notes: 'Evento sugerido: purchase, com o valor do pedido.'}},
    ],
    links: [['@paid', 'produto'], ['traffic.retargeting', 'produto', 'Remarketing'], ['communication.email', 'checkout', 'Recuperação de carrinho'], ['produto', 'carrinho'], ['carrinho', 'checkout'], ['checkout', 'compra']],
  },
  {
    id: 'b2b-demand', name: 'Geração de demanda B2B', objective: 'Reuniões e negócios', siteKind: 'multipagina',
    summary: 'Conteúdo e página da solução levam ao contato; a venda segue em reunião e proposta.',
    channels: [['traffic.linkedin', true], ['traffic.google_search', true], ['traffic.organic_search', false], ['communication.email_sequence', false]],
    steps: [
      {key: 'conteudo', kind: 'page.blog', title: 'Conteúdo ou estudo de caso', stage: 'entry', spec: {goal: 'Atrair pelo problema que a solução resolve.', suggested_path: '/conteudos/estudo-de-caso'}},
      {key: 'solucao', kind: 'page.generic', title: 'Página da solução', stage: 'exploration', spec: {goal: 'Mostrar benefícios, provas e próximos passos.', suggested_path: '/solucao', cta: 'Falar com um especialista'}},
      {key: 'contato', kind: 'page.form', title: 'Formulário de contato', stage: 'intent', spec: {content: 'Nome, e-mail corporativo, empresa e cargo.', cta: 'Agendar conversa'}},
      {key: 'lead', kind: 'conversion.lead', title: 'Lead qualificado', stage: 'conversion', spec: {goal: 'Contar contatos que pedem conversa.'}},
      {key: 'reuniao', kind: 'crm.meeting', title: 'Reunião agendada', stage: 'support'},
      {key: 'ganho', kind: 'crm.deal_won', title: 'Negócio ganho', stage: 'support'},
      {key: 'perdido', kind: 'crm.deal_lost', title: 'Negócio perdido', stage: 'support'},
    ],
    links: [['@paid', 'conteudo'], ['traffic.organic_search', 'conteudo'], ['communication.email_sequence', 'solucao', 'Nutrição'], ['conteudo', 'solucao'], ['solucao', 'contato'], ['contato', 'lead'], ['lead', 'reuniao'], ['reuniao', 'ganho', 'Ganhou'], ['reuniao', 'perdido', 'Perdeu']],
  },
  {
    id: 'brand-consideration', name: 'Presença e consideração', objective: 'Engajamento', siteKind: 'institucional',
    summary: 'Mídia de alcance leva ao site institucional; o sucesso é visitar serviços, cases e contato.',
    channels: [['traffic.youtube', true], ['traffic.dv360', true], ['traffic.google_display', false], ['traffic.organic_search', true], ['traffic.organic_social', false]],
    steps: [
      {key: 'home', kind: 'page.generic', title: 'Página inicial', stage: 'entry', spec: {goal: 'Apresentar a marca e direcionar para serviços.', suggested_path: '/'}},
      {key: 'servicos', kind: 'page.generic', title: 'Serviços', stage: 'exploration', spec: {suggested_path: '/servicos'}},
      {key: 'cases', kind: 'page.generic', title: 'Cases', stage: 'exploration', spec: {suggested_path: '/cases'}},
      {key: 'contato', kind: 'page.form', title: 'Contato', stage: 'intent', spec: {cta: 'Enviar mensagem'}},
      {key: 'lead', kind: 'conversion.lead', title: 'Contato enviado', stage: 'conversion', spec: {goal: 'Contar mensagens enviadas pelo site.'}},
    ],
    links: [['@paid', 'home'], ['traffic.organic_search', 'home'], ['traffic.organic_social', 'home'], ['home', 'servicos'], ['home', 'cases'], ['servicos', 'contato'], ['cases', 'contato'], ['contato', 'lead']],
  },
  {
    id: 'ab-landing', name: 'Teste A/B de landing page', objective: 'Leads', siteKind: 'landing',
    summary: 'O tráfego é dividido entre duas versões da página para descobrir a que converte mais.',
    channels: [['traffic.meta', true], ['traffic.google_search', true]],
    steps: [
      {key: 'divisao', kind: 'logic.condition', title: 'Divisão 50/50', stage: 'entry', condition: {mode: 'ab_test', split: [50, 50], metric: 'Taxa de lead'}},
      {key: 'a', kind: 'page.landing', title: 'Landing page A', stage: 'exploration', spec: {goal: 'Versão de controle.', suggested_path: '/oferta-a'}},
      {key: 'b', kind: 'page.landing', title: 'Landing page B', stage: 'exploration', spec: {goal: 'Versão com a mudança a testar.', suggested_path: '/oferta-b', notes: 'Mude uma coisa por vez: título, oferta ou formulário.'}},
      {key: 'form', kind: 'page.form', title: 'Formulário', stage: 'intent', spec: {content: 'O mesmo formulário nas duas versões.'}},
      {key: 'lead', kind: 'conversion.lead', title: 'Lead captado', stage: 'conversion', spec: {goal: 'Comparar a taxa de lead de A e B.'}},
    ],
    links: [['@paid', 'divisao'], ['divisao', 'a', 'Variante A · 50%'], ['divisao', 'b', 'Variante B · 50%'], ['a', 'form'], ['b', 'form'], ['form', 'lead']],
  },
]);

export const defaultStrategyChannels = strategy => strategy.channels.filter(([, selected]) => selected).map(([kind]) => kind);

/** Builds an editable v2 flow document from a strategy and the channels the planner keeps. */
export function buildStrategyConfig(strategy, channelKinds = defaultStrategyChannels(strategy)) {
  const chosen = strategy.channels.map(([kind]) => kind).filter(kind => channelKinds.includes(kind));
  const rows = {};
  const place = stage => {const row = rows[stage] || 0; rows[stage] = row + 1; return {x: stageX(stage), y: 80 + row * ROW_HEIGHT};};
  const ids = {};
  const nodes = [];
  for (const kind of chosen) {
    const block = flowBlockRegistry[kind];
    const id = crypto.randomUUID();
    ids[kind] = id;
    nodes.push({id, type: 'source', kind, source: block.source, title: block.label, stage: 'source', origin: 'strategy',
      data: {label: block.label, url: ''}, ...place('source')});
  }
  for (const step of strategy.steps) {
    const block = flowBlockRegistry[step.kind];
    const id = crypto.randomUUID();
    ids[step.key] = id;
    const node = {id, type: block.type, kind: step.kind, title: step.title, stage: step.stage, origin: 'strategy',
      data: {label: step.title, url: ''}, ...place(step.stage)};
    if (MEASURED.has(block.type)) Object.assign(node, {status: 'planned', ...(step.spec ? {spec: {...step.spec}} : {})});
    if (step.condition) node.condition = {...step.condition};
    nodes.push(node);
  }
  const paid = chosen.filter(kind => kind.startsWith('traffic.') && !strategy.links.some(([from]) => from === kind));
  const edges = strategy.links.flatMap(([from, to, label]) => (from === '@paid' ? paid : [from]).filter(key => ids[key] && ids[to])
    .map(key => ({id: crypto.randomUUID(), from: ids[key], to: ids[to], variant: 'direct', label: label || 'Próximo'})));
  return {schema_version: 2, site_kind: strategy.siteKind, strategy_id: strategy.id, nodes, edges};
}
