# Seu hub de mídia na Centralcomm: plano de PI, briefing e onboarding

Data: 2026-11-17. Status: **F0 e F1 (nome e e-mails) prontos. F2 e F3a (base de leitura e Entrada de PI no CentralX) construídas em 2026-11-17, ainda sem teste com PDF real nem deploy.** O que falta está nas seções 3B.8 e 5.

## 0. Decisões já tomadas

| Tema | Decisão |
|---|---|
| Nome | A ferramenta se chama **"seu hub de mídia na Centralcomm"**. "Área do Cliente" deixa de existir como nome. Ela faz parte da entrega do serviço de mídia: é uma plataforma facilitadora. |
| Remetente dos e-mails | "Centralcomm" (relacionamento: "[Executivo] da Centralcomm"). |
| E-mails para revisar e disparar ao Apolo | Boas-vindas, os 6 transacionais e a sequência de ativação de 4 e-mails (seg, qua, sex e a segunda seguinte). |
| PI | O cliente (ou a agência) anexa PDFs e envia o PI ao executivo. Fase de **avaliação**: hoje só um importador com OCR; a importação definitiva para o CentralX vem depois. |
| Briefing | Três formas de começar, todas mais simples que o wizard atual. |
| Regra da casa | O hub nunca mostra custo, margem, fee ou comissão da Centralcomm (ver decisão D1 sobre valores do PI). |
| Banco | O `.env` local aponta para o banco de produção. Nada de migração rodando daqui: migração só no deploy, com `ORDER.txt` e testada em Postgres local. |

## 1. Nome: de "Área do Cliente" para "seu hub de mídia"

Onde aparece hoje (103 ocorrências em ~40 arquivos): `area_cliente/` (rotas, e-mails, `acesso.py`), 8 templates de e-mail, 7 templates e a `base.html` do shell, o manifesto do app, `static/js` (6), CRM v3 (toggle "Acesso à Área do Cliente"), `parametros`, `brevo_service.py` (marca `clientes`), config do remetente.

Regras de texto:
- Em frases: "no seu hub de mídia" (antes: "na Área do Cliente"). Botão padrão: **"Abrir meu hub de mídia"**.
- Título das páginas: "Hub de mídia · Centralcomm". Nome do app instalado: "Hub Centralcomm". Menu e manifesto: "Hub de mídia".
- Remetente: "Centralcomm". Nunca "Área do Cliente".
- Nomes de código (`area_cliente`, `clientes.centralcomm.media`) **não mudam agora**. Mudar domínio e pacote é uma etapa separada, com redirecionamento (decisão D2).

Entrega: um único arquivo de constantes (`NOME_HUB`, `NOME_HUB_CURTO`, `BOTAO_ABRIR`) usado por e-mails e telas, para trocar o nome em um lugar só no futuro. Teste que falha se "Área do Cliente" reaparecer em template de e-mail ou tela.

## 2. E-mails de onboarding: revisão detalhada e disparo

### 2.1 Inventário (todos passam pela revisão)
Transacionais (já existem, texto a revisar): boas-vindas (`acesso-liberado`), novo acesso, redefinir senha, senha alterada, briefing recebido, pedido de acesso (interno), briefing novo (interno).

Sequência de ativação (nova, 4 e-mails): seg, qua, sex e a segunda seguinte.

| # | Dia | Recurso | Pergunta que o e-mail responde |
|---|---|---|---|
| 1 | Seg | O que o hub mostra: campanhas no ar e entregas | "O que eu ganho abrindo isso?" |
| 2 | Qua | Mandar PI e briefing sem sair do hub | "Como eu peço algo para a Centralcomm?" |
| 3 | Sex | Descobrir: canais, formatos e audiências | "Como eu decido o que comprar?" |
| 4 | Seg | Acompanhar PIs, metas e relatórios | "Como eu sei se está funcionando?" |

Atenção: a sequência passa a mencionar **enviar PI** e **os 3 tipos de briefing**, que só existem depois das seções 3 e 4. Ordem de produção: o texto é escrito agora; o disparo real só depois das telas.

