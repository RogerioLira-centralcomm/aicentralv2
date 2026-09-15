# Conversas: mapa de reconstrução e contratos

## Escopo confirmado pelo usuário

- Conversas é um serviço do Workspace, consumido por Workspace, SmartPlanner e Connect.
- Studio e Skills não exibem o agente central. Serviços criativos podem ser reutilizados sem incorporar o painel a esses produtos.
- Documentos pertencem ao **Cadu Media/SmartPlanner**. Conversas cria propostas e acessa referências autorizadas; não terá um repositório concorrente de documentos.
- Audiências, canais e formatos permanecem no escopo; canais e formatos explicitamente confirmados nesta revisão.
- **Cotações, analytics e dados de mídia estão fora desta migração das Conversas.** Não apagar seus dados nem confundir exclusão do chat com remoção desses produtos.

## Evidência e limites do levantamento

O [inventário gerado](cadu-conversas-inventario-gerado.md) relaciona 60 arquivos,
31.650 linhas, 726 candidatos a funções/métodos e 54 aliases de 18 implementações
de ferramentas. São contagens estruturais, não 726 funcionalidades e não comprovação
de funcionamento dos recursos. Inclui recursos fora do escopo para evitar perda
de referência antes do desligamento do PHP.

O script extrai nomes, linhas e hashes, sem executar PHP, copiar configurações,
exportar corpos de funções, acessar provedores ou consultar o banco. `php_fields`
inclui parâmetros internos e campos de respostas; não deve virar automaticamente
uma lista de parâmetros permitidos ao navegador. Os nomes de tabelas são candidatos
extraídos de SQL, não confirmação do esquema instalado.

## Campos: composição da conversa

| Campo legado | Tipo/finalidade observada | Contrato Python e situação |
|---|---|---|
| query / message | Texto do usuário | `message`: string não vazia, até 20.000 caracteres; implementado |
| conversation_id | Continuidade da conversa | ID local verificado por usuário/cliente; ID Dify resolvido no servidor |
| request_id | Não era o gate uniforme do PHP | UUID de envio para rejeitar repetição; implementado, retomada/reconciliação pendente |
| user | Identidade do provedor | Derivada da sessão; nunca aceitar identidade Dify do navegador |
| profile | Papel do produto | Workspace/Planner/Connect; vinculado à conversa, troca implícita recusada |
| projeto_id | Projeto do Centro de Inteligência | Referência qualificada `ci:`/outros namespaces; autorização no contexto compartilhado |
| brand_ref | Identidade de marca | Referência autorizada; enriquecimento visual completo pendente |
| nome_usuario / nome_cliente | Personalização Dify | Strings derivadas da sessão e cliente autorizado; implementado |
| skill_id / skill_context | Modo e prompt personalizado | Leitura dos modos no servidor; edição/restauração pendente |
| is_first_message / saudacao_permitida | Evitar saudação repetitiva | Implementado parcialmente; legado alinha ambos à abertura pura, Python ainda usa gates diferentes |
| turn_index | Turno da conversa | Derivado das mensagens, não do browser; semântica com resultados de ferramentas requer revisão |
| files_context | Texto extraído dos anexos | Atualmente vazio; falta extração com ownership, limites e armazenamento seguro |
| projeto_context | RAG e identidade visual | Contexto cadastral parcial; retrieval semântico e fontes pendentes |
| response_mode | Modo Dify | Fixado em streaming no servidor |

Fontes principais: `DifyChat.js` L529–702; `DifyStream.js`; `service.prepare`.
Não encaminhar campos arbitrários ao Dify. Conteúdo de arquivos e pesquisa são
dados não confiáveis, nunca instruções de sistema nem autorização de ferramentas.

## Campos: anexos e resultados de imagem

| Campo/ação | Legado | Migração necessária |
|---|---|---|
| file | Multipart binário | Upload Python existe para raster/PDF/texto; Office e análise antimalware pendentes |
| name / type / size | Prévia e indicação do arquivo | Nome sanitizado, MIME verificado, até 3 arquivos de 15 MiB no piloto |
| upload_file_id | Referência Dify | Servidor resolve ID interno por usuário e cliente; não aceitar ID arbitrário do provedor |
| localPath / path | Extração por caminho local | Não aceitar caminhos fornecidos pelo browser; substituir por asset ID autorizado |
| status / progress | Fila de anexos | Selecionado/enviando/erro/pronto parcial; progresso real e retomada pendentes |
| prompt | Pedido de imagem | Extrair contrato de ImageGenerator, sem copiar chave/provedor para JS; executor pendente |
| style | photo/art/digital/sketch/banner etc. | Enum validado a partir das capacidades reais; não apenas inferir por palavra-chave |
| aspect_ratio | Proporção da imagem | Enum do adaptador; preservar no resultado e nas variações |
| quality | fast/balanced/pro | Seleção server-side de modelo, preço e limite; validar disponibilidade antes da migração |
| negative_prompt | Restrições criativas | Texto limitado; regras do provedor não substituem autorização |
| reference_image / reference_images | Referência única ou composição | Asset IDs autorizados, não URL/base64 arbitrária; preservar vínculo com original |
| use_branding_logo | Aplicação da marca | Marca/projeto autorizados; resolver asset no servidor |
| image_url / url | Imagem resultante | Resultado persistido e acessível por permissão; evitar links de provedor expirados |
| count / expectedTotal | Variações e slots pendentes | Estado por variação, sucesso parcial, repetir somente falhas; executor pendente |
| editar / usar referência / baixar | Ações do card | Recriar com identidade do resultado, sem executar HTML salvo no PHP |

