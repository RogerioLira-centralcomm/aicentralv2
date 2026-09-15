# Reconstrução chat-v2/Dify em Python

## Escopo e referência atualizados

O detalhamento campo a campo está em [Contratos das Conversas](cadu-conversas-contratos.md)
e a evidência de código em [Inventário estrutural](cadu-conversas-inventario-gerado.md).
Documentos pertencem ao Cadu Media/SmartPlanner com conexão às Conversas; canais
e formatos entram. Cotações, analytics e dados de mídia ficam **fora desta migração
do chat**, mesmo quando aparecem no inventário histórico. Seus dados são preservados.

## Fonte identificada

No PHP, `.htaccess` resolve `/chat-v2` e `/chat-v2/<id>` para
`chat-cadu-dify.php`. O nome informal cadu-dify-v2 corresponde a essa composição,
não a um único arquivo. Referência local: `centralcomm/www/cadu`, somente leitura.

## Matriz de paridade (não considerar entregue por simples cópia)

| Fonte PHP | Responsabilidade | Estado no Python |
| --- | --- | --- |
| `includes/dify/chat-input.php` | Input, anexos, modos, projeto/RAG, web e ferramentas | Painel/composer básico separado; Enter/Shift+Enter e IME implementados; toolbar completa pendente |
| `includes/dify/chat-scripts.php` | Upload, colar/arrastar, fila, inicialização, histórico | Handoff limitado a 30 mensagens, 4.000 chars por mensagem e 24.000 total; upload parcial implementado, fila de envios pendente |
| `DifyStream.js` | SSE, cancelar, eventos e continuidade do thread | Parser JS de fragmentos + projeção Python de text_chunk, respostas finais e progresso; resultados ricos e arquivos pendentes |
| `DifyChat.js` | Orquestração, histórico, projeto, arquivos, persistência | Serviço movido para Workspace; persistência/consumo básicos existentes; RAG/extração/fila pendentes |
| `DifyGuardrails.js` | Data/hora, intenção, texto vs imagem, confirmação, web, contexto | Validações e classificação parcial de intenção; precedência completa ainda não portada |
| `DifyMarkdown.js` | Markdown, tabelas, cards e conteúdo rico | Subconjunto seguro de Markdown implementado; SmartDocs, fontes, imagens e cards pendentes |
| `DifyTools.js` | Dispatch de ferramentas, pesquisa e resultados | Pendente; não executar comandos vindos do navegador sem autorização/validação server-side |
| `DifyUI.js`, `DifyChatUI.js` | Estados, ações de mensagem, feedback e renderização | Painel, foco, histórico e estados básicos; restante pendente |
| `CaduChatSkills.js`, `chat-skills-*.php` | Modos, prompts personalizados e restauração | Leitura dos modos existente; edição/restauração pendentes |
| `chat-projeto-selector.js` | Projeto e base de conhecimento | Contexto autorizado da navbar existente; retrieval de documentos pendente |
| `web-search-toggle.js` | Permissão de pesquisa por intenção | Pendente; ligado não deve significar pesquisar qualquer mensagem |
| `chat-cadu.css`, `dify-chat.css`, `chat-dify-{page,layout,skills}.css`, `chat-model-select.css` | Layout e estados responsivos | CSS do painel separado; não há paridade completa do layout/composer |

## Dependências de backend encontradas

- `/api/dify-proxy.php`, `/api/dify-messages.php`, `/api/chat-messages.php`:
  proxy, continuidade e persistência; substituir pelos serviços Python, sem chave
  Dify no browser.
- `/api/dify-upload.php`, `/api/extract-file-content.php`: ownership, limites,
  validação de MIME/tamanho, extração e retenção de anexos antes de ativar upload.
- `/api/projetos/branding.php`, `/api/projetos/retrieve.php`: identidade visual e
  RAG no contexto autorizado; não confiar no client_id enviado pelo navegador.
- `/api/chat/tools.php`, `/api/chat/deep-search.php`,
  `/api/dify-tool-audiencias.php`: reconstrução de ferramentas, allowlist de
  destinos e defesa SSRF, confirmação/idempotência para mutações.
- `/api/chat-skills.php`, `/api/dify-feedback.php`, `/api/tokens.php`: modos,
  feedback, consumo e conciliação.

## Regras obrigatórias

1. Workspace é dono do serviço; Workspace, SmartPlanner e Connect o consomem.
   Studio e Skills não carregam scripts, CSS ou painel desse agente.
2. PHP permanece referência. Não copiar credenciais, URLs de API ou scripts
   executáveis que continuem dependendo do PHP como substituto de migração.