### 2.2 Critérios da revisão de texto (checklist por e-mail)
1. Assunto com o primeiro nome, até ~45 caracteres, sem a palavra "Centralcomm" repetida no remetente e no assunto.
2. Abre com uma premissa verificável (fato do cliente), e a conclusão vem do leitor (método de premissas). Confirmar com você o material do método do Leandro Ladeira, pois não achei um método de e-mail dele publicado.
3. Máximo ~120 palavras no corpo, um parágrafo por ideia, voz de pessoa ("a gente").
4. Um único botão: "Abrir meu hub de mídia". Em redefinir senha, o botão principal continua sendo o link da senha.
5. Nome de empresa e executivo sempre com fallback (nunca "a  com a").
6. Sem jargão interno (PI, CPM) sem explicar; sem "sistema", "plataforma de IA".
7. Rodapé e bloco do executivo com foto, WhatsApp com mensagem pronta (já feito).
8. Conferir leitura em 390px e no desktop, e as imagens publicadas.

### 2.3 Disparo de teste para o Apolo
- Script único chama as **funções reais** de cada e-mail (assunto, remetente e executivo reais), sempre com destinatário fixo no próprio script.
- Pré-requisito: deploy de `static/emails/area_cliente/` (imagens). Sem isso as fotos chegam quebradas.
- Cada e-mail leva a tag `teste` no Brevo para não entrar em relatório.
- Entregável: um e-mail por modelo (11 no total: 7 + 4) e uma folha de revisão com assunto, pré-visualização e botão de cada um.

### 2.4 Automação da sequência (depois do teste)
Reaproveitar o padrão do timer de e-mail que já existe em `deploy/install_email_sequence_timer.sh` e em `services/cadu_signup_emails.py`. Tabela de controle (`hub_onboarding_envio`): contato, passo, enviado_em, aberto. Regras: só contas liberadas e com senha criada; pular o e-mail 2 se o cliente já enviou briefing ou PI; parar se o cliente entrou 3 vezes na semana. Decisão D6 abaixo.

## 3. Importador de PI (avaliação)

### 3.1 O que o cliente vê
1. Em **PIs**, botão "Enviar um PI". Arrasta um ou mais PDFs (digitalizados) ou escolhe do computador.
2. Barra de progresso animada enquanto o hub lê (leitura de páginas, extração, conferência).
3. Tela **"O que entendi do seu PI"**:
   - cartões: cliente, agência (ou "direto"), número do PI, período, campanha/produto;
   - valores: bruto, líquido e comissão da agência quando constarem no documento;
   - tabela de linhas (praça, veículo ou plataforma, formato, quantidade, valor);
   - selo de confiança por campo e trecho/página de origem; campo duvidoso vem destacado e editável.
4. Bloco do executivo: foto, nome, telefone e botão de WhatsApp com mensagem pronta ("Oi [nome], enviei o PI [nº] da [cliente]").
5. Botão **"Enviar para [executivo]"**. Mensagem de confirmação com o que acontece agora e o prazo de retorno.

### 3.2 O que acontece por trás
```
upload -> cópia privada + sha256 -> páginas em imagem (PyMuPDF) + texto embutido, se houver
      -> OpenRouter multimodal (modelo configurável) -> JSON no esquema do PI
      -> normalização (BRL, datas, CNPJ, %) -> conferência (bruto x soma das linhas, líquido x comissão)
      -> casamento com cadastro (cliente e agência por CNPJ, depois por nome) -> executivo = cliente.vendas_central_comm
      -> tela de conferência -> envio -> e-mail ao executivo e confirmação ao cliente
```

Reaproveita o que já existe: `crm_v3_routes._call_openrouter_multimodal` (OCR de imagem com Gemini 2.5 Flash), PyMuPDF e PyPDF2 já em `requirements.txt`, `por.traineddata` na raiz, `_executivo_do_cliente` e `_contato_executivo` dos e-mails, `_whatsapp`. Novo: pacote `hub/` com `leitor_documentos.py` (base comum com o briefing de cotação, seção 4.2) e `pi_importador.py`.

