# Smart Planner — plano de execução v3

Status: especificação para implementação. Esta revisão altera somente o planejamento, não a aplicação.

## 1. Escopo fechado

Dois documentos distintos, com editores, versões, publicação e PDF próprios:

- **One page / proposta comercial:** plano base que chama atenção de agência e anunciante, demonstra a ideia e defende por que aprovar o projeto e seu investimento.
- **Planejamento completo:** aprofundamento de uma versão identificada do one page. Acrescenta evidências, indicadores, mídia, linha criativa, quantidades e orientações de execução sem reconstruir a proposta.

Nesta fase o Smart Planner gera **somente imagens como mídia**. Continua gerando textos, dados estruturados, gráficos e documentos. Não gera vídeo, áudio, animação ou frames em lote; não chama motores de vídeo. A conexão com o gerador de vídeos do Cadu Media Studio é uma fase futura.

Um canal pode recomendar um formato de vídeo. Nesse caso, o documento apresenta orientação textual e uma imagem conceitual identificada como referência visual; não promete vídeo produzido. Recomendar formato de vídeo não autoriza gerar vídeo.

Regras transversais:

1. Um formato principal por canal, persistido e validado contra o catálogo.
2. Quantidade de criativos planejados é distinta de quantidade de imagens geradas para apresentar a proposta.
3. One page pelo menos 30% menor em palavras que a versão atual da mesma campanha, somando todas as abas e notas.
4. Defesa comercial e imagem principal sempre na primeira aba.
5. Números vêm dos dados e cálculos; o modelo explica e recomenda, não inventa indicadores.
6. Modelo de texto da família GPT-5 via API direta OpenAI; modelo de imagem próprio pela API direta. Sem fallback silencioso de provedor.
7. Acesso público, navegação, download e impressão não geram conteúdo nem custo de IA.

## 2. Base atual e limites da revisão

Arquivos revisados: `smart_planner/generator.py`, `images.py`, `models.py`, `ai.py`, `cost.py`, `one_page.py`, `public_view.py`, `repository.py`, `routes.py`, prompts internos, templates `index.html` e `public.html` e JS do histórico/publicação.

- A geração completa já recebe o one page; preservar essa derivação.
- O editor já diferencia folha e completo; preservar caminhos separados.
- A publicação pública hoje pode misturar as duas visualizações no mesmo token; separar novas publicações sem quebrar os links existentes.
- O histórico possui nove colunas e até três ações por item. A busca atual filtra linhas carregadas; a consulta usa limite sem navegação paginada equivalente na tela.
- O gerador de arte existente gera fundo e criativo. Priorizar o criativo nesta fase; fundo exclusivo passa a ser opcional e não pode consumir orçamento automaticamente.
- O custo atual procura valores monetários em usage; a resposta direta precisa ser precificada por tokens/modelo para evitar despesas não registradas.

Esta revisão não mediu uma amostra autenticada de campanhas públicas nem consumo real. Tamanhos e orçamentos serão calibrados na etapa de baseline.

## 3. Telas internas

| Tela | Conteúdo e ação principal | Estados essenciais |
|---|---|---|
| Histórico | Abas Propostas comerciais / Planos completos; busca; lista compacta; Nova proposta | Carregando, vazio inicial, nenhum resultado, erro com recuperação |
| Briefing e fontes | Entradas por abas; fontes e extração; Revisar briefing | Fonte processando, falha individual, conteúdo extraído, conflito |
| Revisão do briefing | Objetivo, público, praça, verba, período, restrições e origem de cada campo; Configurar mix | Confirmado, ausente, divergente; bloqueio apenas do cálculo dependente |
| Mix e formatos | Canal, percentual, valor e um formato; resumo gráfico; Gerar proposta | Totais inválidos, formato incompatível, dados insuficientes |
| Editor da proposta | Tese, defesa, mix e criativo; ajuste por bloco; Publicar proposta | Rascunho, geração parcial, revisão, publicado, alterado após publicação |
| Detalhe da proposta | Versão enviada e situação comercial; Gerar plano completo | Não enviada, enviada, em ajuste, aprovada; aprovação registrada por responsável |
| Editor do completo | Derivação visível; áreas Estratégia / Mídia / Indicadores / Criação / Execução; Publicar completo | Base válida, base alterada, blocos desatualizados, revisão, publicado |
| Revisão de imagens | Prévia ampliada, origem, canal/formato e versão; Usar imagem ou Gerar nova versão | Em geração, disponível, falhou, antiga preservada |

