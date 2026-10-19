# Leads v3 — mesa de operações de prospecção + Golden Circle

Plano escrito em 2026-10-19. Nada implementado ainda.

## 1. O que existe hoje (`/leads`, "Cadu Leads V2")

- Tela: [cadu_leads.html](../aicentralv2/templates/cadu_leads.html) com duas visões, lista
  (barra lateral + detalhe) e kanban por status (`inbox`, `tentativa_contato`,
  `reuniao_agendada`, `nutricao`, …). A análise fica numa página separada, `/leads/analise`.
- Dados: `cadu_leads` (empresa, contato principal, origem/canal/fonte, UTM parcial via
  `referrer`/`pagina_origem`, `potencial`, `tipo_lead`, `qualificacao_score`, executivo),
  `cadu_lead_contatos` (com `status_pipeline` por pessoa), `cadu_lead_comunicacoes`
  (rascunhos de e-mail/WhatsApp gerados por IA, com `status` e `data_envio_programado`)
  e atividades.
- Ações: criar, importar em lote (colar ou arquivo), mesclar, desqualificar, converter em
  cliente, extrair dados de URL, gerar comunicação com IA e mover no kanban.
- Entrada automática: os formulários dos sites e landing pages já gravam direto em
  `cadu_leads` pelo banco, fora deste repositório. Há também `/onboarding` e o cadastro
  do Workspace. Não é preciso criar captação nova.
- WhatsApp: módulo `aicentralv2/whatsapp` via **WaSender** (API não oficial, sessão de
  WhatsApp Web), já com conversas, inbound e status.
- E-mail: `email_service.send_email` (transacional). Sem domínio de prospecção, sem
  rastreio de abertura/clique e sem descadastro.
- Reaproveitável do CRM v3: layout de mesa em 4 colunas, drawers, copiloto
  (`/api/ia/gerar-comunicacao`, `touchpoints`, `sugerir-atividade`), sequência de
  atividades (`/atividades/sequencia`) e `crm_v3_web_scout` (leitura do site).

## 2. O que falta (funcionalidades novas)

### Operação e mesa
1. Mesa no padrão CRM v3: **Fila → Lead → Pessoas → Contexto**, com a "fila do dia"
   ordenada por próxima ação vencida, score e Golden Circle.
2. Próxima ação obrigatória: lead ativo sem tarefa futura aparece como "parado".
3. SLA de primeiro contato para leads de inbound (ex.: 15 min no horário comercial), com alerta.
4. Distribuição automática (roleta ou regra por segmento/UF) e reatribuição em massa.
5. Ações em massa na fila: atribuir, mudar etapa, incluir em cadência e exportar.
6. Visões salvas por usuário ("meus inbound de hoje", "Golden Circle sem contato").
7. Separação entre **conta** (empresa) e **pessoa**: hoje o lead é a empresa com um
   contato principal. Para conta-alvo é preciso mapear o comitê de compra por pessoa.

### Golden Circle
8. Lista de contas-alvo por executivo e **trimestre** (`2026-Q4`), com meta por conta.
9. Mapa de cobertura por papel: Marketing, Mídia, Criação/Brand, Diretoria/C-level,
   Compras. Cada conta mostra quais papéis já têm contato e quais têm conversa ativa.
10. Painel do trimestre: contas tocadas, reuniões, cotações abertas e % de cobertura,
    por executivo e consolidado.
11. Ponte com o CRM: a conta-alvo pode ser lead novo **ou** cliente já na carteira
    (Unimed, Sicredi etc. podem já existir como cliente). Nesse caso o alvo é expansão,
    não captação.

### Enriquecimento e inteligência
12. Busca de pessoas por empresa + cargo (Apollo e alternativas, seção 4) com revisão
    humana antes de gravar.
13. Dados cadastrais por CNPJ (Receita: razão social, CNAE, porte, sócios, endereço).
14. Sinais da conta: notícias, mudança de diretoria, vagas de marketing, lançamentos e
    campanhas no ar, via busca web com LLM e o `crm_v3_web_scout`.
15. Validação de e-mail (bounce) e de telefone/WhatsApp antes de disparar.
16. Deduplicação por domínio, CNPJ e e-mail, além da mesclagem manual que já existe.

### Comunicação e campanhas
17. Envio real de e-mail 1:1 a partir da mesa, com thread, resposta capturada e
    abertura/clique.
18. **Cadências** multicanal (D0 e-mail → D2 LinkedIn → D4 WhatsApp → D7 ligação), que
    pausam sozinhas quando o lead responde.
19. Campanhas segmentadas de e-mail e WhatsApp com variáveis personalizadas pela IA por
    pessoa (setor, cargo, sinal recente) e aprovação antes do envio.
