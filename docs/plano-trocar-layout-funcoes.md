# Trocar — plano de layout, funções e otimização

Data: 14/09/2026. Escopo: `/parametros/modelagem-criativos/trocar`.

## Execução — checkpoint de 14/09/2026

Implementado no código local:

- Grid responsivo com elementos à esquerda, canvas central e propriedades/IA em abas; CSS específico do Trocr.
- Formatos reais existentes separados do histórico. Histórico recolhível e parâmetro de formato preservado.
- Lista pesquisável de textos/elementos vinculada aos campos e às regiões disponíveis no canvas; sem porcentagem de confiança inventada.
- Marcação de região por elemento e ajuste numérico X/Y/largura/altura, com validação de limites e coordenadas da imagem original.
- Desfazer/refazer local, atalho de salvar, sugestões de pedido e resumo das operações do plano quando fornecidas pela API.
- Rascunho versionado salvo na sessão, separado dos parâmetros das imagens geradas. Restaura textos, seleções, região, formato, qualidade e opções de prompt.
- Salvamento com estado visível, fila compartilhada e recuperação por download JSON em conflito. Abrir histórico não provoca nova gravação automaticamente.
- Conflito entre abas preserva a edição local; não recarrega silenciosamente sobre ela.
- Geração usa campos e hash após atualizar o plano; bloqueia edição concorrente durante a chamada e mantém a referência base explícita.
- Proteção contra resposta antiga de OCR/preview, IDs de versão sem reutilização após exclusão e canvas respeitando a proporção da imagem carregada.
- Limpeza do estado ao abrir uma marca/sessão vazia; envio de imagem acessível por teclado.

Validação realizada:

- 58 testes passaram: `tests.test_trocr_editor`, `tests.test_creative_format_lab.CreativeFormatLabSwapTest`, `tests.test_trocr_session`, `tests.test_modelagem_criativos.CreativeFilesContractTest`.
- Sintaxe dos dois scripts verificada com `node --check`; `git diff --check` sem erros.
- Navegador em servidor local isolado, usando templates e scripts reais e APIs simuladas: seleção, preço, desfazer/refazer, salvar, recarregar, marcar região, gerar versão com hash atualizado, preservar base e conflito entre duas abas.
- Revisão visual em desktop, 1024 px e 390 px. Corrigidos largura mínima herdada, transbordamento de controles e posicionamento do aviso de erro.
- Não executadas chamadas pagas de OCR/imagem, teste autenticado em produção ou deploy. A simulação valida integração de interface; não mede qualidade da imagem gerada pelo provedor.

Ainda fora deste checkpoint: extração de camadas independentes, edição tipográfica completa, múltiplas regiões simultâneas, jobs duráveis multiformato, pacote de exportação e expansão dos presets IAB. A tira atual escolhe um formato por geração; não promete execução em lote. O fluxo de vídeo existente é preservado.

Os capítulos abaixo permanecem como plano de evolução; esta implementação não representa a conclusão de todas as fases 0–6.

## 1. Conclusão

Evoluir a mesa para um editor centrado na peça: elementos à esquerda, canvas ao centro, propriedades e IA à direita, formatos abaixo. Manter a infraestrutura Flask/Jinja, o histórico e o planejador existentes. Entregar primeiro a reorganização com as capacidades reais; depois edição estruturada e desdobramento em lote.

O mockup representa uma evolução de produto, além de uma troca visual. OCR identifica conteúdo em uma imagem; isso não cria automaticamente textos, pessoas e fundo editáveis como camadas independentes. Essa diferença determina o escopo e a ordem de implementação.

### Evidências e limites

- A URL publicada redirecionou para `/login` no navegador disponível. Não foi possível verificar visualmente a sessão autenticada nem medir desempenho em produção.
- Diagnóstico baseado nos templates, JavaScript, schema e rotas locais, comparados ao mockup anexado. Não há garantia de que o checkout seja idêntico ao deploy.
- Há alterações pré-existentes no workspace, inclusive em templates compartilhados, rotas e vídeo. A entrega desta análise adiciona apenas este documento.
- Textos dentro do mockup, como “Trocar o preço para R$ 99,90”, são exemplos da interface, não pedidos para executar alterações.
- Nenhuma geração foi executada. Metas de desempenho abaixo são propostas, não resultados medidos.

