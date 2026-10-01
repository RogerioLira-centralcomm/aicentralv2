import {flowBlockRegistry} from './flowBlockRegistry.js';
import {FLOW_GRID} from './flowStages.js';
import {defaultMedia, isPaidPlatform} from './flowMedia.js';

// Curated starting points for planners: every measured step starts planned, with a production brief.
// Cards are about 100px tall (taller with a page capture); rows are a multiple of the board grid.
const ROW_HEIGHT = FLOW_GRID * 7;
const TOP = FLOW_GRID * 6;
const COLUMN_START = FLOW_GRID * 4;
const COLUMN_WIDTH = FLOW_GRID * 15;
const MEASURED = new Set(['page','form','event','conversion','whatsapp','error']);

const STRATEGY_SOURCE = [
  {
    id: 'leads-landing', sector: 'Geral', mediaObjective: 'leads', name: 'Captação de leads com landing page', objective: 'Leads', siteKind: 'landing',
    summary: 'Anúncios levam a uma landing page com formulário. Quem não converte volta por remarketing.',
    channels: [['traffic.meta', true], ['traffic.google_search', true], ['traffic.instagram', false], ['traffic.linkedin', false], ['traffic.tiktok', false], ['traffic.retargeting', true]],
    steps: [
      {key: 'lp', kind: 'page.landing', title: 'Landing page da oferta', stage: 'entry', spec: {goal: 'Apresentar a oferta e levar ao formulário.', suggested_path: '/oferta', headline: 'Promessa principal da campanha', cta: 'Quero receber a proposta'}},
      {key: 'form', kind: 'page.form', title: 'Formulário de cadastro', stage: 'intent', spec: {goal: 'Captar nome, e-mail e telefone com o mínimo de campos.', content: 'Nome, e-mail, telefone e consentimento LGPD.', cta: 'Enviar'}},
      {key: 'lead', kind: 'conversion.lead', title: 'Lead captado', stage: 'conversion', spec: {goal: 'Contar o envio do formulário como lead.', notes: 'Evento sugerido: lead_enviado.'}},
    ],
    links: [['@paid', 'lp', null, 100], ['traffic.retargeting', 'lp', 'Remarketing', 100], ['lp', 'form', null, 35], ['form', 'lead', null, 60]],
  },
  {
    id: 'leads-whatsapp', sector: 'Geral', mediaObjective: 'mensagens', name: 'Conversa no WhatsApp', objective: 'Conversas e vendas', siteKind: 'landing',
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
    links: [['@paid', 'lp', null, 100], ['lp', 'click', null, 20], ['click', 'conversa', null, 70], ['conversa', 'atendimento', null, 100], ['atendimento', 'venda', 'Ganhou', 20], ['atendimento', 'perdida', 'Perdeu', 80]],
  },
  {
    id: 'event-webinar', sector: 'Eventos', mediaObjective: 'leads', name: 'Inscrição em evento ou webinar', objective: 'Inscrições e vendas', siteKind: 'landing',
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
    links: [['@paid', 'inscricao', null, 100], ['communication.email', 'inscricao', 'Convite', 100], ['inscricao', 'form', null, 40], ['form', 'inscrito', null, 80], ['inscrito', 'lembretes', null, 100], ['lembretes', 'sala', null, 40], ['sala', 'compra', null, 10]],
  },
  {
    id: 'ecommerce', sector: 'Varejo', mediaObjective: 'vendas', name: 'Venda em e-commerce', objective: 'Compras', siteKind: 'ecommerce',
    summary: 'Do anúncio ao produto, carrinho e checkout, com recuperação de carrinho.',
    channels: [['traffic.google_search', true], ['traffic.meta', true], ['traffic.google_display', false], ['traffic.tiktok', false], ['traffic.retargeting', true], ['communication.email', true]],
    steps: [
      {key: 'produto', kind: 'page.sales', title: 'Página de produto', stage: 'entry', spec: {goal: 'Apresentar o produto e levar ao carrinho.', suggested_path: '/produto', cta: 'Adicionar ao carrinho'}},
      {key: 'carrinho', kind: 'page.generic', title: 'Carrinho', stage: 'exploration', spec: {suggested_path: '/carrinho', cta: 'Finalizar compra'}},
      {key: 'checkout', kind: 'page.checkout', title: 'Checkout', stage: 'intent', spec: {goal: 'Concluir pagamento com o menor atrito possível.', suggested_path: '/checkout'}},
      {key: 'compra', kind: 'conversion.purchase', title: 'Compra concluída', stage: 'conversion', spec: {goal: 'Contar o pedido pago.', notes: 'Evento sugerido: purchase, com o valor do pedido.'}},
    ],
    links: [['@paid', 'produto', null, 100], ['traffic.retargeting', 'produto', 'Remarketing', 100], ['communication.email', 'checkout', 'Recuperação de carrinho', 100], ['produto', 'carrinho', null, 10], ['carrinho', 'checkout', null, 50], ['checkout', 'compra', null, 60]],
  },
  {
    id: 'b2b-demand', sector: 'B2B', mediaObjective: 'leads', name: 'Geração de demanda B2B', objective: 'Reuniões e negócios', siteKind: 'multipagina',
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
    links: [['@paid', 'conteudo', null, 100], ['traffic.organic_search', 'conteudo', null, 100], ['communication.email_sequence', 'solucao', 'Nutrição', 100], ['conteudo', 'solucao', null, 25], ['solucao', 'contato', null, 8], ['contato', 'lead', null, 70], ['lead', 'reuniao', null, 40], ['reuniao', 'ganho', 'Ganhou', 25], ['reuniao', 'perdido', 'Perdeu', 75]],
  },
  {
    id: 'brand-consideration', sector: 'Marca', mediaObjective: 'alcance', name: 'Presença e consideração', objective: 'Engajamento', siteKind: 'institucional',
    summary: 'Mídia de alcance leva ao site institucional; o sucesso é visitar serviços, cases e contato.',
    channels: [['traffic.youtube', true], ['traffic.dv360', true], ['traffic.google_display', false], ['traffic.organic_search', true], ['traffic.organic_social', false]],
    steps: [
      {key: 'home', kind: 'page.generic', title: 'Página inicial', stage: 'entry', spec: {goal: 'Apresentar a marca e direcionar para serviços.', suggested_path: '/'}},
      {key: 'servicos', kind: 'page.generic', title: 'Serviços', stage: 'exploration', spec: {suggested_path: '/servicos'}},
      {key: 'cases', kind: 'page.generic', title: 'Cases', stage: 'exploration', spec: {suggested_path: '/cases'}},
      {key: 'contato', kind: 'page.form', title: 'Contato', stage: 'intent', spec: {cta: 'Enviar mensagem'}},
      {key: 'lead', kind: 'conversion.lead', title: 'Contato enviado', stage: 'conversion', spec: {goal: 'Contar mensagens enviadas pelo site.'}},
    ],
    links: [['@paid', 'home', null, 100], ['traffic.organic_search', 'home', null, 100], ['traffic.organic_social', 'home', null, 100], ['home', 'servicos', null, 30], ['home', 'cases', null, 15], ['servicos', 'contato', null, 5], ['cases', 'contato', null, 8], ['contato', 'lead', null, 60]],
  },
  {
    id: 'ab-landing', sector: 'Testes', mediaObjective: 'leads', name: 'Teste A/B de landing page', objective: 'Leads', siteKind: 'landing',
    summary: 'O tráfego é dividido entre duas versões da página para descobrir a que converte mais.',
    channels: [['traffic.meta', true], ['traffic.google_search', true]],
    steps: [
      {key: 'divisao', kind: 'logic.condition', title: 'Divisão 50/50', stage: 'entry', condition: {mode: 'ab_test', split: [50, 50], metric: 'Taxa de lead'}},
      {key: 'a', kind: 'page.landing', title: 'Landing page A', stage: 'exploration', spec: {goal: 'Versão de controle.', suggested_path: '/oferta-a'}},
      {key: 'b', kind: 'page.landing', title: 'Landing page B', stage: 'exploration', spec: {goal: 'Versão com a mudança a testar.', suggested_path: '/oferta-b', notes: 'Mude uma coisa por vez: título, oferta ou formulário.'}},
      {key: 'form', kind: 'page.form', title: 'Formulário', stage: 'intent', spec: {content: 'O mesmo formulário nas duas versões.'}},
      {key: 'lead', kind: 'conversion.lead', title: 'Lead captado', stage: 'conversion', spec: {goal: 'Comparar a taxa de lead de A e B.'}},
    ],
    links: [['@paid', 'divisao', null, 100], ['divisao', 'a', 'Variante A · 50%', 50], ['divisao', 'b', 'Variante B · 50%', 50], ['a', 'form', null, 35], ['b', 'form', null, 35], ['form', 'lead', null, 60]],
  },
  {
    id: 'education-enrollment', sector: 'Educação', mediaObjective: 'leads', name: 'Captação de alunos', objective: 'Matrículas', siteKind: 'landing',
    summary: 'Anúncios levam à página do curso; o interesse vira atendimento do consultor e matrícula.',
    channels: [['traffic.google_search', true], ['traffic.meta', true], ['traffic.youtube', false], ['traffic.retargeting', true], ['communication.email_sequence', false]],
    steps: [
      {key: 'curso', kind: 'page.landing', title: 'Página do curso', stage: 'entry', spec: {goal: 'Mostrar grade, diferenciais, formato e investimento.', suggested_path: '/curso', cta: 'Quero saber mais'}},
      {key: 'interesse', kind: 'page.form', title: 'Formulário de interesse', stage: 'intent', spec: {content: 'Nome, WhatsApp, curso e turno de interesse.', cta: 'Falar com um consultor'}},
      {key: 'lead', kind: 'conversion.lead', title: 'Interessado captado', stage: 'conversion', spec: {goal: 'Contar cada pedido de contato.'}},
      {key: 'consultor', kind: 'crm.meeting', title: 'Atendimento do consultor', stage: 'support'},
      {key: 'matricula', kind: 'crm.deal_won', title: 'Matrícula realizada', stage: 'support'},
    ],
    links: [['@paid', 'curso', null, 100], ['communication.email_sequence', 'curso', 'Nutrição', 100], ['curso', 'interesse', null, 25], ['interesse', 'lead', null, 70], ['lead', 'consultor', null, 60], ['consultor', 'matricula', 'Matriculou', 20]],
  },
  {
    id: 'real-estate-launch', sector: 'Imobiliário', mediaObjective: 'leads', name: 'Lançamento imobiliário', objective: 'Visitas e vendas', siteKind: 'landing',
    summary: 'A página do empreendimento capta cadastros; o corretor agenda a visita ao decorado e conduz a proposta.',
    channels: [['traffic.meta', true], ['traffic.google_search', true], ['traffic.youtube', false], ['traffic.retargeting', true]],
    steps: [
      {key: 'empreendimento', kind: 'page.landing', title: 'Página do empreendimento', stage: 'entry', spec: {goal: 'Apresentar plantas, localização, condições e diferenciais.', suggested_path: '/lancamento', cta: 'Quero receber a tabela'}},
      {key: 'cadastro', kind: 'page.form', title: 'Cadastro de interesse', stage: 'intent', spec: {content: 'Nome, WhatsApp, renda aproximada e tipologia de interesse.', cta: 'Receber tabela'}},
      {key: 'lead', kind: 'conversion.lead', title: 'Cadastro recebido', stage: 'conversion', spec: {goal: 'Contar cadastros qualificados.'}},
      {key: 'visita', kind: 'crm.meeting', title: 'Visita ao decorado', stage: 'support'},
      {key: 'venda', kind: 'crm.deal_won', title: 'Proposta aceita', stage: 'support'},
      {key: 'perdida', kind: 'crm.deal_lost', title: 'Sem negócio', stage: 'support'},
    ],
    links: [['@paid', 'empreendimento', null, 100], ['empreendimento', 'cadastro', null, 15], ['cadastro', 'lead', null, 75], ['lead', 'visita', null, 25], ['visita', 'venda', 'Comprou', 15], ['visita', 'perdida', 'Não comprou', 85]],
  },
  {
    id: 'health-appointment', sector: 'Saúde', mediaObjective: 'leads', name: 'Agendamento de consulta', objective: 'Consultas agendadas', siteKind: 'multipagina',
    summary: 'A busca leva à página da especialidade; o paciente agenda online ou chama no WhatsApp.',
    channels: [['traffic.google_search', true], ['traffic.organic_search', true], ['traffic.meta', false]],
    steps: [
      {key: 'especialidade', kind: 'page.generic', title: 'Página da especialidade', stage: 'entry', spec: {goal: 'Explicar a especialidade, os profissionais e os convênios.', suggested_path: '/especialidades', cta: 'Agendar consulta'}},
      {key: 'agenda', kind: 'page.calendar', title: 'Agenda online', stage: 'intent', spec: {goal: 'Escolher profissional, data e horário.', suggested_path: '/agendar'}},
      {key: 'whatsapp', kind: 'event.whatsapp', title: 'Clique no WhatsApp', stage: 'intent', spec: {goal: 'Atender quem prefere conversar antes de agendar.'}},
      {key: 'agendada', kind: 'conversion.signup', title: 'Consulta agendada', stage: 'conversion', spec: {goal: 'Contar agendamentos confirmados.', notes: 'Evento sugerido: consulta_agendada.'}},
    ],
    links: [['@paid', 'especialidade', null, 100], ['traffic.organic_search', 'especialidade', null, 100], ['especialidade', 'agenda', null, 20], ['especialidade', 'whatsapp', null, 10], ['agenda', 'agendada', null, 50], ['whatsapp', 'agendada', 'Pelo WhatsApp', 40]],
  },
  {
    id: 'saas-trial', sector: 'Tecnologia', mediaObjective: 'leads', name: 'Teste grátis de software', objective: 'Assinaturas', siteKind: 'multipagina',
    summary: 'A página do produto leva ao cadastro do teste; a sequência de e-mails ativa o uso até a assinatura.',
    channels: [['traffic.google_search', true], ['traffic.linkedin', true], ['traffic.meta', false], ['communication.email_sequence', true]],
    steps: [
      {key: 'produto', kind: 'page.sales', title: 'Página do produto', stage: 'entry', spec: {goal: 'Mostrar o problema resolvido, provas e planos.', suggested_path: '/produto', cta: 'Testar grátis'}},
      {key: 'cadastro', kind: 'page.form', title: 'Cadastro do teste', stage: 'intent', spec: {content: 'Nome, e-mail corporativo e empresa; sem cartão.', cta: 'Começar teste'}},
      {key: 'trial', kind: 'conversion.signup', title: 'Teste iniciado', stage: 'conversion', spec: {goal: 'Contar contas de teste criadas.', notes: 'Evento sugerido: trial_iniciado.'}},
      {key: 'assinatura', kind: 'conversion.purchase', title: 'Assinatura', stage: 'support', spec: {goal: 'Contar testes que viram assinatura.'}},
    ],
    links: [['@paid', 'produto', null, 100], ['produto', 'cadastro', null, 15], ['cadastro', 'trial', null, 70], ['communication.email_sequence', 'produto', 'Ativação por e-mail', 100], ['trial', 'assinatura', null, 15]],
  },
  {
    id: 'local-store', sector: 'Varejo', mediaObjective: 'trafego', name: 'Visita à loja física', objective: 'Visitas à loja', siteKind: 'institucional',
    summary: 'Mídia local e busca levam à página da loja; a pessoa pede a rota ou chama no WhatsApp antes de ir.',
    channels: [['traffic.meta', true], ['traffic.organic_search', true], ['traffic.qr', false], ['traffic.google_search', false]],
    steps: [
      {key: 'loja', kind: 'page.generic', title: 'Página da loja', stage: 'entry', spec: {goal: 'Endereço, horário, estoque em destaque e ofertas da semana.', suggested_path: '/loja', cta: 'Como chegar'}},
      {key: 'rota', kind: 'event.button', title: 'Clique em “Como chegar”', stage: 'intent', spec: {goal: 'Medir quem pede a rota até a loja.', notes: 'Evento sugerido: rota_solicitada.'}},
      {key: 'whatsapp', kind: 'event.whatsapp', title: 'Clique no WhatsApp', stage: 'intent'},
      {key: 'visita', kind: 'conversion.generic', title: 'Intenção de visita', stage: 'conversion', spec: {goal: 'Somar pedidos de rota e conversas como intenção de visita.'}},
    ],
    links: [['@paid', 'loja', null, 100], ['traffic.organic_search', 'loja', null, 100], ['traffic.qr', 'loja', 'QR na vitrine', 100], ['loja', 'rota', null, 12], ['loja', 'whatsapp', null, 6], ['rota', 'visita', null, 100], ['whatsapp', 'visita', null, 60]],
  },
  {
    id: 'reach-awareness', sector: 'Marca', mediaObjective: 'alcance', name: 'Alcance e reconhecimento de marca', objective: 'Alcance', siteKind: 'institucional',
    summary: 'Campanhas de alcance apresentam a marca a um público novo; quem visita o site entra em uma lista para ser impactado de novo.',
    channels: [['traffic.youtube', true], ['traffic.meta', true], ['traffic.instagram', true], ['traffic.tiktok', false], ['traffic.google_display', false], ['traffic.organic_social', false]],
    steps: [
      {key: 'home', kind: 'page.landing', title: 'Página de apresentação', stage: 'entry', spec: {goal: 'Contar quem somos em poucos segundos e convidar a conhecer mais.', suggested_path: '/', headline: 'O que a marca resolve, em uma frase', cta: 'Conhecer a marca'}},
      {key: 'video', kind: 'event.video', title: 'Vídeo institucional assistido', stage: 'exploration', spec: {goal: 'Medir quem assiste ao vídeo até o fim.', notes: 'Evento sugerido: video_completo.'}},
      {key: 'sobre', kind: 'page.generic', title: 'Quem somos', stage: 'exploration', spec: {suggested_path: '/sobre'}},
      {key: 'newsletter', kind: 'page.form', title: 'Cadastro para novidades', stage: 'intent', spec: {goal: 'Formar uma lista própria para campanhas de remarketing.', content: 'E-mail e consentimento LGPD.', cta: 'Quero receber novidades'}},
      {key: 'inscrito', kind: 'conversion.signup', title: 'Inscrito na lista', stage: 'conversion', spec: {goal: 'Contar cada cadastro como público aquecido.', notes: 'Evento sugerido: inscricao_novidades.'}},
    ],
    links: [['@paid', 'home', null, 100], ['traffic.organic_social', 'home', null, 100], ['home', 'video', null, 25], ['home', 'sobre', null, 18], ['video', 'newsletter', null, 8], ['sobre', 'newsletter', null, 6], ['newsletter', 'inscrito', null, 55]],
  },
  {
    id: 'content-traffic', sector: 'Conteúdo', mediaObjective: 'trafego', name: 'Conteúdo e tráfego qualificado', objective: 'Visitas e leitura', siteKind: 'multipagina',
    summary: 'Artigos atraem quem pesquisa o problema; o sucesso é ler até o fim e baixar um material.',
    channels: [['traffic.organic_search', true], ['traffic.organic_social', true], ['traffic.linkedin', false], ['traffic.meta', false], ['communication.email', false]],
    steps: [
      {key: 'artigo', kind: 'page.blog', title: 'Artigo do blog', stage: 'entry', spec: {goal: 'Responder a dúvida que trouxe a pessoa.', suggested_path: '/blog/artigo'}},
      {key: 'leitura', kind: 'event.scroll', title: 'Leitura até o fim', stage: 'exploration', spec: {goal: 'Medir quem lê o artigo completo.', notes: 'Rolagem de 75% ou mais.'}},
      {key: 'relacionado', kind: 'page.blog', title: 'Outro artigo', stage: 'exploration', spec: {suggested_path: '/blog'}},
      {key: 'material', kind: 'page.landing', title: 'Material gratuito', stage: 'intent', spec: {goal: 'Oferecer um guia em troca do e-mail.', suggested_path: '/materiais/guia', cta: 'Baixar o guia'}},
      {key: 'download', kind: 'conversion.lead', title: 'Guia baixado', stage: 'conversion', spec: {goal: 'Contar quem baixa o material.', notes: 'Evento sugerido: guia_baixado.'}},
    ],
    links: [['@paid', 'artigo', null, 100], ['traffic.organic_search', 'artigo', null, 100], ['traffic.organic_social', 'artigo', null, 100], ['communication.email', 'artigo', 'Newsletter', 100], ['artigo', 'leitura', null, 40], ['artigo', 'relacionado', null, 20], ['leitura', 'material', null, 12], ['relacionado', 'material', null, 8], ['material', 'download', null, 35]],
  },
  {
    id: 'video-engagement', sector: 'Marca', mediaObjective: 'alcance', name: 'Vídeo e engajamento', objective: 'Visualizações e cliques', siteKind: 'landing',
    summary: 'Vídeos curtos geram interesse; quem assiste e clica segue para uma página que aprofunda a oferta.',
    channels: [['traffic.youtube', true], ['traffic.tiktok', true], ['traffic.instagram', true], ['traffic.meta', false]],
    steps: [
      {key: 'pagina', kind: 'page.landing', title: 'Página do vídeo ou campanha', stage: 'entry', spec: {goal: 'Continuar a história contada no vídeo.', suggested_path: '/campanha', cta: 'Ver mais'}},
      {key: 'video', kind: 'event.video', title: 'Vídeo assistido na página', stage: 'exploration', spec: {goal: 'Medir a retenção do vídeo no site.'}},
      {key: 'cta', kind: 'event.button', title: 'Clique na chamada principal', stage: 'intent', spec: {goal: 'Medir o interesse em saber mais.', notes: 'Botão principal da página.'}},
      {key: 'oferta', kind: 'page.generic', title: 'Página da oferta', stage: 'exploration', spec: {suggested_path: '/oferta'}},
      {key: 'interesse', kind: 'conversion.generic', title: 'Interesse demonstrado', stage: 'conversion', spec: {goal: 'Contar quem chega à página da oferta como interessado.'}},
    ],
    links: [['@paid', 'pagina', null, 100], ['pagina', 'video', null, 35], ['pagina', 'cta', null, 12], ['video', 'cta', null, 20], ['cta', 'oferta', null, 85], ['oferta', 'interesse', null, 60]],
  },
];

