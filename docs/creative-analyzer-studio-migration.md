# Creative Analyzer no Studio — mapa e execução em fases

Estado em 16/09/2026: Fases 0 e 1 concluídas; pipeline de imagem da Fase 2 implementado, com smoke test externo pendente de uma mídia autorizada. Nenhuma análise, mídia ou URL legada foi apagada ou substituída.

## Resultado esperado

O Creative Analyzer será uma ferramenta nativa do Studio, implementada em Python/Flask e integrada ao contexto de marca, projetos e biblioteca do Workspace. O novo módulo não carregará PHP, CSS, JavaScript, uploads ou serviços do CentralX em tempo de execução.

A migração é aditiva:

- análises, criativos e uploads existentes permanecem onde estão;
- links públicos antigos continuam abrindo o relatório antigo;
- o histórico do Studio agrega registros antigos em modo somente leitura;
- análises novas usam processamento, armazenamento e URLs novos do Studio;
- nenhum dado legado será removido antes de paridade funcional, observabilidade e período de convivência.

## Fonte legada confirmada

A implementação completa foi localizada em `/Users/apololira/PhpstormProjects/centralcomm/www/cadu`.

### Superfícies

- `creative-analyzer.php`: aplicação autenticada e histórico.
- `creative-analyzer-new.php`: variação da aplicação autenticada.
- `creative-analyzer-historico.php`: histórico de análises.
- `creative-analyzer-publico.php`: relatório público sem autenticação.
- `assets/js/creative-analyzer/`: upload, análise, extração de frames, atenção, heatmap, performance, compartilhamento e estados.

### Backend canônico atual

O fluxo efetivamente chamado pelo frontend é `POST /api/analise-criativo-async.php`, dividido em três requisições:

1. `step=upload`: valida e armazena a mídia, recebe os frames do navegador e cria uma sessão temporária.
2. `step=extract`: envia imagem ou frames para visão computacional/LLM e persiste `extracted.json` temporário.
3. `step=analyze`: produz o laudo, enriquece o resultado, grava no banco e retorna `analysis_id` e `analysis_uuid`.

O código contém processadores alternativos (`analysis-processor.php`, `analysis-processor-staged.php`, `analysis-processor-unified.php` e `analysis-processor-v4.php`), mas eles não são o contrato do frontend atual. A migração usará o comportamento do endpoint assíncrono como referência e não copiará implementações concorrentes.

## Contrato funcional levantado

### Entradas

- arquivo de imagem ou vídeo;
- contexto opcional da campanha;
- usuário e cliente autenticados;
- no Studio: marca e projeto ativos serão referências explícitas, não inferidas do navegador.

### Imagem

A implementação atual envia uma imagem ao estágio de extração. O novo pipeline preservará OCR, textos, headline, CTA, logo, pessoa, produto, preço/oferta, paleta, tipografia, qualidade técnica, composição e coordenadas normalizadas de 0 a 100.

### Vídeo

O PHP depende de extração no navegador e aceita quantidade variável:

- menos de 2 s: 1 frame;
- de 2 a 5 s: 3 frames;
- de 5 a 15 s: 4 frames;
- acima de 15 s: 5 frames.

O novo contrato do Studio será determinístico e analisará **quatro frames representativos**: abertura/hook, desenvolvimento inicial, desenvolvimento final e encerramento/CTA. Para vídeos curtos, os tempos serão distribuídos dentro da duração e quadros repetidos serão evitados quando tecnicamente possível. A extração será responsabilidade do backend do Studio com FFmpeg; o navegador poderá mostrar prévias, mas não será a única forma de processar o vídeo.

Além dos quatro frames, o novo pipeline preservará duração, dimensões, proporção, presença de áudio, ritmo, transições, narrativa, força do hook, retenção prevista, clareza narrativa, momento do CTA e pacing. A análise não afirmará música ou narração apenas por inferência visual quando o áudio puder ser inspecionado.

### Saída canônica

O JSON legado é a referência de compatibilidade. O modelo novo terá versão explícita e normalizará:

- `classificacao`: tipo, formato, funil, vertical e complexidade;
- `score`: geral, clareza, impacto visual, adequação digital, originalidade e explicações;
- `video_metrics`: hook, retenção, narrativa, CTA e pacing quando aplicável;
- `elementos_visuais`: cores, textos, headline, logo, CTA, faces, produto, oferta, tipografia e composição;
- `attention_analysis`: atenção, hook, scroll stop, tempo, carga cognitiva, hierarquia, fixação, sequência, curva e zonas;
- `branding_analysis`: saliência, recall, visibilidade e tempo até a marca;
- `publico_alvo`: faixa etária, gênero, classe, momento, interesses, comportamentos e segmentos;
- `tom_mensagem`: tipo, sentimento e proposta de valor;
- `adequacao_canais`: Instagram, Stories/Reels, TikTok, Facebook, LinkedIn, display e demais formatos aplicáveis;
- `performance_prediction`: melhor canal e fatores positivos/negativos;
- `recomendacoes`, `alertas` e `compliance`;
- `technical`: arquivo, dimensões, duração, frames, modelo, tokens, tempos, versão e falhas parciais.

