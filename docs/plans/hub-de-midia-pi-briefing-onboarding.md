# Seu hub de mídia na Centralcomm: plano de PI, briefing e onboarding

Data: 2026-11-17. Status: **planejamento, nada construído ainda**.

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

## 4. Briefing: três caminhos, menos complexidade

### 4.1 Tela de entrada
`/briefing` vira uma escolha em três cartões grandes:

| Cartão | Para quem | Resultado |
|---|---|---|
| **Tenho arquivos para cotar** | Já tenho PDF, planilha ou mídia kit | Cotação em até 24 h |
| **Quero repetir um PI antigo** | Já fiz algo parecido | Formulário quase todo preenchido |
| **Quero montar um planejamento** | Não tenho nada | Formulário único, tudo na tela |

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
| F3 | Importador de PI: upload, leitura, tela "o que entendi", envio ao executivo | F2 |
| F4 | Briefing: tela de entrada + planejamento (formulário único) | F0 |
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
| D1 | Mostrar valores bruto e líquido do PI ao cliente na tela "o que entendi"? Hoje a regra da casa proíbe valor de PI no hub. | Mostrar **só o que está no documento que o próprio cliente enviou**, só para quem enviou, sem custo, margem, fee ou comissão da Centralcomm. |
| D2 | Trocar o domínio `clientes.centralcomm.media` e o nome do pacote? | Não agora. Manter o domínio e redirecionar depois, junto com um domínio novo (ex.: `hub.`). |
| D3 | Quando o PI vem de uma **agência**, quem recebe: o executivo da agência ou o do cliente final? | O executivo do cadastro da conta de quem enviou; mostrar também o cliente detectado. |
| D4 | O prazo de 24 h conta horas corridas ou úteis? | Úteis (seg a sex, 9h às 18h), com o limite visível ao cliente. |
| D5 | Modelo de OCR: Gemini 2.5 Flash (padrão atual) ou outro? | Começar com Flash e medir contra um modelo mais forte no lote de amostra. |
| D6 | A sequência de ativação para ao enviar o primeiro PI ou briefing? | Sim: pula o e-mail 2 e segue. |
| D7 | Material do método Leandro Ladeira para e-mail. | Você envia; eu reescrevo os textos com ele. |

## 9. O que eu preciso de você
- Alguns PIs em PDF (idealmente 3 a 5, de agências diferentes e de cliente direto) e os PIs correspondentes já cadastrados no CentralX.
- Respostas para D1, D3, D4 (as outras eu já assumo pela recomendação).
- Deploy das imagens dos e-mails (para o disparo de teste ter foto e ícones).
- Uma conta de cliente de teste para eu verificar as telas logadas.
