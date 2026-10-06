# Auditoria do Workspace: conector de tokens, contas e faturas, telas (lançamento 11/10/2026)

Data: 06/10/2026. Auditoria somente leitura: nenhum código do produto foi alterado e nada foi escrito no banco. Telas vistas no ambiente local `tests/visual/workspace` (fixtures, sem backend) em 1440x900 e 800x600.

## Veredito por área

| Área | Veredito | Resumo |
|---|---|---|
| 1. Conector global de tokens | **Risco** | Os produtos de cliente (chat, pesquisa, MCP, Planner, Reports, Studio, Radar, RAG, creative_*) debitam por `CaduCreditConnector`/`ToolTokenLedger` com chave idempotente. Ainda há chamadas auxiliares de IA sem débito, falhas de cobrança só registradas em log e um admin do Centralx que trabalha com tabelas paralelas. |
| 1b. Admin do Centralx | **Bloqueador** (operacional) | `/cadu/creditos` lança compras e ajustes em `cadu_credit_movements`/`cadu_credit_purchases`, que o saldo real (`cadu_credits_extras`) não lê. A lista de planos mostra `tokens_used_current_month`, um contador que nenhum fluxo de IA atualiza. |
| 2. Conta e faturas | **Bloqueador** | Qualquer usuário logado, inclusive uma conta pública Free criada na hora, credita tokens ilimitados sem pagar (`/workspace/api/creditos/solicitar`). Contas públicas nascem sem administrador, então não editam a Agência nem convidam pessoas. |
| 3. Telas | **Risco** | Não há tela quebrada com os dados no formato que o backend envia. Há problemas de layout em Tarefas do Projeto, no painel direito da Marca, em Equipe e na Marca a 800px, além de "créditos" que sobraram. |
| 4. Skills | Anotação | Restam referências (lista abaixo). |

---

## 1. Conector de tokens: pontos de consumo

### Passam pelo conector com idempotência (OK)
| Produto | Ponto | Chave |
|---|---|---|
| Workspace chat (Dify) | `cadu_workspace/conversations/service.py:841` `charge_chat_usage`, chamada em :989 | por run |
| Pesquisa externa do chat | `conversations/service.py:874` | `research:<run>:<plan>` |
| Agente v2 / jobs longos / inteligência de mercado | `agent_v2/service.py`, `agent_v2/long_job_worker.py`, `agent_v2/routes.py` (voz: `transcription_credit_tokens`) | por job |
| RAG / indexação de projeto | `project_index_service.py:291` → `cadu_skills/repository.py:387` `charge_project_rag` | por fonte e hash |
| Busca web, mídia, ícones, identidade visual | `web_search.py`, `media_creation_service.py`, `dock_icon_service.py`, `visual_identity_service.py` | sim |
| MCP (workspace e público) | `cadu_workspace/mcp/tools/media.py`, `cadu_public_mcp/usage.py` | sim |
| Planner | `cadu_planner/revisions.py` (`charge_review_pass`) | sim |
| Reports | `cadu_connect/reports_ai.py:56/70/90` (chat, typesafe, firecrawl), `report_review.py`, `reports_imports.py`, `reports_page_captures.py` | `uuid4` por chamada (sem replay em retry) |
| Studio | `creative_media/studio.py`, `studio_create.py` (`charge_studio_call`), `creative_lab/studio_bridge.py` | sim |
| Radar | `cadu_radar/pipeline.py` (CaduAIConnector) | sim |
| creative_* | `creative_brand_analysis.py`, `creative_modeling_service.py`, `creative_format_lab/service.py`, `creative_analyzer/service.py` | sim |
| Insights | `cadu_workspace/insights_research.py` (CaduAIConnector) | sim |
| Skills | `cadu_skills/runtime.py` (CaduAIConnector) | sim |

### Consumo SEM débito (vazamento de custo)
| Sev. | Arquivo:linha | O quê | Correção sugerida |
|---|---|---|---|
| Média | `cadu_workspace/conversations/memory_extractor.py:94-105` | Extração de memória com `gpt-4.1-mini` depois de cada conversa, **ligada por padrão** (`CADU_MEMORY_EXTRACTION` != "0"). Sem débito. | Debitar via `charge_provider` com a chave `memory:<conversation>:<window>`, ou assumir como custo interno e documentar. |
| Média | `cadu_workspace/agent_v2/retrieval_query.py:74` | Reescrita da consulta (`gpt-4.1-mini`) a cada recuperação do executor. Sem débito. | Somar ao débito do turno do agente. |
| Baixa | `cadu_workspace/project_knowledge.py:156` `query_embedding` | O embedding de cada consulta não é cobrado (a indexação é). | Aceitável; documentar. |
| Baixa | `cadu_workspace/agent_v2/rerank.py:53` | Rerank fica desligado por padrão (`CADU_RERANK=0`). Se ligado, não debita. | Debitar antes de ligar. |
| Baixa | `routes.py:4930-4950` (audiências do Centralx) | Geração de imagem só incrementa `image_credits_used_current_month` (contador legado). | Ferramenta interna; ok se continuar só no Centralx. |
| Interno | `smart_planner/*` (`centralcomm_required`), `creative_lab/connector.py`, `evaluation.py`, `intelligence.py`, `training_studio/*`, `crm*`, `financeiro/*` | Ferramentas internas sem débito por cliente. | Ok, desde que nenhuma rota de cliente as chame. |