## 2. Frontend atual

| Área | Evidência no código | Consequência para o projeto |
|---|---|---|
| Estrutura | `_mc_trocar.html` inclui etapas, inspetor, canvas, versões e pedido | Reorganizar componentes existentes antes de recriar fluxos |
| Etapas | `_flow_sidebar.html`: upload, OCR, análise, edição, geração e resultado | O mockup adiciona desdobramento; o estado correspondente precisa existir |
| Canvas | `_canvas.html`: imagem, zoom, comparação, seleção de região e download | Já há base para navegação; não há editor geral de objetos neste canvas |
| Propriedades | `_inspector.html`: marca, formato, visualização e campos OCR | Hoje o usuário edita campos da peça, não propriedades de um objeto selecionado |
| Pedido | `_prompt.html` e `_order.html`: instrução, preservar/alterar, conflitos e geração | Reaproveitar no painel IA, mantendo as validações |
| Formatos | Inspetor oferece 16:9, 9:16, 4:5 e 1:1, um por vez | A tira de formatos do mockup exige outro estado e execução em lote |
| Elementos | `SwapElement` contém ID, texto, tipo, bbox opcional e sinal de reconhecimento | Ampliar contrato para estilo, transformação, ordem e vínculo com formato |
| Reconhecimento | `recognition_score` opcional e explicitamente não calibrado | Não apresentar “100% de confiança” como garantia |
| Estado cliente | `mc-trocar.js` tem 2.740 linhas e reúne muitas responsabilidades | Extrair módulos gradualmente, com adaptação do contrato legado |
| Persistência | `schedulePersist` / `persistHistory`, linhas 2495 em diante | Erros que não sejam conflito podem retornar `null` silenciosamente; falta feedback confiável |
| CSS | `modelagem_criativos.css` compartilhado, com mais de 14 mil linhas | Isolar os estilos da nova mesa para reduzir conflitos e custo de manutenção |
| Vídeo | Existem módulos `trocr/animate-*`, rotas de animação e integração com a mesa de vídeo | Avaliar reuso; não deduzir da existência dos arquivos que o fluxo do mockup esteja pronto |

### Preservar

Histórico por marca e sessão; distinção entre versão visualizada e base de edição; original preservada; comparação; seleção manual de região; conflitos do plano; hash do preview; revisão concorrente; CSRF e acesso autenticado a imagens. Debounce e cancelamento de requisições OCR/preview já existem e devem ser mantidos.

## 3. Revisão do mockup

### O que adotar

- Peça como centro da tela, com ferramentas próximas.
- Lista de elementos sincronizada com seleção visual.
- Propriedades contextuais, exibindo somente controles aplicáveis.
- Formatos com miniaturas, dimensões e canal de destino.
- Comandos sugeridos de IA e comparação antes de aplicar.
- Marca, histórico e status de salvamento visíveis.

### O que corrigir

1. **Quatro painéis comprimem a peça.** Usar um painel direito com abas Propriedades, IA e Parâmetros. Painel IA simultâneo somente como opção em telas largas.
2. **OCR e Camadas repetem a mesma estrutura.** Começar com uma lista “Elementos”. Distinguir “Texto identificado”, “Região marcada” e “Camada editável”. Só oferecer ocultar, reordenar e agrupar quando houver camadas reais.
3. **Caixas azuis em todos os elementos geram ruído.** Destacar o selecionado e mostrar os demais ao passar o cursor ou ativar “Mostrar regiões”.
4. **Checkboxes têm significado ambíguo.** Separar seleção, visibilidade e proteção. Usar rótulos e ícones próprios; evitar um checkbox que signifique tanto “editar” quanto “preservar”.
5. **Três ações competem.** Substituir “Gerar versões”, “Aplicar em todos” e “Gerar todos” por uma ação principal contextual: “Gerar prévia” ou “Gerar 4 formatos”.
6. **Imagem estática não precisa de player.** Exibir reprodução e duração apenas ao selecionar vídeo. Transformar em vídeo abre o fluxo específico de cenas.
7. **16:9 e resolução precisam coincidir.** No mockup, a peça visível parece mais alta que o formato anunciado. O viewport deve preservar a proporção real, com espaço livre ao redor, sem esticar a imagem.
8. **9:16 e 1080×1920 podem compartilhar dimensões.** Usar um preset geométrico e perfis de destino separados quando houver diferenças reais de exportação ou área segura.
9. **Corrigir “L” para “Y”.** Posição usa X/Y e tamanho usa largura/altura, com unidades explícitas.
10. **Não prometer fonte detectada.** Exibir fonte sugerida ou escolhida. Identificação de texto não assegura identificação da família tipográfica.