20. Templates por objetivo e etapa, com biblioteca compartilhada e teste A/B de assunto.
21. Caixa unificada: respostas de e-mail e WhatsApp caem na timeline do lead.
22. Opt-out/descadastro e base legal LGPD por pessoa (legítimo interesse B2B, com
    registro da origem do dado).

### LinkedIn
23. URL do perfil por pessoa, tarefas "conectar/comentar/mensagem" dentro da cadência e
    registro manual do resultado. Ver os limites na seção 5.

### Atribuição (marketing)
24. Ligar os leads que já chegam dos formulários à jornada do Supertag
    (`reports_supertag_leads.py`), para ver UTM e páginas visitadas na timeline.
25. Atribuição: qual campanha ou página gerou o lead e quanto virou cotação/PI.

### Métricas
26. Funil por origem e executivo (inbound vs. lista própria), tempo por etapa, taxa de
    resposta por canal/template e conversão em cliente/cotação.
27. Score combinando fit (porte, segmento, Golden Circle) e engajamento (respostas,
    aberturas, visitas).

## 3. Desenho da mesa Leads v3 (`/leads-v3`)

| Coluna | Conteúdo |
|---|---|
| **Fila** | Abas: Hoje, Inbound, Minhas listas, Golden Circle Q4. Card com score, etapa, próxima ação e selo GC. Filtros salvos e ações em massa. |
| **Lead (centro)** | Cabeçalho da conta (CNPJ, segmento, porte), etapa, próxima ação, timeline unificada (e-mail, WhatsApp, LinkedIn, notas, atividades) e cadência ativa. |
| **Pessoas** | Comitê de compra por papel, com origem do dado, validação de e-mail/telefone, LinkedIn, opt-out e botão "buscar mais pessoas". |
| **Contexto** | Sinais recentes, site (web scout), progresso no Golden Circle, cotações (se já for cliente) e copiloto (próxima ação, mensagem). |

Mesma pilha do CRM v3: blueprint próprio, `/leads-v3/api` com contrato
`{"success", "data"}`, store em memória para testes e repositório Postgres.

## 4. Fontes de contatos: Apollo e alternativas

Estratégia recomendada: **cascata de provedores** atrás de uma interface única
(`enrichment/providers/*`). Cada chamada grava fonte, data e custo, e nada entra no
lead sem aprovação do executivo.