/** Where in the funnel each plan works: top (be found), middle (be considered), bottom (decide). */
export const FUNNEL_STAGES = Object.freeze([
  {id: 'topo', label: 'Topo de funil', hint: 'Alcance e descoberta: apresentar a marca a quem ainda não conhece.'},
  {id: 'meio', label: 'Meio de funil', hint: 'Consideração: nutrir o interesse até o contato.'},
  {id: 'fundo', label: 'Fundo de funil', hint: 'Decisão: levar a pessoa a comprar, agendar ou pedir proposta.'},
]);
const FUNNEL_BY_ID = {
  'reach-awareness': 'topo', 'content-traffic': 'topo', 'video-engagement': 'topo', 'brand-consideration': 'topo',
  'event-webinar': 'meio', 'b2b-demand': 'meio', 'saas-trial': 'meio',
};
export const FLOW_STRATEGIES = Object.freeze(STRATEGY_SOURCE.map(item => Object.freeze({...item, funnel: FUNNEL_BY_ID[item.id] || 'fundo'})));

/** The measured result a plan aims at: its last conversion step, or else its last step. */
export const strategyResult = strategy => {
  const conversions = strategy.steps.filter(step => step.kind.startsWith('conversion.'));
  return (conversions.at(-1) || strategy.steps.at(-1))?.title || '';
};