## 4. Layout proposto

```text
┌ Marca / navegação do Studio ──────────────────────────────────┐
│ Ajuste da peça · Nome       Salvo agora  Histórico  Gerar prévia│
├ Upload → Leitura → Revisão → Edição → Formatos → Resultado ───┤
│ Elementos       │ Ferramentas do canvas    │ Propriedades | IA │
│ Busca e filtros │                          │                   │
│ Título          │                          │ Conteúdo          │
│ Apoio           │        PEÇA              │ Estilo disponível │
│ Preço           │                          │ Posição / região  │
│ Logo protegido  │                          │                   │
│ Pessoa          │                          │ Proteção          │
│                 │ Comparar · zoom          │                   │
├─────────────────┴──────────────────────────┴───────────────────┤
│ Formatos · 4 selecionados         Estimativa   Gerar 4 formatos │
│ 16:9       1:1       9:16       4:5       + Adicionar           │
└───────────────────────────────────────────────────────────────┘
```

### Dimensões e comportamento

- A partir de 1440 px: elementos 240 px; centro flexível; inspetor 304 px. Navegação lateral do shell compacta. Painéis redimensionáveis posteriormente.
- De 1100 a 1439 px: elementos 208 px; inspetor 280 px; tira de formatos recolhível. Abrir IA substitui propriedades no mesmo painel.
- De 768 a 1099 px: canvas ocupa a largura; elementos e propriedades abrem em gavetas. Só uma gaveta por vez.
- Abaixo de 768 px: revisar, ajustar texto, solicitar geração e baixar em fluxo vertical. Edição geométrica complexa fica em modo dedicado com canvas ampliado.
- Cabeçalho compacto, barra de ferramentas de 44–48 px e tira de formatos recolhível. Painéis têm rolagem própria; evitar rolagem horizontal da página.
- As etapas representam progresso real. Leitura e análise automáticas podem aparecer como uma fase; geração informa estado assíncrono, sem exigir uma tela vazia exclusiva.

### Direção visual

Paleta proposta, a reconciliar com tokens existentes: superfície `#FFFFFF`, área de trabalho `#F4F6F8`, texto `#182331`, texto secundário `#526174`, borda `#DCE3E8`, ação `#087F79`. Azul de seleção deve ficar reservado às regiões da peça. Validar contraste antes de implementar.

Manter a fonte do shell atual; corpo 14 px, auxiliares 12 px, títulos de painel 14–16 px. Alinhamento à esquerda. Controles discretos, sem sombras em cada bloco. A identidade vem do criativo, e o editor oferece uma moldura neutra.

## 5. Funções e contratos

### A. Elementos e seleção

- Clique na lista seleciona a região correspondente; clique na região seleciona a linha.
- Sem bbox, oferecer “Marcar região”, reaproveitando a ferramenta atual. Nunca inventar uma caixa precisa com base apenas na descrição textual.
- Permitir corrigir a leitura sem gerar imagem. Separar texto original, texto proposto e verificação do usuário.
- Exibir “Revisar leitura” quando faltar evidência suficiente; nunca preencher scores ausentes com 100%.
- Proteção de logo, pessoa e texto legal deve entrar no plano da operação.

### B. Edição e canvas

- Primeira entrega: texto e região com renderização existente; campos de fonte e efeitos aparecem apenas quando suportados de ponta a ponta.
- Edição direta posterior: modelo de cena com objetos, estilos, transformações e assets. Extrair texto de uma imagem exige reconstruir o fundo sob os glifos; adicionar uma caixa HTML por cima não remove o texto original.
- Drag, redimensionamento e campos numéricos usam coordenadas da imagem original, independentes do zoom e do tamanho da tela.
- Undo/redo registra alterações locais; histórico registra versões geradas. Desfazer edição não repete chamadas de IA.
- Prévia local deve ser identificada como prévia quando não reproduzir exatamente o resultado de exportação.
- Comparar original, base e resultado sem trocar silenciosamente a base da próxima edição.

