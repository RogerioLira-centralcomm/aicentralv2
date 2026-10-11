# Cadu — sequência de e-mails de adoção e painel de monitoramento (CentralX)

Plano de 2026-10-11. Nada aqui foi implementado. Decisões em aberto estão na seção 7.

## 1. Diagnóstico (verificado no código)

**Já dispara sozinho (por evento):** boas-vindas, bônus, follow-up do Demétrius (5 min após onboarding, timer `process-onboarding-followups`), "primeira base pronta", reset/troca de senha, convite, assinatura, tokens, Studio (4 eventos), auditoria de marca, Reports e avisos internos.

**Não existe:**
- Envio por tempo (a cada 2 dias). Os 7 modelos de `GROWTH_EMAIL_MODELS` só rodam em `/teste-brevo/cadu-growth`, com destinatário fixo.
- Estado da sequência por usuário.
- Descadastro / consentimento. Nenhum template tem link de saída; não há coluna de opt-out; o `enviar_email` da Brevo não manda `List-Unsubscribe` nem `tags`.
- Tela de monitoramento. `cadu_workspace_email_events` só é escrita; nenhuma tela lê.

**Falhas do registro atual (`email_service._record_workspace_email_event`):**
1. Descarta o envio se não resolver `id_cliente` (leads, e-mails internos, follow-up do Demétrius ficam invisíveis).
2. `VARCHAR(48)` em `event_type` e uma linha por envio, sem noção de sequência/passo.
3. Status único: não há aberto/clicado separados de entregue (só `last_event_at`).
4. Dois webhooks: `/api/brevo/webhook` (só loga) e `/workspace/api/email-events/brevo` (atualiza). Confirmar qual está cadastrado na Brevo; o painel depende disso.
5. O follow-up do Demétrius guarda o resultado só em `cadu_user_onboardings`, fora do ledger.

## 2. Revisão dos templates e padrão

Há **dois padrões visuais paralelos**: `workspace-base.html` (cabeçalho escuro, ilustração, rodapé verde-escuro, botão sólido) para transacionais, e `cadu-growth.html` (faixa por solução, card branco, CTA em link sublinhado) para adoção. Além disso `onboarding-demetrius.html` é HTML solto, sem estilo de marca.

| # | Achado | Onde | Correção |
|---|---|---|---|
| T1 | Sem link de descadastro | todos os de adoção | Rodapé com "Não quero mais receber estas dicas" (token assinado) + header `List-Unsubscribe` / `List-Unsubscribe-Post` |
| T2 | Sem preheader | `cadu-growth.html` (a base do Workspace tem) | Bloco oculto com `description` |
| T3 | Rodapé fora do playbook: diz "Powered by CentralComm" + "Continue aprendendo no Cadu."; playbook manda rodapé mínimo `CentralComm` | `cadu-growth.html` | Alinhar ao playbook ou atualizar o playbook (decidir) |
| T4 | CTA é link sublinhado; transacionais usam botão. Em e-mail de adoção o CTA é a conversão e fica pouco visível, e o alvo de toque é pequeno | `cadu-growth.html` | Botão sólido 48 px, igual ao `.button` da base |
| T5 | `<title>` e `h1` repetem o mesmo texto longo; assunto = título (26–31 px com ~75 caracteres) quebra em 4 linhas no mobile | `GROWTH_EMAIL_MODELS` | Títulos de até ~60 caracteres; assunto diferente do título |
| T6 | Cópia dos modelos mistura "você" e voz de produto, e termina em frases genéricas; nenhum usa o nome da pessoa | `default_body` | Saudação com primeiro nome; revisão de cópia (seção 5) |
| T7 | Textos com `**negrito**` em markdown próprio: ok e escapado, mas não há teste de XSS no `_format_body_html` | `cadu_growth_email_templates.py` | Teste de unidade |
| T8 | `onboarding-demetrius.html` sem `<head>`, sem meta viewport, sem preheader; opt-out só "responda este e-mail" | arquivo | Reescrever sobre a base; manter reply-to do Demétrius (é e-mail pessoal, sem botão) |
| T9 | Sem endereço/identificação do remetente no rodapé além de "CentralComm" | todos | Razão social + contato no rodapé de marketing |
| T10 | `color-scheme: light only` + `!important` forçando branco: ok, mas as faixas PNG têm texto embutido? | `GROWTH_EMAIL_BAND_URLS` | Verificar se há texto na imagem (acessibilidade); `alt=""` hoje |
| T11 | Imagens em `ai.centralcomm.media/static/...` versionadas por `-v2`; se o domínio cair o e-mail perde a faixa | bandas | Aceitável; só garantir cache longo e que o deploy leve as imagens |
| T13 | `workspace-base.html` fixa `#007d6d`/`#173843` e o nome "Cadu Workspace"; serve para conta e acesso, mas não herda `brand.*` | `workspace-base.html` | Aceitável para transacionais de conta. Todo e-mail de uma solução usa `brand.accent/soft/deep` |
| T14 | Modelo `formatos` marcado como Studio, mas Formatos é do Planner no catálogo novo; `Docs` ainda aparece como Smart Docs | `GROWTH_EMAIL_MODELS` | Corrigir `product` e retirar `smart-docs` da sequência |
| T12 | Sem `tags` Brevo por sequência/passo, o que impede cruzar com o relatório da Brevo | `brevo_service.enviar_email` | Enviar `tags: ["seq:adocao","passo:3"]` |