### Débito engolido ou parcial
| Sev. | Arquivo:linha | O quê | Correção |
|---|---|---|---|
| Média | `cadu_connect/reports_ai.py:47-53` `_charge` | Uma falha de débito (inclusive saldo insuficiente depois da autorização) só vai para o log: a resposta é entregue sem cobrança e sem fila de reconciliação. | Gravar uma linha `failed`/`pending` no ledger para reconciliar, ou alertar. |
| Baixa | `conversations/service.py:873-889` | A pesquisa roda e só depois é debitada. Se o débito der `InsufficientToolCredits`, o custo já aconteceu e a evidência é descartada. | Reservar (`authorize`) antes de `research.execute`. |
| Baixa | `conversations/service.py:989-1000` | Uma resposta de chat que estoura o saldo fica salva e marcada, mas não é cobrada. | Aceitável (corrida), com monitoramento. |
| Info | `cadu_plan_allowance.py:32` | A franquia mensal do plano depende de `CADU_PLAN_ALLOWANCE_ENABLED`. Desligada, o Free (100 mil/mês) não libera franquia e o cliente vê "liberação automática ainda não está ativa". | Decidir antes de 11/10 e ligar em produção. |

### Tabelas paralelas e divergência no admin do Centralx
| Sev. | Arquivo:linha | O quê | Correção |
|---|---|---|---|
| **Bloqueador** | `routes.py:645-720` + `db.py:4894-4990` | "Compra registrada e créditos liberados" grava em `cadu_credit_purchases`/`cadu_credit_movements`. O conector e o Workspace leem `cadu_credits_extras`, então o saldo do cliente não muda. O financeiro vai achar que liberou e não liberou. | Fazer o admin criar um lote em `cadu_credits_extras` (como `credit_purchase_service.purchase_extra`) ou esconder a tela até lá. |
| Alta | `db.py:4735-4747` (`obter_gestao_creditos`) | A gestão de créditos usa `image_credits_monthly` / `image_credits_used_current_month`, ou seja, o modelo antigo de créditos de imagem. | Trocar por `cadu_plan_allowance.get_balance` + ledger. |
| Alta | `templates/cadu_planos.html:103-106`, `routes.py:2732` | O uso do plano exibido vem de `tokens_used_current_month`, que nenhum fluxo atualiza (o próprio `cadu_billing_catalog.py:354` documenta isso). O admin sempre vê 0%. | Calcular o uso pelo `cadu_tools_token_usage` do ciclo. |
| Média | `cadu_skills/repository.py:354-357` `credit_position` | `monthly_used` lê o mesmo contador legado. | Ler do ledger. |
| Média | `cadu_family/repository.py:343-353` `plan()`/`consumption()` | Lê `cadu_token_usage` (telemetria do Dify) como consumo. Hoje não há chamadas, é código morto. | Remover. |
| Info | `db.py:5212` `registrar_uso_token` / `cadu_token_usage` | Telemetria de tokens do Dify, não cobrança. Ok, mas não deve ser somada como consumo. | Documentar. |

---

## 2. Contas e faturas (`WorkspaceAccount.jsx` + `cadu_workspace/routes.py`)