A revisão de imagens e os detalhes de fontes podem ser painéis, não novas páginas obrigatórias. Uma ação principal por contexto. Custos ficam no fluxo interno de geração, nunca na página do cliente.

## 4. One page público

Documento independente, sem alternador para um completo que o comercial não enviou.

### Aba Proposta

- Cliente/agência e título comercial específico.
- Oportunidade em até duas frases.
- Tese e recomendação do projeto.
- Uma imagem conceitual aplicada ao canal de maior peso, com legenda de referência.
- Investimento, período e mix compacto.
- Até três argumentos de aprovação: adequação ao negócio, defesa do mix e benefício fundamentado.
- Próximo passo comercial e pendências que possam mudar a decisão.

### Aba Mix e investimento

Um gráfico e resumo dos canais: peso, valor, papel e formato principal. Não repetir o investimento em vários cards nem reproduzir matriz mensal detalhada.

### Aba Referências

Fontes, premissas e imagem ampliada. Referências devem estar acessíveis junto das afirmações também. Não esconder defesa comercial nesta aba.

Orçamento editorial inicial: até 500 palavras em todas as abas, sujeito à comparação de campanhas. O corte é feito por síntese, nunca por truncamento de ressalvas ou redução da fonte. Remover catálogo genérico de portais, Gantt detalhado, objeções extensas e repetição de formatos.

PDF: folha executiva própria; não imprimir a árvore inteira de abas. Página web mobile pode rolar; uma página no PDF não significa comprimir o conteúdo em um viewport móvel.

## 5. Planejamento completo público

Link, identidade de documento, versão e exportação próprios. Exibir a proposta/versão de origem; não expor automaticamente outro documento por vínculo interno.

| Área | Conteúdo obrigatório | Forma visual |
|---|---|---|
| Estratégia | Tese herdada, oportunidade, evidências, público e defesa aprofundada | Síntese e matriz público/mensagem |
| Mídia | Um formato por canal, função, investimento, compra e ritmo | Mix, matriz financeira e cronograma com dados válidos |
| Indicadores | KPI por objetivo/canal, estimativa ou meta identificada, método, fonte e acompanhamento | Quadro de indicadores e cenários calculados |
| Criação | Linha criativa e quantidade de peças por canal; orientação de mensagem, visual, CTA e restrições | Fichas por canal, imagem principal reaproveitada e imagens adicionais opcionais |
| Execução | Entregas, dependências, responsabilidades a definir, medição, otimização e próximos passos | Tabela de entregáveis e sequência de execução |

Os dados podem ser mais profundos sem criar 25 abas. Detalhes adicionais ficam dentro de cada área. Priorizar tabelas e gráficos úteis sobre prosa repetida; não acrescentar componentes vazios para preencher o layout.

## 6. Contrato de criação por canal

Cada canal deve conter:

- `channel_id`, papel e público prioritário.
- `primary_format_id`, nome, proporção/dimensões e duração quando aplicável.
- Justificativa do formato e referência de catálogo.
- `creative_direction`: conceito, mensagem, argumento, tom, direção visual, CTA, obrigatórios e restrições.
- `deliverables`: conceitos, variações, arquivos finais, distribuição por fase e justificativa da quantidade.
- `quantity_status`: recomendada, revisada ou confirmada; não rotular recomendação como contratação.
- Imagens conceituais associadas, sem confundir prévias com arquivos finais da campanha.

Um formato por canal admite várias mensagens/peças dentro do mesmo formato. Dois formatos no mesmo canal geram erro de validação, não uma adaptação automática. Se um ponto/catálogo não suporta o formato escolhido, sinalizar incompatibilidade para revisão.