Campos calculados e campos observados serão identificáveis. O backend validará e normalizará a resposta da IA antes da persistência; a tela não dependerá diretamente de JSON instável do provedor.

## Persistência e compatibilidade

### Legado preservado

A fonte atual é `public.cadu_analises_criativos`. Ela contém `id`, `uuid`, usuário, cliente, metadados do arquivo, `thumbnail_base64`, `imagem_path`, scores, métricas de atenção e `analise_completa` em JSONB. A URL autenticada prefere `/creative-analyzer/{uuid}` e possui fallback por ID. O relatório público aceita `/laudo/{uuid}`, `/creative-analyzer-public/{uuid}`, `/creative-analyzer-publico/{uuid}` e URLs antigas por query string.

O Studio não reescreverá esses endereços. Cada item agregado terá `source=legacy`, `source_id`, `source_uuid`, `legacy_result_url` e, quando existente, `legacy_public_url`. A abertura de um item legado redirecionará para o endereço original. O novo domínio não tentará servir caminhos relativos antigos de upload.

### Dados novos

Serão criadas tabelas próprias e aditivas, com nomes finais definidos na Fase 1:

- análise e seu estado (`queued`, `processing`, `complete`, `partial`, `failed`);
- ativos de entrada, thumbnail e quatro frames;
- execuções/etapas, tempos, provedor, modelo, tokens e erro sanitizado;
- compartilhamento público revogável com token próprio;
- vínculo com usuário, cliente, marca e projeto;
- versão do schema do resultado e JSON normalizado.

Os arquivos novos usarão o armazenamento do Workspace/Studio. A tabela legada não receberá novas gravações do módulo migrado.

### Histórico unificado

O repositório exporá uma coleção única ordenada por data:

- `legacy`: leitura de `cadu_analises_criativos`, sem mutação;
- `studio`: leitura e escrita nas tabelas novas;
- filtros por imagem/vídeo, projeto, marca, autor, status e período;
- paginação no servidor e busca por nome/contexto;
- miniatura com fallback explícito, sem esconder uma análise por erro de mídia.

## Experiência de produto

O Creative Analyzer será item do menu principal do Studio e seguirá o shell escuro independente. Não terá breadcrumb redundante nem herança visual/JavaScript do CentralX.

A ferramenta terá:

1. entrada visual com dropzone para imagem/vídeo, seleção de projeto e contexto de campanha;
2. progresso real por etapas, incluindo extração dos quatro frames;
3. histórico visual agrupável por projeto, com imagem e vídeo identificados;
4. relatório completo dividido em quatro áreas navegáveis:
   - Visão geral: score, diagnóstico, classificação e prioridades;
   - Atenção e visual: heatmap, sequência do olhar, branding e elementos;
   - Mensagem e público: textos, tom, proposta, audiência e compliance;
   - Canais e ação: adequação, performance prevista, recomendações e exportação;
5. página pública nova e responsiva para análises novas;
6. ações para abrir a peça na Biblioteca e encaminhá-la aos editores do Studio.

Scores preditivos serão apresentados como estimativas, com metodologia e limitações visíveis; não como métricas observadas de campanha.

## Execução em fases

### Fase 0 — inventário, contratos e proteção do legado — concluída

- fonte PHP, frontend, SQL, email e relatório público localizados;
- endpoint efetivo e fluxo em três etapas identificados;
- contrato de imagem, vídeo e resultado registrado;
- estratégia aditiva definida: preservar dados/uploads/links antigos;
- dependências reaproveitáveis do Python identificadas: análise de marca, Camadas/OCR, mídia/FFmpeg, armazenamento, projetos e infraestrutura pública.

Critério de saída: este documento versionado, sem alterações destrutivas.

### Fase 1 — fundação nativa e histórico compatível

- criar pacote isolado `aicentralv2/creative_analyzer/` com domínio, repositórios, serviços e rotas;
- criar migrations somente aditivas;
- implementar adaptador somente leitura da tabela legada;
- criar histórico unificado autenticado e paginado;
- registrar rotas curtas: `/studio/analyzer`, `/studio/analyzer/<uuid>` e APIs sob `/studio/api/analyzer`;
- aplicar autorização por usuário/cliente/marca/projeto, CSRF e limites de upload;
- adicionar testes de isolamento e compatibilidade do legado.

Critério de saída: usuário vê análises antigas no Studio e abre o link antigo correto; ainda não há processamento novo exposto.

Execução: concluída. A rota `/analyzer`, o item de navegação, o histórico unificado e a migration aditiva foram entregues. O banco real confirmou 59 análises legadas da marca 174, cinco delas em vídeo, todas com UUID e prévia. A primeira página do adaptador foi validada em leitura com 24 itens e URLs antigas preservadas.

### Fase 2 — pipeline de imagem

- upload e persistência no armazenamento do Studio;
- validação por conteúdo, hash, dimensões, tamanho e formato;
- OCR/extração visual reutilizando Camadas onde houver contrato estável;
- análise normalizada, validação de schema e enriquecimento determinístico;
- jobs, idempotência, retry seguro e estados parciais;
- relatório privado com as quatro áreas;
- testes com fixtures reais e falhas simuladas.

