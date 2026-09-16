# Execução da migração do chat Cadu

## Fase 1 — estabilidade da integração (em validação)

Implementado nesta etapa:
- Autenticação do compositor baseada na sessão, inclusive sem variável `user` no template.
- Bloco de produto restaurado no template dos portais, permitindo renderizar a tela do Workspace.
- Painel fechado respeita `hidden`; página dedicada não cria backdrop.
- Inicialização compartilhada entre tentativas simultâneas, com envio e anexos bloqueados até confirmação de capacidades e modos.
- Teste da rota real do Workspace verifica compositor único, perfil, CSRF e ausência de painel flutuante duplicado.

Verificação: 24 testes Python selecionados e 10 testes Node passaram. A execução ampliada retornou 85 aprovações e 14 falhas em testes herdados da Família, incluindo expectativas de troca de cliente, rotas antigas e painel público. Essa suíte ainda exige reconciliação com os contratos atuais. Navegador e Dify real não foram validados nesta etapa.

## Fase 2 — conversa e contexto

Implementado: paginação de 20 no servidor com próxima página, busca por título, abertura por URL (`?conversation=`), proteção contra respostas atrasadas, rascunhos de texto por conversa e retomada do perfil/projeto/marca vinculados à conversa. O contexto continua sendo revalidado no envio; conversas legadas sem vínculo usam o contexto ativo, com aviso na interface.

Segunda entrega: renomear, arquivar/restaurar e filtro de arquivadas. Mutações verificam ator, cliente, CSRF, permissão e flag de escrita; opções são exibidas conforme capacidade do servidor. Status de escrita seguem o esquema PHP preservado (`ativa`/`arquivada`); leitura também reconhece `active`/`archived`. Mensagens não são apagadas. Rascunhos de texto usam sessionStorage separado por conta e conversa, sobrevivem ao reload na mesma aba e são removidos após aceite do envio; anexos não são persistidos no navegador. Se o armazenamento estiver bloqueado, há fallback em memória.

Verificação: 31 testes Python selecionados passaram, incluindo paginação, filtros, payload inválido, CSRF, flag de escrita, escopo de atualização e conversa inacessível. Sintaxe JS verificada. Ainda pendente: validação no navegador com conta real, confirmação do esquema efetivamente instalado e Dify real. Esta etapa não habilitou flags nem gravou no banco real.

## Fase 3 — execução recuperável

### 3a — contrato de recuperação e idempotência (implementado localmente)

- Hash do conteúdo do envio associado ao UUID; advisory lock transacional serializa tentativas com a mesma chave antes da admissão e da verificação de saldo.
- Retry com chave e conteúdo iguais retorna a execução já existente, sem segunda chamada ao Dify nem segunda gravação de mensagem. Chaves de outro ator/cliente/organização, conteúdo diferente e execuções legadas sem hash são rejeitadas.
- GET `/familia/api/conversations/runs/<uuid>` fornece estado e conversa somente no escopo autorizado; não expõe task_id do Dify, payload, prompt ou hash. Respostas de estado/replay e SSE têm `Cache-Control: no-store`.
- Navegador conserva UUID e assinatura do último envio na sessão da aba. Repetir o mesmo payload após falha reaproveita a chave; replay abre o histórico sem gerar outra resposta. Não há reenvio automático. A assinatura inclui anexos e contexto; anexos não são restaurados após reload.
- Migração necessária ANTES de publicar o código: `migrations/add_cadu_chat_request_hash.sql`, após `add_cadu_family.sql`. Nenhuma migração foi aplicada neste trabalho; flags continuam inalteradas.

Verificação: 47 testes Python selecionados (incluindo 8 novos testes de recuperação) e 10 testes Node de parser/renderização passaram; sintaxe de chat.js validada. Testes usam mocks, não provam concorrência em PostgreSQL real. Pendente validar migração, concorrência real, retry na interface e Dify em ambiente de piloto.

### 3b — execução independente (implementação local, desabilitada)