| Sev. | Onde | Achado | Correção sugerida |
|---|---|---|---|
| **Bloqueador** | `cadu_workspace/routes.py:1323-1373` `request_credit_package` | Só exige login e CSRF. Não checa papel, plano nem pagamento. O pedido nasce `approved` e cria o lote em `cadu_credits_extras` na hora, inclusive em pós-pago. A única barreira é um bloqueio de 30 s por pacote, então qualquer conta pública Free pode gerar milhões de tokens em minutos. O texto da tela confirma a regra: "Qualquer pessoa da equipe pode comprar... Liberação imediata" (`WorkspaceAccount.jsx:188`). O caminho MCP (`credit_purchase_service.py:28`) exige admin e cria `pending`, o Workspace não. | Para o lançamento: criar `pending` e liberar o lote só depois da aprovação do financeiro (como o checkout B1), ou no mínimo exigir admin, conta não-Free, limite diário e pós-pago só para clientes com contrato. Ajustar o texto. |
| Alta | `services/onboarding_comercial.py:56` + `routes.py:1436` `_workspace_team_admin` | O cadastro público cria o contato com `user_type='client'`, e Agência, convites e papéis exigem `admin`/`superadmin`. Toda conta pública nasce sem ninguém capaz de editar a Agência ou convidar a equipe. | Criar o primeiro contato da conta pública como `admin`. |
| Alta | `routes.py:10260-10300` `create_team_invite` | Não verifica `max_users` do plano nem se o e-mail já é membro. Os textos prometem "Pessoas ilimitadas" (`WorkspaceAccount.jsx` Planos), mas o plano tem `max_users` (`routes.py:440`, `db.py:5043` padrão 5). | Decidir: ou o plano é ilimitado (remover `max_users`), ou validar no convite. Bloquear convite para quem já é membro. |
| Média | `routes.py:10409-10420` vs `cadu_family/repository.py:74` vs convite | Três vocabulários de papel: convite `member/admin`, edição `client/admin/readonly`, MCP `admin/member/viewer`. `readonly` cai em `member` no MCP, ou seja, um "Somente leitura" tem acesso de membro pelo MCP. | Unificar e mapear `readonly` para `viewer`. |
| Média | Formulários nativos de Perfil, Agência, Convites e Papel (`routes.py:10141-10460`) | Os erros (`abort(400/409/502)`) aparecem como página de erro crua, sem mensagem inline e sem manter o que foi digitado. | Responder com redirect + flash/`?error=` ou com fetch em JSON. |
| Média | Perfil (`routes.py:10141`) | Não há upload de foto: só o selo pré-definido e a foto do Google. Se o escopo do lançamento promete foto, falta. | Confirmar escopo; se a foto entrar, criar upload com validação de MIME e tamanho. |
| Baixa | `routes.py:10194` `update_organization` | O CPF/CNPJ só tem o tamanho validado (sem dígito verificador) e qualquer admin pode trocar a razão social/CNPJ usado no faturamento. | Validar o DV; avisar o financeiro quando o CNPJ mudar. |
| Baixa | `routes.py:1394` | E-mail de confirmação pulado para `apolo@centralcomm.media` no código. | Mover para configuração. |
| Ok | CSRF | Todas as mutações chamam `_workspace_api_csrf()`. Membro ativo/inativo e papel protegem o último admin e a própria conta. | — |
| Ok | Catálogo | Preço e volume vêm só do servidor (`package_by_key`). Planos, Tokens e Uso usam "tokens" e o ledger. | — |

### "Créditos" que sobraram
- `templates/cadu_workspace/account_react.html:2` título da aba "Créditos"; `:8` noscript "plano e créditos", "Créditos disponíveis".
- `WorkspaceFeedback.jsx:86` menu da conta: "Uso de créditos".
- `WorkspaceHomeWidgets.jsx:13,122` widget "Uso e créditos".
- `WorkspaceLegacyChrome.jsx:15` item "Créditos".
- `WorkspaceBrand.jsx:186` estimativa da auditoria "150 mil créditos" / "75 mil créditos".
- `credit_purchase_service.py:31-78` e `mcp/tools/account.py:200-214`: mensagens e descrições de ferramentas MCP com "créditos".

---

## 3. Telas (fixtures em `tests/visual/workspace/fixtures.mjs`)

Novas fixtures: `marca-completa`, `projeto-cheio` (+ 9 visões), `projetos`, `projetos-vazio`, `marcas`, `marcas-vazio`, `conta-equipe`, `conta-equipe-membro`, `conta-perfil`, `conta-agencia`, `conta-agencia-membro`. Foram verificadas 38 telas x 2 viewports por script (erros de console, `role=alert`, rolagem horizontal, textos truncados, links com href vazio ou `undefined`, contagens "0 ..."), mais capturas pontuais.