// Who each channel reaches by default; the planner renames, splits or removes segments.
const DEFAULT_SEGMENTS = {
  google: {name: 'Palavras-chave de intenção', kind: 'palavras_chave'}, retargeting: {name: 'Visitantes dos últimos 30 dias', kind: 'remarketing'},
  email: {name: 'Base de contatos', kind: 'base'},
};
const segmentFor = platform => DEFAULT_SEGMENTS[platform] || (isPaidPlatform(platform) ? {name: 'Público de prospecção', kind: 'prospeccao'} : null);

export const defaultStrategyChannels = strategy => strategy.channels.filter(([, selected]) => selected).map(([kind]) => kind);

/** Builds an editable v2 flow document from a strategy and the channels the planner keeps. */
export function buildStrategyConfig(strategy, channelKinds = defaultStrategyChannels(strategy)) {
  const chosen = strategy.channels.map(([kind]) => kind).filter(kind => channelKinds.includes(kind));
  const ids = {};
  const nodes = [];
  for (const kind of chosen) {
    const block = flowBlockRegistry[kind];
    const id = crypto.randomUUID();
    ids[kind] = id;
    const segment = segmentFor(block.source);
    nodes.push({id, type: 'source', kind, source: block.source, title: block.label, stage: 'source', origin: 'strategy',
      ...(segment ? {segment} : {}), media: defaultMedia(block.source, isPaidPlatform(block.source) ? strategy.mediaObjective : '')});
  }
  for (const step of strategy.steps) {
    const block = flowBlockRegistry[step.kind];
    const id = crypto.randomUUID();
    ids[step.key] = id;
    const node = {id, type: block.type, kind: step.kind, title: step.title, stage: step.stage, origin: 'strategy'};
    if (MEASURED.has(block.type)) Object.assign(node, {status: 'planned', ...(step.spec ? {spec: {...step.spec}} : {})});
    if (step.condition) node.condition = {...step.condition};
    nodes.push(node);
  }
  const paid = chosen.filter(kind => kind.startsWith('traffic.') && !strategy.links.some(([from]) => from === kind));
  // Rates are planning references, so the forecast starts filled; the planner adjusts them to the campaign.
  const edges = strategy.links.flatMap(([from, to, label, rate]) => (from === '@paid' ? paid : [from]).filter(key => ids[key] && ids[to])
    .map(key => ({id: crypto.randomUUID(), from: ids[key], to: ids[to], variant: 'direct', label: label || 'Próximo',
      ...(rate == null ? {} : {forecast: {rate}})})));
  arrangeByDepth(nodes, edges);
  return {schema_version: 3, site_kind: strategy.siteKind, strategy_id: strategy.id, nodes, edges};
}