### 3.3 Esquema de extração (versão 1)
Cada campo volta como `{valor, confianca (0 a 1), pagina, trecho}`.

- Identificação: número do PI (cliente e agência), data de emissão, tipo (PI de agência ou direto), campanha, produto.
- Partes: cliente (razão social, CNPJ), agência (nome, CNPJ), veículo emitente, contatos.
- Período: início e fim; mês de referência.
- Valores: bruto, líquido, comissão da agência (%), impostos, desconto, condições de faturamento e pagamento.
- Linhas: praça, veículo/plataforma, formato, modelo de compra, quantidade, unitário, valor da linha.
- Observações e cláusulas relevantes (texto livre curto).

Os nomes das colunas seguem `cadu_pi` (`vr_bruto_pi`, `vr_liquido_pi`, `periodo_inicio`, `periodo_fim`, `codigo_pi_ag`, `titulo_pi`, `id_cliente`, `id_agencia`) para a importação futura ser um mapeamento direto.

### 3.4 Dados (migração a escrever, rodar só no deploy)
- `hub_pi_importacao`: id, uuid, id_cliente, id_contato, status (`recebido`, `lendo`, `lido`, `revisado`, `enviado`, `importado`, `erro`), modelo e versão do prompt, tokens e custo estimado, `json_extraido`, `json_revisado`, confiança geral, ids detectados (cliente, agência, executivo), `pi_id_importado` (vazio por enquanto), criado e atualizado.
- `hub_pi_importacao_arquivo`: arquivo, sha256 (idempotência), páginas, caminho privado, tamanho.
- `hub_pi_importacao_log`: etapa, duração, erro. Para medir custo e tempo.

### 3.5 Segurança e privacidade
- Arquivos **fora de `static/`**, servidos por rota autenticada. (`static/uploads` é público; PI tem valores comerciais.)
- O cliente só enxerga as próprias importações; ver-como e admins respeitam as regras atuais.
- Limites: 20 MB por arquivo, 30 páginas, 10 importações por hora por cliente.
- Só PDF e imagem; checar assinatura do arquivo e não executar nada do conteúdo.

### 3.6 Avaliação (o que "funcionar" significa)
Você envia alguns PIs. Comparamos campo a campo com o PI já cadastrado no CentralX (verdade de referência). Meta para a primeira rodada: ≥ 95% de acerto em número do PI, cliente, agência, período, bruto e líquido; ≥ 85% nas linhas. Relatório por campo e por modelo de PI (agências diferentes têm leiautes diferentes). Comparar o modelo barato com um mais forte em um lote de amostra antes de escolher (A/B no laboratório, como combinado para o Studio).

### 3.7 Fora do escopo agora
Criar o PI e as campanhas no CentralX (`cadu_pi`, `cadu_pi_campanha`), aprovação do executivo dentro do CentralX e conciliação com financeiro. A estrutura guarda `pi_id_importado` e o JSON revisado para isso.

## 3B. Entrada de PI automatizada no CentralX (comercial)

Pedido de 2026-11-17, depois de receber 3 PIs de amostra (duas agências, três leiautes).

**Princípio:** é uma tela **nova**, ao lado da atual. A tela atual (`/cadu_pi/novo`, `cadu_pi_form.html`, `_coletar_dados_pi_form()` e `db.criar_cadu_pi`) **não muda**. A nova lê, confere e prepara os dados no mesmo formato que a atual espera, para depois ser plugada no fluxo normal.

### 3B.1 Uma fila de entrada, várias origens
Tudo cai na mesma tabela e no mesmo serviço de leitura:
- **Hub de mídia:** o cliente ou a agência anexa o PDF (leitura parcial para quem enviou, seção 3.1).
- **CentralX, Comercial:** o executivo arrasta o arquivo para a área **Entrada de PI** e inicia um PI por ali (leitura completa).
- **Outros lugares, depois:** e-mail encaminhado, pasta compartilhada. A fila já guarda `origem`.