### C. Assistente de mudanças

Fluxo: escrever pedido → obter plano → revisar alterações → gerar prévia → aplicar aos destinos selecionados.

- Sugestões preenchem um pedido editável: atualizar preço, trocar título, adaptar formato, substituir imagem.
- Resumo estruturado: campo, valor anterior, valor novo, elementos preservados, destinos e estimativa.
- Reusar `/swap/prompt`, `plan_hash` e validação de conflitos. Resolver conflitos por ação específica em vez de depender apenas de “Confirmar mesmo assim”.
- “Aplicar em todos” deve indicar o conjunto exato de formatos. Itens sem região ou com incompatibilidade aparecem antes da execução.
- Após mudança em texto, formato ou base, invalidar a prévia anterior.

### D. Formatos

- Cada formato guarda largura, altura, destino, composição, estado e resultado próprios.
- Começar com os quatro formatos atuais. Incluir 300×250 e 728×90 depois de validar renderização e dimensões finais; não apenas acrescentar botões.
- Estados: não gerado, desatualizado, na fila, gerando, pronto e falhou. Uma mudança global marca resultados afetados como desatualizados.
- “Manter composição” preserva relações e prioridades, mas precisa tratar overflow e áreas seguras. Não garantir cópia geométrica idêntica entre proporções incompatíveis.
- Falha de um formato não descarta os demais. Repetir somente itens com falha.
- Histórico e formatos são navegações diferentes: formato seleciona destino; histórico seleciona revisão.

### E. Salvamento e exportação

- Estados explícitos: alterações pendentes, salvando, salvo e falha ao salvar. Botão manual “Salvar” executa a mesma fila do autosave.
- Separar documento de edição e artefatos gerados. Campos ainda não gerados também precisam ser restauráveis.
- Conflito entre abas preserva a edição local e apresenta recuperação; não substituir o trabalho silenciosamente.
- Exportar somente resultados concluídos; pacote de formatos informa itens ausentes. Validar dimensões efetivas e nomes dos arquivos.

## 6. Arquitetura incremental

Manter Flask/Jinja e JavaScript modular. Não há necessidade demonstrada de migrar toda a tela para outro framework.

Proposta de módulos em `static/js/trocr/`: `store`, `api`, `elements-panel`, `canvas`, `inspector`, `change-plan`, `formats`, `history`, `persistence` e `commands`. `mc-trocar.js` vira inicializador gradualmente. Adaptar o padrão de carregamento em `modelagem_desk.html` quando houver imports.

Estado proposto:

```text
document: id, schemaVersion, brandId, runId, revision
source: assetId, width, height, baseVersionId
elements[]: id, kind, textOriginal, text, bbox, style?, transform?, locked
formats[]: id, width, height, destination, overrides, status, resultAssetId
selection: elementIds, formatId
operations[]: elementId, property, from, to, scope
ui: panel, zoom, saveStatus, undoStack, redoStack
```

Esses campos são proposta; não são um contrato já implementado. Estilo e transformação precisam de suporte no backend e no renderizador. Preservar compatibilidade com `SwapElement` e histórico legado por adaptadores versionados.

- Extrair CSS específico para `trocr-editor.css`, mantendo tokens do shell. Remover regras antigas apenas após verificar seus consumidores.
- Avaliar reuso dos módulos de Camadas (`stage`, `transform-controls`, `inspector`, `store`) por interfaces explícitas; evitar acoplar diretamente estados globais de duas mesas.
- Reusar as APIs atuais para edição unitária. Criar persistência de documento e contrato de lote apenas quando os respectivos recursos forem implementados.
- Lotes precisam de identificador idempotente, estado persistido, consulta de progresso e tentativa por formato. Reaproveitar infraestrutura de jobs existente se compatível, após inspeção; não assumir que a rota síncrona de swap já suporta isso.

## 7. Otimização

### Prioridade imediata