Quantidades dependem de duração, investimento, público, renovação e capacidade de produção. Sem dados suficientes, marcar recomendação provisória e explicar a premissa. Não usar uma quantidade fixa para todos os canais. Revisões não contam como novas peças.

Exemplo ilustrativo: 4 peças planejadas de vídeo vertical continuam sendo 4 entregáveis de vídeo recomendados; o Smart Planner pode apresentar 1 imagem conceitual e nenhuma peça de vídeo produzida.

## 7. Política de imagens desta fase

- One page: uma imagem principal, gerada ou reutilizada quando correspondente à mesma versão/material.
- Completo: reutilizar a imagem do one page; imagens extras por canal somente por solicitação, com previsão de custo.
- Alteração textual não regenera imagens automaticamente.
- Uma nova versão não substitui a imagem aprovada até ser selecionada.
- Guardar imagem e prompt com canal, formato, versão de origem e custo.
- Preferir composição determinística para textos, marcas e números que exigem exatidão.
- Falha de geração mantém o documento textual e um estado claro no editor; publicação pode usar referência válida já existente, sem prometer que uma imagem foi produzida.
- Não exibir botões Gerar vídeo, timeline, cenas animadas ou players artificiais.
- Fundo decorativo não é obrigatório nem uma segunda geração padrão.

## 8. Dados e versões

Introduzir entidades ou estrutura equivalente:

- Projeto: vínculo organizacional, cliente e agência.
- Documento: tipo `proposal` ou `full_plan`, identificador e versões.
- Origem do completo: `source_proposal_id`, `source_proposal_version`, hash do snapshot.
- Aprovação comercial: situação, data e autor do registro; não inferida da geração/publicação.
- Versão publicada: conteúdo congelado, data e token público próprio.
- Canais/formatos/entregáveis: dados estruturados, compartilhados por derivação explícita.
- Ativo visual: `media_type=image`, finalidade `concept_reference`, canal, formato, prompt, URL, origem, versão e custo.
- Geração: etapa, modelo efetivo, tokens, custo estimado/apurado, erro e chave de deduplicação.

A publicação anterior continua visível enquanto o rascunho é alterado. Mudança na proposta não atualiza silenciosamente o completo: marcar base alterada e permitir gerar nova versão derivada. Nunca apagar o completo anterior.

Migração: preservar sessões e tokens atuais; adicionar mapeamento compatível para documentos existentes. Links antigos mantêm comportamento compatível, com destino explícito onde houver identificação confiável. Testar casos antigos com apenas folha, apenas completo e ambos. Não registrar aprovações retroativas.

## 9. Histórico leve

- Duas abas: Propostas comerciais e Planos completos.
- Cada linha: miniatura/logo leve, título, cliente/agência secundários, estado e atualização.
- Ação principal Abrir/Continuar; demais ações no menu de opções.
- Verba, período, canais, custos e versões no detalhe, não em colunas fixas.
- Busca/paginação no servidor, com escopo do usuário preservado. Página inicial de 20 registros como hipótese a medir.
- Filtros de cliente, agência e situação em painel; ordenação por atualização.
- No completo, referência discreta à proposta de origem.
- Custo de IA separado da verba de mídia; não colocar custo acumulado no título da listagem.
- Arquivar como ação reversível; excluir com confirmação e análise dos vínculos entre documentos.
- Não converter a tabela atual em cards gigantes com as mesmas informações.

## 10. Geração e custo

Família GPT-5 pela API direta OpenAI:

- Nano/mini: organização de fontes, síntese de material e extração.
- GPT-5.4: núcleo e defesa comercial, com contexto enxuto e saída limitada.
- Mini: aprofundamentos estruturados do completo e revisão editorial localizada.
- GPT-5.4: escalonamento de inconsistência estratégica quando necessário.
- Código: cálculos, schema, formato único, totais de entregáveis, composição, gráficos e exportação.
- Modelo de imagem configurado: apenas imagens; orçamento independente de texto.