Nomes de tabela (substituem os de 3.4): `pi_entrada`, `pi_entrada_arquivo`, `pi_entrada_log`.

### 3B.2 Leitura completa no CentralX e simples no hub
É o mesmo trabalho de leitura; muda **o que cada tela mostra** (decidido em 2026-11-17):

- **CentralX (executivo): mostra tudo.** Todos os dados lidos, incluindo valores bruto, comissão e líquido, e as conferências.
- **Hub (cliente ou agência): simples.** Lê alguns dados, mostra na tela e **avança para o executivo**, que confere e dá andamento manualmente. Mostra: nº do PI, cliente, agência, campanha, período, um resumo das linhas e o executivo da conta. Não mostra comissão, líquido, CNPJs, regras de faturamento nem conferências. (Suposição minha para o total bruto: aparece só se constar no documento enviado; confirme.)

### 3B.2a Dois jeitos de começar, uma verificação só
- **Pelo hub:** o cliente envia, o hub lê o básico e a entrada cai na fila do CentralX com o selo "enviado pelo cliente".
- **Pelo CentralX:** o executivo arrasta o PDF e inicia o processo.
- **Em ambos, nenhuma entrada vira PI sem verificação humana** na página da seção 3B.3. Os PIs que vêm dos clientes passam pela mesma verificação.

### 3B.3 A tela "Entrada de PI" (Comercial)
Pensada para **verificar** o PI dentro do CentralX contra os dados da cotação, ajustar o que precisar e só então seguir.

1. **Fila** (início): entradas por origem, cliente detectado, executivo, idade e status. Filtro "minhas". Arrastar e soltar o PDF aqui cria uma entrada.
2. **Página de verificação, duas colunas comparativas e poucas linhas:**

| Coluna esquerda: **PI lido** | Coluna direita: **Cotação selecionada** |
|---|---|
| Valor lido do PDF, editável | Valor da cotação |
| Selo por linha: igual, diferente, só no PI, só na cotação, sem leitura | |

   - **Poucas linhas:** 12 a 15 linhas-chave por padrão (cliente, agência, nº do PI, campanha, período, meio e plataforma, formato, modelo de compra, preço unitário, entrega contratada, valor bruto, comissão, líquido, prazo de pagamento). As linhas de campanha e as regras de faturamento ficam em blocos recolhidos ("Linhas (9)", "Regras de faturamento").
   - **Cotação:** um seletor no topo escolhe uma cotação do cliente (`cadu_cotacoes`). Ao escolher, a página **faz sozinha a checagem de tudo** e mostra no cabeçalho "14 de 16 conferem" e o que diverge. Sem cotação, mostra só as conferências internas do PI (3B.5).
   - **PDF ao lado:** um painel recolhível com o PDF; clicar numa linha leva à página e destaca o trecho de origem.
3. **Ajustes com justificativa (3B.3a)** antes de seguir.
4. **Aprovar e preparar entrada do PI:** gera o rascunho no formato de `_coletar_dados_pi_form()` e abre a próxima tela.

**Componentes:** os do design system do CentralX (classes `cx-*`, folha `static/css/tailwind/enterprise-system.css`, a mesma dos drawers de CRM v3 e do cadastro de clientes), sem criar componente novo se já houver um equivalente. Confirmar o mapa de componentes antes de construir.

### 3B.3a Ajustes com justificativa
- Qualquer campo que o executivo mude (ou aceite divergente da cotação) exige **motivo** (erro de leitura, erro do PI, combinado com o cliente, diferente da cotação aprovada, outro) e **justificativa em texto**.
- Fica numa tabela `pi_entrada_ajuste` (campo, valor lido, valor final, motivo, justificativa, quem, quando) e na auditoria que já existe (`registrar_auditoria`).
- Nada segue para "preparar entrada" com divergência sem justificativa.

### 3B.4 Preparação dos dados para a tela atual
O rascunho usa as chaves que a tela atual já coleta, entre elas: `codigo_pi_ag`, `titulo_pi`, `id_cliente`, `id_agencia`, `valor_bruto`, `valor_liquido`, `perc_comissao_agencia`, `periodo_inicio`, `periodo_fim`, `mes_ref_comp`, `plataforma_campanha`, `obs_operacao`, `obs_financeiro`, contatos de mídia e financeiro do cliente e da agência, `cotacao_id`, `resp_comercial`.