Critério de saída: imagem atravessa upload, processamento, banco e relatório sem PHP/CentralX.

Execução: backend e frontend implementados. O upload valida os pixels, limita tamanho e dimensões, grava fonte/thumbnail no storage privado do Studio, executa extração e diagnóstico em duas passagens, normaliza o resultado e registra execução/erros. A tela possui envio com CSRF e um relatório privado inicial nas quatro áreas. Testes locais cobrem storage, normalização, serviço, autenticação e CSRF. O smoke test com provedor externo não foi executado porque exigiria enviar uma mídia local sem autorização específica; ele permanece como critério antes de considerar a fase integralmente validada em produção.

### Fase 3 — pipeline de vídeo com quatro frames

- ingestão de MP4, MOV e WebM dentro dos limites publicados;
- normalização e inspeção via FFmpeg/ffprobe no backend;
- extração determinística dos quatro frames e thumbnail;
- inspeção de áudio e narrativa sem depender do canvas do navegador;
- análise conjunta dos frames e métricas específicas de vídeo;
- recuperação de falha por etapa e testes para vídeos curtos, longos, sem áudio e corrompidos.

Critério de saída: vídeo processa quatro momentos verificáveis e gera laudo completo mesmo quando a extração client-side não existe.

### Fase 4 — relatório interativo e integração com a Biblioteca

- visual arrojado do Studio com mídia em movimento e transições funcionais, respeitando redução de movimento;
- heatmap e sequência de atenção sobre a mídia correta;
- comparação entre frames do vídeo;
- histórico agrupado por projeto;
- envio do ativo aos editores de imagem/vídeo e retorno à Biblioteca;
- responsividade, teclado, estados vazio/loading/erro e acessibilidade.

Critério de saída: experiência completa em desktop e mobile, sem folhas ou scripts do CentralX.

### Fase 5 — compartilhamento público novo

- token público não enumerável, revogação e expiração opcional;
- página pública independente, metadados sociais e URLs canônicas;
- análises novas usam apenas os links novos;
- links antigos continuam intactos e identificados no histórico;
- proteção contra indexação ou exposição quando o compartilhamento não estiver ativo.

Critério de saída: novo link público abre sem sessão; revogação bloqueia o acesso; legado continua abrindo no endereço original.

### Fase 6 — paridade, rollout e observabilidade

- matriz de paridade entre PHP e Studio com amostra de imagens e vídeos;
- comparação de campos, tempos, erros, consumo e qualidade do laudo;
- testes ponta a ponta de frontend, API, banco, storage e link público;
- flag de ativação e liberação gradual;
- telemetria por etapa e painel de falhas, sem registrar mídia ou prompts sensíveis em logs;
- retirada futura do processamento PHP somente após decisão explícita; dados e links legados não são parte dessa retirada.

Critério de saída: Studio assume novas análises com rollback simples e sem perda do acervo anterior.

## Decisões de implementação

- Não portar templates PHP nem copiar JavaScript legado para dentro do Studio.
- Não acoplar o novo módulo ao pacote grande dos editores; compartilhar serviços por contratos pequenos.
- Não usar `thumbnail_base64` como armazenamento principal novo; guardar ativos no storage e metadados no banco.
- Não confiar em MIME, IDs de cliente, marca ou projeto enviados pelo navegador sem validação no servidor.
- Não usar o UUID público como autorização para páginas privadas.
- Não ocultar resultado parcial: registrar etapa, erro e o que foi concluído.
- Não apagar registros, uploads ou tokens legados durante esta execução.

## Riscos conhecidos

- URLs de uploads legados são relativas ao host antigo; o histórico deve redirecionar, não remontá-las no novo domínio.
- o JSON histórico possui versões e formatos diferentes; o adaptador precisa tolerar `score`/`scores`, campos ausentes e estruturas antigas;
- o PHP atual usa inferências de áudio a partir de frames; o Studio deve separar observação técnica de inferência da IA;
- o frontend atual varia de um a cinco frames; o novo contrato de quatro frames exige fixtures e regra documentada para vídeos muito curtos;
- métricas de atenção e performance são preditivas e precisam de rótulo claro;
- envio de email é efeito colateral do salvamento atual e não será copiado para a primeira versão sem contrato próprio.

## Evidências e validação da Fase 0

- `assets/js/creative-analyzer/analysis.js` confirma o endpoint assíncrono em três etapas.
- `assets/js/creative-analyzer/video-frames.js` confirma a extração variável de 1 a 5 frames no navegador.
- `api/analise-criativo-async.php` confirma múltiplos frames, persistência, UUID e resposta final.
- `api/creative-analyzer/database.php` confirma os campos materializados e `analise_completa`.
- `database/sql/criar_tabela_analises_criativos.sql` e alterações v2/v3 confirmam o histórico e métricas.
- `includes/creative-analyzer-helpers.php` confirma a resolução autenticada por UUID/ID.
- `creative-analyzer-publico.php` confirma os formatos de links públicos antigos.