3. Heurística de intenção não autoriza ação. Confirmações devem representar
   uma ação exata e revalidar permissões no servidor.
4. Preservar histórico, arquivos, perfil e contexto. Fluxo com dados reais/Dify
   ainda precisa de validação antes de liberar as flags de escrita/envio.
5. Reconstruir e testar as capacidades da matriz até a paridade; o painel atual
   não é substituto completo do chat-v2.

## Verificação desta etapa

### Refinamento de composer e anexos

- Composer agrupado, histórico/nova conversa, contexto visível e mensagens com
  autoria. Desktop redimensionável, tablet sobreposto e mobile em tela cheia.
- Seleção local de até três arquivos, remoção, prévia de imagens por object URL,
  colar/arrastar e estados de envio/erro. Envio ocorre somente ao submeter mensagem;
  sem texto, o envio solicita análise dos arquivos anexados.
- Endpoint Python de upload com CSRF, flags fechadas por padrão, permissões,
  limite multipart/arquivo, validação de imagem e texto e referência por usuário
  e cliente. Somente PNG/JPEG/GIF/WebP/PDF/TXT/CSV/MD/JSON nesta etapa.
  PDF passa por verificação de assinatura/terminador, não por antivírus.
- Pré-validação de intenção antes do upload: pedidos de texto e confirmações
  não disparam ferramentas. Comandos explícitos reconhecidos de ferramentas
  ainda não migradas retornam indisponibilidade, preservando texto e anexos.
  Essa classificação é parcial; não substitui permissões ou isolamento das
  ferramentas configuradas no workflow Dify.
- Reabertura mantém a conversa atual. Escape e foco após envio foram corrigidos
  durante verificação visual.
- Revisão em 1440×900, 820×1180 e 390×844; anexo fictício selecionado, bloqueio
  por intenção e resposta SSE simulada. Nenhum upload real ao Dify foi feito.
- 92 execuções Python e cinco testes Node passaram na suíte desta etapa.

Ainda pendentes: Office/SVG, extração/RAG de documentos, regras completas de
data/hora e intenção do PHP, ferramentas e confirmações, cota/rate limit e
conciliação/limpeza de uploads órfãos caso o provedor aceite e o banco falhe,
análise antimalware e teste com Dify real. Não habilitar em produção como paridade
completa antes dessas validações. A matriz acima descreve o estágio inicial;
este adendo registra o avanço parcial dos anexos e guardrails.

105 execuções Python passaram (inclui testes herdados repetidos); cinco testes
Node do parser SSE passaram. Não houve chamada ao Dify nem gravação no banco.
# Correção de escopo: reconstrução, não substituição simplificada

O usuário informa mais de 200 recursos no Conversas legado. Essa quantidade ainda
não foi auditada como funcionalidades independentes; contagem de métodos não é
contagem de recursos. O painel Python permanece um piloto, não possui paridade.

Nesta revisão, `render.js` passa a apresentar um subconjunto seguro de Markdown:
títulos, listas, ênfase, links HTTP(S), citações, código e tabelas com rolagem.
Histórico e respostas finalizadas usam a mesma apresentação; durante streaming
o texto é incremental. HTML do modelo é escapado e blocos de raciocínio são
ocultados. Não é o parser completo de DifyMarkdown: SmartDocs, imagens, badges
de fontes, destaque de sintaxe e resultados de ferramentas ainda não estão portados.
Dez testes Node de renderização e transporte passam; esta alteração ainda não
foi verificada visualmente em navegador nem contra Dify real.

Prioridades para fechar paridade, com referência explícita:

| Frente | Referência PHP | Falta no Python |
|---|---|---|
| Resultados ricos | DifyMarkdown / DifyChatUI | SmartDocs, fontes, feedback, lightbox e cartões |
| Ferramentas | DifyTools | Contratos e execução de image_generate, screenshot_url, link_test, web_scrape, web_search, audience_detail |
| Intenção/contexto | DifyGuardrails | Precedência completa, edição da última imagem, pesquisa contextual, audiência e RAG |
| Streaming | DifyStream / DifyChat | Ciclo completo das ferramentas, estados intermediários e reconciliação |
| Anexos | chat-input / extração PHP | Office, extração, referências persistidas e seleção de recursos |
| Compositor | chat-inline-scripts / CaduChatSkills | Fila editável, atalhos, habilidades personalizadas e contexto de projeto |

Cada frente exige teste funcional e de autorização antes de encaminhar o usuário
do legado. Não habilitar botões sem implementação nem declarar recursos migrados
apenas por haver um controle visual. Studio e Skills continuam sem agente central.
