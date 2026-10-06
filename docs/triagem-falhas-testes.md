# Triagem das falhas de teste (06/10/2026)

Medição feita num worktree limpo no HEAD, para que as edições não commitadas de outras sessões
não entrassem na conta. Comandos: `DB_HOST=127.0.0.1 DB_PORT=1 .venv/bin/python -m pytest` e `node --test tests/frontend/*.test.* tests/frontend/*.cjs`.

| | Início | Fim |
|---|---|---|
| pytest | 139 falhas + 2 erros (190 no working tree compartilhado, por causa de `auth.py` ainda não commitado) | 35 falhas, todas fora do meu escopo (ver "O que ficou") |
| node | 23 falhas (mais README/.py rodados como teste quando se usa `tests/frontend/*`) | 0 com `--test-concurrency=4`; com a concorrência padrão (8), 1–2 testes de vídeo do Studio ainda podem estourar o tempo |

## Bugs reais de produto (corrigidos)

- **Pedido de pacote de tokens com observação nunca chegava à API** (`WorkspaceAccount.jsx`): `onChange={setNote}` guardava o evento React e o `JSON.stringify` falhava. Corrigido para usar `event.target.value`.
- **Prévia pública de Skill sempre dava 500** (`cadu_skills/routes.py`): usava `reservation` sem defini-la e `session["cliente_id"]` sem conta logada. Agora exige conta (401) e usa uma chave de idempotência própria. A rota `/skills/api/` continua acessível mesmo com a chave de Skills desligada.
- **Ciclo de alertas do Reports quebrava com o banco fora do ar** (`reports_alerts.PeriodicRunner`): o `get_db().rollback()` dentro do `except` lançava de novo a exceção e derrubava o loop do monitor.
- **Home do Studio ficava em "Carregando marca…"** quando a leitura dos contextos de projeto falhava ou vinha vazia: `mc-cadu-nav.js` só publica `cadu:project-ready`, e `mc-cadu-home.js` não escutava esse evento.
- **Navegação móvel do Workspace** podia gerar link `href="#"` (`WorkspaceMobileChrome.jsx`). Agora cai na Home.
- **Bootstraps React do Workspace** davam 500 quando `workspace_user_avatar` não estava no contexto (apps parciais, handlers de erro). Agora usam `|default('')`.

Os bundles `static/**/react/*.js` estão no `.gitignore` e são gerados no deploy. As correções de `frontend/` entram no próximo build.

## Testes desatualizados, por grupo (corrigidos no teste)

- **CRM v3 (40)**: desde set/2026 o padrão é o repositório real, sem fallback para o mock. A API passou a ser testada com `USE_CRM_V3_STORE=mock`.
- **Workspace/projetos (6)**: URL limpa `/projetos/<id>`, rota de contexto delegando ao `project_context_service`, SQL com espaços diferentes, visão "Indexação", textos de crédito trocados por "Tokens", ref opaca da marca e gaveta de notificações.
- **Identidade**: o callback do Google passa pela ponte `/acesso-confirmado`; a sessão guarda `login_conversion.next`.
- **Créditos**: `cadu_plan_allowance.py` (concede e expira o lote da franquia) entrou na lista de fronteiras do razão.
- **E-mails de crescimento**: o CTA usa o `product_url` do produto, não o `CADU_URL`.
- **Chat**: o stream usa `runtime_provider`, e não mais `dify` direto; `/conversas` redireciona para `/chat`; seções de conversa são opcionais.
- **Reports**: o editor legado de relatórios virou redirecionamento para o app React; a paridade de validação passou a carregar o arquivo (que agora tem import); as estratégias trazem orgânico e direto sem taxa; as telas foram divididas em vários `.jsx`.
- **Smart Planner**: título no formato cliente · objetivo; referência sem cabeçalho; voo com data fixa (**C**: dependia da data de hoje, "2026-09").
- **Skills**: visitante vai para o Workspace e o catálogo é testado logado.
- **PI/Campanhas, integrações, Trocr, protótipos**: JS extraído para arquivo estático, CHECK canônico de provedores, cache por impressão digital, `url_for` sem arquivo.
- **Frontend Workspace**: a sidebar contextual substituiu o dock nas telas internas (o dock ficou só na Home); o modal de marca virou slideout; os botões são `CaduButton` Untitled (com `data-cadu-variant`); o artefato no tablet em retrato abre em tela cheia.
- **Studio**: as fixtures renderizavam o template órfão `parametros/modelagem_criativos.html`; agora usam a Home real `cadu_studio/home.html`, com `skills_enabled` e contextos de projeto.

## Dependentes de ambiente (C), agora determinísticos

- As fixtures do Studio eram regravadas em paralelo por cerca de 10 testes; a gravação passou a ser atômica.
- As esperas de `videoWidth` e `aria-busy` passaram a ser tolerantes à carga.
- `test_design_system_ads::matriz_de_consumo` depende de `.agents/`, que está no `.gitignore`. O teste agora é pulado quando o diretório não existe.

## O que ficou e por quê

- **35 falhas pytest, todas por `'skills_enabled' is undefined` no blueprint `cadu_family`** (Planner: `test_cadu_family`, `test_cadu_attachments`, `test_cadu_copy_ads`, `test_cadu_foundation`, `test_planner_hero_backgrounds`), mais **`test_product_portals`** (4). Pertencem à frente de separação de papéis admin, conduzida por outro agente. A correção é chamar `register_product_flags(app)` em `cadu_family.register`, no mesmo padrão já usado em Connect/Workspace. A alteração foi bloqueada pela permissão desta sessão e ficou para quem cuida de `product_flags`.
- **Concorrência dos testes de navegador**: com 8 workers, dezenas de Chromium disputam a máquina. Recomenda-se rodar com `node --test --test-concurrency=4`.
- **Cópia de produto**: `smart_planner.references.reference_block` gera "Apoio da arquivo …" (concordância errada para arquivo/dados). Não foi corrigido.
