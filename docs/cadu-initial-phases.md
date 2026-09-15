# Fases iniciais — inventário e fundação

## Condições de execução

- Origem PHP e PostgreSQL usados somente como consulta.
- Nenhuma migration aplicada, nenhum dado importado e nenhuma ativação em produção nesta etapa.
- `CADU_FAMILY_ENABLED` controla o piloto e permanece desativado por padrão.
- `CADU_FAMILY_WRITES_ENABLED` é falso por padrão. Bloqueia gravações e ações externas das novas rotas, incluindo perfil, entidades, confirmações e interrupção de tarefas externas.
- Seleção de contexto altera apenas a sessão. Validação de Copy Ads consulta o catálogo sem gravar.
- O chat exige ambas as permissões de configuração: chat habilitado e gravações habilitadas. Não habilitar no banco legado durante a consulta.

## Contratos funcionais iniciais

| Destino | Fonte PHP | Contrato a preservar | Tabelas/dependências identificadas | Situação |
| --- | --- | --- | --- | --- |
| Auth | login, recuperação, cadastro, callbacks Google e `auth/` | Email completo de cliente; validação de senha; retorno seguro ao produto; logout e recuperação | `tbl_contato_cliente`, `tbl_cliente`; OAuth e serviço de email | Código existente, validação ponta a ponta pendente |
| Workspace | `configuracoes-*`, `centro-inteligencia.php`, planos e integrações | Organização separada de cliente selecionado; papéis; limites; arquivos e vínculos | `cadu_ci_projetos`, `cadu_projetos`, `cx_clients`, planos, faturas e integrações | Consultas e contexto iniciais; administração completa pendente |
| Studio / Copy Ads | `api/copy-ads/formatos.php`, `api/gerar-copy-v2.php` | Briefing mínimo; extração revisável; geração de variações; campos por formato; históricos | `cadu_formatos`, `cadu_plataformas_formatos`; OpenRouter; limites da ferramenta | Editor/validação implementados; IA, histórico e consumo pendentes |
| Studio / Creative Analyzer | `api/creative-analyzer/`, `analise-criativo*` | Arquivos suportados; análise; progresso; relatório; histórico | Processadores, upload, prompts e persistência a detalhar | Referências preservadas; inventário detalhado pendente |
| Studio / Link Tester | `api/link-tester*` | URL; verificações; diagnóstico; histórico; limites | Dependências de rede e persistência a detalhar | Referências preservadas; inventário detalhado pendente |
| SmartPlanner | Audiências, Canais, Formatos, Interativos, Docs, Cotações | Jornada de cliente; cotação independente; exportação sem informações internas | Catálogos e `cadu_cotacoes`; contratos de Docs/Planos a detalhar | Consultas iniciais; fluxos completos pendentes |
| Conversas | `chat-cadu-dify.php`, `includes/dify`, scripts Dify, conhecimento | Modos; anexos; conhecimento; streaming; parar; histórico; confirmação; consumo | `cadu_conversations`, mensagens, `cadu_ci_chunks`, `cadu_token_usage`; Dify/Gemini | Transporte parcial; paridade integral pendente |
| Connect | Campanhas, relatórios, integrações | Relatórios por cliente; vínculos confirmados com projetos; perfil operacional | Campanhas e integrações; associação por sidecar proposta | Consultas iniciais; fluxo completo pendente |

Esse inventário não é uma declaração de paridade. Tabelas e dependências ainda não detalhadas precisam de inspeção adicional; nomes não bastam para inferir regras de autorização.

## Fundação verificada localmente

- Usuário e autorização de cliente reavaliados no servidor.
- Organização de login não é sobrescrita ao selecionar um cliente.
- Referências qualificadas evitam colisão entre IDs de fontes distintas.
- Troca de cliente descarta marca/projeto anteriores.
- Retorno de login rejeita hosts externos, credenciais na URL, portas não autorizadas, controles e barras ambíguas.
- Testes do bloqueio de gravação e das entradas inválidas em `tests/test_cadu_foundation.py`.

## Pendências antes de concluir as fases 0 e 1

1. Inventário detalhado de Creative Analyzer, Link Tester, Docs, Cotações e Connect, incluindo todos os estados e exportações.
2. Backup/restauração do banco e arquivos por processo autorizado; o snapshot de código não cobre dados.
3. Confirmar versões efetivamente publicadas de Dify e provedores, sem expor credenciais.
4. Testar login de cliente, Google, recuperação, logout e sessão entre domínios em ambiente isolado.
5. Validar navbar autenticada/visitante em desktop, tablet e mobile, teclado, nomes longos e falhas de rede.
6. Preparar ambiente de dados de teste para testar gravações sem tocar no legado.

Nenhuma dessas pendências deve ser marcada como concluída somente porque testes unitários passaram.

## Inspeção adicional do Studio

### Creative Analyzer

- A tela principal é modular: `creative-analyzer.php`, helpers e `api/creative-analyzer/`.
- O PHP diferencia imagem e vídeo. O validador anuncia imagens de até 10 MB e vídeo de até 50 MB; os tipos configurados precisam ser conciliados com o pipeline real antes da implementação.
- O preparo de imagem para o modelo usa alvo de 4 MB e dimensão máxima de 2.048 pixels. Isso é limite do processamento, não limite do upload.
- Persistência identificada: `cadu_analises_criativos`. O histórico inclui nome/tipo/tamanho/dimensões, miniatura, caminho da imagem, tipo de criativo, formato, funil, vertical, score e data.
- Há acesso por UUID público condicionado a `link_publico_ativo`, além do acesso autenticado. A recriação precisa distinguir explicitamente compartilhamento público e contexto privado.
- Algumas consultas legadas usam `(user_id = usuário OR client_id = cliente)`. Não copiar essa condição indiscriminadamente: o novo contexto exige verificar o cliente autorizado também quando o usuário é dono de registros em outro cliente.
- Rotinas de exclusão existentes no PHP não serão executadas nem transportadas como parte da consulta.