Obrigatórios hoje na tela atual: executivo de vendas (`resp_comercial`), tipo de PI (`id_pi_tipo`) e datas de início e fim. A nova tela preenche o executivo pelo cadastro do cliente e as datas pelo PI; o **tipo de PI** é do executivo.
Ficam para o executivo, porque não vêm do PDF: margem, tech fee, impostos %, comissão de vendas, status e sub-status.

### 3B.4b Oportunidades de cadastro (pedido de 2026-11-17)
Cada PI que chega é uma chance de deixar o CentralX mais completo. A página de verificação mostra um bloco **"Cadastro: oportunidades"** e a fila mostra um selo ("3 oportunidades") quando o PI traz dado que o cadastro não tem ou tem diferente:
- **Cliente ou agência que não existe** (CNPJ não encontrado): sugerir o cadastro, com razão social, CNPJ, endereço, CEP, município e UF, inscrições estadual e municipal já lidos.
- **Campo vazio no cadastro e preenchido no PI** (endereço, CEP, município, UF, IE, IM, telefone, e-mail): "preencher".
- **Campo diferente** (por exemplo, endereço ou razão social): "revisar e atualizar", mostrando o valor do cadastro ao lado do valor do PI.
- **Contato novo**: e-mail de faturamento, contato de mídia ou responsável que o PI cita e o cadastro não tem.
- **Regras de faturamento da conta** (prazo, retenções, centro de custos, documentos exigidos): sugerir guardar na ficha do cliente ou da agência para as próximas entradas.

Primeira versão **só sinaliza** (leitura): cada oportunidade abre o cadastro certo para o executivo atualizar. Aplicar a atualização direto, com um clique, fica para depois e só com sua aprovação, porque escreve no cadastro de produção.

### 3B.4a Conferência do texto depois do OCR
Duas passadas independentes: (1) a leitura extrai os campos; (2) uma **segunda checagem** recebe o texto bruto e os campos extraídos e devolve, por campo, "confirmado", "divergente" ou "não encontrado no texto". Campo divergente nasce em âmbar na página de verificação. Você sugeriu usar uma API para isso ("api do jev"): preciso saber qual é (ver D11). Sem ela, a segunda passada roda no mesmo provedor de OCR com outro modelo.

### 3B.5 Conferências (calculadas nos 3 PIs de amostra)
- **Soma das linhas = total bruto.** No PI da CEMIG, as 9 segmentações da Meta somam R$ 13.500 e a LinkedIn R$ 5.500, total R$ 19.000.
- **Comissão e líquido:** líquido = bruto − comissão. Nos três PIs a comissão da agência é 20% (R$ 2.000 de 10.000; R$ 3.800 de 19.000; R$ 11.878,64 de 59.393,20).
- **Entrega × preço = valor.** CPM: 163.399 impressões × R$ 61,20 / 1.000 ≈ R$ 10.000. CPC: 148.483 cliques × R$ 0,40 = R$ 59.393,20.
- **Valor por extenso × número.** O PI da COPASA traz "quarenta e dois mil reais" ao lado de R$ 59.393,20: erro real do documento que a leitura deve sinalizar.
- **Período:** PI × linhas × mês de referência; emissão antes do início.
- **CNPJ:** dígito verificador; cliente e agência casados no cadastro por CNPJ.
- **Veículo:** deve ser a Centralcomm; senão, alerta.
- **Número do PI repetido:** já existe esse `codigo_pi_ag`?