- Flag `CADU_CHAT_WORKER_ENABLED`, falsa por padrão. No modo antigo, o SSE continua ligado à execução; a desconexão ainda encerra esse gerador. O novo comportamento somente existe com a flag habilitada e um worker em operação.
- Migração aditiva `migrations/add_cadu_chat_jobs.sql`, após as duas migrações anteriores: fila com payload e journal de eventos. Sem exclusão de dados existentes.
- Mensagem, execução e job são gravados na mesma transação. O endpoint retorna HTTP 202 e não chama o Dify. O navegador consulta páginas de até 100 eventos, usando cursor e mantendo o texto incremental. A consulta termina após cinco minutos; esse limite não cancela o trabalho.
- Comando Flask `cadu_family chat-worker-once`: processa no máximo um job, para invocação por supervisor externo. A reserva é persistida antes da chamada ao provedor, com `FOR UPDATE SKIP LOCKED`. O processo não depende da conexão do navegador.
- Eventos ficam disponíveis em GET `/familia/api/conversations/runs/<uuid>/events?after=<cursor>`, com autorização de ator/cliente/organização antes de ler o journal. Entradas desconhecidas não expõem dados.
- Cancelamento de jobs ainda não iniciados é serializado com a reserva. Para jobs em execução, permanece o cancelamento explícito pelo Dify; se o task_id ainda não chegou, o usuário recebe orientação para tentar novamente.
- Jobs já reservados NÃO são redisparados automaticamente após crash. Eventos gravados continuam disponíveis, mas execução presa exige conciliação: isso evita duplicar geração/cobrança quando o resultado externo é incerto. Não há promessa de exactly-once no provedor.

Verificação: 69 testes Python selecionados passaram, incluindo 11 novos testes da fila, worker, cancelamento e endpoints. São testes com mocks, não testes reais de concorrência em PostgreSQL. Sintaxe JS validada. Não foram aplicadas migrações, habilitadas flags nem iniciados workers reais.

Ainda pendente antes do rollout: supervisor e configuração de produção, teste de duas instâncias concorrentes, queda/reinício durante geração, conciliação de tokens/execuções presas, política de retenção dos payloads e eventos e testes reais de navegador/Dify.

### 3c — retomada da interface (implementada localmente)

- A leitura do journal foi extraída para o módulo de transporte e ganhou até três retries de consulta com espera de 1, 2 e 4 segundos, conservando o cursor. Não refaz POST de envio. 401/403/404 interrompem imediatamente; falhas transitórias e 429 têm tentativas limitadas.
- Ao inicializar, reabrir o painel ou receber o evento `online`, o chat consulta o UUID pendente na sessão da aba. Só reconstrói o journal quando o servidor confirma um job durável autorizado; respeita outra conversa escolhida explicitamente na URL.
- No reload, reconstrói a resposta desde o primeiro evento, sem persistir tokens da resposta no navegador. No retry da consulta em andamento, continua do cursor atual e ignora IDs já vistos. Recarrega o histórico canônico ao finalizar; não adiciona novamente a mensagem do usuário na retomada.
- Reconsulta o estado depois de abrir o histórico, cobrindo a corrida com a gravação da resposta final. Anexos e cards anteriores continuam vindo do histórico existente; não há regeneração de arquivos.
- A consulta é cancelável; encerrar acompanhamento não chama o provedor. O botão de interrupção continua sendo ação explícita. O prazo de cinco minutos limita somente o acompanhamento, não o worker. Novas tentativas podem ocorrer ao reabrir o painel/recarregar ou quando a rede voltar.

Limites: depende da flag e infraestrutura de 3b; sessionStorage bloqueado não permite recuperar UUID após reload. Não localiza automaticamente um job iniciado em outra aba/dispositivo e não resolve jobs presos após crash do worker. Testes de transporte cobrem retry, cursor, repetição de IDs, paginação terminal, erros de autorização, abort, payload inválido e prazo; a retomada completa no DOM ainda precisa de validação em navegador.

Verificação desta entrega: 70 testes Python selecionados e 19 testes Node passaram; sintaxe do controlador JS e `git diff --check` sem erros. Não foram aplicadas migrações, ativadas flags ou feitas chamadas reais ao Dify.

## Fase 4 — persistência completa

Versionar mensagens e resultados. Recuperar anexos, fontes, cards e propostas no histórico; preservar compatibilidade com mensagens PHP existentes.

### Transição de criativos e uploads — decisão de produto

- Preservar dados, arquivos e referências existentes. A migração não exige apagar, mover ou reenviar o acervo.
- Criativos e uploads já existentes continuam usando os links antigos, inclusive quando apresentados no novo histórico.
- Até a entrada da nova ferramenta, manter os destinos atuais. Após a mudança, novos arquivos/resultados usam os novos links e o novo local da ferramenta; não reescrever retroativamente URLs antigas.
- Tratar a origem por registro/referência, sem substituição global de domínio ou caminho. Manter autorização de usuário/cliente; um link legado não concede acesso adicional.
- Manter o serviço antigo de arquivos acessível enquanto houver referências dependentes dele. Links assinados expirados precisam de renovação pelo serviço de origem, não de mera troca de domínio.
- Antes da mudança, validar abertura/download de uploads e criativos antigos e novos no histórico, incluindo acesso negado entre clientes. Destinos novos e data de corte ainda precisam ser definidos na implementação.

