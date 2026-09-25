# RAG V2 do Cadu — contrato e migração

## Decisão

O RAG V2 passa a ser o caminho principal de indexação e recuperação. Os arquivos
originais, notas, artefatos versionados e permissões do projeto continuam sendo
as fontes canônicas. Trechos, texto extraído e embeddings são derivados e podem
ser reconstruídos. Nenhuma migração apaga os arquivos do usuário.

O problema a resolver é a cadeia completa: ingestão → extração → cobertura →
fragmentação → embedding → recuperação → seleção do contexto → resposta com
proveniência. A qualidade não será inferida do sucesso de uma chamada à API.

## Contrato de fonte

Cada versão indexável deve registrar:

| Campo | Finalidade |
| --- | --- |
| `client_id`, `project_ref`, `source_id`, `resource_id` | Isolamento e vínculo à fonte original. |
| `source_version`, `source_hash` | Detectar alteração e remoção. |
| `mime_type`, `category`, `origin`, `permission_snapshot` | Filtros antes da recuperação. |
| `extraction_version`, `coverage` | Páginas totais/processadas, OCR, limites e motivo de incompletude. |
| `pipeline_version`, `chunker_version`, `embedding_model`, `dimensions` | Reproduzir e refazer o índice. |
| `status` | `queued`, `extracting`, `partial`, `ready`, `failed`, `superseded`. |

Um arquivo de 100 páginas com 8 páginas OCR não fica `ready` como se a fonte
inteira tivesse sido lida. Se a extração falhar, o arquivo permanece no projeto
e seu estado explica por que não aparece na busca de conteúdo.

## Contrato de trecho

Cada trecho deve incluir IDs estáveis da fonte e versão, ordem, título/seção,
página ou intervalo quando houver, posição no texto, hash, texto, vetor e
`tsvector`. A fragmentação respeita títulos, parágrafos e frases. Sobreposição
serve para continuidade, sem duplicar a mesma evidência na resposta. Uma
citação aponta para a versão e o trecho efetivamente recuperados.

## Recuperação

1. Resolver a intenção da pergunta: busca exata, conceitual, panorama ou
   continuidade. O projeto selecionado delimita o escopo; ele não força uma
   busca quando a resposta está na conversa.
2. Pré-filtrar por cliente, projeto, autorização, status `ready` ou `partial`,
   fonte ativa e filtros explícitos de data/categoria.
3. Recuperar candidatos lexicais e vetoriais. Fundir rankings; registrar
   `hybrid`, `lexical`, `overview` ou `unavailable` conforme a execução real.
4. Selecionar trechos diversos e úteis, limitando repetição por fonte e custo
   de contexto. Reranking é uma opção medida, não dependência inicial.
5. Enviar ao agente somente trechos com ID, origem, cobertura e estado. Metadados
   de links não são conteúdo lido. Consulta indisponível não é busca vazia.

## Migração operacional

| Etapa | Trabalho | Critério de saída |
| --- | --- | --- |
| 0. Inventário | Contar fontes por tipo/estado, verificar originais disponíveis e exportar IDs, hashes e vínculos. | Nenhuma fonte fica sem caminho de reconstrução conhecido. |
| 1. Instrumentação | Persistir cobertura da extração e versão da pipeline; corrigir modo de recuperação reportado. | Fontes parciais e fallback lexical são identificáveis. |
| 2. Índice V2 | Criar espaço derivado versionado e jobs idempotentes; reprocessar por projeto sem remover originais. | Cada fonte termina `ready`, `partial` ou `failed`, com motivo. |
| 3. Avaliação | Rotular perguntas e trechos relevantes para briefing, relatório, contrato, imagem/OCR, reunião e artefato. Medir Recall@5/10, MRR, nDCG, cobertura, latência e custo. | V2 supera V1 nos cenários prioritários sem vazamento entre projetos. |
| 4. Corte | Colocar leitura V2 como padrão; manter restauração operacional do índice anterior durante a observação. | Citações abrem a fonte correta e estados de falha são honestos. |
| 5. Limpeza | Remover apenas tabelas/linhas derivadas V1 após reconciliação e janela de observação. | Contagem de fontes originais e recursos do projeto permanece igual. |

## Casos obrigatórios de avaliação

- Termo exato, sinônimo, nome de campanha e pergunta longa.
- Documento com título repetido, tabela, página digitalizada e página sem OCR.
- Arquivo maior que o limite de texto e PDF além do limite de páginas.
- Fonte alterada, removida, supersedida e reindexada após mudança de modelo.
- Dois projetos com termos idênticos e permissões diferentes.
- Busca vazia, embedding indisponível, OCR indisponível e índice parcial.
- Continuação de conversa que não exige nova busca.

## Créditos da reconstrução

O job automático `rebuild_v2` registra tokens de embedding, mas não cobra
créditos do cliente. Reindexações pedidas posteriormente pelo usuário seguem a
política normal de cobrança. A reconstrução só deve iniciar com orçamento e
limite operacional definidos para a plataforma.

## Estado da primeira etapa no código

A primeira alteração melhora os limites observáveis da extração, a divisão em
frases, o registro da versão da pipeline e a decisão de reindexar quando modelo
ou dimensão mudarem. A migração de dados, a avaliação rotulada e o corte de
leitura dependem das etapas seguintes; até lá, não chamar o índice inteiro de V2
nem declarar todos os documentos completamente lidos.