### 3B.6 O que as 3 amostras ensinam sobre a leitura
- **Três leiautes, duas agências.** Os rótulos mudam ("PI Nº" e "PIT Nº", "Contato" e "Responsável", "Prazo de pagamento" só em um). A leitura é por **esquema semântico**, nunca por posição.
- **Os PDFs têm camada de texto e imagem** (assinatura manuscrita, carimbo). Ler a camada de texto primeiro (mais barato e exato) e usar as imagens das páginas só para o que faltar, para assinaturas e para PDF escaneado de verdade.
- **O cabeçalho repete em toda página e o conteúdo atravessa páginas** (uma segmentação começa numa página e termina na outra, com "veja página seguinte"). Juntar as páginas antes de extrair e ignorar cabeçalho repetido e o calendário de dias.
- **As páginas finais trazem regras de faturamento** em texto corrido. Extrair como campos (prazo de pagamento, NF pelo valor líquido, retenção de IR e ISS, e-mail de faturamento, documentos exigidos, centro de custos, help desk, responsável no cliente) e guardar o texto integral.
- **As linhas de campanha são texto livre** (meio, plataforma, estratégia, praça, segmentação, formato, modelo de compra, CPM ou CPC, entrega, valor bruto, peças A e B). Viram linhas estruturadas.
- **Um PI tem várias campanhas e várias segmentações com valor próprio** (Meta e LinkedIn no mesmo PI).
- **O nome do arquivo não é confiável:** o PDF da COPASA se chama "app behavior", que é a estratégia.

### 3B.7 Segurança
Os PDFs têm dados de pessoas e valores comerciais. Arquivos em área privada, acesso só ao Comercial e administradores, registro de quem abriu. As 3 amostras reais **não entram no repositório**: os testes usam cópias anonimizadas.

### 3B.8 Entregas
| Etapa | O que sai |
|---|---|
| F2 | Base de leitura (texto + imagem, juntar páginas, esquema, conferências) |
| F3a | Fila e tela **Entrada de PI** no CentralX (leitura completa, arrastar e soltar) |
| F3b | Visão parcial no hub e envio ao executivo |
| F3c | Seleção de cotação e comparação PI × cotação |
| F3d | "Preparar entrada do PI": rascunho no formato da tela atual |
| Depois | Plugar no fluxo normal (`/cadu_pi/novo` pré-preenchido), sem mudar a tela atual |

## 4. Briefing: três caminhos, menos complexidade

### 4.1 Tela de entrada
`/briefing` vira uma escolha em três cartões grandes:

| Cartão | Para quem | Resultado |
|---|---|---|
| **Tenho arquivos para cotar** | Já tenho PDF, planilha ou mídia kit | Cotação em até 24 h |
| **Quero repetir um PI antigo** | Já fiz algo parecido | Formulário quase todo preenchido |
| **Quero montar um planejamento** | Não tenho nada | Formulário único, tudo na tela |

### 4.1a Tela inicial do briefing (sem briefing) e lista de todos
Hoje, sem nenhum briefing, a página mostra "Seu primeiro briefing" com 4 passos ilustrados (Objetivo, Público, Praças, Período) e um botão "Começar briefing": é o desenho do wizard antigo. Passa a mostrar os **3 caminhos**:

- **Sem nenhum briefing:** título "Como você quer começar?" e **3 cartões grandes** com ilustração no mesmo estilo (fundo verde-claro, traço verde): "Tenho arquivos para cotar", "Quero repetir um PI antigo" e "Quero montar um planejamento". Embaixo, a linha "Briefing → Planejamento → PI → Campanhas". O botão único "Começar briefing" sai.
- **Com briefings:** os 3 cartões ficam compactos no topo, seguidos dos 3 últimos briefings e do link **"Ver todos os briefings"**.
- **Lista de todos os briefings:** página própria (`/briefing/todos`), com busca, filtro por status e modo, e por linha: título, modo, data, status, executivo e, nos de cotação, o relógio das 24 h. **Sem item na barra lateral:** o acesso é só por dentro da página de briefing (link "Ver todos os briefings" e migalha de pão), para não poluir o menu.