## 3. Modelo de dados (migração aditiva)

Seguir `migrations/ORDER.txt` e testar em Postgres local (produção diverge do esquema do repo).

```sql
-- Preferência de contato (nível usuário, vale para qualquer sequência de marketing)
CREATE TABLE cadu_email_preferences (
    contato_id INTEGER PRIMARY KEY REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    marketing_opt_out BOOLEAN NOT NULL DEFAULT FALSE,
    opted_out_at TIMESTAMPTZ,
    opt_out_source VARCHAR(24),            -- link | admin | reply | brevo_webhook
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Estado da sequência por usuário
CREATE TABLE cadu_email_sequence_state (
    id BIGSERIAL PRIMARY KEY,
    contato_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    sequence_key VARCHAR(40) NOT NULL DEFAULT 'adocao_v1',
    next_step INTEGER NOT NULL DEFAULT 1,         -- 1..6; 7 = concluída
    next_send_at TIMESTAMPTZ,
    status VARCHAR(16) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','paused','completed','cancelled')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    paused_reason VARCHAR(80),
    UNIQUE (contato_id, sequence_key)
);
CREATE INDEX ON cadu_email_sequence_state (next_send_at) WHERE status = 'active';

-- Ledger único de TODOS os envios (substitui a dependência de id_cliente)
CREATE TABLE cadu_email_log (
    id BIGSERIAL PRIMARY KEY,
    contato_id INTEGER,                    -- pode ser nulo (lead, interno)
    id_cliente BIGINT,
    recipient_email VARCHAR(320) NOT NULL,
    kind VARCHAR(16) NOT NULL,             -- sequence | transactional | internal | onboarding
    event_type VARCHAR(80) NOT NULL,
    sequence_key VARCHAR(40), step INTEGER,
    subject VARCHAR(255) NOT NULL,
    status VARCHAR(16) NOT NULL,           -- queued|sent|failed|skipped|delivered|opened|clicked|bounced|complained|unsubscribed
    provider_message_id VARCHAR(255),
    provider_error TEXT,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ, first_opened_at TIMESTAMPTZ, first_clicked_at TIMESTAMPTZ,
    open_count INTEGER NOT NULL DEFAULT 0, click_count INTEGER NOT NULL DEFAULT 0,
    last_event_at TIMESTAMPTZ
);
-- índices: (contato_id, sent_at DESC), (status, sent_at DESC), (provider_message_id)
```

`cadu_workspace_email_events` continua sendo escrita por compatibilidade; a nova camada grava no `cadu_email_log` dentro de `send_cadu_event` e dos helpers de `email_service`, sem exigir `id_cliente`.

## 4. Motor da sequência

- Módulo `services/cadu_email_sequence.py`: `SEQUENCES['adocao_v1']` = lista de 6 passos (`model_key`, rótulo), `INTERVAL = 2 dias`.
- Comando `flask process-email-sequence --limit 50` e timer `deploy/install_email_sequence_timer.sh` (a cada 15 min, copiando o instalador do onboarding).
- Seleção: `status='active' AND next_send_at <= NOW()` com `FOR UPDATE SKIP LOCKED` (dois workers nunca enviam o mesmo passo).
- Guardas antes de enviar: opt-out, conta ativa, e-mail verificado, distância ≥ 48 h do último e-mail de marketing, não enviar entre 21h e 8h (horário de Brasília; adia para 9h).
- Envio via `build_growth_email` + `get_brevo_product_service(...).enviar_email` com `tags` e headers `List-Unsubscribe`. Resultado gravado no `cadu_email_log`; `next_step += 1`, `next_send_at = agora + 2 dias`; passo 6 → `completed`.
- Falha: até 3 tentativas com espera de 1 h; depois `paused` com `paused_reason='falha_envio'`. Um erro nunca trava os demais.
- Entrada: ao concluir o onboarding (`salvar_onboarding_comercial`), cria o estado com `next_send_at = NOW() + 2 dias`. Backfill da base existente só com ação explícita do admin (seção 7).
- A sequência pausa sozinha quando o usuário faz o que o e-mail ensina (ex.: já criou plano em Conversas → pula esse passo). Fase 2; não entra na primeira entrega.