| Camada | Opções | Papel |
|---|---|---|
| Cadastro da empresa | **BrasilAPI / ReceitaWS** (CNPJ, grátis ou barato); **Econodata**, **Speedio**, **Casa dos Dados** (bases BR pagas, com filtros por CNAE/porte e telefones da empresa) | Fit e dados oficiais. Forte para empresas brasileiras. |
| Pessoas + e-mail | **Apollo** (já contratado, comece por ele); alternativas: **Lusha**, **Snov.io**, **Hunter** (só e-mail por domínio), **Cognism**/**ZoomInfo** (caros, foco EUA/Europa) | Nome, cargo, e-mail e às vezes celular. A cobertura de LATAM costuma ser mais fraca que a dos EUA, então medir a taxa de acerto nas 14 contas antes de assinar outro. |
| Cascata pronta | **Clay** (orquestra dezenas de provedores, inclusive Apollo, e cobra por crédito) | Alternativa a construir a cascata em casa. Bom para validar antes de integrar. |
| Validação | **ZeroBounce / NeverBounce** (e-mail); checagem de número no WhatsApp | Evita bounce e queima de domínio/número. |
| Pesquisa aberta | **OpenRouter + Perplexity Sonar / Sonar Pro Search** (busca web com citações); **Exa** ou **Tavily** (busca semântica de pessoas/empresas); **Firecrawl** (páginas "quem somos", imprensa, LinkedIn público indexado) | Sinais, notícias, organograma público e "quem é o diretor de marketing da X". Bom para contexto, **não** substitui a base de contatos: LLM não tem e-mail/celular confiável e pode inventar. Usar só com citação e marcar como "a confirmar". |

Sobre a pergunta do OpenRouter: ele não tem uma ferramenta de prospecção com e-mails. O
que oferece são modelos com busca web (Sonar, e o plugin `:online`/web search em outros
modelos). Servem para a camada de **pesquisa e sinais**, ligados ao copiloto existente.
Para e-mail e telefone verificados, o caminho continua sendo um provedor de dados
(Apollo primeiro).

Piloto proposto: rodar as 14 contas do Golden Circle Q4 de João Figueiredo no Apollo com
os papéis Marketing/Mídia/Criação/Diretoria e medir pessoas encontradas, e-mails válidos
e celulares por conta. Só contratar um segundo provedor se a cobertura ficar abaixo de
~50% dos papéis.

## 5. Riscos e decisões

- **WhatsApp em massa no WaSender:** é API não oficial. Disparo de campanha para quem
  nunca falou com o número tende a levar a banimento. Recomendação: WaSender só para
  conversa 1:1, e campanhas via **WhatsApp Cloud API oficial** (Meta), com templates
  aprovados e custo por conversa.
- **E-mail frio:** usar um subdomínio ou domínio separado de prospecção (SPF, DKIM,
  DMARC, aquecimento) num provedor como Amazon SES, Resend ou Brevo, para não afetar a
  entrega dos e-mails transacionais do domínio principal. Limite diário por caixa e
  descadastro obrigatório.
- **LinkedIn:** a API oficial não permite enviar convites ou mensagens nem ler perfis de
  terceiros. Ferramentas que automatizam via sessão/extensão violam os termos e põem a
  conta do executivo em risco. Proposta: LinkedIn como **tarefa assistida** (abrir
  perfil, mensagem sugerida pela IA, registrar resultado). Sales Navigator, se houver,
  só por links e CRM Sync oficial.
- **LGPD:** gravar origem e data de cada dado de pessoa, base legal (legítimo interesse
  B2B), opt-out global por e-mail/telefone e exclusão a pedido.
- **Banco:** o `.env` local aponta para produção, então migrações devem ser testadas
  em Postgres local e entrar pela ordem do `ORDER.txt`.

## 6. Fluxo de trabalho e fases

O fluxo do executivo, que guia a ordem das fases:

1. **Listar contatos**: trazer pessoas de cada empresa (Apollo, importação, manual,
   formulário do site).
2. **Entender os contatos da empresa**: papel (marketing, mídia, criação, diretoria,
   compras), senioridade e influência (decisor, influenciador, usuário, bloqueador),
   mostrando o que falta cobrir.
3. **Separar as empresas**: Golden Circle do trimestre, prioridade A/B/C, grupo
   econômico, captação vs. expansão (se já é cliente).
4. **Cadências de conexão**: sequência multicanal por pessoa, que pausa quando a
   pessoa responde.

| Fase | Entrega | Observações |
|---|---|---|
| 0 | Esquema (`migrations/add_cadu_leads_v3_prospeccao.sql`): papel/senioridade/influência/LinkedIn/origem do dado por contato, fila de candidatos do enriquecimento, CNPJ/domínio/grupo/prioridade por empresa, `cadu_golden_circle`, opt-out, cadências + inscrições, eventos de mensagem. | Só aditivo. Não mexe nos CHECKs de status nem nas views do site, então o insert dos formulários continua igual. |
| 1 | **Listar contatos**: mesa `/leads-v3` (fila → empresa → pessoas → contexto) e busca de pessoas no Apollo por papel, com fila de revisão. Importação e cadastro manual já gravam papel e origem. | O `/leads` antigo continua no ar. Piloto nas 14 contas. |
| 2 | **Entender contatos**: mapa do comitê por papel × influência, lacunas ("sem ninguém de mídia"), validação de e-mail, CNPJ (BrasilAPI) e sinais (Sonar + web scout). | |
| 3 | **Separar empresas**: Golden Circle por trimestre, prioridade A/B/C, grupo econômico, ponte com clientes da carteira (expansão) e painel de cobertura. Semente do **Q4 2026 – João Figueiredo**. | Ver a lista abaixo. |
| 4 | **Cadências de conexão**: modelos de cadência (e-mail, LinkedIn como tarefa, WhatsApp 1:1, ligação), inscrição em massa a partir do Golden Circle, fila do dia, pausa por resposta e opt-out. | Reaproveita o copiloto do CRM v3 para os textos. |
| 5 | Campanhas em escala: segmentos, personalização por IA com aprovação, e-mail em domínio dedicado, WhatsApp oficial com templates, A/B. | Depende da decisão sobre WhatsApp oficial e domínio. |
| 6 | Score fit + engajamento, métricas de funil e atribuição com Supertag. | |

### Golden Circle Q4 2026 — João Figueiredo

Sindifer · Grupo Senhor do Bonfim · ArcelorMittal · Gerdau · Anglo American · Unimed
(definir qual singular/federação) · Onfly · MaxMilhas · Algar · Itambé · Sicredi
(definir cooperativa ou central) · Vale · Sankhya · Auren Energia.

Antes da semente: confirmar a grafia (a lista original traz "Sankya" e "Grupo senhor do
Bomfim", aqui normalizados para Sankhya e Senhor do Bonfim) e qual unidade de
Unimed/Sicredi é o alvo, porque cada uma é um sistema com muitas empresas.

## 7. Decisões pendentes

1. WhatsApp de campanha: Cloud API oficial (recomendado) ou só 1:1 no WaSender.
2. Domínio/provedor de e-mail de prospecção.
3. Apollo sozinho no piloto ou já testar Clay em paralelo.
4. Golden Circle só por executivo, ou também por carteira/time com metas consolidadas.