/** A team template becomes a new plan: every node and connection gets a fresh identifier. */
export function instantiateTemplate(config) {
  const ids = new Map((config.nodes || []).map(node => [node.id, crypto.randomUUID()]));
  return {
    ...config, schema_version: 3,
    nodes: (config.nodes || []).map(node => ({...node, id: ids.get(node.id), origin: 'template'})),
    edges: (config.edges || []).filter(edge => ids.has(edge.from) && ids.has(edge.to))
      .map(edge => ({...edge, id: crypto.randomUUID(), from: ids.get(edge.from), to: ids.get(edge.to)})),
    groups: (config.groups || []).map(group => ({...group, id: crypto.randomUUID(), memberIds: group.memberIds.filter(id => ids.has(id)).map(id => ids.get(id))}))
      .filter(group => group.memberIds.length),
  };
}

// The journey reads left to right: a step sits one column after the furthest step that feeds it, and each
// column hangs from a shared middle line, ordered by where its predecessors are to keep connections short.
function arrangeByDepth(nodes, edges) {
  const incoming = new Map(nodes.map(node => [node.id, []]));
  for (const edge of edges) incoming.get(edge.to)?.push(edge.from);
  const depth = new Map();
  const visit = (id, trail) => {
    if (depth.has(id)) return depth.get(id);
    if (trail.has(id)) return 0;
    trail.add(id);
    const value = incoming.get(id).length ? 1 + Math.max(...incoming.get(id).map(from => visit(from, trail))) : 0;
    trail.delete(id);
    depth.set(id, value);
    return value;
  };
  nodes.forEach(node => visit(node.id, new Set()));
  const columns = [];
  for (const node of nodes) (columns[depth.get(node.id)] ||= []).push(node);
  const rowOf = new Map();
  columns.forEach(items => {
    const score = node => {const rows = incoming.get(node.id).map(from => rowOf.get(from)).filter(value => value != null); return rows.length ? rows.reduce((sum, value) => sum + value, 0) / rows.length : Infinity;};
    if (items.some(node => score(node) !== Infinity)) items.sort((a, b) => score(a) - score(b) || nodes.indexOf(a) - nodes.indexOf(b));
    items.forEach((node, row) => rowOf.set(node.id, row));
  });
  const tallest = Math.max(...columns.filter(Boolean).map(items => items.length));
  const middle = (tallest - 1) * ROW_HEIGHT / 2;
  columns.forEach((items, column) => {
    if (!items) return;
    const top = middle - (items.length - 1) * ROW_HEIGHT / 2;
    items.forEach((node, row) => {
      node.x = COLUMN_START + column * COLUMN_WIDTH;
      node.y = TOP + Math.round((top + row * ROW_HEIGHT) / FLOW_GRID) * FLOW_GRID;
    });
  });
}