### 4.2 Briefing para cotação
- O cliente anexa arquivos (PDF, imagem, planilha). O mesmo `leitor_documentos` extrai objetivo, praças, período, verba, canais, formatos e materiais.
- Tela "o que entendi" com os campos principais, o que faltou e um campo livre. O cliente confirma ou corrige.
- **Ao enviar:** (a) o comercial é notificado (e-mail com resumo e arquivos; aparece na tela de Briefings do CentralX com o modo e a leitura); (b) o cliente recebe "seu briefing seguiu para [executivo]; ele retorna em até 24 horas" com foto, telefone e WhatsApp.
- **Prazo de 24 h:** `prazo_resposta_em` gravado no envio. Aviso ao executivo com 12 h restantes, aviso ao gestor com 4 h, marca de atraso depois. Contar horas corridas ou úteis é a decisão D4.
- Se a leitura falhar, o briefing é enviado do mesmo jeito, com os arquivos anexados e a nota "não consegui ler: veja o anexo".

### 4.3 Briefing a partir de PI antigo
- O cliente escolhe um PI da lista (o histórico de hoje, `briefing.historico`, expandido com `cadu_pi` e campanhas: praça, segmentação, objetivo, plataforma, formato, período).
- O formulário abre **com tudo que dá para preencher já preenchido**, cada campo com o selo "vem do PI X". O que falta aparece agrupado no fim, em "Falta só isso".
- Atalhos: "mesmas datas do PI anterior, deslocadas para o próximo mês" e "mesma verba (faixa)".
- Respeita a regra da casa: nenhum custo, margem ou valor de PI entra no formulário (faixa de verba é informada pelo cliente).

### 4.4 Briefing de planejamento
- **Uma única página, sem etapas.** Todos os campos visíveis: o essencial (título, objetivo, período, verba em faixa, canais) no topo e o detalhamento opcional abaixo em blocos já abertos.
- Os itens que o cliente separou no **Descobrir** aparecem como chips editáveis (hoje a seleção fica na sessão, até 30 itens).
- Salvar rascunho (`status = 'rascunho'` já existe) e enviar para a Centralcomm.

### 4.5 Dados e código
- `cadu_briefings`: novas colunas `modo` (`cotacao`, `pi_antigo`, `planejamento`), `prazo_resposta_em`, `respondido_em`, `arquivos` (jsonb), `leitura_ia` (jsonb), `pi_origem_id`, `lembretes` (jsonb). Status do cliente ganha "Com o executivo" e "Retorno até [hora]".
- Reaproveitar: `briefing.validar`, `qualidade()` (nota de qualidade e pendências), `resumo()` e `enviar()` com o parâmetro `modo`; o wizard atual (`briefing.html` com 393 linhas, `area_cliente_briefing.js`) é **substituído** pelos três formulários, mantendo o autocompletar de praças e "Praças com IA".
- Rotas: `/briefing` (escolha), `/briefing/cotacao`, `/briefing/pi-antigo`, `/briefing/planejamento`; os POSTs reutilizam o CSRF e os limites atuais.
- CentralX: tela de Briefings mostra o modo, os arquivos, a leitura da IA e o relógio das 24 h.

## 5. Ordem de entrega

| Fase | Entrega | Depende de |
|---|---|---|
| F0 | Nome "seu hub de mídia" em e-mails e telas + constantes + teste de regressão | decisões D2 |
| F1 | Revisão dos 11 e-mails e disparo de teste ao Apolo (11 envios) | F0 e deploy das imagens |
| F2 | Base de leitura de documentos (`leitor_documentos`, OCR OpenRouter, PyMuPDF) + migração | — |
| F3a | Entrada de PI no CentralX: fila, arrastar e soltar, leitura completa (3B) | F2 |
| F3b | Hub: upload de PI, tela "o que entendi" parcial, envio ao executivo | F3a |
| F3c | Seleção de cotação e comparação PI × cotação | F3a |
| F3d | "Preparar entrada do PI" no formato da tela atual | F3a e F3c |
| F4 | Briefing: tela inicial com os 3 caminhos (inclusive sem briefing), lista de todos por dentro da página e planejamento (formulário único) | F0 |
| F5 | Briefing a partir de PI antigo | F4 |
| F6 | Briefing para cotação: arquivos, OCR, aviso, prazo de 24 h e lembretes | F2 e F4 |
| F7 | Sequência de ativação automática + deploy e verificação em tela | F1 a F6 |