### Link Tester

- Tela principal `ferramentas-link-tester.php`; resultado separado `link-tester-resultado`, com entrada por ID; aceita URL pré-preenchida e agrupa recentes por domínio.
- Modos identificados: `campanha` e `agentic`, com seleção de escopos via `LinkTesterScopes`.
- Análise inclui SSL, robots/AdsBot, status HTTP, redirecionamentos, desempenho, tags de mídia, elementos de conversão, metadados e compliance.
- Persistência principal: `cadu_link_tests`; catálogo de verificações: `cadu_site_agentic_checks`.
- Operações adicionais: screenshot, inspeção aprofundada de tags/rede, teste de sessão, resumo de IA, arquivo agentic, email, monitoramento/alertas e estado de recomendação.
- Monitoramento referencia `cadu_link_tester_monitored` e `cadu_link_tester_alerts`.
- A versão Python deve proteger toda chamada de rede contra SSRF, inclusive redirecionamentos, DNS e ferramentas auxiliares. Ainda não implementado.
- Email, monitoramento e ações externas ficam separados da consulta de histórico e precisam de autorização e confirmação próprias.

### Copy Ads

- Histórico identificado em `cadu_copy_ads` no gerador v2.
- A geração aplica limite da ferramenta `copy_generator`, além dos limites de texto do formato. Não confundir essas duas regras.
- O gerador legado tem extração de briefing e geração como etapas distintas; a versão Python precisa manter a revisão entre elas.

### Auth e cookies

- Existem configurações de Google para CentralX e Cadu separadas, além de compatibilidade com o Google/PHP legado.
- O domínio do cookie é configurável e pode estar ausente. Não considerar a sessão entre produtos comprovada apenas pela presença das rotas.
- Validar em ambiente isolado domínio, Secure, HttpOnly, SameSite, chave de sessão e comportamento de logout. Não alterar valores de produção automaticamente.

## Avanço: identidade nativa e revisão visual

- Implementado Google Cadu nativo para contas existentes e ativas, sob `CADU_GOOGLE_NATIVE_ENABLED=1`. A flag continua desligada por padrão; nenhuma configuração de produção foi alterada.
- O fluxo não cria usuários nem modifica cadastros. Reutiliza verificação OIDC, state, nonce e PKCE; erro de rede passa a retornar uma mensagem segura de login.
- Testes simulados verificam callback, retorno ao Studio, renovação da sessão, descarte do contexto anterior, conta/organização inativa e compartilhamento de cookie pelos cinco produtos. Verificam também que o cookie não é enviado a domínio externo.
- Revisão no navegador local com dados simulados: Workspace autenticado em 1440×900, 820×1180 e 390×844; visitante e painel no mobile; Escape e retorno de foco.
- Corrigida regra CSS que mantinha altura de sidebar desktop no mobile, empurrando o conteúdo para fora da primeira tela. Corrigida largura do menu mobile.
- Links do seletor no piloto apontam para as rotas `/familia/<produto>/`; Skills mantém sua entrada existente. Cobertura adicionada ao teste de template.
- Ainda pendentes: Google real com callback publicado, email/senha e recuperação reais, logout entre hosts publicados, falhas de rede na interface, navegação completa de todos os produtos e paridade integral do chat.

As verificações de cookie são feitas pelo cliente de testes Flask. Não comprovam configuração de proxy, DNS, certificados, segredo de sessão ou comportamento de cookies no ambiente publicado.

## Avanço: email/senha, recuperação e logout

- Testadas as rotas reais de login/logout/recuperação com todos os acessos ao banco e emails simulados em `tests/test_cadu_password_flows.py`.
- Login de cliente retorna diretamente ao Studio e aceita domínio de email externo. Organização inativa é recusada novamente na rota, além da verificação existente das credenciais.
- Quando o modo Google nativo está habilitado, o destino padrão do login passa a ser Workspace, evitando o encaminhamento implícito ao PHP.
- Logout limpa identidade e contexto da sessão; teste acompanha os cinco produtos no mesmo cliente de testes. Não equivale a revogação de sessões em outros dispositivos.
- Recuperação apresenta a mesma mensagem para email desconhecido, conta inativa e solicitação válida. O link usa o domínio Auth configurado, não o Host enviado na requisição.
- Redefinição agora faz consumo do token e atualização de senha em um único UPDATE condicional: token, validade e estados do usuário/organização são revalidados no momento da escrita.
- Testados token expirado, token já consumido, senhas divergentes, preservação de espaços na senha, sucesso e rollback. Nenhuma operação foi executada no banco real.

Pendências reais desta frente: entrega do email e callback Google no ambiente de homologação, compatibilidade dos hashes de contas piloto, testes de proxy/cookies entre domínios publicados, política de limitação de tentativas e proteção CSRF completa das rotas Auth. Não ativar a migração considerando apenas os testes simulados.