Usar saída estruturada e validar por código. Cache/reuso por versão do prompt, modelo, material e snapshot. Completo herda conteúdo comercial e gera apenas os aprofundamentos necessários. Corrigir um bloco não exige refazer o documento.

Implementar medição de tokens de entrada, cache e saída e precificação versionada por modelo. Não tratar custo desconhecido como zero. Registrar tentativas, custo conhecido de falhas e conversão cambial com origem/data. Limites internos provisórios de texto do plano anterior devem ser calibrados em piloto; imagens têm limite separado. Reservar orçamento antes de chamadas concorrentes. Reenvio do mesmo pedido não pode duplicar geração.

Pesquisa e fontes têm custo e origem próprios. Abertura de documentos públicos é somente leitura. Nunca gerar mídia no GET de página pública ou PDF.

## 11. Integração futura com Cadu Media Studio

Preparar somente identificadores estáveis de documento, canal, formato e ativo. Não criar chamadas, filas ou dependências do gerador de vídeo nesta entrega.

Futura ação Enviar ao Cadu Media Studio poderá transferir linha criativa, formato, duração, quantidade planejada, imagens selecionadas, marca e versão de origem. Autorização, créditos, geração e retorno do vídeo serão definidos em fase própria. O conteúdo do Smart Planner não depende dessa integração para funcionar.

## 12. Pacotes de implementação e dependências

1. **Baseline e contratos:** três campanhas representativas; medir palavras, repetição, renderização e custo; schemas de proposta, completo e criação por canal. Fixar critérios de redução antes de redesenhar.
2. **Modelo de documentos:** derivação, aprovação registrada, versões, publicações e migração compatível. Nenhuma mudança destrutiva em sessão existente.
3. **Protótipos finais:** histórico, editor/publicação da proposta, editor/publicação do completo e revisão de imagem. Desktop e mobile; validar conteúdo real antes de integrar.
4. **Motor:** formato único, quantidades justificadas, prompts separados, geração incremental, medição financeira e pipeline de imagem isolado. Sem vídeo.
5. **Histórico:** endpoint paginado e projeção leve, busca global no escopo do usuário, lista compacta e menus.
6. **One page:** defesa comercial, primeira aba autossuficiente, arte principal e PDF próprio; comprovar redução mínima de 30%.
7. **Completo:** cinco áreas, indicadores, fichas de criação, quantidades, reuso da arte e PDF completo.
8. **Validação e liberação:** fixtures antigas, dados reais autorizados, testes e reversão; validar separação de tokens e permissões.

Não alterar os editores/geradores de vídeo do Cadu Media Studio durante esses pacotes. Trabalhos simultâneos nessa área permanecem fora do escopo.

## 13. Critérios de aceite

- Proposta e completo têm identidade, versão e publicação separadas.
- Completo identifica a versão exata da proposta que aprofundou.
- Gerado, publicado, enviado e aprovado não são sinônimos.
- One page mantém tese, defesa, investimento e demonstração visual e reduz palavras em pelo menos 30% na mesma campanha.
- Um único formato válido por canal nos dois documentos.
- Completo informa quantidades e justificativas sem confundir conceitos, variações, arquivos e revisões.
- Indicadores distinguem fato, estimativa, meta e recomendação, com origem; soma de alcance entre canais exige método.
- Smart Planner não chama nenhum endpoint de vídeo nem gera áudio/animação.
- Imagem de formato em vídeo está identificada como referência conceitual estática.
- Quantidade planejada de entregáveis não dispara lote automático de imagens.
- Histórico sem nove colunas, com uma ação principal por linha e busca no servidor.
- Público não vê custo de IA, fontes privadas ou conteúdo do outro documento sem compartilhamento próprio.
- PDFs corretos independentemente da aba aberta; links antigos preservados.
- Testes de deduplicação, retomada parcial, custo ausente, falha de imagem, mudança da proposta e atualização seletiva.
- Verificação em 1440/1024/768/390px, teclado, foco, estados vazios/erro/carregamento e carregamento de imagens.