1. Propagar falhas de persistência para um estado visível e permitir nova tentativa.
2. Registrar baseline autenticado: tempo de carga, tamanho de JS/CSS/imagens, tempo até editar, latência de OCR/preview/geração e taxa de falha.
3. Preservar cancelamento e debounce existentes; vincular respostas ao documento, à base e à revisão para evitar aplicar resposta antiga ao estado novo.
4. Atualizar somente o painel afetado; usar `requestAnimationFrame` durante arraste e evitar leituras e escritas de layout intercaladas.
5. Carregar miniaturas na tira e imagem completa no canvas; liberar URLs temporárias e reduzir retenção de data URLs.

### Próxima etapa

- Persistência por mudanças e referência de asset, evitando reenviar todo o histórico em cada edição.
- Upload multipart e redução de cópias base64, mantendo validações de arquivo e dimensões.
- Cache de leitura por conteúdo e versão do leitor, respeitando isolamento por usuário/marca.
- Limite de concorrência para formatos; fila e retry idempotentes para evitar cobrança duplicada.
- Carregar código de vídeo e edição avançada quando o recurso for aberto.

### Metas de aceite propostas

- Resposta visual a seleção e digitação em até 100 ms no equipamento de referência.
- Arraste fluido com meta de 60 fps no cenário definido para teste; medir antes de afirmar cumprimento.
- Zero perda de edição nos testes de falha de rede e conflito entre abas.
- Zero chamadas de geração por simples troca de seleção, zoom ou desfazer local.
- Exportação com dimensões exatas do preset e nenhuma distorção de aspecto.

## 8. Plano de entrega

| Fase | Entrega | Dependência | Aceite |
|---|---|---|---|
| 0 — Base | Confirmar deploy, sessão autenticada e baseline; mapear alterações em andamento | Acesso ao ambiente | Capturas e métricas com versão identificada |
| 1 — Estrutura | Novo grid, barra compacta, painel direito com abas, CSS isolado e estado de salvamento | Componentes atuais | Upload, leitura, edição unitária, histórico e download continuam funcionando |
| 2 — Elementos | Lista vinculada ao canvas, seleção, correção de leitura e regiões | Schema e leitura reais | Seleção e bbox corretas com zoom, resize e orientação da imagem |
| 3 — Edição | Propriedades suportadas, undo/redo e documento persistido | Contrato de cena/renderização | Reabrir restaura edições; exportação corresponde aos controles |
| 4 — IA | Plano estruturado, revisão de mudanças e prévia | Operações por elemento | Prévia obsoleta bloqueada; preservar/alterar respeitados |
| 5 — Formatos | Destinos, fila, progresso, retry e exportação em lote | Documento e jobs | Falha parcial recuperável; sem duplicação ao reenviar |
| 6 — Vídeo e qualidade | Integração com cenas, responsividade, acessibilidade e performance | Fluxo de still estabilizado | Imagem sem player; vídeo com duração real; regressões verificadas |

Primeira fatia funcional recomendada: abrir peça → selecionar preço → marcar/corrigir região → editar valor → revisar plano → gerar prévia → comparar → salvar versão. Em seguida, ampliar para demais elementos e formatos.

## 9. Verificação necessária na implementação

- Fluxo principal com OCR completo, parcial, vazio e indisponível.
- Preço com região: pixels fora da área preservados no modo local.
- Seleção com zoom, resize e diferentes proporções.
- Duas abas, conexão perdida, recarga e recuperação de rascunho.
- Formato incompleto, falha parcial de lote e retry sem geração duplicada.
- Documento legado sem bbox, estilo ou formato explícito.
- Teclado, foco visível, retorno de foco ao fechar gavetas e nomes acessíveis.
- Layouts 1440, 1280, 1024 e 390 px, mais tela larga; nomes longos e histórico cheio.
- Revisar os testes existentes de swap/sessão e adicionar regressões relevantes aos novos comportamentos. Nesta entrega documental não foram executados testes de runtime.

## 10. Decisão recomendada

Usar o mockup como direção de organização, com canvas maior e painel direito unificado. Aprovar cada fase pelo fluxo funcional entregue, sem disponibilizar controles que o pipeline ainda não consiga executar. Priorizar persistência confiável e edição por região antes da promessa de camadas completas e geração multiformato.