| Sev. | Tela / viewport | Achado | Correção |
|---|---|---|---|
| Alta | Projeto › Tarefas, 1440 e 800 | A linha da tarefa colapsa numa coluna de cerca de 40px: o título vira "Aprovar ..." em cinza e o responsável e o prazo quebram em 3 ou 4 linhas. O painel principal fica quase vazio. | Revisar a grade da linha de tarefa (min-width do título, `grid-template-columns`). |
| Média | Marca (completa), 1440 | No painel direito, "Base da marca / Disponível" se sobrepõe em fonte grande e "Projetos da marca" mostra "Ce / mi / g" quebrado letra a letra. | Dar `min-width:0`/largura ao rail e ajustar a tipografia do status. |
| Média | Marca, 1440 | "Estado da base: Análise ainda não iniciada" aparece ao lado de "86% · Cobertura consolidada" e de uma auditoria concluída. A mensagem contradiz os dados (vale checar o campo `reviewPack.status` que o backend envia). | Derivar o estado do histórico de auditoria e da cobertura. |
| Média | Marca, 800 | A barra de abas transborda ("Bibli…" cortado) e o texto do estado da base estoura a largura. | Abas com rolagem horizontal visível ou menu; quebrar o texto. |
| Média | Conta › Equipe, 800 | O campo de e-mail do convite colapsa (cerca de 25px) e os botões da linha do membro ("Salvar", "Desativar") saem da tela. | Empilhar o formulário e as ações abaixo de 900px. |
| Baixa | Marca | Um `analysisMetadata.sources` que não seja lista derruba a página inteira ("Não foi possível abrir o chat"). O backend já converte para lista (`routes.py:8721`), mas a tela não tem boundary local. | Usar `asList()` também em `WorkspaceBrand.jsx:591`. |
| Baixa | Projeto (cabeçalho), 1440 | "Cemig — Campanha Verão 2027" já aparece truncado na barra lateral ("Cemig — Campan…"). | Permitir 2 linhas ou mostrar um tooltip. |
| Baixa | Conta › Tokens | "tokens por mês · renova em 01/11/2026" truncado nos dois viewports. | Quebrar a linha. |
| Baixa | Conta › Integrações | `role=alert` "Não foi possível verificar a conexão agora" no estado sem conexão (vem do endpoint de agentes; na fixture retorna `{}`). Vale confirmar que, em produção, uma conta sem integração não vê esse alerta. | Tratar a resposta vazia como "sem conexão". |
| Baixa | Projetos / Marcas vazios | Cabeçalho "0 projetos"/"0 marcas" acima do estado vazio é redundante. | Esconder a contagem quando for 0. |
| Baixa | Conta › Faturamento | "0 faturas" para quem só tem pedido de tokens. | Texto "Nenhuma fatura ainda". |
| Info | Home | Mostra só o composer e "Retomar trabalho recente" (com `resume: []` não há estado vazio explicativo). | Opcional. |
| Info | Links mortos | "Criar plano de mídia/imagem/vídeo", "Gerenciar equipe", "Método de compatibilidade" aparecem sem href só porque a fixture não envia essas URLs (o template real envia). Não é bug. | — |
| Ok | Todas | Nenhum erro de console nas telas com dados no formato do backend. Sem rolagem horizontal de página em 1440. | — |

Não foram vistos: cartão-dentro-de-cartão evidente e botões sem contraste (o script não achou texto da mesma cor do fundo).

---

## 4. Skills: referências remanescentes (só anotação)
- `templates/cadu_workspace/account_react.html:29,31` (`solutions.skills`, `solutionIcons.skills`).
- `templates/cadu_workspace/_app_sidebar.html`, `brands_react.html`, `brand_detail_react.html`, `conversations_v2_lab.html`, `design_system.html`, `public.html`, `public_page.html`, `mcp_agents.html`.
- `frontend/cadu-design-system/components/WorkspaceLegacyChrome.jsx`.
- `tests/visual/workspace/fixtures.mjs` (`solutions.skills: '#'`).

---

## Corrigir antes de 11/10
1. **Compra de tokens no Workspace sem pagamento nem papel** (`cadu_workspace/routes.py:1323`): pedido `pending` com liberação pelo financeiro, ou no mínimo admin + conta paga + limite.
2. **Admin do Centralx credita em tabelas que o saldo não lê** (`routes.py:645-720`): gravar lote em `cadu_credits_extras` ou ocultar a tela.
3. **Conta pública sem administrador** (`onboarding_comercial.py:56`): o primeiro contato deve ser `admin`.
4. **Uso no admin sempre 0** (`cadu_planos.html:103`, `db.py:4735`): ler do ledger.
5. **Decidir `CADU_PLAN_ALLOWANCE_ENABLED`** em produção (a franquia Free depende dele).
6. **Layout de Tarefas do Projeto** e **Equipe a 800px**.
7. **Máximo de usuários x "pessoas ilimitadas"**: alinhar o texto e o convite.

## Pode esperar
- Débito de memory_extractor, retrieval_query e embedding de consulta (ou registrar como custo interno).
- Reconciliação das falhas de débito no Reports; reserva antes da pesquisa do chat.
- Unificação dos papéis (member/client/readonly/viewer).
- Erros inline nos formulários de conta; DV de CNPJ; upload de foto.
- Painel direito e abas da Marca; textos truncados; contagens "0".
- Trocar "créditos" restantes por "tokens".
- Remover `cadu_family/repository.plan/consumption` e o contador legado `tokens_used_current_month`.