F3 e F6 compartilham a base de leitura (F2). F4 pode andar em paralelo a F2/F3.

## 6. Testes e verificação por fase
- Normalizadores (valor em reais, datas, CNPJ, %) com casos reais e quebrados.
- Contrato do modelo: respostas gravadas (fixtures) validadas contra o esquema; JSON inválido, página em branco e PDF protegido.
- Casamento de cliente e agência (CNPJ, nome parecido, homônimo).
- Permissões: cliente A nunca vê importação ou briefing do cliente B.
- Prazo de 24 h: relógio, lembretes e atraso (com data simulada).
- Telas: captura em 390px e 1280px de cada caminho do briefing e da tela do PI. O fluxo logado exige uma conta de teste; combinar uma (sem tocar em dados reais de produção).
- E-mails: previa de cada modelo e teste real ao Apolo.

## 7. Riscos
1. **Qualidade do OCR em PI escaneado torto** → pré-processamento de imagem, confiança por campo, edição manual sempre possível.
2. **Custo por importação** → registrar tokens; modelo barato por padrão, modelo forte só em baixa confiança; limite por cliente.
3. **Valores comerciais na tela** → ver D1.
4. **Banco de produção no ambiente local** → desenvolver contra Postgres local; migração só no deploy.
5. **Expectativa de 24 h sem equipe para cumprir** → lembretes e visão de atraso para o gestor desde o primeiro dia.
6. **Mudança de nome** → rota e domínio ficam como estão até a D2.

## 8. Decisões em aberto

| # | Decisão | Recomendação |
|---|---|---|
| D1 | Mostrar valores bruto e líquido do PI. | **Decidido (2026-11-17):** o CentralX mostra tudo; o hub só um resumo simples (ver 3B.2). |
| D2 | Trocar o domínio `clientes.centralcomm.media` e o nome do pacote? | Não agora. Manter o domínio e redirecionar depois, junto com um domínio novo (ex.: `hub.`). |
| D3 | Quando o PI vem de uma **agência**, quem recebe: o executivo da agência ou o do cliente final? | O executivo do cadastro da conta de quem enviou; mostrar também o cliente detectado. |
| D4 | O prazo de 24 h conta horas corridas ou úteis? | Úteis (seg a sex, 9h às 18h), com o limite visível ao cliente. |
| D5 | Modelo de OCR: Gemini 2.5 Flash (padrão atual) ou outro? | Começar com Flash e medir contra um modelo mais forte no lote de amostra. |
| D6 | A sequência de ativação para ao enviar o primeiro PI ou briefing? | Sim: pula o e-mail 2 e segue. |
| D7 | Material do método Leandro Ladeira para e-mail. | Você envia; eu reescrevo os textos com ele. |
| D8 | O que a visão do hub mostra do PI? | **Decidido:** simples (nº, cliente, agência, campanha, período, resumo das linhas, executivo) e avança para o executivo. Falta confirmar o total bruto. |
| D9 | Os PIs 86761, 86698 e 036826 já estão cadastrados no CentralX? São a verdade de referência. | Sim: comparar campo a campo antes de liberar. |
| D11 | Qual é a "API do jev" para conferir o texto depois do OCR? | Você me diz o nome ou o endereço da documentação. |
| D10 | Quem vê a fila Entrada de PI no CentralX? | Comercial (executivos) e administradores; cada executivo vê primeiro as suas. |

## 9. O que eu preciso de você
- **Recebido em 2026-11-17:** 3 PIs de amostra (Lápis Raro ×2 e Faz Publicidade). Falta mandar mais 3 a 5, de outras agências e de cliente direto, e confirmar que os 3 já estão no CentralX (D9).
- Respostas para D1, D3, D4 (as outras eu já assumo pela recomendação).
- Deploy das imagens dos e-mails (para o disparo de teste ter foto e ícones).
- Uma conta de cliente de teste para eu verificar as telas logadas.
