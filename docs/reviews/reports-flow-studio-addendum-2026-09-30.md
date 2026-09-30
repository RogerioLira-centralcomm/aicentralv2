# Flow Studio — execução e revisão do adendo

Data: 30/09/2026. Trabalho na branch `main`, sem deploy ou alterações em dados de produção.

## Revisão do plano com a skill TypeSafe

A skill foi usada para separar regras determinísticas, observações e sugestões semânticas. Foram consultados a [API oficial](https://docs.typesafe.ai/api) e o [contrato de confiança](https://docs.typesafe.ai/confidence). As versões `.md` falharam; as páginas HTML estavam disponíveis.

- Regras, coordenadas, deduplicação, grupos, autorização, limites e publicação permanecem em código.
- IA classifica apenas páginas ambíguas, por opção explícita na montagem ou por página no catálogo.
- Reutiliza o serviço existente, respostas tipadas, auditoria, trava transacional e cota de 50 análises por cliente em 24 h. A montagem limita-se a 20 representantes e ao orçamento de tempo.
- Texto do site é evidência não confiável; não é instrução. Nenhuma métrica é produzida por IA.
- Sugestões não alteram o rascunho no worker; a aplicação é explícita. Objetivo de blueprint exige confirmação antes da publicação.
- Não foi feita chamada paga ao modelo para avaliar a qualidade semântica com páginas reais nesta execução.

## Implementação

### Editor e navegação

- Rail em coluna de 48 px, canvas no espaço restante, painéis com área reservada.
- Correção do enquadramento inicial: esperar todos os nós medidos, em vez de enquadrar só o primeiro.
- Minimapa com dimensões explícitas; header compacto; botões e seleção com foco visível.
- Erros no estado de salvamento, com referências da resposta e localização dos nós quando disponíveis.
- Corrigida projeção v2 que inseria portas nulas e causava HTTP 400. Reconexão usa portas padrão quando ausentes.
- Inspetor com papel, etapa, posição fixa, toggle de entrada, descrição recolhida e grupos existentes/criação.
- Captura reduzida a 240 px no canvas, imagem omitida abaixo de 40% de zoom; regeneração na toolbar.
- Comandos com diálogo nativo acessível; busca de nós e catálogo, montagem, organização e retornos.

### Organização e monitoramento

- Etapas semânticas, organização em worker ELK e preservação de posições fixadas.
- Grupos organizados como unidades; colapsar/expandir é estado da visualização.
- Funil filtra malha de links, retornos e ligações internas; preserva o documento completo.
- Até 20 conexões na visão resumida; seleção por volume quando há métricas, máximo de três saídas por origem; indicação de conexões ocultas.
- Arestas recíprocas unificadas na visão resumida, com setas nos dois sentidos; roteamento ortogonal.
- Navegação completa bloqueia alterações pelo canvas, inspetor e atalhos.
- Grupos recebem contagem por união de sessões no servidor. Não há soma de visitantes de páginas diferentes.
- Quando uma projeção parcial de grupos não tem agregado correspondente, não é fabricada uma taxa. Expanda para inspecionar conexões individuais.
- Hover mostra evidência, fonte, sessões e caminhos disponíveis; animações continuam condicionadas a atividade observada.

### Catálogo e montagem

- Canonical, domínio/www, tracking, barra final e paginação normalizados.
- Agrupamento exige pelo menos três páginas e assinatura estrutural coincidente.
- Papéis por regras; destinos pós-formulário podem sugerir conversão com evidência observada repetida.
- Catálogo compacto, busca, filtros, seleção, localizar itens existentes, grupos e classificação opcional.
- Jobs autenticados e isolados por cliente/fluxo, compartilhando o executor de capturas.
- Descoberta limitada a 500 URLs/profundidade 4; interrupção entre lotes e resultado parcial em sites lentos.
- Reutilização do catálogo de até 24 h; URL observada nova invalida o reaproveitamento. URLs observadas entram na descoberta.
- Proposta com limite de 15 elementos visíveis/20 conexões, grupos para modelos, origem e evidência explícitas.
- Camada fantasma, seleção individual, confirmação, aplicação única no histórico, reabertura e aviso quando pronta.
- Remontagem mantém nós manuais, editados, fixados e endpoints de conexões manuais.
- Revisão local e backend compartilham verificações de objetivo, mapeamento, duplicatas, ciclo e intenção sem caminho até objetivo. A coleta é verificada separadamente e gera aviso, sem impedir instalar/publicar um fluxo ainda sem visitas.

## Validação executada

- 54 testes Python + 3 subtestes: Flow Studio, workspace v2, descoberta, schema, versões, live e assistência TypeSafe.
- Teste JavaScript: preservação na remontagem, política de arestas, documento imutável na visualização e guarda contra `border-2` nos componentes novos.
- Playwright: edição/monitoramento, seleção, explorador, pausa, comando, screenshots desktop 1920/1440/1366/1024 e ausência de overflow horizontal.
- Build Vite e `git diff --check`.
- Testes legados atualizados para API v2 e escopo exclusivo por `client_id`.

### Medição de 200 nós

O fixture executa 120 frames de arraste e observa mutações do painel. Baseline usa bundles do HEAD anterior; o resultado atualizado confirma mudança de posição durante o arraste.

| Medida | Antes | Depois |
|---|---:|---:|
| FPS médio local | 23,48 | 60,39 |
| Frame mediano | 40,7 ms | 16,7 ms |
| Frame p95 | 59 ms | 17,4 ms |
| Mutações no painel | 0 | 0 |

Arquivos: `output/reports-workspace-qa/profile-before.json`, `profile-after.json` e screenshots `studio-*.png` / `monitor-*.png`.

Esta é uma medição sintética em Chromium headless, não um perfil React Profiler/DevTools capturado manualmente nem garantia em todos os dispositivos.

## Limites da verificação

- Não houve deploy, aplicação de migração nem escrita no PostgreSQL de produção.
- Aceites específicos de `centralcomm.media` (cobertura real, similaridade de `/audiencia/*`, menos de três cruzamentos e tempo de descoberta de aproximadamente 70 páginas) dependem da execução com o site e os eventos reais; não são afirmados a partir dos fixtures.
- A consulta de agregados de grupos foi implementada; sua execução com volume real deve ser conferida em homologação.
- O build informa tamanho acima do limiar de 500 kB. ELK saiu do bundle principal para um worker carregado sob demanda.

## Fechamento das correções adicionais

- Reconectar uma ligação automática passa a marcá-la como manual, preservando a conexão e seus endpoints na remontagem.
- O arraste individual e em grupo considera as seis etapas, incluindo suporte e erros.
- A proposta limita origens distintas a três mesmo quando há poucas páginas.
- Regressões JavaScript e Python aprovadas; Playwright de edição e monitoramento aprovado em quatro resoluções desktop.
- Criação de projetos pelo Reports registra o proprietário atomicamente; mesclagem transfere vínculos e referências de operações; associações inacessíveis podem ser removidas sob autorização de escrita do recurso Reports.

### Descoberta no domínio real

Em 30/09/2026, `_discover_site` foi executado por leitura HTTP pública em `https://www.centralcomm.media`, sem escrita no banco. Resultado: 439 páginas em 45,9 segundos, 513 URLs pendentes e descoberta parcial. Isso comprova acesso e execução do crawler no domínio real; não valida ainda agrupamento visual, cruzamentos nem os agregados de sessões em produção.

Publicação: o envio de `main` foi tentado, mas o Git não encontrou credencial HTTPS para GitHub neste ambiente. O deploy depende ainda do acesso SSH ao servidor.