Fontes: `chat-input.php`, `DifyChat.js` L595–664 e ações de imagem;
`DifyTools.js` L619 em diante; `ImageGenerator.php` L100 em diante.
Modelos e preços no PHP são referência histórica, não configuração validada atual.

## Contratos de ferramentas no escopo

| Família | Entradas observadas | Resultado/experiência | Destino e gates |
|---|---|---|---|
| audience_search / audience_detail | id, search/q, limit, plataforma_id | Encontrado, audiência, sugestões, lista | SmartPlanner; projeção para cliente, sem campos internos |
| channel_search | search/q, categoria/category, tipo/type, limit | canais, total, query | Serviço de catálogo SmartPlanner; limite e filtros validados |
| channel_detail | id, search/slug | found, canal, sugestões, notícias, plataformas relacionadas | SmartPlanner; não copiar SELECT * do legado |
| format_search | search/q, plataforma/plataforma_slug, tipo/type, limit | formatos, total, plataformas_disponiveis | SmartPlanner; specs públicos explicitamente selecionados |
| format_detail | id, search/nome, plataforma/plataforma_slug | found, formato, formatos relacionados | SmartPlanner; cliente não recebe controles internos |
| doc / doc_save / save_doc | titulo/title, conteudo/content/markdown, tipo/type, formato/format | Documento persistido e referência | **Media/SmartPlanner**; proposta no chat, confirmação antes de salvar |
| briefing / briefing_create | titulo, conteudo, objetivo, budget, canais, tags, responsavel, cliente | Briefing e link | Tratar como documento do Media/SmartPlanner, não nova entidade duplicada no Workspace |
| image_generate e aliases | prompt, style, aspect_ratio, quality, referências | Imagem, variações, custo, estado | Serviço criativo; confirmação/cota/ownership antes de execução |
| screenshot_url | url, device, format, full_page | Desktop/mobile, prévia e download | Adaptador seguro; SSRF, redirecionamentos, timeout e quota |
| link_test | url | Diagnóstico, recomendações, score | Serviço Studio reutilizável pelo chat; sem agente central no Studio |
| creative_analyze | url, context/contexto | Análise e resultado persistido | Serviço Studio; usar asset autorizado quando aplicável |
| web_search | query/q/search, limit, lang, country, tbs, sources | Fontes, trechos e resultados | Pesquisa contextual; toggle não força pesquisa de toda mensagem |
| web_scrape | url, extract_mode, wait_for, only_main_content | Conteúdo, metadados | URL validada, conteúdo não confiável, limites de resposta |
| web_map / web_crawl | url, search, limit, include_subdomains, paths, max_depth | URLs/rastreamento | Descobertos no backend; validar se necessários à experiência antes de ativar |

Aliases devem convergir para uma operação canônica. Registro de ferramenta não
é permissão: não haverá dispatch arbitrário pelo nome enviado pelo cliente ou
pelo modelo. A confirmação futura vinculará usuário, cliente, perfil, operação,
parâmetros normalizados, custo/efeitos, validade e chave idempotente; executar
exatamente a proposta confirmada e revalidar acesso.

## Entrega iniciada: catálogos SmartPlanner

As rotas Python `GET /familia/api/planner/catalog/{canais|formatos|audiencias}`
e `GET /familia/api/planner/catalog/{kind}/{id}` estão disponíveis apenas para
usuários autenticados com cliente autorizado. A busca é limitada a 30 registros,
o identificador é inteiro positivo e as respostas usam projeções pequenas:

- Canais: `id`, nome, descrição, categoria e alcance.
- Formatos: `id`, nome, descrição, dimensões e arquivos aceitos.
- Audiências: `id`, nome, descrição curta e público estimado.