## 5. Sequência padrão — Cadu novo, uma cor por família

Escopo: só o que existe no Cadu novo (`cadu_family/catalog.py`): **Workspace, Planner, Studio e Reports**. Ficam de fora **Smart Docs** (decisão do Apolo) e **Skills** (desligado por `CADU_SKILLS_ENABLED`). Cada e-mail usa o token de cor da sua família em `PRODUCT_EMAIL_BRANDS`, sem criar paleta nova:

| Família | Accent | Soft | Faixa |
|---|---|---|---|
| Workspace | `#007D6D` | `#E9F6F3` | `workspace-band-v2.png` |
| Planner | `#087D4D` | `#E8F7EF` | `planner-band-v2.png` |
| Studio | `#6344CF` | `#F1EDFC` | `studio-band-v2.png` |
| Reports | `#1363C5` | `#EAF2FD` | `connect-band-v2.png` |

Risco visual: Workspace (teal) e Planner (verde) são próximos. Diferenciar por faixa, ícone e nome da solução no cabeçalho, nunca só pela cor.

| Passo | Dia | Família | Tema | CTA |
|---|---|---|---|---|
| 1 | +2 | Workspace | Conversas → plano (`conversa-para-plano`) | Conversas |
| 2 | +4 | Planner | Audiências (`audiencias`) | Audiências |
| 3 | +6 | Studio | **Novo:** criar peça com o contexto da marca | Studio → Criar |
| 4 | +8 | Planner | Canais (`canais`) | Canais |
| 5 | +10 | Reports | Ler resultado e decidir (`connect-reports`) | Reports |
| 6 | +12 | Planner | Locais (`places`) | Locais |

**Revisão (Formatos e Interativos precisam existir):** seis passos não comportam Audiências, Canais, Locais, Formatos e Interativos mais Workspace, Studio e Reports. Opções: sequência de 8 e-mails, ou 6 e-mails agrupando temas. Formatos e Interativos ainda não têm modelo de e-mail (Interativos não existe em `GROWTH_EMAIL_MODELS`); criar os dois, em verde Planner.

A alternância de famílias evita três e-mails verdes seguidos e mostra o Cadu inteiro nos primeiros 12 dias.

Ajustes nos modelos para casar com o catálogo novo:
- **Remover** `smart-docs` (e `skills-conhecimento-reutilizavel`, já escondido por flag) da lista de modelos ativos da sequência.
- **`formatos`** hoje é do produto `studio`, mas no catálogo novo Formatos está no Planner. Corrigir o produto (vira verde) ou tirar da sequência; fica fora dos 6 passos.
- **Novo modelo `studio-criar`:** começa pela marca já cadastrada no Workspace e leva a Criar. Não prometer Áudio (lançamento dez/26, hoje só "quero ser avisado") nem recursos da mesa infinita antes de 2026-10-14; revisar a cópia depois do lançamento.
- **Nomenclatura:** usar "Locais" na cópia e na interface (rótulo do catálogo), com o caminho `/places`.
- **Radar** não entra: a busca real ainda não existe, então qualquer e-mail prometeria algo que o produto não entrega.
- **Reports (passo 5)** pressupõe fonte conectada. Se a pessoa ainda não conectou nada, o texto precisa funcionar como convite, não como "veja seu relatório".
- Conferir o caminho do CTA de cada modelo contra `product_domains` (hoje `connect` aponta para `/`).

Revisar a cópia de cada `default_body` com o usuário antes da ativação (T6).

## 5b. Boas-vindas no cadastro (3 e-mails) — a aprovar primeiro

Hoje o cadastro envia: (1) "Sua conta está pronta" (`bem-vindo.html`), (2) tokens de boas-vindas (`bonus-creditos.html`, variante `welcome_tokens`) e (3) o bônus de lançamento, que é **pulado** no cadastro público porque o direito `cadu_launch_100k` é gravado com 0 (`replaced_by_welcome`). Não há e-mail que leve a configurar marca e projeto; "primeira base pronta" só chega depois do onboarding.

Série proposta, todos na família Workspace:

| # | Quando | Conteúdo | Ilustração candidata |
|---|---|---|---|
| 1 | cadastro | Boas-vindas e acesso | `output/email-welcome-illustrations/01-boas-vindas.png` |
| 2 | cadastro + alguns minutos | Configure sua marca e seu primeiro projeto (CTA: `/workspace/onboarding`) | `02-marca-e-projeto.png` |
| 3 | cadastro + alguns minutos | Seus tokens iniciais e como usar | `03-tokens.png` |

**Divergência a resolver:** o cadastro público concede **50.000** tokens (`DEFAULT_WELCOME_TOKENS`, `CADU_WELCOME_TOKENS`). Os **100.000** existem como franquia mensal do plano Free (só com `CADU_PLAN_ALLOWANCE_ENABLED`) e como bônus de lançamento (convidados e contas antigas). O e-mail 3 só pode dizer "100 mil" se o valor concedido for esse; senão o e-mail promete mais do que o saldo.

## 6. Painel no CentralX — `/admin/emails`

Rota com `@admin_required`, no menu ERP. Quatro abas:

1. **Visão geral:** enviados/entregues/abertos/cliques/falhas/descadastros nos últimos 7 e 30 dias; funil da sequência (quantos usuários em cada passo); alertas (taxa de falha > 5%, bounces, reclamações).
2. **Eventos:** tabela paginada do `cadu_email_log` com filtros por tipo, status, sequência/passo, período e busca por e-mail. Linha abre o detalhe (assunto, erro do provedor, linha do tempo de entregue/aberto/clicou).
3. **Por usuário:** busca por pessoa e histórico completo do que recebeu, estado da sequência (passo atual, próximo envio), botões **pausar / retomar / pular passo / reenviar passo / descadastrar / enviar agora**.
4. **Sequência:** lista de usuários na sequência com seleção múltipla.

**Ações em massa** (sempre com confirmação mostrando a contagem e uma lista prévia dos primeiros destinatários; ação gravada em log de auditoria `audit.py`):
- pausar / retomar selecionados ou todos os filtrados;
- reenviar falhas do período;
- pular para o passo N;
- inscrever segmento na sequência (com prévia);
- marcar descadastro (o inverso exige confirmação extra).

Backend: `aicentralv2/admin_emails_routes.py` (blueprint) + `services/cadu_email_admin.py` (consultas e ações, sem SQL na rota). Front em Tailwind/DaisyUI, igual ao ERP existente. Webhook Brevo unificado: `/api/brevo/webhook` passa a gravar no `cadu_email_log` (entregue, aberto, clique, bounce, reclamação, descadastro) com o mesmo token; o endpoint antigo do Workspace continua funcionando.

## 7. Decisões que dependem do Apolo

1. Ordem dos 6 passos (tabela da seção 5), em especial se o passo 6 deve ser Locais ou Creative Analyzer.
2. Quem entra: só novos onboardings a partir da ativação, ou também a base atual (backfill). Ambiente local aponta para o banco de produção; backfill só com prévia e confirmação.
3. A contagem dos 2 dias parte do onboarding concluído ou do cadastro?
4. Rodapé (T3): seguir o playbook (`CentralComm`) ou manter "Powered by CentralComm".
5. Razão social/endereço para o rodapé (T9) e e-mail de resposta da sequência.
6. Confirmar na Brevo qual webhook está cadastrado e se o remetente tem DKIM/DMARC ok para volume recorrente.

## 8. Fases

| Fase | Entrega | Verificação |
|---|---|---|
| 0 | Confirmar webhooks e domínio na Brevo; decisões da seção 7 | checklist |
| 1 | Migração + `cadu_email_log` + gravação em todos os pontos de envio + webhook unificado | testes + um envio real de homologação |
| 2 | Painel somente leitura (Visão geral, Eventos, Por usuário) | tela em 1280 px e mobile |
| 3 | Descadastro (rota pública assinada, preferências, header) + templates corrigidos (T1–T12) | teste de render e envio para `apolo@centralcomm.media` |
| 4 | Motor da sequência + timer, ligado **desligado por padrão** (`CADU_EMAIL_SEQUENCE_ENABLED`) | testes de seleção, concorrência, guardas |
| 5 | Ações individuais e em massa no painel | testes + auditoria |
| 6 | Ativação para novos onboardings; backfill opcional | acompanhar 1 semana no painel |

Testes novos: `tests/test_cadu_email_sequence.py`, `tests/test_cadu_email_admin.py`; estender `test_cadu_growth_email_templates.py` (opt-out, preheader, escape). Lembrar: usar `.venv/bin/python` (3.13), há ~125 falhas antigas na suíte.