### 4a — leitura compatível de anexos (implementada localmente)

O histórico agora seleciona `files` após verificar a propriedade da conversa. Uma projeção somente de leitura aceita listas JSON e os campos legados `url`, `file_url`, `remote_url` e `download_url`, devolvendo apenas nome e URL utilizável. O chat apresenta uma ação textual de abrir em nova aba, sem carregar automaticamente imagens externas ou introduzir cards adicionais, seguindo a contenção visual da skill frontend-design.

URLs absolutas HTTP(S) mantêm domínio, caminho e assinatura. Caminhos relativos somente são resolvidos quando `CADU_LEGACY_ASSET_BASE_URL` estiver explicitamente configurado na aplicação com a origem e diretório antigos (incluindo barra final para caminhos relativos ao diretório). Não há origem presumida nem substituição global de URLs. Links com esquemas inseguros, credenciais ou caracteres inválidos não são ativados. Sem URL, o nome permanece visível com indicação de indisponibilidade.

Verificação: 52 testes Python selecionados e 11 testes Node passaram, incluindo autorização antes da leitura, projeção sem escrita, preservação de URLs assinadas, dados malformados e bloqueio de links inseguros. Sintaxe JS validada. Sem acesso ao banco real, downloads reais ou validação visual no navegador nesta entrega.

Pendente: confirmar a origem legada para caminhos relativos; mapear criativos guardados fora de `files` (metadados, ferramentas e marcadores de documentos); validar links reais e a retenção do serviço de origem. O upload Python atual guarda identificador do provedor e nome, não uma URL permanente de download. Não inventamos URLs para esses registros nem renovamos assinaturas expiradas. Novos destinos da ferramenta continuam por definir. Nenhum arquivo ou registro foi movido, apagado ou regravado.

### 4b — resultados legados no histórico

Implementado localmente, somente na leitura:
- Consulta opcional de `tool_calls` via `to_jsonb(m)->'tool_calls'`, compatível também com tabelas sem essa coluna legada.
- Projeção dos resultados de `image_generate` (diretos ou em `data`) em links de criativos; preserva URLs e elimina repetição com anexos da mesma mensagem. Não interpreta URLs dos parâmetros nem executa chamadas antigas. Não devolve prompts e payloads brutos das ferramentas.
- Marcadores `SMART_DOC` válidos de mensagens do assistente são apresentados como título e conteúdo legíveis pelo renderer seguro existente. Não pressupõe que o documento tenha sido salvo como arquivo e não inventa URL de editor. Marcadores inválidos, vazios e incompletos permanecem no texto; dados armazenados não são modificados.
- Outros tipos de ferramenta não foram migrados por inferência. As referências usadas foram `DifyChat.js`, `DifyMarkdown.js` e a migração legada `add_tool_calls_to_messages.sql`.

Verificação: 58 testes Python selecionados passaram, incluindo seis novos testes para os resultados legados. Ainda faltam testes com registros e links reais, documentos em HTML no editor antigo e demais resultados de ferramentas. Nenhuma migração SQL ou escrita de dados é necessária para esta projeção. A fase 3b de execução durável continua pendente.

## Fase 5 — conhecimento

Extração, RAG, fontes do projeto e identidade de marca com autorização e referências verificáveis.

## Fase 6 — ferramentas

Catálogos e Docs, pesquisa e diagnósticos, imagens e variações. Cada recurso precisa de entrada validada, execução, resultado persistido, recuperação e confirmação proporcional ao efeito.

## Fase 7 — paridade e lançamento

Fila, personalização de modos, feedback, ações de mensagem, navegação pela sidebar, revisão visual e testes reais. Registrar aceite por recurso antes de substituir o PHP.

## Escopo vigente

Workspace é dono do serviço. Workspace, Planner, Connect e Skills são superfícies previstas; Studio fornece recursos criativos. As exclusões de Skills em documentos anteriores foram superadas pela decisão posterior do usuário. As fases acima permanecem pendentes até evidência de implementação e validação; não representam recursos já migrados.