As telas Canais, Formatos e Audiências do SmartPlanner agora têm busca e cartões
responsivos; o botão de detalhe abre modal acessível e obtém o dado pelo contrato
Python. O texto de catálogo é sempre inserido como texto, não HTML. Esta é a base
que Conversas usa para cartões de resultados: no perfil SmartPlanner, os aliases
permitidos de busca/detalhe de canal, formato e audiência são projetados em cartões
somente de leitura durante o streaming. O adaptador ignora qualquer outro nome de
ferramenta, input malformado e falha de catálogo; não transmite `tool_input`,
observações, SQL, URLs ou raciocínio ao browser. Nenhum fluxo mutável foi habilitado.

## Entrega iniciada: Docs do Cadu Media/SmartPlanner

Docs agora tem leitura no SmartPlanner por meio de `GET /familia/api/planner/documents`
e `GET /familia/api/planner/documents/{id}`. As duas rotas derivam cliente e ator
da sessão, aplicam a regra de proprietário ou documento compartilhado e não aceitam
`client_id` do navegador. A prévia devolve uma projeção de metadados e texto limitado
a 20.000 caracteres; o HTML persistido não é enviado nem inserido na página.

A tela mostra documentos existentes e abre prévia responsiva em modal. Criação,
edição, duplicação, publicação, compartilhamento e exportação permanecem fora desta
entrega: exigirão uma prévia de alteração/efeito, confirmação explícita, chave
idempotente e nova verificação de proprietário no servidor. Conversas ainda não
cria ou modifica Docs; a próxima integração será uma referência de documento
autorizada no contexto do agente, sem tratar o conteúdo como instrução confiável.

## Eventos Dify: diferenças e reconstrução desta revisão

| Evento | Python nesta revisão | Limite/decisão |
|---|---|---|
| message / agent_message | Delta de texto, persistência da resposta | Não deduplicar texto legitimamente repetido por heurística |
| text_chunk | Agora suporta `data.text` | Testado com adaptador simulado |
| message_replace | Substitui resposta, inclusive limpeza | Mesma resposta usada para persistência |
| message_end | Agora recupera `answer`, mesmo sem chunks | Confirma término e captura usage |
| workflow_started | Progresso público fixo | Sem nomes internos de workflow |
| node_started / node_finished | Progresso sem duplicação consecutiva | Sem inputs, outputs, títulos ou IDs internos |
| workflow_finished | Recupera `outputs.answer`; falhas não viram sucesso | Aguarda `message_end` no contrato chat; não implementa `/workflows/run` |
| thinking / message_thinking / agent_thought | Apenas estado genérico | Não copiar fallback legado que promovia thought à resposta |
| tool_call | Apenas indicação de processamento | Não executa ferramenta nem expõe parâmetros/observação; cards pendentes |
| message_file | Ainda não exposto | Precisa asset autorizado; não publicar URL bruta de provedor |
| error | Erro genérico e resposta parcial preservada | Nunca expor erro interno/segredos do provedor |
| ping / desconhecido | Ignorado | Não tratar como conclusão |

O frontend consome `progress`; renderização Markdown é parcial. Esta etapa não
reconstrói resultados de ferramentas, SmartDocs, lightbox ou feedback. Eventos
de raciocínio não são conteúdo do cliente e ficam fora das mensagens salvas.

## Comportamentos de interface ainda a recuperar

| Grupo | Critério verificável |
|---|---|
| Compositor | Atalhos, modos, projeto/RAG, pesquisa e ferramentas sem perder rascunho |
| Fila | Editar/remover envios pendentes, não duplicar execução após reconexão |
| Anexos | Colar, arrastar, cancelar, remover, retry e preservar referências no histórico |
| Mensagens | Streaming, fontes web/projeto, copiar, feedback, erro parcial e recuperação |
| Imagens | Geração, edição, múltiplas referências, carrossel, retry parcial e download |
| Documentos | Prévia no chat, salvar confirmado no Media/SmartPlanner, abrir versão autorizada |
| Catálogos | Busca e detalhe de audiência/canal/formato, escolhas explícitas e retorno ao plano |
| Acessibilidade | Foco/Escape, teclado, status anunciados, nomes longos e falhas de rede |
| Responsividade | Desktop redimensionável, tablet sobreposto, mobile tela cheia |

## Ordem de entrega revisada

1. Contratos/eventos e regressões de transporte (avanço nesta revisão).
2. Ferramentas de catálogo: canais, formatos e audiências, com cartões e autorização.
3. Integração de Docs com Media/SmartPlanner: referência, prévia e confirmação.
4. Anexos avançados, extração, RAG e identidade visual.
5. Imagem/edição e demais ferramentas no escopo, com limites, confirmação e resultados persistidos.
6. Fila, feedback, recuperação, paridade responsiva e validação com contas piloto.

Não incluir cotações, analytics ou dados de mídia nestas fases. Nenhuma flag de
produção foi habilitada. Não houve consulta/gravação no banco ou chamada real
ao Dify nesta revisão. O desligamento do PHP depende de aceite por capacidade,
não de contagem de arquivos portados.
